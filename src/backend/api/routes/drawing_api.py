"""
Drawing and canvas processing API endpoints
"""

import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from datetime import datetime
import uuid
import base64
import io

from services.drawing_service import DrawingService

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class DrawingProcessRequest(BaseModel):
    drawing_data: str  # Base64 encoded image
    process_type: str = "equation_recognition"
    options: Optional[Dict[str, Any]] = {}

class DrawingProcessResponse(BaseModel):
    id: str
    processed_data: Dict[str, Any]
    confidence: float
    processing_time: float
    timestamp: str

class StrokeAnalysisRequest(BaseModel):
    strokes: List[Dict[str, Any]]  # List of stroke data
    analysis_type: str = "shape_recognition"

class StrokeAnalysisResponse(BaseModel):
    id: str
    recognized_shapes: List[Dict[str, Any]]
    equations: List[Dict[str, Any]]
    confidence: float
    timestamp: str

class CanvasStateRequest(BaseModel):
    canvas_data: str  # Base64 encoded canvas image
    canvas_objects: List[Dict[str, Any]] = []

class CanvasStateResponse(BaseModel):
    id: str
    analysis: Dict[str, Any]
    suggestions: List[str]
    timestamp: str

# Initialize services
drawing_service = DrawingService()

@router.post("/process-drawing", response_model=DrawingProcessResponse)
async def process_drawing(request: DrawingProcessRequest):
    """
    Process a drawing for mathematical content
    """
    try:
        logger.info(f"Processing drawing with type: {request.process_type}")

        # Process the drawing
        result = await drawing_service.process_drawing(
            request.drawing_data,
            request.process_type,
            request.options
        )

        return DrawingProcessResponse(
            id=str(uuid.uuid4()),
            processed_data=result["data"],
            confidence=result.get("confidence", 0.0),
            processing_time=result.get("processing_time", 0.0),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error processing drawing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process drawing: {str(e)}")

@router.post("/analyze-strokes", response_model=StrokeAnalysisResponse)
async def analyze_strokes(request: StrokeAnalysisRequest):
    """
    Analyze individual strokes for shape and equation recognition
    """
    try:
        logger.info(f"Analyzing {len(request.strokes)} strokes")

        # Analyze strokes
        result = await drawing_service.analyze_strokes(
            request.strokes,
            request.analysis_type
        )

        return StrokeAnalysisResponse(
            id=str(uuid.uuid4()),
            recognized_shapes=result.get("shapes", []),
            equations=result.get("equations", []),
            confidence=result.get("confidence", 0.0),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error analyzing strokes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze strokes: {str(e)}")

@router.post("/analyze-canvas", response_model=CanvasStateResponse)
async def analyze_canvas_state(request: CanvasStateRequest):
    """
    Analyze complete canvas state for mathematical content
    """
    try:
        logger.info("Analyzing canvas state")

        # Analyze canvas
        result = await drawing_service.analyze_canvas_state(
            request.canvas_data,
            request.canvas_objects
        )

        return CanvasStateResponse(
            id=str(uuid.uuid4()),
            analysis=result["analysis"],
            suggestions=result.get("suggestions", []),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error analyzing canvas state: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze canvas state: {str(e)}")

@router.post("/upload-drawing")
async def upload_drawing(
    file: UploadFile = File(...),
    process_type: str = Form("equation_recognition"),
    options: str = Form("{}")
):
    """
    Upload and process a drawing file
    """
    try:
        logger.info(f"Processing uploaded drawing: {file.filename}")

        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read file data
        image_data = await file.read()

        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Parse options
        try:
            process_options = json.loads(options)
        except:
            process_options = {}

        # Process drawing
        result = await drawing_service.process_drawing(
            base64_image,
            process_type,
            process_options
        )

        return {
            "filename": file.filename,
            "process_type": process_type,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error processing uploaded drawing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded drawing: {str(e)}")

@router.post("/enhance-drawing")
async def enhance_drawing_quality(request: DrawingProcessRequest):
    """
    Enhance drawing quality for better recognition
    """
    try:
        logger.info("Enhancing drawing quality")

        # Enhance drawing
        result = await drawing_service.enhance_drawing(
            request.drawing_data,
            request.options
        )

        return {
            "id": str(uuid.uuid4()),
            "enhanced_data": result["enhanced_data"],
            "enhancements_applied": result.get("enhancements", []),
            "original_confidence": result.get("original_confidence", 0.0),
            "enhanced_confidence": result.get("enhanced_confidence", 0.0),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error enhancing drawing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enhance drawing: {str(e)}")

@router.post("/convert-to-latex")
async def convert_to_latex(request: DrawingProcessRequest):
    """
    Convert recognized mathematical expressions to LaTeX
    """
    try:
        logger.info("Converting drawing to LaTeX")

        # Convert to LaTeX
        result = await drawing_service.convert_to_latex(
            request.drawing_data,
            request.options
        )

        return {
            "id": str(uuid.uuid4()),
            "latex_expressions": result.get("latex", []),
            "confidence": result.get("confidence", 0.0),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error converting to LaTeX: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to convert to LaTeX: {str(e)}")

@router.get("/drawing-tools")
async def get_available_drawing_tools():
    """
    Get list of available drawing tools and their capabilities
    """
    try:
        tools = await drawing_service.get_available_tools()
        return {
            "tools": tools,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting drawing tools: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get drawing tools: {str(e)}")

@router.get("/recognition-types")
async def get_recognition_types():
    """
    Get list of supported recognition types
    """
    try:
        types = await drawing_service.get_recognition_types()
        return {
            "recognition_types": types,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recognition types: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recognition types: {str(e)}")

@router.post("/batch-process")
async def batch_process_drawings(requests: List[DrawingProcessRequest]):
    """
    Process multiple drawings in batch
    """
    try:
        logger.info(f"Processing batch of {len(requests)} drawings")

        results = []
        for req in requests:
            try:
                result = await drawing_service.process_drawing(
                    req.drawing_data,
                    req.process_type,
                    req.options
                )
                results.append({
                    "request_id": str(uuid.uuid4()),
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"Error processing drawing in batch: {e}")
                results.append({
                    "request_id": str(uuid.uuid4()),
                    "error": str(e),
                    "status": "failed"
                })

        return {
            "results": results,
            "total_requests": len(requests),
            "successful_requests": len([r for r in results if r["status"] == "success"]),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process batch drawings: {str(e)}")

@router.post("/validate-equation")
async def validate_equation(request: DrawingProcessRequest):
    """
    Validate if a drawing represents a valid mathematical equation
    """
    try:
        logger.info("Validating mathematical equation from drawing")

        # Validate equation
        result = await drawing_service.validate_equation(
            request.drawing_data,
            request.options
        )

        return {
            "id": str(uuid.uuid4()),
            "is_valid": result.get("is_valid", False),
            "equation": result.get("equation", ""),
            "validation_errors": result.get("errors", []),
            "suggestions": result.get("suggestions", []),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error validating equation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate equation: {str(e)}")

@router.post("/export-drawing")
async def export_drawing(request: DrawingProcessRequest):
    """
    Export drawing in different formats
    """
    try:
        logger.info("Exporting drawing")

        # Export drawing
        result = await drawing_service.export_drawing(
            request.drawing_data,
            request.options
        )

        return {
            "id": str(uuid.uuid4()),
            "export_formats": result.get("formats", []),
            "export_data": result.get("export_data", {}),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error exporting drawing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export drawing: {str(e)}")