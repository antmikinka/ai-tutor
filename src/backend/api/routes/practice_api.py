"""
Practice API: generate word problems from course material, check answers,
hand out hints, reveal solutions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_practice_service
from services.practice_service import PracticeService

logger = logging.getLogger(__name__)
router = APIRouter()


class LearningStyleIn(BaseModel):
    """VARK questionnaire scores (each mode 0-16)."""

    visual: int = Field(default=0, ge=0, le=16)
    aural: int = Field(default=0, ge=0, le=16)
    read_write: int = Field(default=0, ge=0, le=16)
    kinesthetic: int = Field(default=0, ge=0, le=16)


class GenerateRequest(BaseModel):
    topic: str = Field(default="", max_length=300)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    doc_ids: Optional[List[str]] = None
    family: Optional[str] = None
    mode: Literal["auto", "llm", "templates"] = "auto"
    seed: Optional[int] = None
    learning_style: Optional[LearningStyleIn] = None


class CheckRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


class WhiteboardSaveRequest(BaseModel):
    canvas_json: str = Field(min_length=2, max_length=2_000_000)


class BoardReadRequest(BaseModel):
    texts: List[str] = Field(default_factory=list, max_length=40)
    problem_id: Optional[str] = None


def _get(service: PracticeService, problem_id: str, *, touch: bool = False):
    problem = service.get(problem_id, touch=touch)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found (it may have expired). Open it from History or generate a new one.")
    return problem


@router.get("/status")
async def practice_status(service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    return service.status()


@router.post("/generate")
async def generate_problem(request: GenerateRequest, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    try:
        return await service.generate(
            request.topic,
            request.difficulty,
            doc_ids=request.doc_ids,
            family=request.family,
            mode=request.mode,
            seed=request.seed,
            learning_style=request.learning_style.model_dump() if request.learning_style else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Practice generation failed")
        raise HTTPException(status_code=500, detail=f"Could not generate a problem: {exc}")


@router.get("/history")
async def practice_history(limit: int = 50, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    return service.history(limit)


@router.delete("/history")
async def clear_practice_history(service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    service.clear_history()
    return {"cleared": True, "stats": service.stats()}


@router.get("/problems/{problem_id}")
async def get_problem(problem_id: str, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    payload = service.public_problem(problem_id, touch=True)
    if payload is None:
        raise HTTPException(status_code=404, detail="Problem not found (it may have expired). Open it from History or generate a new one.")
    return payload


@router.delete("/problems/{problem_id}")
async def delete_problem(problem_id: str, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    if not service.delete_problem(problem_id):
        raise HTTPException(status_code=404, detail="Problem not found.")
    return {"deleted": problem_id, "stats": service.stats()}


@router.put("/problems/{problem_id}/whiteboard")
async def save_whiteboard(problem_id: str, request: WhiteboardSaveRequest, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    _get(service, problem_id)
    try:
        return service.save_whiteboard(problem_id, request.canvas_json)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/problems/{problem_id}/whiteboard")
async def load_whiteboard(problem_id: str, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    _get(service, problem_id)
    return service.load_whiteboard(problem_id)


@router.post("/read-board")
async def read_board(request: BoardReadRequest, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    if request.problem_id:
        _get(service, request.problem_id)
    return service.interpret_board(request.texts, request.problem_id)


@router.post("/problems/{problem_id}/check")
async def check_answer(problem_id: str, request: CheckRequest, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    _get(service, problem_id)
    try:
        return await asyncio.to_thread(service.check, problem_id, request.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/problems/{problem_id}/hint")
async def get_hint(problem_id: str, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    _get(service, problem_id)
    return service.hint(problem_id)


@router.post("/problems/{problem_id}/solution")
async def reveal_solution(problem_id: str, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    _get(service, problem_id)
    return await asyncio.to_thread(service.solution, problem_id)
