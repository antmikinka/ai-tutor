"""
System and administrative API endpoints
"""

from __future__ import annotations

import logging
import platform
import shutil
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import ServiceContainer, get_container
from services.common import utc_now_iso
from services.optional_deps import psutil, ml_stack_status

logger = logging.getLogger(__name__)
router = APIRouter()

_PROCESS_STARTED = time.time()
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ServiceStatusResponse(BaseModel):
    services: Dict[str, Dict[str, Any]]
    overall_status: str
    timestamp: str


class ConfigResponse(BaseModel):
    config: Dict[str, Any]
    timestamp: str


class LogResponse(BaseModel):
    logs: List[Dict[str, Any]]
    total_count: int
    log_file: Optional[str]
    timestamp: str


def _memory() -> Dict[str, Any]:
    if psutil is None:
        return {"available": False}
    vm = psutil.virtual_memory()
    return {"available": True, "total": vm.total, "available_bytes": vm.available, "used": vm.used, "percent": vm.percent}


def _disk(path: Path) -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {}
    return {"total": usage.total, "used": usage.used, "free": usage.free, "percent": round(usage.used / usage.total * 100, 2) if usage.total else 0.0}


def _service_states(container: ServiceContainer) -> Dict[str, Dict[str, Any]]:
    ai = container.ai_service
    return {
        "ai_service": {**ai.status(), "description": "Symbolic solver (SymPy) with optional Qwen3-Omni reasoning"},
        "audio_service": {
            "initialized": container.audio_service.is_initialized,
            "healthy": container.audio_service.is_healthy(),
            "stt_available": bool(getattr(container.audio_service, "meralion_service", None)),
            "tts_available": bool(getattr(container.audio_service, "vibevoice_service", None)),
            "description": "Speech recognition and text-to-speech (models load on demand)",
        },
        "drawing_service": {
            "initialized": container.drawing_service.is_initialized,
            "healthy": container.drawing_service.is_healthy(),
            "description": "Canvas analysis and stroke geometry",
        },
        "model_service": {
            "initialized": container.model_service.is_initialized,
            "healthy": container.model_service.is_healthy(),
            "loaded_models": list(getattr(container.model_service, "models", {}).keys()),
            "description": "Model download/load management",
        },
        "websocket": {
            "healthy": True,
            "active_connections": container.websocket_manager.get_connection_count(),
            "clients": container.websocket_manager.get_all_connections(),
        },
    }


@router.get("/status")
async def system_status(container: ServiceContainer = Depends(get_container)):
    """Detailed status used by the desktop UI to decide what to enable."""
    return {
        "status": "running",
        "timestamp": utc_now_iso(),
        "version": container.settings.version,
        "services": _service_states(container),
        "ml_stack": ml_stack_status(),
        "ui_ready": True,
        "architecture": "lazy_loading",
        "uptime_seconds": round(time.time() - _PROCESS_STARTED, 1),
    }


@router.get("/service-status", response_model=ServiceStatusResponse)
async def get_service_status(container: ServiceContainer = Depends(get_container)):
    services = _service_states(container)
    healthy = all(s.get("healthy", True) for s in services.values())
    return ServiceStatusResponse(services=services, overall_status="healthy" if healthy else "degraded", timestamp=utc_now_iso())


@router.get("/system-info")
async def get_system_info(container: ServiceContainer = Depends(get_container)):
    return {
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": sys.version.split()[0],
        "cpu_count": psutil.cpu_count() if psutil else None,
        "cpu_usage": psutil.cpu_percent(interval=None) if psutil else None,
        "memory": _memory(),
        "disk_usage": _disk(container.settings.model_dir),
        "ml_stack": ml_stack_status(),
        "timestamp": utc_now_iso(),
    }


@router.get("/config", response_model=ConfigResponse)
async def get_config(container: ServiceContainer = Depends(get_container)):
    s = container.settings
    safe_config = {
        "app_name": s.app_name,
        "version": s.version,
        "debug": s.debug,
        "environment": s.environment,
        "host": s.host,
        "port": s.port,
        "ai_model_name": s.ai_model_name,
        "ai_temperature": s.ai_temperature,
        "ai_max_tokens": s.ai_max_tokens,
        "ai_use_gpu": s.ai_use_gpu,
        "ai_device": s.ai_device,
        "preload_models": s.preload_models,
        "whisper_model": s.whisper_model,
        "tts_model": s.tts_model,
        "log_level": s.log_level,
        "max_upload_size": s.max_upload_size,
        "max_websocket_message_bytes": s.max_websocket_message_bytes,
        "solver_timeout_seconds": s.solver_timeout_seconds,
        "websocket_ping_interval": s.websocket_ping_interval,
        "model_dir": str(s.model_dir),
    }
    return ConfigResponse(config=safe_config, timestamp=utc_now_iso())


