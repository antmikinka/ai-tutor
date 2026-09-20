"""
Drawing and canvas processing API endpoints
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.dependencies import get_drawing_service
from services.common import utc_now_iso
from services.drawing_service import DrawingDecodeError, DrawingService

logger = logging.getLogger(__name__)
router = APIRouter()


class DrawingProcessRequest(BaseModel):
    drawing_data: str = Field(min_length=1)
    process_type: str = "equation_recognition"
    options: Dict[str, Any] = Field(default_factory=dict)


class DrawingProcessResponse(BaseModel):
    id: str
    processed_data: Dict[str, Any]
    confidence: float
    processing_time: float
    image_dimensions: Dict[str, int]
    timestamp: str


class StrokeAnalysisRequest(BaseModel):
    strokes: List[Dict[str, Any]] = Field(max_length=5000)
    analysis_type: str = "shape_recognition"


class StrokeAnalysisResponse(BaseModel):
    id: str
    recognized_shapes: List[Dict[str, Any]]
    equations: List[Dict[str, Any]]
    confidence: float
    timestamp: str


class CanvasStateRequest(BaseModel):
    canvas_data: str = Field(min_length=1)
    canvas_objects: List[Dict[str, Any]] = Field(default_factory=list)


class CanvasStateResponse(BaseModel):
    id: str
    analysis: Dict[str, Any]
    suggestions: List[str]
    timestamp: str


def _http_error(exc: Exception, what: str) -> HTTPException:
    if isinstance(exc, DrawingDecodeError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("%s failed", what)
    return HTTPException(status_code=500, detail=f"Failed to {what}: {exc}")


@router.post("/process-drawing", response_model=DrawingProcessResponse)
async def process_drawing(request: DrawingProcessRequest, drawing: DrawingService = Depends(get_drawing_service)):
    try:
        result = await drawing.process_drawing(request.drawing_data, request.process_type, request.options)
    except Exception as exc:
        raise _http_error(exc, "process drawing") from exc
    return DrawingProcessResponse(
        id=str(uuid.uuid4()),
        processed_data=result["data"],
        confidence=result["confidence"],
        processing_time=result["processing_time"],
        image_dimensions=result["image_dimensions"],
        timestamp=result["timestamp"],
    )


@router.post("/analyze-strokes", response_model=StrokeAnalysisResponse)
async def analyze_strokes(request: StrokeAnalysisRequest, drawing: DrawingService = Depends(get_drawing_service)):
    result = await drawing.analyze_strokes(request.strokes, request.analysis_type)
    return StrokeAnalysisResponse(
        id=str(uuid.uuid4()),
        recognized_shapes=result["shapes"],
        equations=result["equations"],
        confidence=result["confidence"],
        timestamp=result["timestamp"],
    )


@router.post("/analyze-canvas", response_model=CanvasStateResponse)
async def analyze_canvas_state(request: CanvasStateRequest, drawing: DrawingService = Depends(get_drawing_service)):
    try:
        result = await drawing.analyze_canvas_state(request.canvas_data, request.canvas_objects)
    except Exception as exc:
        raise _http_error(exc, "analyze canvas") from exc
    return CanvasStateResponse(id=str(uuid.uuid4()), analysis=result["analysis"], suggestions=result["suggestions"], timestamp=result["timestamp"])


@router.post("/upload-drawing")
async def upload_drawing(
    file: UploadFile = File(...),
    process_type: str = Form("equation_recognition"),
    options: str = Form("{}"),
    drawing: DrawingService = Depends(get_drawing_service),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    image_data = await file.read()
    if len(image_data) > drawing.settings.max_upload_size:
        raise HTTPException(status_code=413, detail="Image exceeds the upload size limit")
    try:
        process_options = json.loads(options) if options else {}
    except json.JSONDecodeError:
        process_options = {}
    try:
        result = await drawing.process_drawing(base64.b64encode(image_data).decode("ascii"), process_type, process_options)
    except Exception as exc:
        raise _http_error(exc, "process uploaded drawing") from exc
    return {"filename": file.filename, "process_type": process_type, "result": result, "timestamp": utc_now_iso()}


@router.post("/enhance-drawing")
async def enhance_drawing_quality(request: DrawingProcessRequest, drawing: DrawingService = Depends(get_drawing_service)):
    try:
        result = await drawing.enhance_drawing(request.drawing_data, request.options)
    except Exception as exc:
        raise _http_error(exc, "enhance drawing") from exc
    return {"id": str(uuid.uuid4()), **result}


@router.post("/convert-to-latex")
async def convert_to_latex(request: DrawingProcessRequest, drawing: DrawingService = Depends(get_drawing_service)):
    try:
        result = await drawing.convert_to_latex(request.drawing_data, request.options)
    except Exception as exc:
        raise _http_error(exc, "convert to LaTeX") from exc
    return {"id": str(uuid.uuid4()), "latex_expressions": result["latex"], **{k: v for k, v in result.items() if k != "latex"}}


@router.get("/drawing-tools")
async def get_available_drawing_tools(drawing: DrawingService = Depends(get_drawing_service)):
    return {"tools": await drawing.get_available_tools(), "timestamp": utc_now_iso()}


@router.get("/recognition-types")
async def get_recognition_types(drawing: DrawingService = Depends(get_drawing_service)):
    return {"recognition_types": await drawing.get_recognition_types(), "timestamp": utc_now_iso()}


@router.post("/batch-process")
async def batch_process_drawings(
    requests: List[DrawingProcessRequest],
    drawing: DrawingService = Depends(get_drawing_service),
):
    if len(requests) > 20:
        raise HTTPException(status_code=400, detail="At most 20 drawings per batch")
    results = []
    for req in requests:
        try:
            result = await drawing.process_drawing(req.drawing_data, req.process_type, req.options)
            results.append({"request_id": str(uuid.uuid4()), "result": result, "status": "success"})
        except Exception as exc:
            results.append({"request_id": str(uuid.uuid4()), "error": str(exc), "status": "failed"})
    return {
        "results": results,
        "total_requests": len(requests),
        "successful_requests": sum(1 for r in results if r["status"] == "success"),
        "timestamp": utc_now_iso(),
    }


@router.post("/validate-equation")
async def validate_equation(request: DrawingProcessRequest, drawing: DrawingService = Depends(get_drawing_service)):
    try:
        result = await drawing.validate_equation(request.drawing_data, request.options)
    except Exception as exc:
        raise _http_error(exc, "validate equation") from exc
    return {"id": str(uuid.uuid4()), **result}


@router.post("/export-drawing")
async def export_drawing(request: DrawingProcessRequest, drawing: DrawingService = Depends(get_drawing_service)):
    try:
        result = await drawing.export_drawing(request.drawing_data, request.options)
    except Exception as exc:
        raise _http_error(exc, "export drawing") from exc
    return {"id": str(uuid.uuid4()), "export_formats": result["formats"], "export_data": result["export_data"], "timestamp": result["timestamp"]}
