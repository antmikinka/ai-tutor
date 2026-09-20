"""
Language model source API: choose between the local model and an
OpenAI-compatible provider (OpenRouter, OpenAI, Ollama, LM Studio, custom),
manage the key/model, list available models and test the connection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import ServiceContainer, get_container
from services.ai_service import AIService
from services.llm_client import LLMClientError, PROVIDER_PRESETS
from services.llm_config import RemoteLLMSettings

logger = logging.getLogger(__name__)
router = APIRouter()


class LLMConfigUpdate(BaseModel):
    mode: Optional[Literal["auto", "local", "remote"]] = None
    preset: Optional[str] = Field(default=None, max_length=32)
    base_url: Optional[str] = Field(default=None, max_length=500)
    # ``null`` keeps the stored key; an empty string is ignored; use clear_api_key to remove it.
    api_key: Optional[str] = Field(default=None, max_length=500)
    clear_api_key: bool = False
    model: Optional[str] = Field(default=None, max_length=200)
    timeout_seconds: Optional[float] = Field(default=None, ge=1, le=600)


class LLMTestRequest(LLMConfigUpdate):
    """Same fields; anything omitted falls back to the saved configuration."""


def _ai(container: ServiceContainer = Depends(get_container)) -> AIService:
    return container.ai_service


@router.get("/config")
async def get_llm_config(ai: AIService = Depends(_ai)) -> Dict[str, Any]:
    return ai.llm_status()


@router.put("/config")
async def update_llm_config(update: LLMConfigUpdate, container: ServiceContainer = Depends(get_container)) -> Dict[str, Any]:
    try:
        status = await container.ai_service.apply_llm_config(**update.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await container.broadcast_capabilities()
    return status


@router.delete("/config")
async def reset_llm_config(container: ServiceContainer = Depends(get_container)) -> Dict[str, Any]:
    """Forget the in-app choice and return to the environment / .env defaults."""
    status = await container.ai_service.reset_llm_config()
    await container.broadcast_capabilities()
    return status


@router.get("/presets")
async def list_presets() -> Dict[str, Any]:
    return {"presets": [{"id": pid, **preset} for pid, preset in PROVIDER_PRESETS.items()]}


def _proposed(request: LLMConfigUpdate, saved: RemoteLLMSettings) -> RemoteLLMSettings:
    """Merge unsaved form values over the stored remote settings (never persisted)."""
    preset = request.preset or saved.preset
    if preset not in PROVIDER_PRESETS:
        raise HTTPException(status_code=400, detail=f"unknown provider preset '{preset}'")
    same_preset = preset == saved.preset
    base_url = request.base_url if request.base_url is not None else (saved.base_url if same_preset else PROVIDER_PRESETS[preset]["base_url"])
    model = request.model if request.model is not None else (saved.model if same_preset else PROVIDER_PRESETS[preset]["default_model"])
    if request.clear_api_key:
        api_key = None
    elif request.api_key and request.api_key.strip():
        api_key = request.api_key.strip()
    else:
        api_key = saved.api_key
    return RemoteLLMSettings(
        preset=preset,
        base_url=(base_url or "").strip().rstrip("/"),
        api_key=api_key,
        model=(model or "").strip(),
        timeout_seconds=min(float(request.timeout_seconds or saved.timeout_seconds), 30.0),
    )


@router.get("/models")
async def list_remote_models(refresh: bool = Query(default=False), ai: AIService = Depends(_ai)) -> Dict[str, Any]:
    """Models offered by the *saved* remote provider (cached for ten minutes)."""
    return await _list_models(_proposed(LLMConfigUpdate(), ai.llm_config.config.remote), ai, refresh)


@router.post("/models")
async def list_models_for(request: LLMTestRequest, refresh: bool = Query(default=False), ai: AIService = Depends(_ai)) -> Dict[str, Any]:
    """Models offered by a provider described by unsaved form values (URL / key)."""
    return await _list_models(_proposed(request, ai.llm_config.config.remote), ai, refresh)


async def _list_models(proposed: RemoteLLMSettings, ai: AIService, refresh: bool) -> Dict[str, Any]:
    if not proposed.base_url:
        raise HTTPException(status_code=400, detail="Enter the provider's base URL first.")
    # Reuse the live client (and its cache) when the request describes the saved provider.
    live = ai.remote_llm
    reuse = live is not None and live.base_url == proposed.base_url and live.api_key == proposed.api_key
    client = live if reuse else ai.make_remote_client(RemoteLLMSettings(**{**proposed.__dict__, "model": proposed.model or "-"}))
    try:
        models = await client.list_models(refresh=refresh)
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        if not reuse:
            await client.close()
    return {"provider": proposed.preset, "base_url": proposed.base_url, "count": len(models), "models": models}


@router.post("/test")
async def test_llm(request: LLMTestRequest, ai: AIService = Depends(_ai)) -> Dict[str, Any]:
    """Try a one-token completion with the proposed (unsaved) settings."""
    proposed = _proposed(request, ai.llm_config.config.remote)
    if not proposed.base_url:
        return {"ok": False, "error": "Enter the provider's base URL.", "model": proposed.model, "provider": proposed.preset, "latency_ms": 0}
    if not proposed.model:
        return {"ok": False, "error": "Choose a model first.", "model": "", "provider": proposed.preset, "latency_ms": 0}
    client = ai.make_remote_client(proposed)
    try:
        return await client.test()
    finally:
        await client.close()
