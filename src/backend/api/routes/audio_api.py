"""
Audio processing API endpoints
"""

from __future__ import annotations

import base64
import binascii
import io
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.dependencies import get_audio_service
from services.audio_service import AudioService
from services.common import utc_now_iso

logger = logging.getLogger(__name__)
router = APIRouter()


class SpeechToTextRequest(BaseModel):
    audio_data: str = Field(min_length=1)
    language: str = "en"
    model_size: str = "base"


class SpeechToTextResponse(BaseModel):
    id: str
    text: str
    confidence: float
    language: str
    available: bool
    message: Optional[str] = None
    model_used: str
    processing_time: float
    timestamp: str


class TextToSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice: str = "default"
    language: str = "en"
    speed: float = Field(1.0, ge=0.25, le=4.0)
    pitch: float = Field(1.0, ge=0.25, le=4.0)


class TextToSpeechResponse(BaseModel):
    id: str
    audio_data: Optional[str]
    duration: float
    sample_rate: int
    available: bool
    message: Optional[str] = None
    model_used: str
    timestamp: str


class AudioAnalysisRequest(BaseModel):
    audio_data: str = Field(min_length=1)
    analysis_type: str = "speech_detection"


def _decode_audio(data: str) -> io.BytesIO:
    try:
        return io.BytesIO(base64.b64decode(data, validate=False))
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="audio_data is not valid base64") from exc


@router.post("/speech-to-text", response_model=SpeechToTextResponse)
async def speech_to_text(request: SpeechToTextRequest, audio: AudioService = Depends(get_audio_service)):
    try:
        result = await audio.speech_to_text(_decode_audio(request.audio_data), language=request.language, model_size=request.model_size)
    except Exception as exc:
        logger.exception("Speech-to-text failed")
        raise HTTPException(status_code=500, detail=f"Failed to process speech-to-text: {exc}") from exc
    return SpeechToTextResponse(
        id=str(uuid.uuid4()),
        text=result.get("text", ""),
        confidence=result.get("confidence", 0.0),
        language=request.language,
        available=result.get("available", False),
        message=result.get("message"),
        model_used=result.get("model_used", "none"),
        processing_time=result.get("processing_time", 0.0),
        timestamp=result.get("timestamp", utc_now_iso()),
    )


@router.post("/text-to-speech", response_model=TextToSpeechResponse)
async def text_to_speech(request: TextToSpeechRequest, audio: AudioService = Depends(get_audio_service)):
    try:
        result = await audio.text_to_speech(request.text, voice=request.voice, language=request.language, speed=request.speed, pitch=request.pitch)
    except Exception as exc:
        logger.exception("Text-to-speech failed")
        raise HTTPException(status_code=500, detail=f"Failed to process text-to-speech: {exc}") from exc
    return TextToSpeechResponse(
        id=str(uuid.uuid4()),
        audio_data=result.get("audio_data"),
        duration=result.get("duration", 0.0),
        sample_rate=result.get("sample_rate", audio.settings.tts_sample_rate),
        available=result.get("available", False),
        message=result.get("message"),
        model_used=result.get("model_used", "none"),
        timestamp=result.get("timestamp", utc_now_iso()),
    )


@router.post("/analyze-audio")
async def analyze_audio(request: AudioAnalysisRequest, audio: AudioService = Depends(get_audio_service)):
    try:
        result = await audio.analyze_audio(_decode_audio(request.audio_data), request.analysis_type)
    except RuntimeError as exc:  # optional dependency missing
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Audio analysis failed")
        raise HTTPException(status_code=500, detail=f"Failed to analyze audio: {exc}") from exc
    return {"id": str(uuid.uuid4()), **result, "timestamp": utc_now_iso()}


@router.post("/upload-audio")
async def upload_and_process_audio(
    file: UploadFile = File(...),
    processing_type: str = Form("speech_to_text"),
    language: str = Form("en"),
    audio: AudioService = Depends(get_audio_service),
):
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    data = await file.read()
    if len(data) > audio.settings.max_upload_size:
        raise HTTPException(status_code=413, detail="Audio exceeds the upload size limit")
    buffer = io.BytesIO(data)
    try:
        if processing_type == "speech_to_text":
            result = await audio.speech_to_text(buffer, language=language)
        elif processing_type == "analyze":
            result = await audio.analyze_audio(buffer)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown processing type: {processing_type}")
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Uploaded audio processing failed")
        raise HTTPException(status_code=500, detail=f"Failed to process audio file: {exc}") from exc
    return {"filename": file.filename, "processing_type": processing_type, "result": result, "timestamp": utc_now_iso()}


@router.get("/voices")
async def get_available_voices(audio: AudioService = Depends(get_audio_service)):
    return {"voices": await audio.get_available_voices(), "timestamp": utc_now_iso()}


@router.get("/languages")
async def get_supported_languages(audio: AudioService = Depends(get_audio_service)):
    return {"languages": await audio.get_supported_languages(), "timestamp": utc_now_iso()}


@router.get("/audio-devices")
async def get_audio_devices(audio: AudioService = Depends(get_audio_service)):
    return {"devices": await audio.get_audio_devices(), "timestamp": utc_now_iso()}


@router.get("/models")
async def get_available_models(audio: AudioService = Depends(get_audio_service)):
    return {"models": await audio.get_available_models(), "timestamp": utc_now_iso()}


@router.post("/batch-text-to-speech")
async def batch_text_to_speech(requests: List[TextToSpeechRequest], audio: AudioService = Depends(get_audio_service)):
    if len(requests) > 20:
        raise HTTPException(status_code=400, detail="At most 20 requests per batch")
    results: List[Dict[str, Any]] = []
    for req in requests:
        try:
            result = await audio.text_to_speech(req.text, req.voice, req.language, req.speed, req.pitch)
            results.append({"request": req.model_dump(), "result": result, "status": "success"})
        except Exception as exc:
            results.append({"request": req.model_dump(), "error": str(exc), "status": "failed"})
    return {
        "results": results,
        "total_requests": len(requests),
        "successful_requests": sum(1 for r in results if r["status"] == "success"),
        "timestamp": utc_now_iso(),
    }
