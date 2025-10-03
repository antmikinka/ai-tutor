"""
Audio processing API endpoints
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

from services.audio_service import AudioService

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class SpeechToTextRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    language: str = "en"
    model_size: str = "base"

class SpeechToTextResponse(BaseModel):
    id: str
    text: str
    confidence: float
    language: str
    processing_time: float
    timestamp: str

class TextToSpeechRequest(BaseModel):
    text: str
    voice: str = "default"
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0

class TextToSpeechResponse(BaseModel):
    id: str
    audio_data: str  # Base64 encoded audio
    duration: float
    sample_rate: int
    timestamp: str

class AudioAnalysisRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    analysis_type: str = "speech_detection"

class AudioAnalysisResponse(BaseModel):
    id: str
    has_speech: bool
    speech_segments: List[Dict[str, Any]]
    noise_level: float
    timestamp: str

# Initialize services
audio_service = AudioService()

@router.post("/speech-to-text", response_model=SpeechToTextResponse)
async def speech_to_text(request: SpeechToTextRequest):
    """
    Convert speech to text using Whisper
    """
    try:
        logger.info("Processing speech-to-text request")

        # Convert base64 to audio data
        audio_bytes = base64.b64decode(request.audio_data)
        audio_file = io.BytesIO(audio_bytes)

        # Process speech recognition
        result = await audio_service.speech_to_text(
            audio_file,
            language=request.language,
            model_size=request.model_size
        )

        return SpeechToTextResponse(
            id=str(uuid.uuid4()),
            text=result["text"],
            confidence=result.get("confidence", 0.0),
            language=request.language,
            processing_time=result.get("processing_time", 0.0),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error in speech-to-text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process speech-to-text: {str(e)}")

@router.post("/text-to-speech", response_model=TextToSpeechResponse)
async def text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech using TTS
    """
    try:
        logger.info(f"Processing text-to-speech for text: {request.text[:50]}...")

        # Generate speech
        result = await audio_service.text_to_speech(
            request.text,
            voice=request.voice,
            language=request.language,
            speed=request.speed,
            pitch=request.pitch
        )

        return TextToSpeechResponse(
            id=str(uuid.uuid4()),
            audio_data=result["audio_data"],  # Base64 encoded
            duration=result.get("duration", 0.0),
            sample_rate=result.get("sample_rate", 22050),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process text-to-speech: {str(e)}")

@router.post("/analyze-audio", response_model=AudioAnalysisResponse)
async def analyze_audio(request: AudioAnalysisRequest):
    """
    Analyze audio for speech content and quality
    """
    try:
        logger.info(f"Analyzing audio with type: {request.analysis_type}")

        # Convert base64 to audio data
        audio_bytes = base64.b64decode(request.audio_data)
        audio_file = io.BytesIO(audio_bytes)

        # Analyze audio
        result = await audio_service.analyze_audio(
            audio_file,
            request.analysis_type
        )

        return AudioAnalysisResponse(
            id=str(uuid.uuid4()),
            has_speech=result.get("has_speech", False),
            speech_segments=result.get("speech_segments", []),
            noise_level=result.get("noise_level", 0.0),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error analyzing audio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze audio: {str(e)}")

@router.post("/upload-audio")
async def upload_and_process_audio(
    file: UploadFile = File(...),
    processing_type: str = Form("speech_to_text"),
    language: str = Form("en"),
    voice: str = Form("default")
):
    """
    Upload and process audio file
    """
    try:
        logger.info(f"Processing uploaded audio: {file.filename}")

        # Validate file type
        if not file.content_type.startswith("audio/"):
            raise HTTPException(status_code=400, detail="File must be an audio file")

        # Read file data
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)

        # Process based on type
        if processing_type == "speech_to_text":
            result = await audio_service.speech_to_text(audio_file, language=language)
            return {
                "filename": file.filename,
                "processing_type": processing_type,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        elif processing_type == "analyze":
            result = await audio_service.analyze_audio(audio_file)
            return {
                "filename": file.filename,
                "processing_type": processing_type,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown processing type: {processing_type}")

    except Exception as e:
        logger.error(f"Error processing uploaded audio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process audio file: {str(e)}")

@router.get("/voices")
async def get_available_voices():
    """
    Get list of available TTS voices
    """
    try:
        voices = await audio_service.get_available_voices()
        return {
            "voices": voices,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting available voices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get available voices: {str(e)}")

@router.get("/languages")
async def get_supported_languages():
    """
    Get list of supported languages for speech recognition and TTS
    """
    try:
        languages = await audio_service.get_supported_languages()
        return {
            "languages": languages,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting supported languages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get supported languages: {str(e)}")

@router.get("/audio-devices")
async def get_audio_devices():
    """
    Get list of available audio input/output devices
    """
    try:
        devices = await audio_service.get_audio_devices()
        return {
            "devices": devices,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting audio devices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get audio devices: {str(e)}")

@router.get("/models")
async def get_available_models():
    """
    Get list of available speech recognition models
    """
    try:
        models = await audio_service.get_available_models()
        return {
            "models": models,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get available models: {str(e)}")

@router.post("/stream-speech-to-text")
async def stream_speech_to_text(file: UploadFile = File(...)):
    """
    Stream speech-to-text processing for real-time applications
    """
    try:
        logger.info(f"Streaming speech-to-text for: {file.filename}")

        # This is a placeholder for streaming implementation
        # In production, this would use WebSocket for real-time streaming
        audio_data = await file.read()
        audio_file = io.BytesIO(audio_data)

        result = await audio_service.speech_to_text(audio_file)

        return {
            "filename": file.filename,
            "result": result,
            "streaming": False,  # Placeholder
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in streaming speech-to-text: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stream speech-to-text: {str(e)}")

@router.post("/batch-text-to-speech")
async def batch_text_to_speech(requests: List[TextToSpeechRequest]):
    """
    Process multiple text-to-speech requests in batch
    """
    try:
        logger.info(f"Processing batch of {len(requests)} text-to-speech requests")

        results = []
        for req in requests:
            try:
                result = await audio_service.text_to_speech(
                    req.text,
                    req.voice,
                    req.language,
                    req.speed,
                    req.pitch
                )
                results.append({
                    "request": req.dict(),
                    "result": result,
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"Error processing text-to-speech request: {e}")
                results.append({
                    "request": req.dict(),
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
        logger.error(f"Error in batch text-to-speech: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process batch text-to-speech: {str(e)}")