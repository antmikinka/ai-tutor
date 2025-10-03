"""
Math-related API endpoints
"""

import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from datetime import datetime
import uuid

from services.ai_service import AIService
from services.drawing_service import DrawingService

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class MathProblemRequest(BaseModel):
    problem: str
    problem_type: Optional[str] = "general"
    context: Optional[Dict[str, Any]] = {}
    enable_step_by_step: bool = True
    enable_explanation: bool = True

class MathSolutionResponse(BaseModel):
    id: str
    problem: str
    solution: str
    steps: List[str]
    confidence: float
    problem_type: str
    timestamp: str
    metadata: Dict[str, Any]

class DrawingAnalysisRequest(BaseModel):
    drawing_data: str  # Base64 encoded image
    analysis_type: str = "equation_recognition"
    context: Optional[Dict[str, Any]] = {}

class DrawingAnalysisResponse(BaseModel):
    id: str
    recognized_text: str
    confidence: float
    equations: List[Dict[str, Any]]
    timestamp: str

class BatchProblemsRequest(BaseModel):
    problems: List[str]
    context: Optional[Dict[str, Any]] = {}

class VerificationRequest(BaseModel):
    problem: str
    solution: str
    verification_type: str = "correctness"

class VerificationResponse(BaseModel):
    is_correct: bool
    confidence: float
    feedback: str
    alternative_solutions: List[str]

# Initialize services
ai_service = AIService()
drawing_service = DrawingService()

@router.post("/solve", response_model=MathSolutionResponse)
async def solve_math_problem(request: MathProblemRequest):
    """
    Solve a mathematical problem using AI
    """
    try:
        logger.info(f"Solving math problem: {request.problem[:100]}...")

        # Get solution from AI service
        solution = await ai_service.solve_math_problem(
            request.problem,
            request.context
        )

        return MathSolutionResponse(
            id=str(uuid.uuid4()),
            problem=request.problem,
            solution=solution["solution"],
            steps=solution.get("steps", []),
            confidence=solution.get("confidence", 0.0),
            problem_type=request.problem_type,
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "processing_time": solution.get("processing_time", 0),
                "model_used": solution.get("model_used", "default"),
                "tokens_used": solution.get("tokens_used", 0)
            }
        )

    except Exception as e:
        logger.error(f"Error solving math problem: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to solve math problem: {str(e)}")

@router.post("/analyze-drawing", response_model=DrawingAnalysisResponse)
async def analyze_drawing(request: DrawingAnalysisRequest):
    """
    Analyze a drawing for mathematical content
    """
    try:
        logger.info(f"Analyzing drawing of type: {request.analysis_type}")

        # Process drawing data
        analysis = await drawing_service.analyze_drawing(
            request.drawing_data,
            request.analysis_type,
            request.context
        )

        return DrawingAnalysisResponse(
            id=str(uuid.uuid4()),
            recognized_text=analysis["recognized_text"],
            confidence=analysis["confidence"],
            equations=analysis.get("equations", []),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error analyzing drawing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze drawing: {str(e)}")

@router.post("/batch-solve")
async def solve_batch_problems(request: BatchProblemsRequest):
    """
    Solve multiple math problems in batch
    """
    try:
        logger.info(f"Solving batch of {len(request.problems)} problems")

        solutions = []
        for problem in request.problems:
            try:
                solution = await ai_service.solve_math_problem(
                    problem,
                    request.context
                )
                solutions.append({
                    "problem": problem,
                    "solution": solution,
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"Error solving problem '{problem}': {e}")
                solutions.append({
                    "problem": problem,
                    "error": str(e),
                    "status": "failed"
                })

        return {
            "solutions": solutions,
            "total_problems": len(request.problems),
            "successful_solutions": len([s for s in solutions if s["status"] == "success"]),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in batch solve: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to solve batch problems: {str(e)}")

@router.post("/verify")
async def verify_solution(request: VerificationRequest):
    """
    Verify if a mathematical solution is correct
    """
    try:
        logger.info(f"Verifying solution for: {request.problem}")

        verification = await ai_service.verify_solution(
            request.problem,
            request.solution,
            request.verification_type
        )

        return VerificationResponse(
            is_correct=verification["is_correct"],
            confidence=verification["confidence"],
            feedback=verification["feedback"],
            alternative_solutions=verification.get("alternative_solutions", [])
        )

    except Exception as e:
        logger.error(f"Error verifying solution: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify solution: {str(e)}")

@router.post("/upload-image")
async def upload_and_analyze_image(
    file: UploadFile = File(...),
    analysis_type: str = Form("equation_recognition"),
    context: str = Form("{}")
):
    """
    Upload an image for mathematical analysis
    """
    try:
        logger.info(f"Analyzing uploaded image: {file.filename}")

        # Validate file
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read image data
        image_data = await file.read()

        # Convert to base64 for processing
        import base64
        base64_image = base64.b64encode(image_data).decode('utf-8')

        # Parse context
        try:
            context_data = json.loads(context)
        except:
            context_data = {}

        # Analyze image
        analysis = await drawing_service.analyze_drawing(
            base64_image,
            analysis_type,
            context_data
        )

        return {
            "filename": file.filename,
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error analyzing uploaded image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze image: {str(e)}")

@router.get("/problem-types")
async def get_supported_problem_types():
    """
    Get list of supported mathematical problem types
    """
    try:
        problem_types = await ai_service.get_supported_problem_types()
        return {
            "problem_types": problem_types,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting problem types: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get problem types: {str(e)}")

@router.get("/history")
async def get_solution_history(
    limit: int = 50,
    offset: int = 0,
    problem_type: Optional[str] = None
):
    """
    Get historical solutions (placeholder - would connect to database in production)
    """
    try:
        # This is a placeholder implementation
        # In production, this would query a database
        history = []

        return {
            "history": history,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting solution history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get solution history: {str(e)}")

@router.delete("/history/{solution_id}")
async def delete_solution_from_history(solution_id: str):
    """
    Delete a solution from history (placeholder)
    """
    try:
        # This is a placeholder implementation
        # In production, this would delete from database
        logger.info(f"Deleting solution {solution_id} from history")

        return {
            "message": f"Solution {solution_id} deleted successfully",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error deleting solution from history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete solution: {str(e)}")

@router.get("/statistics")
async def get_math_statistics():
    """
    Get usage statistics (placeholder)
    """
    try:
        # This is a placeholder implementation
        # In production, this would query analytics database
        statistics = {
            "total_problems_solved": 0,
            "average_confidence": 0.0,
            "popular_problem_types": [],
            "daily_usage": []
        }

        return {
            "statistics": statistics,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")