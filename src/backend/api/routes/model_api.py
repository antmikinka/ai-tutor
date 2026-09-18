"""
Model API endpoints for manual model management (mounted under ``/api``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_model_service
from services.common import utc_now_iso
from services.model_service import MODEL_TYPE_ALIASES, ModelNotAvailableError, ModelService

logger = logging.getLogger(__name__)
router = APIRouter()


class ModelLoadRequest(BaseModel):
    options: Dict[str, Any] = Field(default_factory=dict)
    wait: bool = Field(False, description="Block until the model is loaded instead of loading in the background")


class PersistenceConfigRequest(BaseModel):
    enabled: bool = True
    models: List[str] = Field(default_factory=list)


def _resolve(service: ModelService, name_or_alias: str) -> str:
    config = service.get_config(name_or_alias)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {name_or_alias}")
    return config.name


@router.get("/models")
async def get_all_models(service: ModelService = Depends(get_model_service)):
    return {
        "models": await service.list_models(),
        "system_memory": await service.get_system_memory_usage(),
        "aliases": MODEL_TYPE_ALIASES,
        "timestamp": utc_now_iso(),
    }


@router.get("/models/status")
async def get_models_status(service: ModelService = Depends(get_model_service)):
    return await service.list_models()


@router.get("/models/types")
async def get_model_types(service: ModelService = Depends(get_model_service)):
    return {
        "model_types": {
            alias: service.describe(service.get_config(alias)) for alias in MODEL_TYPE_ALIASES if service.get_config(alias)
        }
    }


@router.get("/models/system/resources")
async def get_system_resources(service: ModelService = Depends(get_model_service)):
    return service.get_system_resources()


@router.get("/models/persistence/info")
async def get_persistence_info(service: ModelService = Depends(get_model_service)):
    return await service.get_persistence_info()


@router.post("/models/persistence/restore")
async def restore_model_states(service: ModelService = Depends(get_model_service)):
    return {"status": "success", **await service.restore_model_states()}


@router.get("/models/persistence/config")
async def get_persistence_config(service: ModelService = Depends(get_model_service)):
    return {"config": await service.persistence_service.get_auto_load_config(), "timestamp": utc_now_iso()}


@router.post("/models/persistence/config")
async def set_persistence_config(request: PersistenceConfigRequest, service: ModelService = Depends(get_model_service)):
    await service.persistence_service.set_auto_load_config(request.enabled, request.models)
    return {"status": "success", "config": request.model_dump(), "timestamp": utc_now_iso()}


@router.get("/models/{model_type}/status")
async def get_model_status(model_type: str, service: ModelService = Depends(get_model_service)):
    return await service.get_model_info(_resolve(service, model_type))


@router.get("/models/{model_type}/requirements")
async def get_model_requirements(model_type: str, service: ModelService = Depends(get_model_service)):
    return await service.validate_model_requirements(_resolve(service, model_type))


@router.get("/models/{model_type}/progress")
async def get_model_progress(model_type: str, service: ModelService = Depends(get_model_service)):
    return await service.get_loading_progress(_resolve(service, model_type))


@router.post("/models/load/{model_type}")
async def load_model(model_type: str, request: Optional[ModelLoadRequest] = None, service: ModelService = Depends(get_model_service)):
    name = _resolve(service, model_type)
    request = request or ModelLoadRequest()
    try:
        result = await service.load_model(name, request.options, wait=request.wait)
    except ModelNotAvailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Loading %s failed", name)
        raise HTTPException(status_code=500, detail=f"Failed to load {name}: {exc}") from exc
    result["message"] = {
        "loaded": "Model loaded",
        "already_loaded": "Model is already loaded",
        "loading": "Model loading started",
        "error": result.get("error") or "Model failed to load",
    }.get(result["status"], result["status"])
    return result


@router.delete("/models/unload/{model_type}")
async def unload_model(model_type: str, service: ModelService = Depends(get_model_service)):
    name = _resolve(service, model_type)
    try:
        return await service.unload_model(name)
    except Exception as exc:
        logger.exception("Unloading %s failed", name)
        raise HTTPException(status_code=500, detail=f"Failed to unload {name}: {exc}") from exc


@router.post("/models/cancel/{model_type}")
async def cancel_loading(model_type: str, service: ModelService = Depends(get_model_service)):
    return await service.cancel_loading(_resolve(service, model_type))
