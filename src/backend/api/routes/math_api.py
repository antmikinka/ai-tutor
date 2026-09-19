"""
Math-related API endpoints
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.dependencies import get_ai_service, get_drawing_service
from services.ai_service import AIService
from services.common import utc_now_iso
from services.drawing_service import DrawingDecodeError, DrawingService

logger = logging.getLogger(__name__)
router = APIRouter()


class MathProblemRequest(BaseModel):
    problem: str = Field(min_length=1, max_length=4000)
    problem_type: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    enable_step_by_step: bool = True
    enable_explanation: bool = True


class MathSolutionResponse(BaseModel):
    id: str
    problem: str
    solution: str
    solution_latex: str = ""
    steps: List[str]
    confidence: float
    problem_type: str
    variable: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any]


class DrawingAnalysisRequest(BaseModel):
    drawing_data: str = Field(min_length=1)
    analysis_type: str = "equation_recognition"
    context: Dict[str, Any] = Field(default_factory=dict)


class BatchProblemsRequest(BaseModel):
    problems: List[str] = Field(min_length=1, max_length=50)
    context: Dict[str, Any] = Field(default_factory=dict)


class VerificationRequest(BaseModel):
    problem: str = Field(min_length=1, max_length=4000)
    solution: str = Field(min_length=1, max_length=4000)
    verification_type: str = "correctness"


class VerificationResponse(BaseModel):
    is_correct: bool
    confidence: float
    feedback: str
    expected: Optional[str] = None
    expected_steps: List[str] = Field(default_factory=list)
    alternative_solutions: List[str] = Field(default_factory=list)


def _to_solution_response(problem: str, solution: Dict[str, Any]) -> MathSolutionResponse:
    return MathSolutionResponse(
        id=solution["id"],
        problem=problem,
        solution=solution["solution"],
        solution_latex=solution.get("solution_latex", ""),
        steps=solution.get("steps", []),
        confidence=solution.get("confidence", 0.0),
        problem_type=solution.get("problem_type", "unknown"),
        variable=solution.get("variable"),
        timestamp=solution.get("timestamp", utc_now_iso()),
        metadata={
            "processing_time": solution.get("processing_time", 0.0),
            "model_used": solution.get("model_used", "none"),
            "tokens_used": solution.get("tokens_used", 0),
            "verification": solution.get("verification", {}),
        },
    )


@router.post("/solve", response_model=MathSolutionResponse)
async def solve_math_problem(request: MathProblemRequest, ai: AIService = Depends(get_ai_service)):
    context = dict(request.context)
    context.setdefault("enable_step_by_step", request.enable_step_by_step)
    try:
        solution = await ai.solve_math_problem(request.problem, context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Solve failed")
        raise HTTPException(status_code=500, detail=f"Failed to solve math problem: {exc}") from exc
    return _to_solution_response(request.problem, solution)


@router.post("/batch-solve")
async def solve_batch_problems(request: BatchProblemsRequest, ai: AIService = Depends(get_ai_service)):
    solutions = []
    for problem in request.problems:
        try:
            solution = await ai.solve_math_problem(problem, dict(request.context))
            solutions.append({"problem": problem, "solution": solution, "status": "success"})
        except Exception as exc:
            logger.warning("Batch item failed (%r): %s", problem, exc)
            solutions.append({"problem": problem, "error": str(exc), "status": "failed"})
    return {
        "solutions": solutions,
        "total_problems": len(request.problems),
        "successful_solutions": sum(1 for s in solutions if s["status"] == "success"),
        "timestamp": utc_now_iso(),
    }


@router.post("/verify", response_model=VerificationResponse)
async def verify_solution(request: VerificationRequest, ai: AIService = Depends(get_ai_service)):
    try:
        verdict = await ai.verify_solution(request.problem, request.solution, request.verification_type)
    except Exception as exc:
        logger.exception("Verification failed")
        raise HTTPException(status_code=500, detail=f"Failed to verify solution: {exc}") from exc
    return VerificationResponse(**{k: v for k, v in verdict.items() if k in VerificationResponse.model_fields})


@router.post("/analyze-drawing")
async def analyze_drawing(
    request: DrawingAnalysisRequest,
    ai: AIService = Depends(get_ai_service),
    drawing: DrawingService = Depends(get_drawing_service),
):
    try:
        processed = await drawing.process_drawing(request.drawing_data, request.analysis_type, request.context)
        analysis = await ai.analyze_drawing(request.drawing_data, request.context)
    except DrawingDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Drawing analysis failed")
        raise HTTPException(status_code=500, detail=f"Failed to analyze drawing: {exc}") from exc
    analysis["image_analysis"] = processed["data"]["image_analysis"]
    analysis["image_dimensions"] = processed["image_dimensions"]
    return analysis


@router.post("/upload-image")
async def upload_and_analyze_image(
    file: UploadFile = File(...),
    analysis_type: str = Form("equation_recognition"),
    context: str = Form("{}"),
    ai: AIService = Depends(get_ai_service),
    drawing: DrawingService = Depends(get_drawing_service),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    image_data = await file.read()
    if len(image_data) > drawing.settings.max_upload_size:
        raise HTTPException(status_code=413, detail="Image exceeds the upload size limit")
    try:
        context_data = json.loads(context) if context else {}
    except json.JSONDecodeError:
        context_data = {}
    b64 = base64.b64encode(image_data).decode("ascii")
    try:
        processed = await drawing.process_drawing(b64, analysis_type, context_data)
        analysis = await ai.analyze_drawing(b64, context_data)
    except DrawingDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    analysis["image_analysis"] = processed["data"]["image_analysis"]
    return {"filename": file.filename, "analysis": analysis, "timestamp": utc_now_iso()}


@router.get("/problem-types")
async def get_supported_problem_types(ai: AIService = Depends(get_ai_service)):
    return {"problem_types": await ai.get_supported_problem_types(), "timestamp": utc_now_iso()}


@router.get("/history")
async def get_solution_history(
    limit: int = 50,
    offset: int = 0,
    problem_type: Optional[str] = None,
    ai: AIService = Depends(get_ai_service),
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    data = ai.get_history(limit=limit, offset=offset, problem_type=problem_type)
    data["timestamp"] = utc_now_iso()
    return data


@router.delete("/history/{solution_id}")
async def delete_solution_from_history(solution_id: str, ai: AIService = Depends(get_ai_service)):
    if not ai.delete_history_item(solution_id):
        raise HTTPException(status_code=404, detail="Solution not found in history")
    return {"message": f"Solution {solution_id} deleted", "timestamp": utc_now_iso()}


@router.delete("/history")
async def clear_solution_history(ai: AIService = Depends(get_ai_service)):
    ai.clear_history()
    return {"message": "History cleared", "timestamp": utc_now_iso()}


@router.get("/statistics")
async def get_math_statistics(ai: AIService = Depends(get_ai_service)):
    return {"statistics": ai.get_statistics(), "timestamp": utc_now_iso()}
