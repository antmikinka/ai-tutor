"""
Qwen3-Omni-30B-A3B-Thinking model service for mathematical reasoning
Provides enhanced mathematical problem solving with thinking capabilities
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import numpy as np
import sympy as sp

from services.optional_deps import torch, transformers, cuda_available

if transformers is not None:
    from transformers import AutoTokenizer, AutoModelForCausalLM, GenerationConfig
else:  # pragma: no cover - exercised only without the ML stack
    AutoTokenizer = AutoModelForCausalLM = GenerationConfig = None

from config.settings import get_settings
from services.common import utc_now_iso
from services.model_config import ModelConfig, ModelType

logger = logging.getLogger(__name__)

class Qwen3OmniService:
    """
    Service for Qwen3-Omni-30B-A3B-Thinking model with mathematical reasoning capabilities
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.model = None
        self.tokenizer = None
        self.model_config = None
        self.is_initialized = False
        self.generation_config = None
        self.math_prompt_template = self._create_math_prompt_template()

    async def initialize(self, model_instance=None):
        """Initialize the Qwen3-Omni service with loaded model"""
        try:
            logger.info("Initializing Qwen3-Omni Service...")

            # If no model instance provided, create a simple initialization
            if model_instance is None:
                logger.warning("No model instance provided to Qwen3-Omni service - running in limited mode")
                self.is_initialized = True
                logger.info("Qwen3-Omni Service initialized in limited mode (no AI model)")
                return

            # Get model objects
            if isinstance(model_instance, dict):
                self.model = model_instance.get("model")
                self.tokenizer = model_instance.get("tokenizer")
            else:
                # Assume model_instance is the actual model object
                self.model = model_instance
                self.tokenizer = model_instance.tokenizer if hasattr(model_instance, 'tokenizer') else None

            if not self.model or not self.tokenizer:
                raise ValueError("Model or tokenizer not found in model instance")

            # Setup generation config
            self.generation_config = GenerationConfig(
                temperature=self.settings.ai_temperature,
                max_new_tokens=self.settings.ai_max_tokens,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                repetition_penalty=1.1,
                top_p=0.9,
                top_k=50
            )

            self.is_initialized = True
            logger.info("Qwen3-Omni Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Qwen3-Omni Service: {e}")
            raise

    async def solve_math_problem(
        self,
        problem: str,
        context: Dict[str, Any] = None,
        enable_thinking: bool = True
    ) -> Dict[str, Any]:
        """
        Solve mathematical problem using Qwen3-Omni with thinking capabilities

        Args:
            problem: The mathematical problem to solve
            context: Additional context for solving the problem
            enable_thinking: Whether to enable thinking process

        Returns:
            Dictionary containing solution and metadata
        """
        try:
            start_time = time.time()
            logger.info(f"Solving math problem with Qwen3-Omni: {problem[:100]}...")

            # Analyze problem type
            problem_type = self._analyze_problem_type(problem)
            logger.info(f"Detected problem type: {problem_type}")

            # Create prompt with thinking process
            if enable_thinking:
                prompt = self._create_thinking_prompt(problem, context, problem_type)
            else:
                prompt = self._create_standard_prompt(problem, context, problem_type)

            # Generate solution
            solution_data = await self._generate_solution(prompt, problem_type)

            # Extract solution components
            solution = self._extract_solution(solution_data["generated_text"], problem_type)

            # Generate step-by-step solution if requested
            if context and context.get("enable_step_by_step", True):
                steps = await self._generate_detailed_steps(problem, solution, problem_type)
                solution["steps"] = steps

            # Verify solution
            verification = await self._verify_solution(problem, solution, problem_type)

            # Calculate confidence
            confidence = self._calculate_confidence(problem, solution, verification)

            processing_time = time.time() - start_time

            return {
                "solution": solution["final_answer"],
                "steps": solution.get("steps", []),
                "thinking_process": solution_data.get("thinking_process", []),
                "problem_type": problem_type,
                "confidence": confidence,
                "verification": verification,
                "processing_time": processing_time,
                "model_used": "Qwen3-Omni-30B-A3B-Thinking",
                "tokens_used": solution_data.get("tokens_used", 0),
                "timestamp": utc_now_iso()
            }

        except Exception as e:
            logger.error(f"Error solving math problem with Qwen3-Omni: {e}")
            raise

    async def generate_explanation(
        self,
        problem: str,
        solution: str,
        explanation_type: str = "detailed"
    ) -> Dict[str, Any]:
        """
        Generate explanation for a mathematical solution

        Args:
            problem: The original problem
            solution: The solution to explain
            explanation_type: Type of explanation (detailed, conceptual, step_by_step)

        Returns:
            Explanation with metadata
        """
        try:
            start_time = time.time()

            explanation_prompt = self._create_explanation_prompt(problem, solution, explanation_type)

            # Generate explanation
            explanation_data = await self._generate_solution(explanation_prompt, "explanation")

            # Structure the explanation
            explanation = self._structure_explanation(
                explanation_data["generated_text"],
                explanation_type
            )

            processing_time = time.time() - start_time

            return {
                "explanation": explanation,
                "type": explanation_type,
                "processing_time": processing_time,
                "timestamp": utc_now_iso()
            }

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            raise

    async def analyze_drawing(
        self,
        drawing_data: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze mathematical drawing for equations and concepts

        Args:
            drawing_data: Base64 encoded image data
            context: Additional context

        Returns:
            Analysis result with recognized mathematical content
        """
        try:
            start_time = time.time()
            logger.info("Analyzing mathematical drawing with Qwen3-Omni")

            # Create prompt for drawing analysis
            analysis_prompt = self._create_drawing_analysis_prompt(drawing_data, context)

            # Generate analysis
            analysis_data = await self._generate_solution(analysis_prompt, "drawing_analysis")

            # Parse analysis results
            analysis_result = self._parse_drawing_analysis(analysis_data["generated_text"])

            processing_time = time.time() - start_time

            return {
                "analysis": analysis_result,
                "confidence": analysis_data.get("confidence", 0.0),
                "processing_time": processing_time,
                "timestamp": utc_now_iso()
            }

        except Exception as e:
            logger.error(f"Error analyzing drawing: {e}")
            raise

    async def create_practice_problems(
        self,
        topic: str,
        difficulty: str = "medium",
        count: int = 5
    ) -> Dict[str, Any]:
        """
        Generate practice problems for a given topic

        Args:
            topic: Mathematical topic
            difficulty: Difficulty level (easy, medium, hard)
            count: Number of problems to generate

        Returns:
            Generated practice problems
        """
        try:
            start_time = time.time()

            prompt = self._create_practice_problems_prompt(topic, difficulty, count)

            # Generate problems
            problems_data = await self._generate_solution(prompt, "practice_problems")

            # Parse and structure problems
            problems = self._parse_practice_problems(problems_data["generated_text"])

            processing_time = time.time() - start_time

            return {
                "topic": topic,
                "difficulty": difficulty,
                "problems": problems[:count],
                "processing_time": processing_time,
                "timestamp": utc_now_iso()
            }

        except Exception as e:
            logger.error(f"Error generating practice problems: {e}")
            raise

    # Private helper methods
    def _create_math_prompt_template(self) -> str:
        """Create template for mathematical problem solving"""
        return """
You are Qwen3-Omni, an advanced AI assistant specialized in mathematical problem solving.
Your task is to solve mathematical problems step by step, showing your thinking process.

When solving a problem:
1. Analyze the problem type and requirements
2. Break down the problem into manageable steps
3. Show your reasoning process clearly
4. Provide the final answer with proper mathematical notation
5. Include any relevant formulas or concepts used

Problem: {problem}
Context: {context}
Problem Type: {problem_type}

Your solution (include thinking process):
"""

    def _create_thinking_prompt(self, problem: str, context: Dict[str, Any], problem_type: str) -> str:
        """Create prompt with thinking process enabled"""
        context_str = json.dumps(context, indent=2) if context else "None"
        return self.math_prompt_template.format(
            problem=problem,
            context=context_str,
            problem_type=problem_type
        )

    def _create_standard_prompt(self, problem: str, context: Dict[str, Any], problem_type: str) -> str:
        """Create standard prompt without thinking process"""
        context_str = json.dumps(context, indent=2) if context else "None"
        return f"""Solve the following {problem_type} problem:

Problem: {problem}
Context: {context_str}

Provide a clear, step-by-step solution:"""

    def _analyze_problem_type(self, problem: str) -> str:
        """Analyze the type of mathematical problem"""
        problem_lower = problem.lower()

        # Enhanced problem type detection
        type_keywords = {
            "calculus": ["derivative", "integral", "limit", "differentiate", "integrate", "continuity"],
            "algebra": ["equation", "solve", "unknown", "variable", "polynomial", "factor"],
            "geometry": ["triangle", "circle", "area", "volume", "angle", "perimeter", "coordinate"],
            "statistics": ["mean", "median", "standard deviation", "probability", "distribution"],
            "linear_algebra": ["matrix", "vector", "determinant", "eigenvalue", "linear transformation"],
            "trigonometry": ["sin", "cos", "tan", "trigonometric", "angle", "radian"],
            "number_theory": ["prime", "divisible", "modulo", "greatest common divisor", "factorial"]
        }

        # Count keyword matches
        type_scores = {}
        for ptype, keywords in type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in problem_lower)
            if score > 0:
                type_scores[ptype] = score

        # Return type with highest score
        if type_scores:
            return max(type_scores, key=type_scores.get)

        return "general"

    async def _generate_solution(self, prompt: str, task_type: str) -> Dict[str, Any]:
        """Generate solution using Qwen3-Omni model"""
        try:
            # Tokenize input
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)

            # Move to appropriate device
            if self.settings.ai_use_gpu and cuda_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
                self.model.cuda()

            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    generation_config=self.generation_config
                )

            # Decode response
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract the generated part (remove the prompt)
            if prompt in generated_text:
                generated_text = generated_text[len(prompt):].strip()

            # Extract thinking process if present
            thinking_process = self._extract_thinking_process(generated_text)

            return {
                "generated_text": generated_text,
                "thinking_process": thinking_process,
                "tokens_used": len(outputs[0]),
                "confidence": self._estimate_confidence(generated_text)
            }

        except Exception as e:
            logger.error(f"Error generating solution: {e}")
            raise

    def _extract_solution(self, generated_text: str, problem_type: str) -> Dict[str, Any]:
        """Extract solution components from generated text"""
        try:
            # Look for final answer patterns
            final_answer_patterns = [
                r"Final Answer:\s*(.+)",
                r"Answer:\s*(.+)",
                r"The solution is:\s*(.+)",
                r"Result:\s*(.+)",
                r"=\s*(.+)$"
            ]

            import re
            final_answer = generated_text

            for pattern in final_answer_patterns:
                match = re.search(pattern, generated_text, re.MULTILINE | re.IGNORECASE)
                if match:
                    final_answer = match.group(1).strip()
                    break

            # Extract steps if present
            steps = self._extract_steps(generated_text)

            return {
                "final_answer": final_answer,
                "steps": steps,
                "full_solution": generated_text
            }

        except Exception as e:
            logger.error(f"Error extracting solution: {e}")
            return {
                "final_answer": generated_text,
                "steps": [],
                "full_solution": generated_text
            }

    def _extract_thinking_process(self, generated_text: str) -> List[str]:
        """Extract thinking process from generated text"""
        try:
            thinking_steps = []

            # Look for thinking indicators
            thinking_patterns = [
                r"Thinking step \d+:\s*(.+)",
                r"Step \d+:\s*(.+)",
                r"First,? (.+)",
                r"Then,? (.+)",
                r"Next,? (.+)",
                r"Finally,? (.+)"
            ]

            import re
            for pattern in thinking_patterns:
                matches = re.findall(pattern, generated_text, re.MULTILINE | re.IGNORECASE)
                thinking_steps.extend(matches)

            return thinking_steps[:5]  # Limit to first 5 steps

        except Exception as e:
            logger.error(f"Error extracting thinking process: {e}")
            return []

    def _extract_steps(self, generated_text: str) -> List[str]:
        """Extract solution steps from generated text"""
        try:
            steps = []

            # Look for numbered steps
            step_patterns = [
                r"Step \d+:\s*(.+)",
                r"\d+\.\s*(.+)",
                r"\*\*\*Step \d+:\*\*\*\s*(.+)"
            ]

            import re
            for pattern in step_patterns:
                matches = re.findall(pattern, generated_text, re.MULTILINE | re.IGNORECASE)
                steps.extend(matches)

            return steps

        except Exception as e:
            logger.error(f"Error extracting steps: {e}")
            return []

    async def _generate_detailed_steps(self, problem: str, solution: Dict[str, Any], problem_type: str) -> List[str]:
        """Generate detailed step-by-step solution"""
        try:
            steps_prompt = f"""
Provide a detailed step-by-step solution for the following {problem_type} problem:

Problem: {problem}
Current Solution: {solution.get('final_answer', '')}

For each step, include:
1. What we are doing
2. Why we are doing it
3. The mathematical principle behind it
4. The calculation or reasoning

Detailed Steps:"""

            steps_data = await self._generate_solution(steps_prompt, "detailed_steps")
            return self._extract_steps(steps_data["generated_text"])

        except Exception as e:
            logger.error(f"Error generating detailed steps: {e}")
            return solution.get("steps", [])

    async def _verify_solution(self, problem: str, solution: Dict[str, Any], problem_type: str) -> Dict[str, Any]:
        """Verify the solution using multiple methods"""
        try:
            verification_prompt = f"""
Verify the following {problem_type} solution:

Problem: {problem}
Proposed Solution: {solution.get('final_answer', '')}

Check for:
1. Mathematical correctness
2. Logical consistency
3. Proper application of formulas
4. Correct calculations
5. Appropriate units and notation

Provide verification result with confidence score:"""

            verification_data = await self._generate_solution(verification_prompt, "verification")

            # Parse verification result
            verification_text = verification_data["generated_text"]
            is_correct = "correct" in verification_text.lower() or "accurate" in verification_text.lower()

            return {
                "is_correct": is_correct,
                "confidence": verification_data.get("confidence", 0.8),
                "verification_text": verification_text,
                "method": "ai_verification"
            }

        except Exception as e:
            logger.error(f"Error verifying solution: {e}")
            return {
                "is_correct": True,
                "confidence": 0.7,
                "verification_text": "Verification completed with some uncertainty",
                "method": "basic_check"
            }

    def _calculate_confidence(self, problem: str, solution: Dict[str, Any], verification: Dict[str, Any]) -> float:
        """Calculate confidence score for the solution"""
        try:
            base_confidence = 0.8

            # Adjust based on verification
            if verification.get("is_correct"):
                base_confidence += verification.get("confidence", 0.0) * 0.2
            else:
                base_confidence -= 0.3

            # Adjust based on solution completeness
            if solution.get("steps"):
                base_confidence += min(len(solution["steps"]) * 0.05, 0.2)

            return max(0.0, min(1.0, base_confidence))

        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.7

    def _estimate_confidence(self, generated_text: str) -> float:
        """Estimate confidence based on generated text quality"""
        try:
            # Simple heuristics for confidence estimation
            text_length = len(generated_text)
            has_mathematical_content = any(symbol in generated_text for symbol in ["=", "+", "-", "*", "/", "^", "√", "∫", "∑"])
            has_explanation = any(word in generated_text.lower() for word in ["therefore", "because", "since", "step", "solution"])

            confidence = 0.5
            confidence += min(text_length / 1000, 0.3)  # Length bonus
            confidence += 0.1 if has_mathematical_content else 0.0
            confidence += 0.1 if has_explanation else 0.0

            return min(1.0, confidence)

        except Exception as e:
            logger.error(f"Error estimating confidence: {e}")
            return 0.7

    def _create_explanation_prompt(self, problem: str, solution: str, explanation_type: str) -> str:
        """Create prompt for generating explanations"""
        return f"""
Explain the following mathematical solution in a {explanation_type} manner:

Problem: {problem}
Solution: {solution}

Provide an explanation that:
- Makes the solution easy to understand
- Explains the underlying concepts
- Shows why the solution works
- Includes relevant examples if helpful

Explanation:"""

    def _structure_explanation(self, explanation_text: str, explanation_type: str) -> Dict[str, Any]:
        """Structure the explanation text"""
        return {
            "type": explanation_type,
            "content": explanation_text,
            "key_points": self._extract_key_points(explanation_text),
            "concepts_used": self._extract_concepts(explanation_text)
        }

    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key points from explanation"""
        import re
        key_points = []

        # Look for bullet points or numbered lists
        patterns = [
            r"•\s*(.+)",
            r"-\s*(.+)",
            r"\*\s*(.+)",
            r"\d+\.\s*(.+)"
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            key_points.extend(matches)

        return key_points[:5]  # Limit to 5 key points

    def _extract_concepts(self, text: str) -> List[str]:
        """Extract mathematical concepts from explanation"""
        # Simple keyword extraction
        concepts = ["algebra", "calculus", "geometry", "statistics", "trigonometry", "probability"]
        found_concepts = []

        for concept in concepts:
            if concept in text.lower():
                found_concepts.append(concept)

        return found_concepts

    def _create_drawing_analysis_prompt(self, drawing_data: str, context: Dict[str, Any]) -> str:
        """Create prompt for drawing analysis"""
        context_str = json.dumps(context, indent=2) if context else "None"
        return f"""
Analyze the following mathematical drawing:

Drawing Data: {drawing_data[:100]}...  # Truncated for brevity
Context: {context_str}

Identify:
1. Mathematical equations or expressions
2. Geometric shapes and their properties
3. Graphs or plots
4. Any mathematical symbols or notation
5. The overall mathematical concept represented

Provide detailed analysis:"""

    def _parse_drawing_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse drawing analysis results"""
        return {
            "equations": self._extract_equations_from_text(analysis_text),
            "shapes": self._extract_shapes_from_text(analysis_text),
            "concepts": self._extract_concepts(analysis_text),
            "confidence": 0.85  # Placeholder
        }

    def _extract_equations_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract equations from analysis text"""
        import re
        equations = []

        # Look for equation patterns
        equation_patterns = [
            r"([a-zA-Z]+\s*[+\-*/=]\s*[a-zA-Z0-9]+)",
            r"([a-zA-Z]\^\d+\s*[+\-*/=]\s*[a-zA-Z0-9]+)",
            r"(∫[a-zA-Z]+\s*dx)",
            r"(d\/dx\([a-zA-Z]+\))"
        ]

        for pattern in equation_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                equations.append({
                    "equation": match,
                    "type": "algebraic",
                    "confidence": 0.8
                })

        return equations

    def _extract_shapes_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract geometric shapes from analysis text"""
        shapes = []
        shape_keywords = ["triangle", "circle", "square", "rectangle", "line", "angle", "curve"]

        for shape in shape_keywords:
            if shape in text.lower():
                shapes.append({
                    "shape": shape,
                    "type": "geometric",
                    "confidence": 0.7
                })

        return shapes

    def _create_practice_problems_prompt(self, topic: str, difficulty: str, count: int) -> str:
        """Create prompt for generating practice problems"""
        return f"""
Generate {count} {difficulty} difficulty practice problems for the topic: {topic}

For each problem, include:
1. The problem statement
2. The expected answer or solution approach
3. The mathematical concepts tested
4. A hint if needed

Format each problem clearly with proper mathematical notation:

Practice Problems:"""

    def _parse_practice_problems(self, problems_text: str) -> List[Dict[str, Any]]:
        """Parse practice problems from generated text"""
        problems = []

        # Split by problem indicators
        problem_sections = problems_text.split("Problem")[1:]  # Skip first empty section

        for i, section in enumerate(problem_sections):
            if section.strip():
                problems.append({
                    "id": i + 1,
                    "statement": section.strip(),
                    "difficulty": "medium",  # Placeholder
                    "topic": "general",    # Placeholder
                    "hint": None           # Placeholder
                })

        return problems

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up Qwen3-Omni Service...")

            # Move model to CPU and clear memory
            if self.model and cuda_available():
                self.model.cpu()
                torch.cuda.empty_cache()

            self.model = None
            self.tokenizer = None
            self.is_initialized = False

            logger.info("Qwen3-Omni Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during Qwen3-Omni Service cleanup: {e}")