def _parse_log_line(line: str) -> Dict[str, Any]:
    # Format produced by main.configure_logging: "<asctime> <LEVEL> <name>: <message>"
    parts = line.rstrip("\n").split(" ", 3)
    if len(parts) == 4 and parts[2] in _LOG_LEVELS:
        return {"timestamp": f"{parts[0]} {parts[1]}", "level": parts[2], "service": parts[3].split(":", 1)[0], "message": parts[3].split(":", 1)[-1].strip()}
    return {"timestamp": None, "level": "INFO", "service": None, "message": line.rstrip("\n")}


@router.get("/logs", response_model=LogResponse)
async def get_logs(
    limit: int = 100,
    offset: int = 0,
    level: Optional[str] = None,
    service: Optional[str] = None,
    container: ServiceContainer = Depends(get_container),
):
    """Tail the real backend log file."""
    limit = max(1, min(limit, 1000))
    log_path = container.settings.log_path
    if not log_path.exists():
        return LogResponse(logs=[], total_count=0, log_file=str(log_path), timestamp=utc_now_iso())

    # Read only the tail of the file; logs can be large.
    window: deque = deque(maxlen=offset + limit + 5000)
    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            window.append(line)
    entries = [_parse_log_line(line) for line in reversed(window)]
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    if service:
        entries = [e for e in entries if e["service"] and service in e["service"]]
    return LogResponse(logs=entries[offset : offset + limit], total_count=len(entries), log_file=str(log_path), timestamp=utc_now_iso())


@router.get("/health")
async def detailed_health(container: ServiceContainer = Depends(get_container)):
    services = _service_states(container)
    mem = _memory()
    return {
        "status": "healthy" if all(s.get("healthy", True) for s in services.values()) else "degraded",
        "timestamp": utc_now_iso(),
        "services": {name: ("healthy" if s.get("healthy", True) else "unhealthy") for name, s in services.items()},
        "metrics": {
            "memory_usage_percent": mem.get("percent"),
            "cpu_usage_percent": psutil.cpu_percent(interval=None) if psutil else None,
            "uptime_seconds": round(time.time() - _PROCESS_STARTED, 1),
            "active_connections": container.websocket_manager.get_connection_count(),
            "problems_solved": container.ai_service.get_statistics()["total_problems_solved"],
        },
    }


@router.get("/metrics")
async def get_metrics(container: ServiceContainer = Depends(get_container)):
    return {
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=None) if psutil else None,
            "memory": _memory(),
            "disk": _disk(container.settings.model_dir),
        },
        "application": {
            "uptime_seconds": round(time.time() - _PROCESS_STARTED, 1),
            "websocket_connections": container.websocket_manager.get_connection_count(),
            **container.ai_service.get_statistics(),
        },
        "timestamp": utc_now_iso(),
    }


@router.post("/restart-service")
async def restart_service(service_name: str, container: ServiceContainer = Depends(get_container)):
    """Re-initialise one service in place (releases and recreates its resources)."""
    services = {
        "ai_service": container.ai_service,
        "audio_service": container.audio_service,
        "drawing_service": container.drawing_service,
        "model_service": container.model_service,
    }
    service = services.get(service_name)
    if service is None:
        raise HTTPException(status_code=400, detail=f"Invalid service name: {service_name}")
    try:
        await service.cleanup()
        await service.initialize()
    except Exception as exc:
        logger.exception("Restart of %s failed", service_name)
        raise HTTPException(status_code=500, detail=f"Failed to restart {service_name}: {exc}") from exc
    return {"message": f"Service {service_name} restarted", "timestamp": utc_now_iso()}


@router.post("/clear-cache")
async def clear_cache(container: ServiceContainer = Depends(get_container)):
    """Empty the temp and model-cache directories owned by the backend."""
    cleared: List[str] = []
    for cache_dir in (container.settings.temp_dir, container.settings.model_cache_dir):
        cache_dir = Path(cache_dir)
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cleared.append(str(cache_dir))
    return {"message": "Cache cleared", "cleared_directories": cleared, "timestamp": utc_now_iso()}
