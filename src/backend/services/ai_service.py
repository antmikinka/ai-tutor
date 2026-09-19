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
from services.llm_client import LLMClientError, RemoteLLMClient, extract_json_object
from services.llm_config import LLMConfigStore, RemoteLLMSettings
from services.math_engine import MathParseError
from services.optional_deps import HAS_ML_STACK, ml_stack_status

logger = logging.getLogger(__name__)

SYMBOLIC_ENGINE = "sympy"
LLM_ENGINE_PREFIX = "qwen3-omni"


class NoLanguageModelError(RuntimeError):
    """Raised when a request needs an LLM and none (local or remote) is available."""


def _clamp(value, low, high):
    return max(low, min(high, value))


def _as_float(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any, default: int) -> int:
    try:
        return default if value is None else int(value)
    except (TypeError, ValueError):
        return default


class AIService:
    """Mathematical problem solving: SymPy first, LLM when available."""

    def __init__(self, settings=None, model_service=None):
        self.settings = settings or get_settings()
        self.model_service = model_service
        self.qwen3_service = None
        self.llm_config = LLMConfigStore(self.settings)
        self.remote_llm: Optional[RemoteLLMClient] = None
        self._stale_remote_clients: List[RemoteLLMClient] = []
        self._build_remote_client()
        self.is_initialized = False
        self._history: Deque[Dict[str, Any]] = deque(maxlen=self.settings.solution_history_size)
        self._stats = {"solved": 0, "failed": 0, "verified": 0, "total_confidence": 0.0}

    # ------------------------------------------------------------------ #
    # Language model selection
    # ------------------------------------------------------------------ #

    @staticmethod
    def make_remote_client(remote: RemoteLLMSettings) -> Optional[RemoteLLMClient]:
        if not remote.configured:
            return None
        return RemoteLLMClient(remote.base_url, remote.api_key, remote.model, remote.timeout_seconds, provider=remote.preset)

    def _build_remote_client(self) -> None:
        if self.remote_llm is not None:
            # Closed asynchronously later; requests in flight keep their client.
            self._stale_remote_clients.append(self.remote_llm)
        self.remote_llm = self.make_remote_client(self.llm_config.config.remote)

    async def apply_llm_config(self, **changes) -> Dict[str, Any]:
        """Update mode/provider/key/model at runtime, persist, and rebuild the remote client."""
        self.llm_config.update(**changes)
        return await self._rebuild_remote_client()

    async def reset_llm_config(self) -> Dict[str, Any]:
        """Drop the persisted choice and go back to the environment defaults."""
        self.llm_config.reset()
        return await self._rebuild_remote_client()

    async def _rebuild_remote_client(self) -> Dict[str, Any]:
        self._build_remote_client()
        for client in self._stale_remote_clients:
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                pass
        self._stale_remote_clients.clear()
        logger.info("LLM config updated: mode=%s remote=%s", self.llm_mode, self.remote_llm.name if self.remote_llm else None)
        return self.llm_status()

    @property
    def llm_mode(self) -> str:
        return self.llm_config.config.mode

    @property
    def remote_allowed(self) -> bool:
        return self.llm_mode in ("auto", "remote") and self.remote_llm is not None

    @property
    def local_allowed(self) -> bool:
        return self.llm_mode in ("auto", "local")

    def active_backend(self) -> Optional[str]:
        """Which language model would answer right now: 'local', 'remote' or None."""
        if self.local_allowed and self.llm_ready:
            return "local"
        if self.remote_allowed:
            return "remote"
        return None

    def llm_status(self) -> Dict[str, Any]:
        active = self.active_backend()
        local_model = self.settings.ai_model_name
        return {
            **self.llm_config.public(),
            "active": {"backend": active, "name": self.llm_name},
            "local": {
                "ready": self.llm_ready,
                "model": local_model,
                "ml_stack": HAS_ML_STACK,
                "allowed": self.local_allowed,
            },
            "remote_active": self.remote_allowed,
        }

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
        if self.remote_llm is not None:
            logger.info("Remote LLM configured: %s (%s), mode=%s", self.remote_llm.base_url, self.remote_llm.model, self.llm_mode)
        self.is_initialized = True

    async def cleanup(self) -> None:
        if self.qwen3_service is not None:
            try:
                await self.qwen3_service.cleanup()
            except Exception as exc:
                logger.error("Error cleaning up Qwen3-Omni service: %s", exc)
        for client in [self.remote_llm, *self._stale_remote_clients]:
            if client is not None:
                await client.close()
        self._stale_remote_clients.clear()
        self.is_initialized = False

    def is_healthy(self) -> bool:
        return self.is_initialized

    @property
    def llm_ready(self) -> bool:
        """True only when a real local language model is loaded (not 'limited mode')."""
        svc = self.qwen3_service
        return bool(svc is not None and svc.is_initialized and getattr(svc, "model", None) is not None)

    @property
    def any_llm_available(self) -> bool:
        return self.active_backend() is not None

    @property
    def llm_name(self) -> Optional[str]:
        backend = self.active_backend()
        if backend == "local":
            return f"{LLM_ENGINE_PREFIX}:{self.settings.ai_model_name}"
        if backend == "remote" and self.remote_llm is not None:
            return self.remote_llm.name
        return None

    def _no_llm_message(self) -> str:
        mode = self.llm_mode
        if mode == "local":
            return "Language model source is set to 'local only' but no local model is loaded. Load Qwen3-Omni from Settings or switch to an API provider."
        if mode == "remote":
            return "Language model source is set to 'API' but no provider/model is configured. Add an OpenRouter (or other) API key and model in Settings."
        return "No language model is available. Load Qwen3-Omni, or configure OpenRouter / another OpenAI-compatible API in Settings."

    # ------------------------------------------------------------------ #
    # Generic text generation (routed by the user's LLM mode)
    # ------------------------------------------------------------------ #

    async def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 1024,
        temperature: Optional[float] = None,
    ) -> str:
        """Return raw model text for a prompt, or raise NoLanguageModelError."""
        if self.local_allowed:
            await self._attach_loaded_llm()
        backend = self.active_backend()
        if backend == "local":
            prompt = f"{system}\n\n{user}"
            result = await self.qwen3_service._generate_solution(prompt, "generic")  # noqa: SLF001 - shared wrapper API
            return result.get("generated_text", "")
        if backend == "remote":
            try:
                return await self.remote_llm.chat(
                    [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=self.settings.ai_temperature if temperature is None else _clamp(temperature, 0.0, 2.0),
                    max_tokens=_clamp(int(max_tokens), 64, 8192),
                    json_mode=json_mode,
                )
            except LLMClientError as exc:
                raise NoLanguageModelError(str(exc)) from exc
        raise NoLanguageModelError(self._no_llm_message())

    async def complete_json(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        text = await self.complete(system, user, json_mode=True, max_tokens=max_tokens, temperature=temperature)
        try:
            return extract_json_object(text)
        except ValueError as exc:
            raise NoLanguageModelError(f"Language model did not return JSON: {exc}") from exc

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
            "llm_mode": self.llm_mode,
            "remote_llm": self.remote_llm.name if self.remote_llm else None,
            "llm_available": self.any_llm_available,
            "llm_active": self.llm_name,
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
            if self.local_allowed:
                await self._attach_loaded_llm()
            backend = self.active_backend()
            if backend == "local":
                response = await self._solve_with_llm(problem, context, started)
            elif backend == "remote":
                response = await self._solve_with_remote_llm(problem, context, started)
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

    _WORD_PROBLEM_SYSTEM = (
        "You are a patient math tutor. Translate the student's problem into mathematics, solve it, and reply "
        "with ONLY a JSON object: {\"equation\": string (a single equation or expression the symbolic engine can "
        "solve, e.g. '3*x + 5 = 20' or 'derivative of x^2'), \"variable\": string|null, \"solution\": string "
        "(final answer), \"steps\": [string], \"problem_type\": string, \"confidence\": number 0-1}. "
        "Use ^ for powers, * for multiplication, sqrt(), pi. The equation must contain only numbers, operators and "
        "ONE unknown written as a single lowercase letter (not e); no words, units or % signs (write 25% as 0.25). "
        "No prose outside the JSON."
    )

    async def _solve_with_remote_llm(self, problem: str, context: Dict[str, Any], started: float) -> Dict[str, Any]:
        """Word problems via the configured OpenAI-compatible endpoint, cross-checked with SymPy."""
        try:
            data = await self.complete_json(
                self._WORD_PROBLEM_SYSTEM,
                f"Problem: {problem}",
                max_tokens=_as_int(context.get("max_tokens"), self.settings.ai_max_tokens),
                temperature=_as_float(context.get("temperature")),
            )
        except NoLanguageModelError as exc:
            logger.error("Remote LLM failed: %s", exc)
            return self._unsolved_response(problem, f"language model error: {exc}", started)

        steps = [str(s) for s in data.get("steps", []) if str(s).strip()]
        solution = str(data.get("solution", "")).strip()
        confidence = float(data.get("confidence", 0.6) or 0.6)
        problem_type = str(data.get("problem_type", "word_problem"))
        equation = str(data.get("equation", "")).strip()
        solution_latex = ""
        verification = {"is_correct": None, "confidence": 0.0, "method": "llm"}

        # If the model gave us an equation the engine understands, let the engine have the final word.
        if equation:
            try:
                engine = await self._run_symbolic(math_engine.solve, equation)
                steps = [f"Model the problem: {equation}"] + list(engine.steps)
                if solution and math_engine.verify(equation, solution)["is_correct"]:
                    verification = {"is_correct": True, "confidence": 0.95, "method": "symbolic"}
                else:
                    verification = {"is_correct": True, "confidence": 0.9, "method": "symbolic-corrected"}
                solution = engine.solution
                solution_latex = engine.solution_latex
                confidence = max(confidence, 0.85)
            except (MathParseError, asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
                logger.debug("Engine could not check LLM equation %r: %s", equation, exc)

        return {
            "id": str(uuid.uuid4()),
            "problem": problem,
            "solution": solution or "The model did not produce a final answer.",
            "solution_latex": solution_latex,
            "steps": steps,
            "thinking_process": [],
            "confidence": confidence if solution else 0.0,
            "problem_type": problem_type,
            "variable": data.get("variable"),
            "processing_time": time.perf_counter() - started,
            "model_used": self.remote_llm.name if self.remote_llm else "remote",
            "tokens_used": 0,
            "verification": verification,
            "timestamp": utc_now_iso(),
        }

    def _unsolved_response(self, problem: str, reason: str, started: float) -> Dict[str, Any]:
        hints = [
            "Write the expression with explicit operators, e.g. 'solve 2x + 3 = 7' or 'derivative of x^2 * sin(x)'.",
            "Supported commands: solve, simplify, factor, expand, derivative, integrate (optionally 'from a to b'), limit ... as x -> a.",
        ]
        if not self.any_llm_available:
            hints.append(f"For word problems: {self._no_llm_message()}")
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
