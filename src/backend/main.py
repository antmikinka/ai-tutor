"""
AI Math Tutor Backend Server
FastAPI application with WebSocket support for real-time communication
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import uuid
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import numpy as np

# Add the backend directory to Python path
sys.path.append(str(Path(__file__).parent))

from config.settings import Settings, get_settings
from api.routes import math_api, audio_api, drawing_api, system_api
from api.websocket_manager import WebSocketManager
from services.ai_service import AIService
from services.audio_service import AudioService
from services.drawing_service import DrawingService
from services.model_service import ModelService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Math Tutor Backend",
    description="Backend API for AI Math Tutor desktop application",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings
settings = get_settings()

# Initialize services
ai_service = AIService(settings)
audio_service = AudioService(settings)
drawing_service = DrawingService(settings)
model_service = ModelService(settings)

# Initialize WebSocket manager
websocket_manager = WebSocketManager()

# Include API routers
app.include_router(math_api.router, prefix="/api/math", tags=["Math"])
app.include_router(audio_api.router, prefix="/api/audio", tags=["Audio"])
app.include_router(drawing_api.router, prefix="/api/drawing", tags=["Drawing"])
app.include_router(system_api.router, prefix="/api/system", tags=["System"])

# Serve static files if in production
if settings.environment == "production":
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "ai_service": ai_service.is_healthy(),
            "audio_service": audio_service.is_healthy(),
            "model_service": model_service.is_healthy(),
        }
    }

# System status endpoint
@app.get("/api/system/status")
async def system_status():
    """Get detailed system status and model loading progress"""
    return {
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "ai_service": {
                "initialized": ai_service.is_initialized,
                "healthy": ai_service.is_healthy(),
                "models_loaded": False,  # Models load on demand
                "description": "AI reasoning and math problem solving (lazy loading)"
            },
            "audio_service": {
                "initialized": audio_service.is_initialized,
                "healthy": audio_service.is_healthy(),
                "models_loaded": False,  # Models load on demand
                "description": "Speech recognition and text-to-speech (lazy loading)"
            },
            "model_service": {
                "initialized": model_service.is_initialized,
                "healthy": model_service.is_healthy(),
                "description": "Model management and loading"
            }
        },
        "ui_ready": True,  # UI is always ready now
        "models_loading": False,  # Models load in background or on demand
        "architecture": "lazy_loading",
        "message": "UI is ready. AI models will load automatically when needed."
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "AI Math Tutor Backend",
        "version": "1.0.0",
        "description": "Backend API for AI Math Tutor desktop application",
        "docs_url": "/api/docs",
        "health_check": "/health"
    }

# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time communication"""
    await websocket_manager.connect(websocket, client_id)
    try:
        while True:
            # Receive message from WebSocket
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message["type"] == "drawing":
                await handle_drawing_message(websocket, client_id, message)
            elif message["type"] == "audio":
                await handle_audio_message(websocket, client_id, message)
            elif message["type"] == "math_input":
                await handle_math_message(websocket, client_id, message)
            elif message["type"] == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            else:
                logger.warning(f"Unknown message type: {message['type']}")

    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        websocket_manager.disconnect(client_id)

async def handle_drawing_message(websocket: WebSocket, client_id: str, message: Dict[str, Any]):
    """Handle drawing data from canvas"""
    try:
        # Process drawing data
        processed_data = await drawing_service.process_drawing(message["data"])

        # Analyze drawing for mathematical content
        analysis = await ai_service.analyze_drawing(processed_data)

        # Send analysis result back to client
        response = {
            "type": "drawing_analysis",
            "data": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }

        await websocket.send_text(json.dumps(response))

    except Exception as e:
        logger.error(f"Error processing drawing: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Failed to process drawing",
            "timestamp": datetime.utcnow().isoformat()
        }))

async def handle_audio_message(websocket: WebSocket, client_id: str, message: Dict[str, Any]):
    """Handle audio data for speech recognition"""
    try:
        # Process audio data
        audio_data = message["data"]
        text = await audio_service.speech_to_text(audio_data)

        # Send transcription result back to client
        response = {
            "type": "audio_transcription",
            "text": text,
            "confidence": message.get("confidence", 0.0),
            "timestamp": datetime.utcnow().isoformat()
        }

        await websocket.send_text(json.dumps(response))

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Failed to process audio",
            "timestamp": datetime.utcnow().isoformat()
        }))

async def handle_math_message(websocket: WebSocket, client_id: str, message: Dict[str, Any]):
    """Handle mathematical problem solving"""
    try:
        problem = message["content"]
        metadata = message.get("metadata", {})

        # Get solution from AI service
        solution = await ai_service.solve_math_problem(problem, metadata)

        # Send solution back to client
        response = {
            "type": "math_solution",
            "solution": solution,
            "timestamp": datetime.utcnow().isoformat()
        }

        await websocket.send_text(json.dumps(response))

        # If text-to-speech is enabled, generate audio response
        if metadata.get("enable_tts", True):
            audio_response = await audio_service.text_to_speech(solution["solution"])
            await websocket.send_text(json.dumps({
                "type": "audio_response",
                "data": audio_response,
                "timestamp": datetime.utcnow().isoformat()
            }))

    except Exception as e:
        logger.error(f"Error solving math problem: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Failed to solve math problem",
            "timestamp": datetime.utcnow().isoformat()
        }))

# Startup event - Non-blocking initialization
@app.on_event("startup")
async def startup_event():
    """Initialize basic services without blocking UI"""
    logger.info("Starting AI Math Tutor Backend...")

    try:
        # Initialize basic service structures (non-blocking)
        # Services will load models lazily when needed
        logger.info("Basic service structures initialized")
        logger.info("AI Math Tutor Backend started successfully")
        logger.info("Models will be loaded on-demand when needed")

        # Start background model preloading after a short delay
        asyncio.create_task(_background_model_preloading())

    except Exception as e:
        logger.error(f"Failed to initialize basic services: {e}")
        raise

# Background model preloading
async def _background_model_preloading():
    """Preload models in background after UI is ready"""
    try:
        # Wait for UI to be ready (5 second delay)
        await asyncio.sleep(5)
        logger.info("Starting background model preloading...")

        # Initialize services in background with error handling
        try:
            await model_service.initialize()
            logger.info("Model service initialized (background)")
        except Exception as e:
            logger.error(f"Background model service initialization failed: {e}")

        try:
            await ai_service.initialize()
            logger.info("AI service initialized (background)")
        except Exception as e:
            logger.error(f"Background AI service initialization failed: {e}")

        try:
            await audio_service.initialize()
            logger.info("Audio service initialized (background)")
        except Exception as e:
            logger.error(f"Background audio service initialization failed: {e}")

        logger.info("Background model preloading completed")

    except Exception as e:
        logger.error(f"Background model preloading failed: {e}")

    # Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Math Tutor Backend...")

    try:
        await ai_service.cleanup()
        await audio_service.cleanup()
        await model_service.cleanup()
        logger.info("All services cleaned up successfully")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
        ws_ping_interval=20,
        ws_ping_timeout=10
    )