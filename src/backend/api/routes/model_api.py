"""
Model API endpoints for manual model management
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from services.model_service import ModelService
from services.model_config import get_model_config

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class ModelLoadRequest(BaseModel):
    model_type: str = Field(..., description="Type of model to load")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Loading options")

class ModelStatusResponse(BaseModel):
    model_name: str
    status: str
    device: Optional[str] = None
    memory_usage: float = 0.0
    loading_progress: float = 0.0
    loaded_at: Optional[str] = None
    error: Optional[str] = None
    timestamp: str

class ModelListResponse(BaseModel):
    models: List[ModelStatusResponse]
    system_memory: Dict[str, Any]
    timestamp: str

class ModelLoadResponse(BaseModel):
    model_name: str
    status: str
    message: str
    loading_progress: float = 0.0
    estimated_time: Optional[float] = None
    timestamp: str

class ModelUnloadResponse(BaseModel):
    model_name: str
    status: str
    message: str
    memory_freed: float = 0.0
    timestamp: str

# Model type mappings
MODEL_TYPES = {
    "ai": {
        "name": "Qwen3-Omni-30B-A3B-Thinking",
        "description": "AI Math Tutor Model",
        "estimated_size_mb": 15000,
        "loading_time_estimate": 120
    },
    "tts": {
        "name": "VibeVoice",
        "description": "Text-to-Speech Model",
        "estimated_size_mb": 2000,
        "loading_time_estimate": 30
    },
    "stt": {
        "name": "MERaLiON",
        "description": "Speech-to-Text Model",
        "estimated_size_mb": 1500,
        "loading_time_estimate": 25
    },
    "whisper": {
        "name": "Whisper",
        "description": "OpenAI Whisper Model",
        "estimated_size_mb": 750,
        "loading_time_estimate": 15
    },
    "xtts": {
        "name": "XTTS-v2",
        "description": "Coqui XTTS Model",
        "estimated_size_mb": 500,
        "loading_time_estimate": 10
    }
}

# Global model service instance
model_service: Optional[ModelService] = None
loading_status: Dict[str, Dict[str, Any]] = {}

def init_model_service(service: ModelService):
    """Initialize the model service"""
    global model_service
    model_service = service

@router.get("/models", response_model=ModelListResponse)
async def get_all_models():
    """Get status of all models"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        # Get model list from service
        models_data = await model_service.list_models()

        # Enhance with loading status
        models = []
        for model_data in models_data:
            model_name = model_data["name"]
            status_info = loading_status.get(model_name, {})

            model_response = ModelStatusResponse(
                model_name=model_name,
                status=status_info.get("status", model_data["status"]),
                device=model_data.get("device"),
                memory_usage=model_data.get("memory_usage", 0),
                loading_progress=status_info.get("loading_progress", 0.0),
                loaded_at=model_data.get("loaded_at"),
                error=status_info.get("error"),
                timestamp=datetime.utcnow().isoformat()
            )
            models.append(model_response)

        # Get system memory info
        system_memory = await _get_system_memory_info()

        return ModelListResponse(
            models=models,
            system_memory=system_memory,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting model list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/status", response_model=List[ModelStatusResponse])
async def get_models_status():
    """Get current status of all models"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        models = []
        for model_name, status_info in loading_status.items():
            model_response = ModelStatusResponse(
                model_name=model_name,
                status=status_info.get("status", "unknown"),
                device=status_info.get("device"),
                memory_usage=status_info.get("memory_usage", 0),
                loading_progress=status_info.get("loading_progress", 0.0),
                loaded_at=status_info.get("loaded_at"),
                error=status_info.get("error"),
                timestamp=datetime.utcnow().isoformat()
            )
            models.append(model_response)

        return models

    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/{model_type}/status", response_model=ModelStatusResponse)
async def get_model_status(model_type: str):
    """Get status of a specific model"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        if model_type not in MODEL_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid model type: {model_type}")

        model_name = MODEL_TYPES[model_type]["name"]
        status_info = loading_status.get(model_name, {})

        # Check if model is loaded in service
        try:
            model_info = await model_service.get_model_info(model_name)
            status_info.update({
                "status": "loaded",
                "device": model_info["device"],
                "memory_usage": model_info["memory_usage"],
                "loaded_at": model_info["loaded_at"]
            })
        except ValueError:
            if "status" not in status_info:
                status_info["status"] = "not_loaded"

        return ModelStatusResponse(
            model_name=model_name,
            status=status_info.get("status", "unknown"),
            device=status_info.get("device"),
            memory_usage=status_info.get("memory_usage", 0),
            loading_progress=status_info.get("loading_progress", 0.0),
            loaded_at=status_info.get("loaded_at"),
            error=status_info.get("error"),
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model status for {model_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/load/{model_type}", response_model=ModelLoadResponse)
async def load_model(model_type: str, request: ModelLoadRequest, background_tasks: BackgroundTasks):
    """Load a specific model"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        if model_type not in MODEL_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid model type: {model_type}")

        model_name = MODEL_TYPES[model_type]["name"]

        # Check if already loading
        if loading_status.get(model_name, {}).get("status") == "loading":
            return ModelLoadResponse(
                model_name=model_name,
                status="loading",
                message="Model is already being loaded",
                loading_progress=loading_status[model_name].get("loading_progress", 0.0),
                timestamp=datetime.utcnow().isoformat()
            )

        # Check if already loaded
        try:
            await model_service.get_model_info(model_name)
            return ModelLoadResponse(
                model_name=model_name,
                status="already_loaded",
                message="Model is already loaded",
                timestamp=datetime.utcnow().isoformat()
            )
        except ValueError:
            pass  # Model not loaded, continue

        # Start loading process
        loading_status[model_name] = {
            "status": "loading",
            "loading_progress": 0.0,
            "start_time": datetime.utcnow().isoformat(),
            "estimated_time": MODEL_TYPES[model_type]["loading_time_estimate"],
            "error": None
        }

        # Start background loading task
        background_tasks.add_task(_load_model_background, model_type, model_name, request.options)

        return ModelLoadResponse(
            model_name=model_name,
            status="loading",
            message="Model loading started",
            loading_progress=0.0,
            estimated_time=MODEL_TYPES[model_type]["loading_time_estimate"],
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting model load for {model_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/models/unload/{model_type}", response_model=ModelUnloadResponse)
async def unload_model(model_type: str):
    """Unload a specific model"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        if model_type not in MODEL_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid model type: {model_type}")

        model_name = MODEL_TYPES[model_type]["name"]

        # Get memory info before unloading
        memory_before = 0
        try:
            model_info = await model_service.get_model_info(model_name)
            memory_before = model_info.get("memory_usage", 0)
        except ValueError:
            return ModelUnloadResponse(
                model_name=model_name,
                status="not_loaded",
                message="Model is not loaded",
                timestamp=datetime.utcnow().isoformat()
            )

        # Unload model
        result = await model_service.unload_model(model_name)

        # Update loading status
        if model_name in loading_status:
            del loading_status[model_name]

        return ModelUnloadResponse(
            model_name=model_name,
            status="unloaded",
            message="Model unloaded successfully",
            memory_freed=result.get("memory_freed", memory_before),
            timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unloading model {model_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/types")
async def get_model_types():
    """Get available model types"""
    return {
        "model_types": {
            model_type: {
                "name": info["name"],
                "description": info["description"],
                "estimated_size_mb": info["estimated_size_mb"],
                "loading_time_estimate": info["loading_time_estimate"]
            }
            for model_type, info in MODEL_TYPES.items()
        }
    }

@router.get("/models/system/resources")
async def get_system_resources():
    """Get system resource information"""
    try:
        return await _get_system_resources_info()
    except Exception as e:
        logger.error(f"Error getting system resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/persistence/info")
async def get_persistence_info():
    """Get model persistence information"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        return await model_service.get_persistence_info()

    except Exception as e:
        logger.error(f"Error getting persistence info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/persistence/restore")
async def restore_model_states():
    """Restore model states from persistence"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        await model_service.restore_model_states()

        return {
            "status": "success",
            "message": "Model states restored successfully",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error restoring model states: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/persistence/config")
async def set_persistence_config(request: Dict[str, Any]):
    """Set persistence configuration"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        enabled = request.get("enabled", True)
        models = request.get("models", [])

        await model_service.persistence_service.set_auto_load_config(enabled, models)

        return {
            "status": "success",
            "message": "Persistence configuration updated",
            "config": {"enabled": enabled, "models": models},
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error setting persistence config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/persistence/config")
async def get_persistence_config():
    """Get persistence configuration"""
    try:
        if not model_service:
            raise HTTPException(status_code=500, detail="Model service not initialized")

        config = await model_service.persistence_service.get_auto_load_config()

        return {
            "config": config,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting persistence config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task for model loading
async def _load_model_background(model_type: str, model_name: str, options: Dict[str, Any]):
    """Background task to load model with progress updates"""
    try:
        logger.info(f"Starting background load for model: {model_name}")

        # Simulate loading progress
        total_steps = 10
        for step in range(total_steps + 1):
            progress = (step / total_steps) * 100

            # Update loading status
            if model_name in loading_status:
                loading_status[model_name]["loading_progress"] = progress

                # Simulate different loading stages
                if step == 2:
                    loading_status[model_name]["status"] = "downloading"
                elif step == 5:
                    loading_status[model_name]["status"] = "initializing"
                elif step == 8:
                    loading_status[model_name]["status"] = "finalizing"

            # Simulate loading time
            await asyncio.sleep(MODEL_TYPES[model_type]["loading_time_estimate"] / total_steps)

        # Actually load the model
        result = await model_service.load_model(model_name, options=options)

        # Update final status
        loading_status[model_name] = {
            "status": "loaded",
            "loading_progress": 100.0,
            "device": result.get("device", "cpu"),
            "memory_usage": result.get("memory_usage", 0),
            "loaded_at": result.get("timestamp"),
            "loading_time": result.get("loading_time", 0),
            "error": None
        }

        logger.info(f"Model {model_name} loaded successfully")

    except Exception as e:
        logger.error(f"Error loading model {model_name}: {e}")

        # Update status with error
        loading_status[model_name] = {
            "status": "error",
            "loading_progress": 0.0,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Helper functions
async def _get_system_memory_info() -> Dict[str, Any]:
    """Get system memory information"""
    try:
        import psutil

        memory = psutil.virtual_memory()
        return {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent_used": memory.percent,
            "model_memory_used": sum(
                status.get("memory_usage", 0)
                for status in loading_status.values()
                if status.get("status") == "loaded"
            )
        }
    except ImportError:
        return {
            "total_gb": 0,
            "available_gb": 0,
            "used_gb": 0,
            "percent_used": 0,
            "model_memory_used": 0
        }

async def _get_system_resources_info() -> Dict[str, Any]:
    """Get detailed system resource information"""
    try:
        import psutil

        # CPU info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # Memory info
        memory = psutil.virtual_memory()

        # Disk info
        disk = psutil.disk_usage('/')

        # GPU info (if available)
        gpu_info = []
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    gpu_info.append({
                        "device_id": i,
                        "name": torch.cuda.get_device_name(i),
                        "memory_total_gb": round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 2),
                        "memory_allocated_gb": round(torch.cuda.memory_allocated(i) / (1024**3), 2),
                        "memory_cached_gb": round(torch.cuda.memory_reserved(i) / (1024**3), 2)
                    })
        except ImportError:
            pass

        return {
            "cpu": {
                "percent_used": cpu_percent,
                "count": cpu_count,
                "count_logical": psutil.cpu_count(logical=True)
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent_used": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent_used": disk.percent
            },
            "gpu": gpu_info,
            "timestamp": datetime.utcnow().isoformat()
        }

    except ImportError:
        return {
            "cpu": {"percent_used": 0, "count": 0, "count_logical": 0},
            "memory": {"total_gb": 0, "available_gb": 0, "used_gb": 0, "percent_used": 0},
            "disk": {"total_gb": 0, "free_gb": 0, "used_gb": 0, "percent_used": 0},
            "gpu": [],
            "timestamp": datetime.utcnow().isoformat()
        }