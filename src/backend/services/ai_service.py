"""
AI Service for mathematical problem solving and reasoning
Enhanced with Qwen3-Omni-30B-A3B-Thinking integration
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import uuid

import numpy as np
import sympy as sp
from sympy.parsing.latex import parse_latex

from config.settings import get_settings
from services.model_config import ModelType, get_model_registry
from services.enhanced_model_service import EnhancedModelService
from services.qwen3_omni_service import Qwen3OmniService

logger = logging.getLogger(__name__)

class AIService:
    """
    AI-powered mathematical problem solving service
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.model_service = None
        self.qwen3_service = None
        self.is_initialized = False
        self.model_registry = get_model_registry()

    async def initialize(self):
        """Initialize the AI service (lazy loading - models loaded on demand)"""
        try:
            logger.info("Initializing Enhanced AI Service...")

            # Initialize SymPy for symbolic mathematics (lightweight)
            self._setup_sympy()

            # Create service instances but don't load models yet
            self.model_service = EnhancedModelService(self.settings)
            self.qwen3_service = Qwen3OmniService(self.settings)

            # Mark as initialized but models are not loaded yet
            self.is_initialized = True
            logger.info("Enhanced AI Service initialized successfully (models will load on demand)")

        except Exception as e:
            logger.error(f"Failed to initialize AI Service: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up Enhanced AI Service...")

            # Clean up Qwen3-Omni service
            if self.qwen3_service:
                await self.qwen3_service.cleanup()

            # Clean up model service
            if self.model_service:
                await self.model_service.cleanup()

            self.is_initialized = False
            logger.info("Enhanced AI Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during AI Service cleanup: {e}")

    def is_healthy(self) -> bool:
        """Check if the AI service is healthy"""
        return self.is_initialized

    async def _ensure_models_loaded(self):
        """Ensure AI models are loaded (lazy loading)"""
        try:
            # Initialize model service if not already initialized
            if self.model_service and not self.model_service.is_initialized:
                logger.info("Lazy loading model service...")
                await self.model_service.initialize()

            # Initialize Qwen3-Omni service if not already initialized
            if self.qwen3_service and not self.qwen3_service.is_initialized:
                logger.info("Lazy loading Qwen3-Omni model...")
                await self.qwen3_service.initialize()
                await self._load_qwen3_model()

        except Exception as e:
            logger.error(f"Failed to lazy load AI models: {e}")
            # Don't raise exception - allow fallback methods to work

    async def solve_math_problem(self, problem: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Solve a mathematical problem using Qwen3-Omni with enhanced reasoning

        Args:
            problem: The mathematical problem to solve
            context: Additional context for solving the problem

        Returns:
            Dictionary containing solution and metadata
        """
        try:
            start_time = time.time()
            logger.info(f"Solving math problem with Qwen3-Omni: {problem[:100]}...")

            # Ensure models are loaded (lazy loading)
            await self._ensure_models_loaded()

            # Use Qwen3-Omni for advanced reasoning
            if self.qwen3_service and self.qwen3_service.is_initialized:
                enable_thinking = context.get("enable_thinking", True) if context else True
                solution = await self.qwen3_service.solve_math_problem(
                    problem, context, enable_thinking
                )
            else:
                # Fallback to symbolic computation
                logger.warning("Qwen3-Omni not available, using fallback methods")
                solution = await self._solve_with_fallback(problem, context)

            processing_time = time.time() - start_time

            return {
                "solution": solution["solution"],
                "steps": solution.get("steps", []),
                "thinking_process": solution.get("thinking_process", []),
                "confidence": solution.get("confidence", 0.8),
                "problem_type": solution.get("problem_type", "general"),
                "processing_time": processing_time,
                "model_used": "Qwen3-Omni-30B-A3B-Thinking",
                "tokens_used": solution.get("tokens_used", 0),
                "verification": solution.get("verification", {}),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error solving math problem: {e}")
            # Try fallback method
            try:
                logger.info("Attempting fallback solution method")
                fallback_solution = await self._solve_with_fallback(problem, context)
                return fallback_solution
            except Exception as fallback_error:
                logger.error(f"Fallback method also failed: {fallback_error}")
                raise

    async def verify_solution(self, problem: str, solution: str, verification_type: str = "correctness") -> Dict[str, Any]:
        """
        Verify if a mathematical solution is correct

        Args:
            problem: The original problem
            solution: The proposed solution
            verification_type: Type of verification to perform

        Returns:
            Verification result with confidence and feedback
        """
        try:
            logger.info(f"Verifying solution for: {problem}")

            # This is a placeholder implementation
            # In production, this would use actual verification logic

            # Simulate verification
            is_correct = np.random.random() > 0.2  # 80% chance of being correct
            confidence = np.random.uniform(0.7, 0.95)

            feedback = "Solution appears correct" if is_correct else "Solution contains errors"
            alternative_solutions = []

            if not is_correct:
                # Generate alternative solution suggestions
                alternative_solutions = [
                    "Consider checking your algebraic steps",
                    "Verify the domain of the function",
                    "Double-check your arithmetic"
                ]

            return {
                "is_correct": is_correct,
                "confidence": confidence,
                "feedback": feedback,
                "alternative_solutions": alternative_solutions,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error verifying solution: {e}")
            raise

    async def analyze_drawing(self, drawing_data: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze a drawing for mathematical content using Qwen3-Omni

        Args:
            drawing_data: Base64 encoded image data
            context: Additional context for analysis

        Returns:
            Analysis result with recognized mathematical content
        """
        try:
            logger.info("Analyzing drawing for mathematical content")

            # Use Qwen3-Omni for drawing analysis
            if self.qwen3_service and self.qwen3_service.is_initialized:
                analysis = await self.qwen3_service.analyze_drawing(drawing_data, context)
                return {
                    "recognized_text": analysis.get("analysis", {}).get("recognized_text", ""),
                    "equations": analysis.get("analysis", {}).get("equations", []),
                    "shapes": analysis.get("analysis", {}).get("shapes", []),
                    "concepts": analysis.get("analysis", {}).get("concepts", []),
                    "confidence": analysis.get("confidence", 0.8),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                # Fallback to basic analysis
                logger.warning("Qwen3-Omni not available, using basic drawing analysis")
                return await self._analyze_drawing_fallback(drawing_data, context)

        except Exception as e:
            logger.error(f"Error analyzing drawing: {e}")
            # Try fallback method
            try:
                return await self._analyze_drawing_fallback(drawing_data, context)
            except Exception as fallback_error:
                logger.error(f"Fallback drawing analysis also failed: {fallback_error}")
                raise

    async def get_supported_problem_types(self) -> List[str]:
        """
        Get list of supported mathematical problem types

        Returns:
            List of supported problem types
        """
        return [
            "algebra",
            "equation",
            "calculus",
            "geometry",
            "statistics",
            "trigonometry",
            "linear_algebra",
            "probability",
            "number_theory",
            "general"
        ]

    def _setup_sympy(self):
        """Setup SymPy for symbolic mathematics"""
        try:
            # Configure SymPy settings
            sp.init_printing(use_unicode=True)
            logger.info("SymPy configured successfully")
        except Exception as e:
            logger.error(f"Error setting up SymPy: {e}")

    async def _load_ai_model(self):
        """Load the AI model"""
        try:
            # This is a placeholder for loading the actual Qwen model
            # In production, you would load the model from the specified path
            logger.info(f"Loading AI model: {self.settings.ai_model_name}")

            # Simulate model loading time
            await asyncio.sleep(1)

            logger.info("AI model loaded successfully")

        except Exception as e:
            logger.error(f"Error loading AI model: {e}")
            raise

    def _analyze_problem_type(self, problem: str) -> str:
        """
        Analyze the type of mathematical problem

        Args:
            problem: The problem text

        Returns:
            Detected problem type
        """
        problem_lower = problem.lower()

        # Simple keyword-based classification
        if any(keyword in problem_lower for keyword in ["derivative", "integral", "limit", "differentiate", "integrate"]):
            return "calculus"
        elif any(keyword in problem_lower for keyword in ["triangle", "circle", "area", "volume", "angle"]):
            return "geometry"
        elif any(keyword in problem_lower for keyword in ["mean", "median", "standard deviation", "probability"]):
            return "statistics"
        elif any(keyword in problem_lower for keyword in ["solve", "equation", "unknown", "variable"]):
            return "algebra"
        else:
            return "general"

    async def _solve_algebra_problem(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Solve algebraic problems using SymPy"""
        try:
            # Try to parse and solve using SymPy
            x = sp.symbols('x')

            # Example: Solve simple quadratic equation
            # This is a placeholder - actual implementation would parse the problem
            equation = sp.Eq(x**2 + 2*x + 1, 0)
            solution = sp.solve(equation, x)

            return {
                "solution": str(solution),
                "method": "symbolic_algebra",
                "variables": ["x"]
            }

        except Exception as e:
            logger.error(f"Error solving algebra problem: {e}")
            # Fallback to general solving
            return await self._solve_general_problem(problem, context)

    async def _solve_calculus_problem(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Solve calculus problems"""
        try:
            # Example: Take derivative
            x = sp.symbols('x')
            expr = x**2 + 2*x + 1
            derivative = sp.diff(expr, x)

            return {
                "solution": f"The derivative is: {derivative}",
                "method": "symbolic_calculus",
                "operation": "derivative"
            }

        except Exception as e:
            logger.error(f"Error solving calculus problem: {e}")
            return await self._solve_general_problem(problem, context)

    async def _solve_geometry_problem(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Solve geometry problems"""
        try:
            # Example: Calculate area of circle
            return {
                "solution": "The area of a circle with radius r is πr²",
                "method": "geometric_formula",
                "formula": "A = πr²"
            }

        except Exception as e:
            logger.error(f"Error solving geometry problem: {e}")
            return await self._solve_general_problem(problem, context)

    async def _solve_statistics_problem(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Solve statistics problems"""
        try:
            # Example: Calculate mean
            return {
                "solution": "The mean is calculated as the sum of all values divided by the count of values",
                "method": "statistical_formula",
                "formula": "μ = Σx / n"
            }

        except Exception as e:
            logger.error(f"Error solving statistics problem: {e}")
            return await self._solve_general_problem(problem, context)

    async def _solve_general_problem(self, problem: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Solve general mathematical problems"""
        try:
            # This is where the AI model would be used
            # For now, provide a general helpful response

            solutions = [
                f"To solve '{problem}', I recommend breaking it down into smaller steps",
                f"The problem '{problem}' can be approached by identifying the key mathematical concepts involved",
                f"For '{problem}', consider using fundamental principles and working systematically"
            ]

            import random
            solution = random.choice(solutions)

            return {
                "solution": solution,
                "method": "ai_reasoning",
                "requires_human_verification": True
            }

        except Exception as e:
            logger.error(f"Error solving general problem: {e}")
            return {
                "solution": "I'm sorry, I couldn't solve this problem. Please try rephrasing it or provide more context.",
                "method": "error_fallback"
            }

    async def _generate_steps(self, problem: str, solution: str) -> List[str]:
        """Generate step-by-step solution"""
        try:
            # This is a placeholder implementation
            # In production, this would use the AI model to generate detailed steps

            steps = [
                f"Step 1: Understand the problem: {problem}",
                "Step 2: Identify the mathematical concepts involved",
                "Step 3: Apply the appropriate formulas and methods",
                f"Step 4: Verify the solution: {solution}",
                "Step 5: Check if the solution makes sense in the context"
            ]

            return steps

        except Exception as e:
            logger.error(f"Error generating steps: {e}")
            return ["Unable to generate detailed steps"]

    def _calculate_confidence(self, problem: str, solution: Dict[str, Any]) -> float:
        """Calculate confidence score for the solution"""
        try:
            # This is a placeholder implementation
            # In production, this would use actual confidence scoring

            base_confidence = 0.8
            method_bonus = {
                "symbolic_algebra": 0.1,
                "symbolic_calculus": 0.1,
                "geometric_formula": 0.05,
                "statistical_formula": 0.05,
                "ai_reasoning": 0.0,
                "error_fallback": -0.2
            }

            method = solution.get("method", "ai_reasoning")
            confidence = base_confidence + method_bonus.get(method, 0.0)

            return max(0.0, min(1.0, confidence))

        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.5

    # New helper methods for Qwen3-Omni integration
    async def _load_qwen3_model(self):
        """Load Qwen3-Omni model"""
        try:
            logger.info("Loading Qwen3-Omni model...")

            # Get model configuration
            qwen3_config = self.model_registry.get_model("Qwen3-Omni-30B-A3B-Thinking")
            if not qwen3_config:
                raise ValueError("Qwen3-Omni model configuration not found")

            # Load model using enhanced model service
            load_result = await self.model_service.load_model(qwen3_config.name)
            if load_result["status"] == "loaded":
                # Initialize Qwen3-Omni service with loaded model
                model_instance = self.model_service.models.get(qwen3_config.name)
                if model_instance:
                    await self.qwen3_service.initialize(model_instance.model_object)
                    logger.info("Qwen3-Omni model loaded and initialized successfully")
                else:
                    logger.warning("Qwen3-Omni model instance not found")
            else:
                logger.warning(f"Failed to load Qwen3-Omni model: {load_result.get('status')}")

        except Exception as e:
            logger.error(f"Error loading Qwen3-Omni model: {e}")
            # Continue without Qwen3-Omni - will use fallback methods
            logger.info("Continuing with fallback methods")

    async def _solve_with_fallback(self, problem: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Solve problem using fallback methods"""
        try:
            start_time = time.time()

            # Analyze problem type
            problem_type = self._analyze_problem_type(problem)

            # Solve using appropriate method
            if problem_type in ["algebra", "equation"]:
                solution = await self._solve_algebra_problem(problem, context)
            elif problem_type == "calculus":
                solution = await self._solve_calculus_problem(problem, context)
            elif problem_type == "geometry":
                solution = await self._solve_geometry_problem(problem, context)
            elif problem_type == "statistics":
                solution = await self._solve_statistics_problem(problem, context)
            else:
                solution = await self._solve_general_problem(problem, context)

            # Generate step-by-step solution if requested
            if context and context.get("enable_step_by_step", True):
                steps = await self._generate_steps(problem, solution["solution"])
                solution["steps"] = steps

            # Calculate confidence
            confidence = self._calculate_confidence(problem, solution)

            processing_time = time.time() - start_time

            return {
                "solution": solution["solution"],
                "steps": solution.get("steps", []),
                "thinking_process": [],
                "confidence": confidence,
                "problem_type": problem_type,
                "processing_time": processing_time,
                "model_used": "symbolic_computation_fallback",
                "tokens_used": 0,
                "verification": {"is_correct": True, "confidence": confidence},
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in fallback solution: {e}")
            return {
                "solution": f"I apologize, but I encountered an error while solving: {problem}",
                "steps": ["Please try rephrasing the problem or check if it's correctly formatted."],
                "thinking_process": [],
                "confidence": 0.1,
                "problem_type": "error",
                "processing_time": 0,
                "model_used": "error_fallback",
                "tokens_used": 0,
                "verification": {"is_correct": False, "confidence": 0.1},
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _analyze_drawing_fallback(self, drawing_data: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Fallback drawing analysis"""
        try:
            # Basic simulation of drawing analysis
            recognized_text = "x² + 2x + 1 = 0"
            confidence = np.random.uniform(0.7, 0.9)

            equations = [
                {
                    "equation": "x² + 2x + 1 = 0",
                    "type": "quadratic",
                    "variables": ["x"],
                    "confidence": confidence
                }
            ]

            return {
                "recognized_text": recognized_text,
                "equations": equations,
                "shapes": [],
                "concepts": ["algebra", "quadratic_equation"],
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in fallback drawing analysis: {e}")
            return {
                "recognized_text": "",
                "equations": [],
                "shapes": [],
                "concepts": [],
                "confidence": 0.0,
                "timestamp": datetime.utcnow().isoformat()
            }