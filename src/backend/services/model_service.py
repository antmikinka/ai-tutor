"""
Model management facade.

``ModelService`` is what the API and the other services talk to. It owns:

* the registry of known models (``services.model_config``),
* on-disk discovery (is the model downloaded into ``settings.model_dir``?),
* delegation of actual loading/unloading to ``EnhancedModelService`` when the
  ML stack (torch + transformers) is installed,
* persistence of "auto-load on startup" preferences.

Without the ML stack every model is reported as ``unavailable`` and
``load_model`` raises a clear error. Nothing is ever faked.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from services.common import utc_now_iso
from services.model_config import ModelConfig, ModelInstance, ModelStatus, ModelType, get_model_registry
from services.model_persistence import ModelPersistenceService
from services.optional_deps import HAS_ML_STACK, cuda_available, ml_stack_status, psutil

logger = logging.getLogger(__name__)

# Short aliases used by the UI / API (``/api/models/load/ai``)
MODEL_TYPE_ALIASES: Dict[str, str] = {
    "ai": "Qwen3-Omni-30B-A3B-Thinking",
    "reasoning": "Qwen3-Omni-30B-A3B-Thinking",
    "stt": "MERaLiON-AudioLLM-Whisper-SEA-LION",
    "tts": "Microsoft-VibeVoice-1.5B",
    "whisper": "whisper-large",
    "xtts": "xtts-v2",
}


class ModelNotAvailableError(RuntimeError):
    """The model cannot be loaded on this machine (missing stack or files)."""


class ModelService:
    """Facade over model discovery, loading and persistence."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.registry = get_model_registry()
        self.persistence_service = ModelPersistenceService(self.settings)
        self.is_initialized = False
        self.preferred_device = "cuda" if cuda_available() else "cpu"
        self._backend = None  # EnhancedModelService, created lazily
        self._loading: Dict[str, Dict[str, Any]] = {}
        self._load_tasks: Dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def initialize(self) -> None:
        self.settings.model_dir.mkdir(parents=True, exist_ok=True)
        self.settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
        await self.persistence_service.initialize()
        self.is_initialized = True
        logger.info("Model service ready (ml_stack=%s, device=%s)", HAS_ML_STACK, self.preferred_device)
        await self._auto_load_models()

    async def cleanup(self) -> None:
        for task in list(self._load_tasks.values()):
            task.cancel()
        self._load_tasks.clear()
        if self._backend is not None:
            try:
                await self._backend.cleanup()
            except Exception as exc:
                logger.error("Error cleaning up model backend: %s", exc)
            self._backend = None
        self.is_initialized = False

    def is_healthy(self) -> bool:
        return self.is_initialized

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    @staticmethod
    def resolve_name(name_or_alias: str) -> str:
        return MODEL_TYPE_ALIASES.get(name_or_alias.lower(), name_or_alias)

    def get_config(self, name_or_alias: str) -> Optional[ModelConfig]:
        return self.registry.get_model(self.resolve_name(name_or_alias))

    def model_path(self, config: ModelConfig) -> Path:
        return self.settings.get_model_path(config.name)

    def is_downloaded(self, config: ModelConfig) -> bool:
        path = self.model_path(config)
        if not path.is_dir():
            return False
        # A real download has weights; an empty placeholder folder does not.
        return any(path.rglob("*.safetensors")) or any(path.rglob("*.bin")) or any(path.rglob("*.gguf"))

    def _backend_instance(self, name: str) -> Optional[ModelInstance]:
        if self._backend is None:
            return None
        return self._backend.models.get(name)

    @property
    def models(self) -> Dict[str, ModelInstance]:
        """Loaded model instances keyed by name (empty without the ML stack)."""
        if self._backend is None:
            return {}
        return {n: i for n, i in self._backend.models.items() if i.status == ModelStatus.LOADED}

    def get_loaded_instance(self, model_type: ModelType) -> Optional[ModelInstance]:
        for instance in self.models.values():
            if instance.config.type == model_type:
                return instance
        return None

    def describe(self, config: ModelConfig) -> Dict[str, Any]:
        instance = self._backend_instance(config.name)
        loading = self._loading.get(config.name)
        downloaded = self.is_downloaded(config)

        if instance is not None and instance.status == ModelStatus.LOADED:
            status = "loaded"
        elif loading is not None and loading.get("status") == "loading":
            status = "loading"
        elif loading is not None and loading.get("status") == "error":
            status = "error"
        elif not HAS_ML_STACK:
            status = "unavailable"
        elif downloaded:
            status = "available"
        else:
            status = "not_downloaded"

        return {
            "name": config.name,
            "model_name": config.name,
            "type": config.type.value,
            "model_id": config.model_id,
            "description": config.description,
            "status": status,
            "downloaded": downloaded,
            "path": str(self.model_path(config)),
            "device": instance.device if instance is not None else None,
            "memory_usage": instance.memory_usage_mb if instance is not None else 0.0,
            "loading_progress": (loading or {}).get("progress", 100.0 if status == "loaded" else 0.0),
            "loaded_at": instance.loaded_at if instance is not None else None,
            "error": (loading or {}).get("error") or (instance.error_message if instance is not None else None),
            "requirements": {
                "file_size_gb": config.file_size_gb,
                "memory_required_gb": config.memory_required_gb,
                "gpu_required": config.gpu_required,
            },
        }

    async def list_models(self) -> List[Dict[str, Any]]:
        return [self.describe(cfg) for cfg in self.registry.get_all_models()]

    async def get_model_info(self, name_or_alias: str) -> Dict[str, Any]:
        config = self.get_config(name_or_alias)
        if config is None:
            raise ValueError(f"Unknown model: {name_or_alias}")
        return {**self.describe(config), "timestamp": utc_now_iso()}

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def _ensure_backend(self):
        if self._backend is None:
            if not HAS_ML_STACK:
                raise ModelNotAvailableError(
                    "Loading AI models requires torch and transformers. "
                    "Install the ML requirements (see README) and restart the backend."
                )
            from services.enhanced_model_service import EnhancedModelService

            self._backend = EnhancedModelService(self.settings)
        return self._backend

    async def validate_model_requirements(self, name_or_alias: str) -> Dict[str, Any]:
        config = self.get_config(name_or_alias)
        if config is None:
            raise ValueError(f"Unknown model: {name_or_alias}")
        checks: Dict[str, bool] = {
            "ml_stack_installed": HAS_ML_STACK,
            "downloaded": self.is_downloaded(config),
            "gpu_ok": (not config.gpu_required) or cuda_available(),
        }
        info: Dict[str, Any] = {"gpu_available": cuda_available()}
        if psutil is not None:
            mem = psutil.virtual_memory()
            checks["ram_ok"] = mem.total >= config.memory_required_gb * 1024**3
            info["ram_gb"] = round(mem.total / 1024**3, 2)
        try:
            free = shutil.disk_usage(self.settings.model_dir).free
            checks["disk_ok"] = checks["downloaded"] or free >= config.file_size_gb * 1024**3
            info["disk_free_gb"] = round(free / 1024**3, 2)
        except OSError:
            pass
        return {"model_name": config.name, "valid": all(checks.values()), "checks": checks, "system_info": info, "requirements": self.describe(config)["requirements"]}

    async def load_model(self, name_or_alias: str, options: Optional[Dict[str, Any]] = None, wait: bool = True) -> Dict[str, Any]:
        """
        Load a model. With ``wait=False`` the load runs in the background and
        progress is exposed through ``get_loading_progress``/``describe``.
        """
        config = self.get_config(name_or_alias)
        if config is None:
            raise ValueError(f"Unknown model: {name_or_alias}")
        name = config.name

        instance = self._backend_instance(name)
        if instance is not None and instance.status == ModelStatus.LOADED:
            return {**self.describe(config), "status": "already_loaded", "timestamp": utc_now_iso()}
        if name in self._load_tasks and not self._load_tasks[name].done():
            return {**self.describe(config), "status": "loading", "timestamp": utc_now_iso()}

        backend = self._ensure_backend()  # raises ModelNotAvailableError without ML stack
        if not self.is_downloaded(config):
            raise ModelNotAvailableError(
                f"{name} is not downloaded. Run `python scripts/setup_models.py --model {name}` "
                f"or place the files in {self.model_path(config)}."
            )

        self._loading[name] = {"status": "loading", "progress": 0.0, "started_at": time.time(), "error": None}

        async def _run():
            try:
                self._loading[name]["progress"] = 5.0
                result = await backend.load_model(name, options or {})
                self._loading[name] = {"status": "loaded", "progress": 100.0, "error": None}
                await self.persistence_service.save_model_state(name, {"options": options or {}, "device": result.get("device")})
                logger.info("Model %s loaded", name)
            except Exception as exc:
                logger.error("Loading %s failed: %s", name, exc)
                self._loading[name] = {"status": "error", "progress": 0.0, "error": str(exc)}
                raise

        task = asyncio.create_task(_run())
        self._load_tasks[name] = task
        if wait:
            try:
                await task
            finally:
                self._load_tasks.pop(name, None)
        return {**self.describe(config), "timestamp": utc_now_iso()}

    async def unload_model(self, name_or_alias: str) -> Dict[str, Any]:
        config = self.get_config(name_or_alias)
        if config is None:
            raise ValueError(f"Unknown model: {name_or_alias}")
        name = config.name
        task = self._load_tasks.pop(name, None)
        if task is not None and not task.done():
            task.cancel()
        self._loading.pop(name, None)
        freed = 0.0
        if self._backend is not None and name in self._backend.models:
            result = await self._backend.unload_model(name)
            freed = float(result.get("memory_freed_mb", 0.0))
        await self.persistence_service.remove_model_state(name)
        return {**self.describe(config), "status": "unloaded", "memory_freed": freed, "timestamp": utc_now_iso()}

    async def get_loading_progress(self, name_or_alias: str) -> Dict[str, Any]:
        config = self.get_config(name_or_alias)
        name = config.name if config else name_or_alias
        state = self._loading.get(name)
        if state is None:
            return {"model_name": name, "status": "not_loading", "progress": 0.0, "timestamp": utc_now_iso()}
        return {"model_name": name, **state, "timestamp": utc_now_iso()}

    async def cancel_loading(self, name_or_alias: str) -> Dict[str, Any]:
        config = self.get_config(name_or_alias)
        name = config.name if config else name_or_alias
        task = self._load_tasks.pop(name, None)
        if task is None or task.done():
            return {"model_name": name, "status": "not_loading", "timestamp": utc_now_iso()}
        task.cancel()
        self._loading.pop(name, None)
        return {"model_name": name, "status": "cancelled", "timestamp": utc_now_iso()}

    # ------------------------------------------------------------------ #
    # Resources / persistence
    # ------------------------------------------------------------------ #

    async def get_system_memory_usage(self) -> Dict[str, Any]:
        loaded = self.models
        model_mb = sum(i.memory_usage_mb for i in loaded.values())
        if psutil is None:
            return {"total_gb": None, "available_gb": None, "used_gb": None, "percent_used": None, "models_loaded": len(loaded), "total_model_memory_gb": round(model_mb / 1024, 2)}
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / 1024**3, 2),
            "available_gb": round(mem.available / 1024**3, 2),
            "used_gb": round(mem.used / 1024**3, 2),
            "percent_used": mem.percent,
            "models_loaded": len(loaded),
            "total_model_memory_gb": round(model_mb / 1024, 2),
        }

    def get_system_resources(self) -> Dict[str, Any]:
        gpus: List[Dict[str, Any]] = []
        if cuda_available():
            from services.optional_deps import torch

            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                gpus.append({
                    "device_id": i,
                    "name": props.name,
                    "memory_total_gb": round(props.total_memory / 1024**3, 2),
                    "memory_allocated_gb": round(torch.cuda.memory_allocated(i) / 1024**3, 2),
                })
        cpu = {"percent_used": psutil.cpu_percent(interval=None) if psutil else None, "count": psutil.cpu_count() if psutil else None}
        memory = {}
        if psutil is not None:
            mem = psutil.virtual_memory()
            memory = {"total_gb": round(mem.total / 1024**3, 2), "available_gb": round(mem.available / 1024**3, 2), "used_gb": round(mem.used / 1024**3, 2), "percent_used": mem.percent}
        disk = {}
        try:
            usage = shutil.disk_usage(self.settings.model_dir)
            disk = {"total_gb": round(usage.total / 1024**3, 2), "free_gb": round(usage.free / 1024**3, 2), "used_gb": round(usage.used / 1024**3, 2), "percent_used": round(usage.used / usage.total * 100, 2) if usage.total else 0.0}
        except OSError:
            pass
        return {"cpu": cpu, "memory": memory, "disk": disk, "gpu": gpus, "ml_stack": ml_stack_status(), "timestamp": utc_now_iso()}

    async def get_persistence_info(self) -> Dict[str, Any]:
        return self.persistence_service.get_persistence_info()

    async def restore_model_states(self) -> Dict[str, Any]:
        states = await self.persistence_service.get_all_model_states()
        restored, failed = [], {}
        for name, state_info in states.items():
            try:
                await self.load_model(name, (state_info.get("state") or {}).get("options"))
                restored.append(name)
            except Exception as exc:
                failed[name] = str(exc)
        return {"restored": restored, "failed": failed, "timestamp": utc_now_iso()}

    async def _auto_load_models(self) -> None:
        if not HAS_ML_STACK:
            return
        try:
            config = await self.persistence_service.get_auto_load_config()
            if not config.get("enabled"):
                return
            for name in await self.persistence_service.get_models_to_auto_load():
                try:
                    await self.load_model(name, wait=False)
                except Exception as exc:
                    logger.warning("Auto-load of %s skipped: %s", name, exc)
        except Exception as exc:
            logger.error("Auto-load failed: %s", exc)
