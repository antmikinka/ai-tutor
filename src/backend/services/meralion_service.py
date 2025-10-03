"""
MERaLiON-AudioLLM-Whisper-SEA-LION STT service for speech recognition
Optimized for Southeast Asian languages and educational content
"""

import json
import logging
import time
import io
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import torch
import numpy as np
import soundfile as sf
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import librosa

from config.settings import get_settings
from services.model_config import ModelConfig, ModelType

logger = logging.getLogger(__name__)

class MERaLiONService:
    """
    Service for MERaLiON-AudioLLM-Whisper-SEA-LION speech recognition model
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.model = None
        self.processor = None
        self.model_config = None
        self.is_initialized = False
        self.limited_mode = False
        self.supported_languages = self._load_supported_languages()
        self.educational_terms = self._load_educational_terms()
        self.noise_profiles = self._load_noise_profiles()

    async def initialize(self, model_instance: Optional[Any] = None):
        """Initialize the MERaLiON service with loaded model"""
        try:
            logger.info("Initializing MERaLiON Service...")

            # If no model instance provided, create a simple initialization
            if model_instance is None:
                logger.warning("No model instance provided to MERaLiON service - running in limited mode")
                self.is_initialized = True
                self.limited_mode = True
                logger.info("MERaLiON Service initialized in limited mode (no STT)")
                return

            # Get model objects
            if isinstance(model_instance, dict):
                self.model = model_instance.get("model")
                self.processor = model_instance.get("processor")
            else:
                # Assume model_instance is the actual model object
                self.model = model_instance
                self.processor = model_instance.processor if hasattr(model_instance, 'processor') else None

            if not self.model or not self.processor:
                raise ValueError("Model or processor not found in model instance")

            # Set model to evaluation mode
            self.model.eval()

            # Move to appropriate device
            if self.settings.ai_use_gpu and torch.cuda.is_available():
                self.model.cuda()
                logger.info("MERaLiON model moved to GPU")
            else:
                self.model.cpu()
                logger.info("MERaLiON model running on CPU")

            self.is_initialized = True
            self.limited_mode = False
            logger.info("MERaLiON Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize MERaLiON Service: {e}")
            raise

    async def speech_to_text(
        self,
        audio_data: Union[bytes, io.BytesIO, np.ndarray],
        language: str = "en",
        task: str = "transcribe",
        chunk_size: int = 30,  # seconds
        enable_educational_mode: bool = True,
        noise_reduction: bool = True,
        return_timestamps: bool = False
    ) -> Dict[str, Any]:
        """
        Convert speech to text using MERaLiON-AudioLLM

        Args:
            audio_data: Audio data as bytes, BytesIO, or numpy array
            language: Language code
            task: Task type (transcribe, translate)
            chunk_size: Size of audio chunks for processing
            enable_educational_mode: Enable educational content optimization
            noise_reduction: Apply noise reduction
            return_timestamps: Include word-level timestamps

        Returns:
            Dictionary with transcription result and metadata
        """
        try:
            start_time = time.time()
            logger.info("Processing speech-to-text with MERaLiON")

            if not self.is_initialized:
                raise RuntimeError("MERaLiON service is not initialized")

            if getattr(self, 'limited_mode', False):
                raise RuntimeError("MERaLiON service is running in limited mode - no STT model available")

            # Prepare audio data
            audio_array, sample_rate = self._prepare_audio_data(audio_data)

            # Apply preprocessing
            if noise_reduction:
                audio_array = self._apply_noise_reduction(audio_array, sample_rate)

            # Normalize audio
            audio_array = self._normalize_audio(audio_array)

            # Handle long audio by chunking
            if len(audio_array) / sample_rate > chunk_size:
                result = await self._transcribe_long_audio(
                    audio_array, sample_rate, language, task, chunk_size
                )
            else:
                result = await self._transcribe_audio(
                    audio_array, sample_rate, language, task
                )

            # Apply educational enhancements if enabled
            if enable_educational_mode:
                result = self._enhance_educational_content(result)

            # Calculate processing time
            processing_time = time.time() - start_time

            # Add metadata
            result.update({
                "language": language,
                "task": task,
                "processing_time": processing_time,
                "audio_duration": len(audio_array) / sample_rate,
                "sample_rate": sample_rate,
                "educational_mode": enable_educational_mode,
                "noise_reduction": noise_reduction,
                "timestamp": datetime.utcnow().isoformat()
            })

            return result

        except Exception as e:
            logger.error(f"Error in speech-to-text conversion: {e}")
            raise

    async def transcribe_math_lecture(
        self,
        audio_data: Union[bytes, io.BytesIO],
        subject: str = "mathematics",
        include_equations: bool = True,
        include_key_terms: bool = True
    ) -> Dict[str, Any]:
        """
        Specialized transcription for mathematical lectures and explanations

        Args:
            audio_data: Audio data from lecture
            subject: Subject area
            include_equations: Extract and format mathematical equations
            include_key_terms: Identify key mathematical terms

        Returns:
            Enhanced transcription with mathematical content analysis
        """
        try:
            start_time = time.time()

            # Transcribe with educational mode
            transcription = await self.speech_to_text(
                audio_data,
                language="en",
                enable_educational_mode=True,
                noise_reduction=True,
                return_timestamps=True
            )

            # Analyze mathematical content
            if include_equations:
                equations = self._extract_equations(transcription["text"])
                transcription["equations"] = equations

            if include_key_terms:
                key_terms = self._extract_mathematical_terms(transcription["text"], subject)
                transcription["key_terms"] = key_terms

            # Generate summary
            summary = await self._generate_lecture_summary(transcription["text"], subject)
            transcription["summary"] = summary

            # Structure by topics if possible
            topics = self._identify_topics(transcription["text"])
            transcription["topics"] = topics

            processing_time = time.time() - start_time
            transcription["processing_time"] = processing_time
            transcription["transcription_type"] = "math_lecture"

            return transcription

        except Exception as e:
            logger.error(f"Error transcribing math lecture: {e}")
            raise

    async def recognize_math_commands(
        self,
        audio_data: Union[bytes, io.BytesIO],
        command_context: str = "general"
    ) -> Dict[str, Any]:
        """
        Recognize mathematical commands and questions

        Args:
            audio_data: Short audio clip with command
            command_context: Context for command recognition

        Returns:
            Recognized command with intent analysis
        """
        try:
            start_time = time.time()

            # Transcribe short audio
            transcription = await self.speech_to_text(
                audio_data,
                language="en",
                enable_educational_mode=True,
                noise_reduction=True
            )

            # Analyze command intent
            intent_analysis = self._analyze_math_intent(transcription["text"], command_context)

            # Extract parameters
            parameters = self._extract_command_parameters(transcription["text"], intent_analysis["intent"])

            processing_time = time.time() - start_time

            return {
                "transcription": transcription["text"],
                "intent": intent_analysis["intent"],
                "confidence": intent_analysis["confidence"],
                "parameters": parameters,
                "context": command_context,
                "processing_time": processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error recognizing math commands: {e}")
            raise

    async def analyze_audio_quality(
        self,
        audio_data: Union[bytes, io.BytesIO, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Analyze audio quality for speech recognition

        Args:
            audio_data: Audio data to analyze

        Returns:
            Audio quality analysis with recommendations
        """
        try:
            # Prepare audio data
            audio_array, sample_rate = self._prepare_audio_data(audio_data)

            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(audio_array, sample_rate)

            # Generate recommendations
            recommendations = self._generate_quality_recommendations(quality_metrics)

            # Estimate transcription accuracy
            estimated_accuracy = self._estimate_transcription_accuracy(quality_metrics)

            return {
                "quality_metrics": quality_metrics,
                "recommendations": recommendations,
                "estimated_accuracy": estimated_accuracy,
                "overall_score": quality_metrics.get("overall_score", 0.5),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing audio quality: {e}")
            raise

    async def get_supported_languages(self) -> List[Dict[str, Any]]:
        """
        Get list of supported languages with quality information

        Returns:
            List of supported languages
        """
        try:
            languages = []

            for lang_code, lang_info in self.supported_languages.items():
                languages.append({
                    "code": lang_code,
                    "name": lang_info["name"],
                    "native_name": lang_info["native_name"],
                    "quality": lang_info.get("quality", "medium"),
                    "educational_support": lang_info.get("educational_support", False),
                    "mathematical_terms": lang_info.get("mathematical_terms", False)
                })

            return languages

        except Exception as e:
            logger.error(f"Error getting supported languages: {e}")
            raise

    async def optimize_for_environment(
        self,
        environment_type: str,
        noise_profile: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Optimize STT for specific environments

        Args:
            environment_type: Type of environment (classroom, quiet_room, noisy_room)
            noise_profile: Custom noise profile

        Returns:
            Optimization configuration
        """
        try:
            optimization_config = {
                "environment_type": environment_type,
                "settings": {},
                "timestamp": datetime.utcnow().isoformat()
            }

            if environment_type == "classroom":
                optimization_config["settings"] = {
                    "noise_reduction": True,
                    "educational_mode": True,
                    "classroom_noise_filter": True,
                    "voice_activity_detection": True,
                    "chunk_size": 15  # Shorter chunks for classroom
                }
            elif environment_type == "quiet_room":
                optimization_config["settings"] = {
                    "noise_reduction": False,
                    "educational_mode": True,
                    "sensitivity": "high",
                    "chunk_size": 30
                }
            elif environment_type == "noisy_room":
                optimization_config["settings"] = {
                    "noise_reduction": True,
                    "aggressive_noise_filter": True,
                    "educational_mode": True,
                    "chunk_size": 10,  # Shorter chunks for noisy environments
                    "voice_enhancement": True
                }

            # Apply custom noise profile if provided
            if noise_profile:
                optimization_config["settings"]["custom_noise_profile"] = noise_profile

            return optimization_config

        except Exception as e:
            logger.error(f"Error optimizing for environment: {e}")
            raise

    # Private helper methods
    def _load_supported_languages(self) -> Dict[str, Dict[str, Any]]:
        """Load supported languages optimized for MERaLiON"""
        return {
            "en": {
                "name": "English",
                "native_name": "English",
                "quality": "excellent",
                "educational_support": True,
                "mathematical_terms": True
            },
            "zh": {
                "name": "Chinese (Mandarin)",
                "native_name": "中文",
                "quality": "excellent",
                "educational_support": True,
                "mathematical_terms": True
            },
            "ms": {
                "name": "Malay",
                "native_name": "Bahasa Melayu",
                "quality": "good",
                "educational_support": True,
                "mathematical_terms": True
            },
            "id": {
                "name": "Indonesian",
                "native_name": "Bahasa Indonesia",
                "quality": "good",
                "educational_support": True,
                "mathematical_terms": True
            },
            "th": {
                "name": "Thai",
                "native_name": "ไทย",
                "quality": "good",
                "educational_support": True,
                "mathematical_terms": False
            },
            "vi": {
                "name": "Vietnamese",
                "native_name": "Tiếng Việt",
                "quality": "good",
                "educational_support": True,
                "mathematical_terms": False
            },
            "tl": {
                "name": "Tagalog",
                "native_name": "Tagalog",
                "quality": "medium",
                "educational_support": True,
                "mathematical_terms": False
            },
            "ja": {
                "name": "Japanese",
                "native_name": "日本語",
                "quality": "good",
                "educational_support": True,
                "mathematical_terms": True
            },
            "ko": {
                "name": "Korean",
                "native_name": "한국어",
                "quality": "good",
                "educational_support": True,
                "mathematical_terms": True
            }
        }

    def _load_educational_terms(self) -> Dict[str, List[str]]:
        """Load educational terms for enhanced recognition"""
        return {
            "mathematics": [
                "derivative", "integral", "limit", "function", "equation", "variable",
                "coefficient", "exponent", "logarithm", "trigonometry", "geometry",
                "algebra", "calculus", "statistics", "probability", "matrix", "vector",
                "polynomial", "quadratic", "linear", "exponential", "sine", "cosine",
                "tangent", "theorem", "proof", "formula", "equation", "solve"
            ],
            "physics": [
                "force", "mass", "acceleration", "velocity", "momentum", "energy",
                "power", "work", "gravity", "friction", "motion", "wave",
                "frequency", "amplitude", "wavelength", "electric", "magnetic"
            ],
            "chemistry": [
                "atom", "molecule", "element", "compound", "reaction", "bond",
                "acid", "base", "pH", "solution", "concentration", "mole"
            ],
            "general": [
                "explain", "describe", "calculate", "solve", "find", "determine",
                "analyze", "compare", "contrast", "define", "what", "how", "why"
            ]
        }

    def _load_noise_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load noise profiles for different environments"""
        return {
            "classroom": {
                "background_noise": ["chairs", "whispers", "paper_rustling"],
                "frequency_range": [100, 8000],
                "reduction_level": "moderate"
            },
            "quiet_room": {
                "background_noise": ["air_conditioning", "computer_fan"],
                "frequency_range": [50, 2000],
                "reduction_level": "minimal"
            },
            "noisy_room": {
                "background_noise": ["traffic", "conversation", "music"],
                "frequency_range": [100, 10000],
                "reduction_level": "aggressive"
            }
        }

    def _prepare_audio_data(self, audio_data: Union[bytes, io.BytesIO, np.ndarray]) -> tuple:
        """Prepare audio data for processing"""
        try:
            if isinstance(audio_data, bytes):
                audio_buffer = io.BytesIO(audio_data)
                audio_array, sample_rate = sf.read(audio_buffer)
            elif isinstance(audio_data, io.BytesIO):
                audio_array, sample_rate = sf.read(audio_data)
            elif isinstance(audio_data, np.ndarray):
                audio_array = audio_data
                sample_rate = self.settings.audio_sample_rate
            else:
                raise ValueError("Unsupported audio data type")

            # Convert to mono if stereo
            if len(audio_array.shape) > 1:
                audio_array = np.mean(audio_array, axis=1)

            # Resample to 16kHz if needed (Whisper's preferred rate)
            if sample_rate != 16000:
                audio_array = librosa.resample(audio_array, orig_sr=sample_rate, target_sr=16000)
                sample_rate = 16000

            return audio_array, sample_rate

        except Exception as e:
            logger.error(f"Error preparing audio data: {e}")
            raise

    def _apply_noise_reduction(self, audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply noise reduction to audio"""
        try:
            # Simple spectral subtraction for noise reduction
            # This is a basic implementation - in production, use more advanced methods

            # Compute STFT
            stft = librosa.stft(audio_array)
            magnitude = np.abs(stft)
            phase = np.angle(stft)

            # Estimate noise spectrum (from first few frames)
            noise_frames = 5
            noise_spectrum = np.mean(magnitude[:, :noise_frames], axis=1, keepdims=True)

            # Apply spectral subtraction
            alpha = 2.0  # Over-subtraction factor
            beta = 0.1   # Floor factor
            enhanced_magnitude = magnitude - alpha * noise_spectrum
            enhanced_magnitude = np.maximum(enhanced_magnitude, beta * noise_spectrum)

            # Reconstruct signal
            enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
            enhanced_audio = librosa.istft(enhanced_stft)

            return enhanced_audio

        except Exception as e:
            logger.error(f"Error applying noise reduction: {e}")
            return audio_array

    def _normalize_audio(self, audio_array: np.ndarray) -> np.ndarray:
        """Normalize audio to optimal level"""
        try:
            # RMS normalization
            rms = np.sqrt(np.mean(audio_array ** 2))
            if rms > 0:
                target_rms = 0.1  # Target RMS level
                audio_array = audio_array * (target_rms / rms)

            # Clip to prevent distortion
            audio_array = np.clip(audio_array, -1.0, 1.0)

            return audio_array

        except Exception as e:
            logger.error(f"Error normalizing audio: {e}")
            return audio_array

    async def _transcribe_audio(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        language: str,
        task: str
    ) -> Dict[str, Any]:
        """Transcribe audio using MERaLiON model"""
        try:
            # Process audio
            inputs = self.processor(
                audio_array,
                sampling_rate=sample_rate,
                return_tensors="pt",
                language=language,
                task=task
            )

            # Move to appropriate device
            if self.settings.ai_use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Generate transcription
            with torch.no_grad():
                predicted_ids = self.model.generate(**inputs)

            # Decode transcription
            transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

            return {
                "text": transcription.strip(),
                "confidence": self._calculate_confidence(transcription)
            }

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise

    async def _transcribe_long_audio(
        self,
        audio_array: np.ndarray,
        sample_rate: int,
        language: str,
        task: str,
        chunk_size: int
    ) -> Dict[str, Any]:
        """Transcribe long audio by chunking"""
        try:
            # Calculate chunk size in samples
            chunk_samples = chunk_size * sample_rate

            # Split audio into chunks
            chunks = []
            for i in range(0, len(audio_array), chunk_samples):
                chunk = audio_array[i:i + chunk_samples]
                chunks.append(chunk)

            # Transcribe each chunk
            transcriptions = []
            total_confidence = 0.0

            for chunk in chunks:
                if len(chunk) > 0:
                    result = await self._transcribe_audio(chunk, sample_rate, language, task)
                    transcriptions.append(result["text"])
                    total_confidence += result["confidence"]

            # Combine transcriptions
            combined_text = " ".join(transcriptions)
            avg_confidence = total_confidence / len(transcriptions) if transcriptions else 0.0

            return {
                "text": combined_text,
                "confidence": avg_confidence,
                "chunks_processed": len(chunks)
            }

        except Exception as e:
            logger.error(f"Error transcribing long audio: {e}")
            raise

    def _enhance_educational_content(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance transcription for educational content"""
        try:
            text = result["text"]

            # Improve mathematical terminology
            for category, terms in self.educational_terms.items():
                for term in terms:
                    # Simple enhancement - could be more sophisticated
                    if term in text.lower():
                        result["educational_terms"] = result.get("educational_terms", [])
                        result["educational_terms"].append({
                            "term": term,
                            "category": category,
                            "context": "mathematical_education"
                        })

            # Clean up common speech recognition errors in educational content
            text = self._clean_educational_text(text)
            result["text"] = text

            return result

        except Exception as e:
            logger.error(f"Error enhancing educational content: {e}")
            return result

    def _clean_educational_text(self, text: str) -> str:
        """Clean up common speech recognition errors"""
        try:
            # Common corrections for educational content
            corrections = {
                "times": "×",
                "divided by": "÷",
                "plus": "+",
                "minus": "-",
                "equals": "=",
                "squared": "²",
                "cubed": "³",
                "square root": "√",
                "pi": "π",
                "theta": "θ",
                "alpha": "α",
                "beta": "β"
            }

            cleaned_text = text
            for spoken_form, symbol in corrections.items():
                cleaned_text = cleaned_text.replace(spoken_form, symbol)

            return cleaned_text

        except Exception as e:
            logger.error(f"Error cleaning educational text: {e}")
            return text

    def _extract_equations(self, text: str) -> List[Dict[str, Any]]:
        """Extract mathematical equations from text"""
        try:
            import re

            equations = []

            # Look for equation patterns
            equation_patterns = [
                r"([a-zA-Z]+\s*[+\-*/=]\s*[a-zA-Z0-9]+)",
                r"([a-zA-Z]\^\d+\s*[+\-*/=]\s*[a-zA-Z0-9]+)",
                r"(∫[a-zA-Z]+\s*dx)",
                r"(d\/dx\([a-zA-Z]+\))",
                r"([a-zA-Z]\s*=\s*[a-zA-Z0-9+\-*/]+)"
            ]

            for pattern in equation_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    equations.append({
                        "equation": match.strip(),
                        "type": "algebraic",
                        "confidence": 0.8
                    })

            return equations

        except Exception as e:
            logger.error(f"Error extracting equations: {e}")
            return []

    def _extract_mathematical_terms(self, text: str, subject: str) -> List[Dict[str, Any]]:
        """Extract mathematical terms from text"""
        try:
            terms = []

            if subject in self.educational_terms:
                subject_terms = self.educational_terms[subject]

                for term in subject_terms:
                    if term.lower() in text.lower():
                        terms.append({
                            "term": term,
                            "subject": subject,
                            "confidence": 0.9
                        })

            return terms

        except Exception as e:
            logger.error(f"Error extracting mathematical terms: {e}")
            return []

    async def _generate_lecture_summary(self, text: str, subject: str) -> str:
        """Generate summary of lecture content"""
        try:
            # Simple extractive summary (first few sentences)
            sentences = text.split('.')
            summary_sentences = sentences[:3]  # First 3 sentences
            summary = '. '.join(summary_sentences).strip() + '.'

            return summary

        except Exception as e:
            logger.error(f"Error generating lecture summary: {e}")
            return ""

    def _identify_topics(self, text: str) -> List[Dict[str, Any]]:
        """Identify main topics in transcription"""
        try:
            topics = []

            # Simple keyword-based topic identification
            topic_keywords = {
                "algebra": ["equation", "variable", "solve", "linear", "quadratic"],
                "calculus": ["derivative", "integral", "limit", "function", "differentiate"],
                "geometry": ["angle", "triangle", "circle", "area", "perimeter"],
                "statistics": ["mean", "median", "standard deviation", "probability", "data"]
            }

            for topic, keywords in topic_keywords.items():
                score = sum(1 for keyword in keywords if keyword.lower() in text.lower())
                if score > 0:
                    topics.append({
                        "topic": topic,
                        "relevance_score": score,
                        "keywords_found": [k for k in keywords if k.lower() in text.lower()]
                    })

            return sorted(topics, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            logger.error(f"Error identifying topics: {e}")
            return []

    def _analyze_math_intent(self, text: str, context: str) -> Dict[str, Any]:
        """Analyze mathematical intent in command"""
        try:
            text_lower = text.lower()

            # Intent patterns
            intents = {
                "solve_equation": ["solve", "calculate", "find", "what is", "determine"],
                "explain_concept": ["explain", "what is", "describe", "tell me about"],
                "derive_formula": ["derive", "show how", "prove", "demonstrate"],
                "compare": ["compare", "difference between", "versus", "vs"],
                "define": ["define", "meaning of", "what does"],
                "example": ["example", "show me", "illustrate"]
            }

            intent_scores = {}
            for intent, keywords in intents.items():
                score = sum(1 for keyword in keywords if keyword in text_lower)
                if score > 0:
                    intent_scores[intent] = score

            if intent_scores:
                best_intent = max(intent_scores, key=intent_scores.get)
                confidence = intent_scores[best_intent] / len(intents[best_intent])
            else:
                best_intent = "general_inquiry"
                confidence = 0.5

            return {
                "intent": best_intent,
                "confidence": confidence,
                "context": context
            }

        except Exception as e:
            logger.error(f"Error analyzing math intent: {e}")
            return {"intent": "general_inquiry", "confidence": 0.3, "context": context}

    def _extract_command_parameters(self, text: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from mathematical command"""
        try:
            parameters = {}

            if intent == "solve_equation":
                # Extract equation or expression
                import re
                equation_pattern = r"([a-zA-Z0-9+\-*/=^()]+)"
                equations = re.findall(equation_pattern, text)
                if equations:
                    parameters["equations"] = equations

            elif intent == "explain_concept":
                # Extract concept name
                words = text.split()
                if len(words) > 2:
                    parameters["concept"] = " ".join(words[2:5])  # Simple extraction

            return parameters

        except Exception as e:
            logger.error(f"Error extracting command parameters: {e}")
            return {}

    def _calculate_quality_metrics(self, audio_array: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Calculate audio quality metrics"""
        try:
            # Calculate basic metrics
            rms = np.sqrt(np.mean(audio_array ** 2))
            peak = np.max(np.abs(audio_array))

            # Signal-to-noise ratio (simplified)
            signal_power = rms ** 2
            noise_power = np.var(audio_array)
            snr = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else 0

            # Clipping detection
            clipping_ratio = np.sum(np.abs(audio_array) > 0.95) / len(audio_array)

            # Overall quality score (0-1)
            quality_score = 1.0 - min(clipping_ratio * 10, 0.5)  # Penalize clipping
            quality_score *= min(snr / 20, 1.0)  # Penalize low SNR
            quality_score = max(0.0, quality_score)

            return {
                "rms_level": float(rms),
                "peak_level": float(peak),
                "snr_db": float(snr),
                "clipping_ratio": float(clipping_ratio),
                "overall_score": float(quality_score)
            }

        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
            return {"overall_score": 0.5}

    def _generate_quality_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate quality improvement recommendations"""
        try:
            recommendations = []

            if metrics.get("clipping_ratio", 0) > 0.05:
                recommendations.append("Reduce input volume to prevent clipping")

            if metrics.get("snr_db", 0) < 15:
                recommendations.append("Reduce background noise for better recognition")

            if metrics.get("rms_level", 0) < 0.05:
                recommendations.append("Increase microphone volume or speak closer")

            if metrics.get("overall_score", 0) < 0.7:
                recommendations.append("Improve recording conditions for better accuracy")

            return recommendations

        except Exception as e:
            logger.error(f"Error generating quality recommendations: {e}")
            return []

    def _estimate_transcription_accuracy(self, metrics: Dict[str, Any]) -> float:
        """Estimate transcription accuracy based on quality metrics"""
        try:
            base_accuracy = 0.9  # Base accuracy for good quality audio

            # Adjust based on metrics
            accuracy = base_accuracy
            accuracy -= metrics.get("clipping_ratio", 0) * 0.5  # Penalize clipping
            accuracy -= max(0, (15 - metrics.get("snr_db", 15)) / 30)  # Penalize low SNR
            accuracy *= metrics.get("overall_score", 0.7)  # Scale by overall quality

            return max(0.0, min(1.0, accuracy))

        except Exception as e:
            logger.error(f"Error estimating transcription accuracy: {e}")
            return 0.7

    def _calculate_confidence(self, transcription: str) -> float:
        """Calculate confidence score for transcription"""
        try:
            # Simple confidence based on transcription characteristics
            confidence = 0.8

            # Adjust based on length
            if len(transcription) > 0:
                if len(transcription) < 10:
                    confidence -= 0.2  # Very short transcriptions are less reliable
                elif len(transcription) > 500:
                    confidence -= 0.1  # Very long transcriptions may have errors

            return max(0.0, min(1.0, confidence))

        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 0.7

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up MERaLiON Service...")

            # Move model to CPU and clear memory
            if self.model and torch.cuda.is_available():
                self.model.cpu()
                torch.cuda.empty_cache()

            self.model = None
            self.processor = None
            self.is_initialized = False

            logger.info("MERaLiON Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during MERaLiON Service cleanup: {e}")