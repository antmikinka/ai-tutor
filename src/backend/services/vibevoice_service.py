"""
Microsoft VibeVoice-1.5B TTS service for text-to-speech
Provides natural sounding speech synthesis optimized for educational content
"""

import json
import logging
import time
import io
import base64
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import torch
import numpy as np
import soundfile as sf
from transformers import AutoProcessor, AutoModelForTextToWaveform

from config.settings import get_settings
from services.model_config import ModelConfig, ModelType

logger = logging.getLogger(__name__)

class VibeVoiceService:
    """
    Service for Microsoft VibeVoice-1.5B text-to-speech model
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.model = None
        self.processor = None
        self.model_config = None
        self.is_initialized = False
        self.limited_mode = False
        self.voice_profiles = self._load_voice_profiles()
        self.supported_languages = self._load_supported_languages()

    async def initialize(self, model_instance: Optional[Any] = None):
        """Initialize the VibeVoice service with loaded model"""
        try:
            logger.info("Initializing VibeVoice Service...")

            # If no model instance provided, create a simple initialization
            if model_instance is None:
                logger.warning("No model instance provided to VibeVoice service - running in limited mode")
                self.is_initialized = True
                self.limited_mode = True
                logger.info("VibeVoice Service initialized in limited mode (no TTS)")
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
                logger.info("VibeVoice model moved to GPU")
            else:
                self.model.cpu()
                logger.info("VibeVoice model running on CPU")

            self.is_initialized = True
            self.limited_mode = False
            logger.info("VibeVoice Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize VibeVoice Service: {e}")
            raise

    async def text_to_speech(
        self,
        text: str,
        voice: str = "default",
        language: str = "en",
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        format: str = "wav",
        sample_rate: int = 22050
    ) -> Dict[str, Any]:
        """
        Convert text to speech using Microsoft VibeVoice

        Args:
            text: Text to convert to speech
            voice: Voice profile to use
            language: Language code
            speed: Speech speed multiplier (0.5 to 2.0)
            pitch: Voice pitch multiplier (0.5 to 2.0)
            volume: Volume multiplier (0.1 to 2.0)
            format: Audio format (wav, mp3, flac)
            sample_rate: Output sample rate

        Returns:
            Dictionary with audio data and metadata
        """
        try:
            start_time = time.time()
            logger.info(f"Converting text to speech: {text[:50]}...")

            # Validate input
            if not text or not text.strip():
                raise ValueError("Text cannot be empty")

            if not self.is_initialized:
                raise RuntimeError("VibeVoice service is not initialized")

            if getattr(self, 'limited_mode', False):
                raise RuntimeError("VibeVoice service is running in limited mode - no TTS model available")

            # Preprocess text
            processed_text = self._preprocess_text(text, language)

            # Generate speech
            audio_data = await self._generate_speech(
                processed_text,
                voice,
                language,
                speed,
                pitch,
                sample_rate
            )

            # Apply volume adjustment
            audio_data = self._adjust_volume(audio_data, volume)

            # Convert to requested format
            audio_buffer = self._convert_audio_format(audio_data, sample_rate, format)

            # Calculate duration
            duration = len(audio_data) / sample_rate

            processing_time = time.time() - start_time

            # Encode audio data
            audio_b64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')

            return {
                "audio_data": audio_b64,
                "duration": duration,
                "sample_rate": sample_rate,
                "format": format,
                "voice": voice,
                "language": language,
                "speed": speed,
                "pitch": pitch,
                "volume": volume,
                "processing_time": processing_time,
                "text_length": len(text),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in text-to-speech conversion: {e}")
            raise

    async def synthesize_math_explanation(
        self,
        explanation: str,
        step_by_step: bool = False,
        emphasis_points: List[str] = None,
        voice: str = "educational"
    ) -> Dict[str, Any]:
        """
        Synthesize mathematical explanation with enhanced speech characteristics

        Args:
            explanation: Mathematical explanation to synthesize
            step_by_step: Whether to pause between steps
            emphasis_points: Points to emphasize in speech
            voice: Voice profile optimized for educational content

        Returns:
            Enhanced speech synthesis with mathematical expression handling
        """
        try:
            start_time = time.time()

            # Process mathematical expressions in explanation
            processed_explanation = self._process_math_expressions(explanation)

            # Split into steps if requested
            if step_by_step:
                steps = self._split_into_steps(processed_explanation)
                audio_segments = []

                for i, step in enumerate(steps):
                    # Apply emphasis if this step contains emphasis points
                    speed = 0.9 if emphasis_points and any(point in step.lower() for point in emphasis_points) else 1.0

                    step_audio = await self.text_to_speech(
                        step,
                        voice=voice,
                        language="en",
                        speed=speed,
                        pitch=1.0,
                        volume=1.0
                    )

                    audio_segments.append(step_audio)

                    # Add pause between steps (except last)
                    if i < len(steps) - 1:
                        pause_duration = 0.5
                        pause_audio = self._generate_pause(pause_duration, step_audio["sample_rate"])
                        audio_segments.append(pause_audio)

                # Combine audio segments
                combined_audio = self._combine_audio_segments(audio_segments)
            else:
                # Generate single audio
                combined_audio = await self.text_to_speech(
                    processed_explanation,
                    voice=voice,
                    language="en",
                    speed=1.0,
                    pitch=1.0,
                    volume=1.0
                )

            processing_time = time.time() - start_time

            return {
                **combined_audio,
                "synthesis_type": "math_explanation",
                "step_count": len(steps) if step_by_step else 1,
                "emphasis_applied": len(emphasis_points) > 0 if emphasis_points else False,
                "processing_time": processing_time
            }

        except Exception as e:
            logger.error(f"Error synthesizing math explanation: {e}")
            raise

    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Get list of available voice profiles

        Returns:
            List of available voice profiles with metadata
        """
        try:
            voices = []

            for voice_id, profile in self.voice_profiles.items():
                voices.append({
                    "id": voice_id,
                    "name": profile["name"],
                    "description": profile["description"],
                    "language": profile["language"],
                    "gender": profile["gender"],
                    "age": profile["age"],
                    "style": profile["style"],
                    "best_for": profile.get("best_for", []),
                    "sample_rate": profile.get("sample_rate", 22050)
                })

            return voices

        except Exception as e:
            logger.error(f"Error getting available voices: {e}")
            raise

    async def get_supported_languages(self) -> List[Dict[str, Any]]:
        """
        Get list of supported languages

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
                    "voice_available": lang_info.get("voice_available", True),
                    "quality": lang_info.get("quality", "high")
                })

            return languages

        except Exception as e:
            logger.error(f"Error getting supported languages: {e}")
            raise

    async def optimize_voice(
        self,
        voice_id: str,
        optimization_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Optimize voice profile for specific use cases

        Args:
            voice_id: Voice profile to optimize
            optimization_options: Optimization parameters

        Returns:
            Optimization result
        """
        try:
            if voice_id not in self.voice_profiles:
                raise ValueError(f"Voice profile {voice_id} not found")

            start_time = time.time()

            # Apply voice optimizations
            optimized_profile = self.voice_profiles[voice_id].copy()

            if optimization_options.get("educational_tone", False):
                optimized_profile["style"] = "educational"
                optimized_profile["speaking_rate"] = 0.9

            if optimization_options.get("clarity_focus", False):
                optimized_profile["articulation"] = "enhanced"
                optimized_profile["prosody"] = "clear"

            if optimization_options.get("mathematical_pronunciation", False):
                optimized_profile["specialization"] = "mathematical"

            optimization_time = time.time() - start_time

            return {
                "voice_id": voice_id,
                "optimized": True,
                "optimizations_applied": optimization_options,
                "processing_time": optimization_time,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error optimizing voice: {e}")
            raise

    # Private helper methods
    def _load_voice_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load voice profiles for VibeVoice"""
        return {
            "default": {
                "name": "Default Voice",
                "description": "Balanced natural voice suitable for general use",
                "language": "en",
                "gender": "neutral",
                "age": "adult",
                "style": "natural",
                "best_for": ["general", "education"],
                "sample_rate": 22050,
                "speaking_rate": 1.0
            },
            "educational": {
                "name": "Educational Voice",
                "description": "Clear and articulate voice optimized for educational content",
                "language": "en",
                "gender": "neutral",
                "age": "adult",
                "style": "educational",
                "best_for": ["teaching", "explanations", "mathematical_content"],
                "sample_rate": 22050,
                "speaking_rate": 0.9,
                "articulation": "enhanced"
            },
            "male_enhanced": {
                "name": "Enhanced Male",
                "description": "Natural male voice with warm tone",
                "language": "en",
                "gender": "male",
                "age": "adult",
                "style": "natural",
                "best_for": ["storytelling", "general_explanation"],
                "sample_rate": 24000,
                "speaking_rate": 1.0
            },
            "female_enhanced": {
                "name": "Enhanced Female",
                "description": "Clear female voice with precise articulation",
                "language": "en",
                "gender": "female",
                "age": "adult",
                "style": "clear",
                "best_for": ["detailed_explanations", "technical_content"],
                "sample_rate": 24000,
                "speaking_rate": 0.95
            },
            "child_friendly": {
                "name": "Child Friendly",
                "description": "Friendly voice suitable for younger learners",
                "language": "en",
                "gender": "neutral",
                "age": "child",
                "style": "friendly",
                "best_for": ["basic_math", "simple_explanations"],
                "sample_rate": 22050,
                "speaking_rate": 1.1
            }
        }

    def _load_supported_languages(self) -> Dict[str, Dict[str, Any]]:
        """Load supported languages for VibeVoice"""
        return {
            "en": {
                "name": "English",
                "native_name": "English",
                "voice_available": True,
                "quality": "high"
            },
            "es": {
                "name": "Spanish",
                "native_name": "Español",
                "voice_available": True,
                "quality": "high"
            },
            "fr": {
                "name": "French",
                "native_name": "Français",
                "voice_available": True,
                "quality": "high"
            },
            "de": {
                "name": "German",
                "native_name": "Deutsch",
                "voice_available": True,
                "quality": "medium"
            },
            "zh": {
                "name": "Chinese",
                "native_name": "中文",
                "voice_available": True,
                "quality": "high"
            },
            "ja": {
                "name": "Japanese",
                "native_name": "日本語",
                "voice_available": True,
                "quality": "medium"
            },
            "ko": {
                "name": "Korean",
                "native_name": "한국어",
                "voice_available": True,
                "quality": "medium"
            }
        }

    def _preprocess_text(self, text: str, language: str) -> str:
        """Preprocess text for better TTS quality"""
        try:
            # Clean up text
            text = text.strip()

            # Handle mathematical expressions
            text = self._process_math_expressions(text)

            # Add appropriate pauses for punctuation
            text = self._add_punctuation_pauses(text)

            # Normalize whitespace
            text = ' '.join(text.split())

            return text

        except Exception as e:
            logger.error(f"Error preprocessing text: {e}")
            return text

    def _process_math_expressions(self, text: str) -> str:
        """Process mathematical expressions for better pronunciation"""
        try:
            # Common mathematical expressions and their spoken forms
            math_expressions = {
                "x²": "x squared",
                "x³": "x cubed",
                "x^n": "x to the power of n",
                "√": "square root of",
                "∫": "integral of",
                "∑": "sum of",
                "π": "pi",
                "θ": "theta",
                "α": "alpha",
                "β": "beta",
                "→": "approaches",
                "≈": "approximately equal to",
                "≠": "not equal to",
                "≤": "less than or equal to",
                "≥": "greater than or equal to",
                "°": "degrees"
            }

            processed_text = text
            for symbol, spoken_form in math_expressions.items():
                processed_text = processed_text.replace(symbol, f" {spoken_form} ")

            return processed_text

        except Exception as e:
            logger.error(f"Error processing math expressions: {e}")
            return text

    def _add_punctuation_pauses(self, text: str) -> str:
        """Add pauses for punctuation"""
        try:
            # Add spaces around punctuation for better natural pauses
            text = text.replace(".", " . ")
            text = text.replace(",", " , ")
            text = text.replace("!", " ! ")
            text = text.replace("?", " ? ")
            text = text.replace(":", " : ")
            text = text.replace(";", " ; ")

            return text

        except Exception as e:
            logger.error(f"Error adding punctuation pauses: {e}")
            return text

    async def _generate_speech(
        self,
        text: str,
        voice: str,
        language: str,
        speed: float,
        pitch: float,
        sample_rate: int
    ) -> np.ndarray:
        """Generate speech audio data"""
        try:
            # Get voice profile
            voice_profile = self.voice_profiles.get(voice, self.voice_profiles["default"])

            # Prepare input for model
            inputs = self.processor(
                text=text,
                voice=voice_profile["name"],
                language=language,
                return_tensors="pt"
            )

            # Move to appropriate device
            if self.settings.ai_use_gpu and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Generate speech
            with torch.no_grad():
                speech = self.model.generate(
                    **inputs,
                    speed=speed,
                    pitch=pitch,
                    sample_rate=sample_rate
                )

            # Convert to numpy array
            audio_data = speech.cpu().numpy().squeeze()

            return audio_data

        except Exception as e:
            logger.error(f"Error generating speech: {e}")
            raise

    def _adjust_volume(self, audio_data: np.ndarray, volume: float) -> np.ndarray:
        """Adjust audio volume"""
        try:
            if volume <= 0 or volume > 2.0:
                raise ValueError("Volume must be between 0.1 and 2.0")

            return audio_data * volume

        except Exception as e:
            logger.error(f"Error adjusting volume: {e}")
            return audio_data

    def _convert_audio_format(self, audio_data: np.ndarray, sample_rate: int, format: str) -> io.BytesIO:
        """Convert audio to requested format"""
        try:
            audio_buffer = io.BytesIO()

            if format.lower() == "wav":
                sf.write(audio_buffer, audio_data, sample_rate, format="WAV")
            elif format.lower() == "flac":
                sf.write(audio_buffer, audio_data, sample_rate, format="FLAC")
            else:
                # Default to WAV
                sf.write(audio_buffer, audio_data, sample_rate, format="WAV")

            audio_buffer.seek(0)
            return audio_buffer

        except Exception as e:
            logger.error(f"Error converting audio format: {e}")
            raise

    def _split_into_steps(self, explanation: str) -> List[str]:
        """Split explanation into logical steps"""
        try:
            # Split by common step indicators
            step_indicators = [
                "Step ", "First,", "Then,", "Next,", "Finally,",
                "Firstly,", "Secondly,", "Thirdly,", "Lastly,"
            ]

            steps = []
            current_step = ""

            for line in explanation.split('\n'):
                if any(indicator in line for indicator in step_indicators):
                    if current_step.strip():
                        steps.append(current_step.strip())
                    current_step = line
                else:
                    current_step += " " + line if current_step else line

            if current_step.strip():
                steps.append(current_step.strip())

            return steps if steps else [explanation]

        except Exception as e:
            logger.error(f"Error splitting into steps: {e}")
            return [explanation]

    def _generate_pause(self, duration: float, sample_rate: int) -> Dict[str, Any]:
        """Generate silent audio pause"""
        try:
            samples = int(duration * sample_rate)
            silence = np.zeros(samples, dtype=np.float32)

            audio_buffer = io.BytesIO()
            sf.write(audio_buffer, silence, sample_rate, format="WAV")
            audio_buffer.seek(0)

            audio_b64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')

            return {
                "audio_data": audio_b64,
                "duration": duration,
                "sample_rate": sample_rate,
                "format": "wav",
                "is_pause": True
            }

        except Exception as e:
            logger.error(f"Error generating pause: {e}")
            raise

    def _combine_audio_segments(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine multiple audio segments"""
        try:
            if not segments:
                raise ValueError("No audio segments to combine")

            # Get common sample rate
            sample_rate = segments[0]["sample_rate"]

            # Combine audio data
            combined_audio = np.array([], dtype=np.float32)

            for segment in segments:
                audio_b64 = segment["audio_data"]
                audio_bytes = base64.b64decode(audio_b64)
                audio_buffer = io.BytesIO(audio_bytes)

                audio_data, sr = sf.read(audio_buffer)
                if sr != sample_rate:
                    # Resample if needed (simplified)
                    audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=sample_rate)

                combined_audio = np.concatenate([combined_audio, audio_data])

            # Convert to base64
            audio_buffer = io.BytesIO()
            sf.write(audio_buffer, combined_audio, sample_rate, format="WAV")
            audio_buffer.seek(0)

            audio_b64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')

            total_duration = len(combined_audio) / sample_rate

            return {
                "audio_data": audio_b64,
                "duration": total_duration,
                "sample_rate": sample_rate,
                "format": "wav",
                "combined": True,
                "segment_count": len(segments)
            }

        except Exception as e:
            logger.error(f"Error combining audio segments: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up VibeVoice Service...")

            # Move model to CPU and clear memory
            if self.model and torch.cuda.is_available():
                self.model.cpu()
                torch.cuda.empty_cache()

            self.model = None
            self.processor = None
            self.is_initialized = False

            logger.info("VibeVoice Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during VibeVoice Service cleanup: {e}")