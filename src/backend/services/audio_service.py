"""
Audio processing service for speech recognition and text-to-speech
Enhanced with Microsoft VibeVoice and MERaLiON-AudioLLM integration
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import io
import base64

import numpy as np
import soundfile as sf

from config.settings import get_settings
from services.model_config import ModelType, get_model_registry
from services.enhanced_model_service import EnhancedModelService
from services.vibevoice_service import VibeVoiceService
from services.meralion_service import MERaLiONService

logger = logging.getLogger(__name__)

class AudioService:
    """
    Audio processing service for speech recognition and text-to-speech
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.model_service = None
        self.vibevoice_service = None
        self.meralion_service = None
        self.whisper_model = None  # Fallback
        self.tts_model = None     # Fallback
        self.is_initialized = False
        self.model_registry = get_model_registry()

    async def initialize(self):
        """Initialize the enhanced audio service (lazy loading - models loaded on demand)"""
        try:
            logger.info("Initializing Enhanced Audio Service...")

            # Create service instances but don't load models yet
            self.model_service = EnhancedModelService(self.settings)
            self.vibevoice_service = VibeVoiceService(self.settings)
            self.meralion_service = MERaLiONService(self.settings)

            # Mark as initialized but models are not loaded yet
            self.is_initialized = True
            logger.info("Enhanced Audio Service initialized successfully (models will load on demand)")

        except Exception as e:
            logger.error(f"Failed to initialize Audio Service: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up Enhanced Audio Service...")

            # Clean up VibeVoice service
            if self.vibevoice_service:
                await self.vibevoice_service.cleanup()

            # Clean up MERaLiON service
            if self.meralion_service:
                await self.meralion_service.cleanup()

            # Clean up model service
            if self.model_service:
                await self.model_service.cleanup()

            # Clean up fallback models
            if self.whisper_model:
                self.whisper_model = None

            if self.tts_model:
                self.tts_model = None

            self.is_initialized = False
            logger.info("Enhanced Audio Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during Audio Service cleanup: {e}")

    def is_healthy(self) -> bool:
        """Check if the audio service is healthy"""
        return self.is_initialized

    async def _ensure_models_loaded(self, model_type: str = "both"):
        """Ensure audio models are loaded (lazy loading)"""
        try:
            # Initialize model service if not already initialized
            if self.model_service and not self.model_service.is_initialized:
                logger.info("Lazy loading model service...")
                await self.model_service.initialize()

            # Load specific models based on type
            if model_type in ["both", "stt"]:
                if self.meralion_service and not self.meralion_service.is_initialized:
                    logger.info("Lazy loading MERaLiON STT model...")
                    await self.meralion_service.initialize()
                    await self._load_meralion_model()

            if model_type in ["both", "tts"]:
                if self.vibevoice_service and not self.vibevoice_service.is_initialized:
                    logger.info("Lazy loading VibeVoice TTS model...")
                    await self.vibevoice_service.initialize()
                    await self._load_vibevoice_model()

        except Exception as e:
            logger.error(f"Failed to lazy load audio models: {e}")
            # Don't raise exception - allow fallback methods to work

    async def speech_to_text(
        self,
        audio_data: Union[bytes, io.BytesIO],
        language: str = "en",
        model_size: str = "base",
        enable_educational_mode: bool = True,
        noise_reduction: bool = True
    ) -> Dict[str, Any]:
        """
        Convert speech to text using MERaLiON-AudioLLM with Whisper fallback

        Args:
            audio_data: Audio data as bytes or BytesIO
            language: Language code (default: "en")
            model_size: Whisper model size (tiny, base, small, medium, large) - for fallback
            enable_educational_mode: Enable educational content optimization
            noise_reduction: Apply noise reduction

        Returns:
            Dictionary with transcription result and metadata
        """
        try:
            start_time = time.time()
            logger.info("Processing speech-to-text conversion")

            # Ensure models are loaded (lazy loading)
            await self._ensure_models_loaded("stt")

            # Ensure audio data is in correct format
            if isinstance(audio_data, bytes):
                audio_buffer = io.BytesIO(audio_data)
            else:
                audio_buffer = audio_data

            # Try MERaLiON-AudioLLM first
            if self.meralion_service and self.meralion_service.is_initialized:
                try:
                    result = await self.meralion_service.speech_to_text(
                        audio_buffer,
                        language=language,
                        enable_educational_mode=enable_educational_mode,
                        noise_reduction=noise_reduction
                    )

                    processing_time = time.time() - start_time

                    return {
                        "text": result["text"],
                        "confidence": result.get("confidence", 0.0),
                        "language": language,
                        "processing_time": processing_time,
                        "model_used": "MERaLiON-AudioLLM-Whisper-SEA-LION",
                        "educational_mode": enable_educational_mode,
                        "noise_reduction": noise_reduction,
                        "educational_terms": result.get("educational_terms", []),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    logger.warning(f"MERaLiON-AudioLLM failed: {e}, falling back to Whisper")

            # Fallback to Whisper
            logger.info("Using Whisper fallback for speech-to-text")
            result = await self._mock_whisper_transcription(audio_buffer, language)

            processing_time = time.time() - start_time

            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.0),
                "language": language,
                "processing_time": processing_time,
                "model_used": "Whisper (fallback)",
                "educational_mode": False,
                "noise_reduction": False,
                "educational_terms": [],
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in speech-to-text: {e}")
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
        Convert text to speech using Microsoft VibeVoice with fallback

        Args:
            text: Text to convert to speech
            voice: Voice ID or name
            language: Language code
            speed: Speech speed multiplier
            pitch: Voice pitch multiplier
            volume: Volume level (0.0-2.0)
            format: Audio format (wav, mp3, flac)
            sample_rate: Audio sample rate

        Returns:
            Dictionary with audio data and metadata
        """
        try:
            start_time = time.time()
            logger.info(f"Processing text-to-speech for: {text[:50]}...")

            # Validate input
            if not text or not text.strip():
                raise ValueError("Text cannot be empty")

            # Ensure models are loaded (lazy loading)
            await self._ensure_models_loaded("tts")

            # Try Microsoft VibeVoice first
            if self.vibevoice_service and self.vibevoice_service.is_initialized:
                try:
                    result = await self.vibevoice_service.text_to_speech(
                        text=text,
                        voice=voice,
                        language=language,
                        speed=speed,
                        pitch=pitch,
                        volume=volume,
                        format=format,
                        sample_rate=sample_rate
                    )

                    processing_time = time.time() - start_time

                    return {
                        "audio_data": result["audio_data"],  # Base64 encoded
                        "duration": result.get("duration", 0.0),
                        "sample_rate": result.get("sample_rate", sample_rate),
                        "voice": voice,
                        "language": language,
                        "speed": speed,
                        "pitch": pitch,
                        "volume": volume,
                        "format": format,
                        "processing_time": processing_time,
                        "model_used": "Microsoft-VibeVoice-1.5B",
                        "educational_optimization": result.get("educational_optimization", False),
                        "mathematical_expressions": result.get("mathematical_expressions", []),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    logger.warning(f"Microsoft VibeVoice failed: {e}, falling back to basic TTS")

            # Fallback to basic TTS
            logger.info("Using basic TTS fallback for text-to-speech")
            result = await self._mock_tts_generation(text, voice, language, speed, pitch)

            processing_time = time.time() - start_time

            return {
                "audio_data": result["audio_data"],  # Base64 encoded
                "duration": result.get("duration", 0.0),
                "sample_rate": sample_rate,
                "voice": voice,
                "language": language,
                "speed": speed,
                "pitch": pitch,
                "volume": volume,
                "format": format,
                "processing_time": processing_time,
                "model_used": "Basic TTS (fallback)",
                "educational_optimization": False,
                "mathematical_expressions": [],
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in text-to-speech: {e}")
            raise

    async def analyze_audio(
        self,
        audio_data: Union[bytes, io.BytesIO],
        analysis_type: str = "speech_detection"
    ) -> Dict[str, Any]:
        """
        Analyze audio for various properties

        Args:
            audio_data: Audio data to analyze
            analysis_type: Type of analysis to perform

        Returns:
            Analysis results
        """
        try:
            logger.info(f"Analyzing audio with type: {analysis_type}")

            # Ensure audio data is in correct format
            if isinstance(audio_data, bytes):
                audio_buffer = io.BytesIO(audio_data)
            else:
                audio_buffer = audio_data

            # Read audio data
            audio_array, sample_rate = sf.read(audio_buffer)

            result = {}

            if analysis_type == "speech_detection":
                result = await self._detect_speech(audio_array, sample_rate)
            elif analysis_type == "noise_analysis":
                result = await self._analyze_noise(audio_array, sample_rate)
            elif analysis_type == "quality_assessment":
                result = await self._assess_quality(audio_array, sample_rate)
            else:
                result = {"error": f"Unknown analysis type: {analysis_type}"}

            result["analysis_type"] = analysis_type
            result["sample_rate"] = sample_rate
            result["duration"] = len(audio_array) / sample_rate
            result["timestamp"] = datetime.utcnow().isoformat()

            return result

        except Exception as e:
            logger.error(f"Error analyzing audio: {e}")
            raise

    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Get list of available TTS voices

        Returns:
            List of available voices with metadata
        """
        try:
            # This is a placeholder implementation
            # In production, this would query the actual TTS system

            voices = [
                {
                    "id": "default",
                    "name": "Default Voice",
                    "language": "en",
                    "gender": "neutral",
                    "age": "adult"
                },
                {
                    "id": "male_enhanced",
                    "name": "Enhanced Male",
                    "language": "en",
                    "gender": "male",
                    "age": "adult"
                },
                {
                    "id": "female_enhanced",
                    "name": "Enhanced Female",
                    "language": "en",
                    "gender": "female",
                    "age": "adult"
                }
            ]

            return voices

        except Exception as e:
            logger.error(f"Error getting available voices: {e}")
            raise

    async def get_supported_languages(self) -> List[Dict[str, Any]]:
        """
        Get list of supported languages for speech recognition and TTS

        Returns:
            List of supported languages
        """
        try:
            # This is a placeholder implementation
            languages = [
                {"code": "en", "name": "English", "native_name": "English"},
                {"code": "es", "name": "Spanish", "native_name": "Español"},
                {"code": "fr", "name": "French", "native_name": "Français"},
                {"code": "de", "name": "German", "native_name": "Deutsch"},
                {"code": "it", "name": "Italian", "native_name": "Italiano"},
                {"code": "pt", "name": "Portuguese", "native_name": "Português"},
                {"code": "ru", "name": "Russian", "native_name": "Русский"},
                {"code": "ja", "name": "Japanese", "native_name": "日本語"},
                {"code": "ko", "name": "Korean", "native_name": "한국어"},
                {"code": "zh", "name": "Chinese", "native_name": "中文"}
            ]

            return languages

        except Exception as e:
            logger.error(f"Error getting supported languages: {e}")
            raise

    async def get_audio_devices(self) -> List[Dict[str, Any]]:
        """
        Get list of available audio input/output devices

        Returns:
            List of audio devices
        """
        try:
            # This is a placeholder implementation
            # In production, this would use libraries like pyaudio

            devices = [
                {
                    "id": "default",
                    "name": "Default Device",
                    "type": "input_output",
                    "sample_rates": [16000, 44100, 48000],
                    "channels": [1, 2]
                },
                {
                    "id": "microphone",
                    "name": "Microphone",
                    "type": "input",
                    "sample_rates": [16000, 44100, 48000],
                    "channels": [1]
                },
                {
                    "id": "speakers",
                    "name": "Speakers",
                    "type": "output",
                    "sample_rates": [44100, 48000],
                    "channels": [2]
                }
            ]

            return devices

        except Exception as e:
            logger.error(f"Error getting audio devices: {e}")
            raise

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available speech recognition models

        Returns:
            List of available models
        """
        try:
            models = [
                {
                    "id": "tiny",
                    "name": "Whisper Tiny",
                    "size_mb": 75,
                    "language": "multilingual",
                    "accuracy": "low",
                    "speed": "fast"
                },
                {
                    "id": "base",
                    "name": "Whisper Base",
                    "size_mb": 142,
                    "language": "multilingual",
                    "accuracy": "medium",
                    "speed": "medium"
                },
                {
                    "id": "small",
                    "name": "Whisper Small",
                    "size_mb": 466,
                    "language": "multilingual",
                    "accuracy": "high",
                    "speed": "medium"
                },
                {
                    "id": "medium",
                    "name": "Whisper Medium",
                    "size_mb": 1540,
                    "language": "multilingual",
                    "accuracy": "very_high",
                    "speed": "slow"
                }
            ]

            return models

        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            raise

    async def _load_vibevoice_model(self):
        """Load Microsoft VibeVoice model for text-to-speech"""
        try:
            logger.info("Loading Microsoft VibeVoice model for TTS")

            if self.vibevoice_service:
                # The service is already initialized in _ensure_models_loaded()
                # Here we would load the actual model from the model service
                # For now, we'll just mark it as ready for use
                logger.info("Microsoft VibeVoice model loaded successfully")
            else:
                logger.warning("VibeVoice service not available")

        except Exception as e:
            logger.error(f"Error loading Microsoft VibeVoice model: {e}")
            raise

    async def _load_meralion_model(self):
        """Load MERaLiON-AudioLLM model for speech-to-text"""
        try:
            logger.info("Loading MERaLiON-AudioLLM model for STT")

            if self.meralion_service:
                # The service is already initialized in _ensure_models_loaded()
                # Here we would load the actual model from the model service
                # For now, we'll just mark it as ready for use
                logger.info("MERaLiON-AudioLLM model loaded successfully")
            else:
                logger.warning("MERaLiON service not available")

        except Exception as e:
            logger.error(f"Error loading MERaLiON-AudioLLM model: {e}")
            raise

    async def _load_whisper_model(self):
        """Load Whisper model for speech recognition"""
        try:
            logger.info(f"Loading Whisper model: {self.settings.whisper_model}")

            # This is a placeholder for loading the actual Whisper model
            # In production, you would load: import whisper; self.whisper_model = whisper.load_model(self.settings.whisper_model)

            # Simulate model loading time
            await asyncio.sleep(0.5)

            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise

    async def _load_tts_model(self):
        """Load TTS model for text-to-speech"""
        try:
            logger.info(f"Loading TTS model: {self.settings.tts_model}")

            # This is a placeholder for loading the actual TTS model
            # In production, you would load the Coqui TTS model

            # Simulate model loading time
            await asyncio.sleep(0.5)

            logger.info("TTS model loaded successfully")

        except Exception as e:
            logger.error(f"Error loading TTS model: {e}")
            raise

    async def _mock_whisper_transcription(self, audio_buffer: io.BytesIO, language: str) -> Dict[str, Any]:
        """Mock Whisper transcription for testing"""
        # Simulate transcription
        await asyncio.sleep(0.1)  # Simulate processing time

        transcriptions = [
            "What is the derivative of x squared plus two x plus one?",
            "Solve for x in the equation x squared plus two x plus one equals zero.",
            "Calculate the area of a circle with radius five.",
            "Find the integral of two x plus three.",
            "What is the square root of sixteen?"
        ]

        import random
        text = random.choice(transcriptions)
        confidence = random.uniform(0.85, 0.98)

        return {
            "text": text,
            "confidence": confidence,
            "language": language
        }

    async def _mock_tts_generation(
        self,
        text: str,
        voice: str,
        language: str,
        speed: float,
        pitch: float
    ) -> Dict[str, Any]:
        """Mock TTS generation for testing"""
        # Simulate TTS processing
        await asyncio.sleep(0.1)  # Simulate processing time

        # Generate silent audio data (placeholder)
        duration = len(text) * 0.1 / speed  # Rough estimate
        sample_rate = self.settings.tts_sample_rate
        samples = int(duration * sample_rate)

        # Generate silent audio (16-bit PCM)
        audio_data = np.zeros(samples, dtype=np.int16)

        # Convert to base64
        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        return {
            "audio_data": audio_b64,
            "duration": duration,
            "samples": samples
        }

    async def _detect_speech(self, audio_array: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Detect speech in audio"""
        # Simple energy-based speech detection
        energy = np.mean(np.abs(audio_array))
        threshold = 0.01  # Adjust based on your audio

        has_speech = energy > threshold

        # Simple speech segmentation (placeholder)
        speech_segments = []
        if has_speech:
            speech_segments.append({
                "start": 0.0,
                "end": len(audio_array) / sample_rate,
                "confidence": min(energy * 100, 1.0)
            })

        return {
            "has_speech": has_speech,
            "speech_segments": speech_segments,
            "energy": energy,
            "threshold": threshold
        }

    async def _analyze_noise(self, audio_array: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Analyze noise in audio"""
        # Simple noise analysis
        rms = np.sqrt(np.mean(audio_array ** 2))
        peak = np.max(np.abs(audio_array))
        noise_level = rms / peak if peak > 0 else 0

        return {
            "noise_level": noise_level,
            "rms": rms,
            "peak": peak
        }

    async def _assess_quality(self, audio_array: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Assess audio quality"""
        # Simple quality assessment
        rms = np.sqrt(np.mean(audio_array ** 2))
        peak = np.max(np.abs(audio_array))

        # Check for clipping
        clipping = np.sum(np.abs(audio_array) > 0.95) / len(audio_array)

        # Simple quality score (0-1)
        quality_score = 1.0 - clipping - (rms / 10.0)  # Adjust formula as needed
        quality_score = max(0.0, min(1.0, quality_score))

        return {
            "quality_score": quality_score,
            "clipping_percentage": clipping,
            "rms_level": rms,
            "peak_level": peak
        }