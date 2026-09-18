"""
AI Service for mathematical problem solving and reasoning.

The deterministic SymPy engine (``services.math_engine``) is the primary
solver: it is fast, exact and works without any ML dependencies. The optional
Qwen3-Omni LLM is only consulted for problems the symbolic engine cannot
interpret, and only when a real model has actually been loaded.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from config.settings import get_settings
from services import math_engine
from services.common import utc_now_iso
from services.math_engine import MathParseError
from services.optional_deps import HAS_ML_STACK, ml_stack_status

logger = logging.getLogger(__name__)

SYMBOLIC_ENGINE = "sympy"
LLM_ENGINE_PREFIX = "qwen3-omni"


class AIService:
    """Mathematical problem solving: SymPy first, LLM when available."""

    def __init__(self, settings=None, model_service=None):
        self.settings = settings or get_settings()
        self.model_service = model_service
        self.qwen3_service = None
        self.is_initialized = False
        self._history: Deque[Dict[str, Any]] = deque(maxlen=self.settings.solution_history_size)
        self._stats = {"solved": 0, "failed": 0, "verified": 0, "total_confidence": 0.0}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        """Lightweight initialisation; heavy models are loaded on demand."""
        if HAS_ML_STACK:
            try:
                from services.qwen3_omni_service import Qwen3OmniService

                self.qwen3_service = Qwen3OmniService(self.settings)
            except Exception as exc:
                logger.warning("Qwen3-Omni wrapper unavailable: %s", exc)
                self.qwen3_service = None
        else:
            logger.info("ML stack not installed; AI service runs with the symbolic engine only")
        self.is_initialized = True

    async def cleanup(self) -> None:
        if self.qwen3_service is not None:
            try:
                await self.qwen3_service.cleanup()
            except Exception as exc:
                logger.error("Error cleaning up Qwen3-Omni service: %s", exc)
        self.is_initialized = False

    def is_healthy(self) -> bool:
        return self.is_initialized

    @property
    def llm_ready(self) -> bool:
        """True only when a real language model is loaded (not 'limited mode')."""
        svc = self.qwen3_service
        return bool(svc is not None and svc.is_initialized and getattr(svc, "model", None) is not None)

    async def _attach_loaded_llm(self) -> None:
        """Bind the Qwen3 wrapper to a reasoning model the user loaded via ModelService."""
        if self.qwen3_service is None or self.model_service is None or self.llm_ready:
            return
        try:
            from services.model_config import ModelType

            instance = self.model_service.get_loaded_instance(ModelType.REASONING)
        except Exception as exc:
            logger.debug("Could not query loaded models: %s", exc)
            return
        if instance is not None and instance.model_object is not None:
            try:
                await self.qwen3_service.initialize(instance.model_object)
                logger.info("Qwen3-Omni attached to loaded model %s", instance.config.name)
            except Exception as exc:
                logger.warning("Failed to attach Qwen3-Omni to loaded model: %s", exc)

    def status(self) -> Dict[str, Any]:
        return {
            "initialized": self.is_initialized,
            "healthy": self.is_healthy(),
            "symbolic_engine": SYMBOLIC_ENGINE,
            "llm_ready": self.llm_ready,
            "llm_model": self.settings.ai_model_name if self.llm_ready else None,
            "ml_stack": ml_stack_status(),
            "problems_solved": self._stats["solved"],
        }

    # ------------------------------------------------------------------ #
    # Solving
    # ------------------------------------------------------------------ #

    async def _run_symbolic(self, func, *args):
        """Run a CPU-bound SymPy call off the event loop with a timeout."""
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args),
            timeout=self.settings.solver_timeout_seconds,
        )

    async def solve_math_problem(self, problem: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        problem = (problem or "").strip()
        started = time.perf_counter()
        if not problem:
            raise ValueError("Problem text is empty")

        logger.info("Solving: %.100s", problem)
        try:
            result = await self._run_symbolic(math_engine.solve, problem)
            response = self._format_symbolic(result, started, context)
        except MathParseError as exc:
            logger.info("Symbolic engine could not interpret problem: %s", exc)
            await self._attach_loaded_llm()
            if self.llm_ready:
                response = await self._solve_with_llm(problem, context, started)
            else:
                response = self._unsolved_response(problem, str(exc), started)
        except asyncio.TimeoutError:
            response = self._unsolved_response(
                problem,
                f"The symbolic solver exceeded {self.settings.solver_timeout_seconds:.0f}s. "
                "Try simplifying the expression.",
                started,
            )

        self._record(response)
        return response

    def _format_symbolic(self, result: math_engine.MathResult, started: float, context: Dict[str, Any]) -> Dict[str, Any]:
        steps = list(result.steps) if context.get("enable_step_by_step", True) else []
        solution_text = result.solution
        if result.approximation:
            solution_text = f"{solution_text}  (≈ {result.approximation})"
        return {
            "id": str(uuid.uuid4()),
            "problem": result.problem,
            "solution": solution_text,
            "solution_latex": result.solution_latex,
            "steps": steps,
            "thinking_process": [],
            "confidence": result.confidence,
            "problem_type": result.problem_type,
            "variable": result.variable,
            "processing_time": time.perf_counter() - started,
            "model_used": SYMBOLIC_ENGINE,
            "tokens_used": 0,
            "verification": {"is_correct": True, "confidence": result.confidence, "method": "symbolic"},
            "timestamp": utc_now_iso(),
        }

    async def _solve_with_llm(self, problem: str, context: Dict[str, Any], started: float) -> Dict[str, Any]:
        try:
            llm = await self.qwen3_service.solve_math_problem(
                problem, context, context.get("enable_thinking", True)
            )
        except Exception as exc:
            logger.error("Qwen3-Omni failed: %s", exc)
            return self._unsolved_response(problem, f"language model error: {exc}", started)
        return {
            "id": str(uuid.uuid4()),
            "problem": problem,
            "solution": llm.get("solution", ""),
            "solution_latex": "",
            "steps": llm.get("steps", []),
            "thinking_process": llm.get("thinking_process", []),
            "confidence": float(llm.get("confidence", 0.6)),
            "problem_type": llm.get("problem_type", "general"),
            "variable": None,
            "processing_time": time.perf_counter() - started,
            "model_used": f"{LLM_ENGINE_PREFIX}:{self.settings.ai_model_name}",
            "tokens_used": llm.get("tokens_used", 0),
            "verification": llm.get("verification", {"is_correct": None, "confidence": 0.0, "method": "llm"}),
            "timestamp": utc_now_iso(),
        }

    def _unsolved_response(self, problem: str, reason: str, started: float) -> Dict[str, Any]:
        hints = [
            "Write the expression with explicit operators, e.g. 'solve 2x + 3 = 7' or 'derivative of x^2 * sin(x)'.",
            "Supported commands: solve, simplify, factor, expand, derivative, integrate (optionally 'from a to b'), limit ... as x -> a.",
        ]
        if not self.llm_ready:
            hints.append("Load the Qwen3-Omni model from Settings to get help with word problems and free-form questions.")
        return {
            "id": str(uuid.uuid4()),
            "problem": problem,
            "solution": "I couldn't interpret that as a math problem I can solve.",
            "solution_latex": "",
            "steps": [f"Reason: {reason}"] + hints,
            "thinking_process": [],
            "confidence": 0.0,
            "problem_type": "unknown",
            "variable": None,
            "processing_time": time.perf_counter() - started,
            "model_used": "none",
            "tokens_used": 0,
            "verification": {"is_correct": False, "confidence": 0.0, "method": "none"},
            "timestamp": utc_now_iso(),
        }

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #

    async def verify_solution(self, problem: str, solution: str, verification_type: str = "correctness") -> Dict[str, Any]:
        try:
            verdict = await self._run_symbolic(math_engine.verify, problem, solution)
        except MathParseError as exc:
            verdict = {
                "is_correct": False,
                "confidence": 0.0,
                "feedback": f"Could not interpret the problem for verification: {exc}",
                "expected": None,
                "expected_steps": [],
                "alternative_solutions": [],
            }
        except asyncio.TimeoutError:
            verdict = {
                "is_correct": False,
                "confidence": 0.0,
                "feedback": "Verification timed out.",
                "expected": None,
                "expected_steps": [],
                "alternative_solutions": [],
            }
        self._stats["verified"] += 1
        verdict["verification_type"] = verification_type
        verdict["timestamp"] = utc_now_iso()
        return verdict

    # ------------------------------------------------------------------ #
    # Drawing analysis
    # ------------------------------------------------------------------ #

    async def analyze_drawing(self, drawing_data: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Recognise mathematical content in an image.

        Real recognition requires the multimodal LLM; without it we say so
        explicitly instead of inventing an equation.
        """
        await self._attach_loaded_llm()
        if self.llm_ready:
            try:
                analysis = await self.qwen3_service.analyze_drawing(drawing_data, context)
                inner = analysis.get("analysis", {})
                return {
                    "available": True,
                    "recognized_text": inner.get("recognized_text", ""),
                    "equations": inner.get("equations", []),
                    "shapes": inner.get("shapes", []),
                    "concepts": inner.get("concepts", []),
                    "confidence": float(analysis.get("confidence", 0.0)),
                    "model_used": f"{LLM_ENGINE_PREFIX}:{self.settings.ai_model_name}",
                    "timestamp": utc_now_iso(),
                }
            except Exception as exc:
                logger.error("Drawing analysis with Qwen3-Omni failed: %s", exc)
        return {
            "available": False,
            "recognized_text": "",
            "equations": [],
            "shapes": [],
            "concepts": [],
            "confidence": 0.0,
            "model_used": "none",
            "message": "Handwriting recognition needs the Qwen3-Omni vision model. Type the expression instead, or load the model from Settings.",
            "timestamp": utc_now_iso(),
        }

    # ------------------------------------------------------------------ #
    # Metadata / history
    # ------------------------------------------------------------------ #

    async def get_supported_problem_types(self) -> List[str]:
        return [
            "equation",
            "system",
            "inequality",
            "derivative",
            "integral",
            "definite_integral",
            "limit",
            "simplify",
            "factor",
            "expand",
            "evaluate",
        ]

    def _record(self, response: Dict[str, Any]) -> None:
        if response["confidence"] > 0:
            self._stats["solved"] += 1
            self._stats["total_confidence"] += response["confidence"]
        else:
            self._stats["failed"] += 1
        self._history.appendleft(
            {
                "id": response["id"],
                "problem": response["problem"],
                "solution": response["solution"],
                "problem_type": response["problem_type"],
                "confidence": response["confidence"],
                "model_used": response["model_used"],
                "timestamp": response["timestamp"],
            }
        )

    def get_history(self, limit: int = 50, offset: int = 0, problem_type: Optional[str] = None) -> Dict[str, Any]:
        items = [h for h in self._history if problem_type is None or h["problem_type"] == problem_type]
        return {"history": items[offset : offset + limit], "total": len(items), "limit": limit, "offset": offset}

    def delete_history_item(self, solution_id: str) -> bool:
        for item in list(self._history):
            if item["id"] == solution_id:
                self._history.remove(item)
                return True
        return False

    def clear_history(self) -> None:
        self._history.clear()

    def get_statistics(self) -> Dict[str, Any]:
        solved = self._stats["solved"]
        by_type: Dict[str, int] = {}
        for item in self._history:
            by_type[item["problem_type"]] = by_type.get(item["problem_type"], 0) + 1
        popular = sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)
        return {
            "total_problems_solved": solved,
            "total_failed": self._stats["failed"],
            "total_verified": self._stats["verified"],
            "average_confidence": (self._stats["total_confidence"] / solved) if solved else 0.0,
            "popular_problem_types": [{"type": t, "count": c} for t, c in popular[:5]],
            "history_size": len(self._history),
        }
