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


def _get(service: PracticeService, problem_id: str):
    problem = service.get(problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found (it may have expired). Generate a new one.")
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


@router.get("/problems/{problem_id}")
async def get_problem(problem_id: str, service: PracticeService = Depends(get_practice_service)) -> Dict[str, Any]:
    return _get(service, problem_id).public()


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
