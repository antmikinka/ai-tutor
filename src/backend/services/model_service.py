"""
Model management service for AI models
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import os
from pathlib import Path
import threading
from dataclasses import dataclass, asdict

import torch
from config.settings import get_settings
from services.model_persistence import ModelPersistenceService

logger = logging.getLogger(__name__)

@dataclass
class ModelMetadata:
    """Metadata for loaded models"""
    name: str
    model_type: str
    version: str
    size_mb: float
    device: str
    loaded_at: str
    loading_time: float
    options: Dict[str, Any]
    is_optimized: bool = False
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

class ModelService:
    """
    Enhanced model management service for loading and managing AI models with manual controls
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.models = {}
        self.model_info = {}
        self.model_metadata = {}
        self.loading_locks = {}
        self.loading_progress = {}
        self.is_initialized = False
        self.auto_load_enabled = True
        self.preferred_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.persistence_service = ModelPersistenceService(settings)

    async def initialize(self):
        """Initialize the model service"""
        try:
            logger.info("Initializing Model Service...")

            # Create model directories if they don't exist
            self.settings.model_dir.mkdir(parents=True, exist_ok=True)
            self.settings.model_cache_dir.mkdir(parents=True, exist_ok=True)

            # Initialize persistence service
            await self.persistence_service.initialize()

            # Check for available models
            await self._scan_models()

            # Auto-load models if enabled
            await self._auto_load_models()

            self.is_initialized = True
            logger.info("Model Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Model Service: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up Model Service...")

            # Unload all models
            for model_name in list(self.models.keys()):
                await self.unload_model(model_name)

            self.is_initialized = False
            logger.info("Model Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during Model Service cleanup: {e}")

    def is_healthy(self) -> bool:
        """Check if the model service is healthy"""
        return self.is_initialized

    async def load_model(
        self,
        model_name: str,
        model_path: Optional[str] = None,
        options: Dict[str, Any] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Load a model into memory

        Args:
            model_name: Name of the model to load
            model_path: Path to model files (optional)
            options: Loading options
            progress_callback: Optional callback for progress updates

        Returns:
            Loading result with model information
        """
        try:
            logger.info(f"Loading model: {model_name}")

            if options is None:
                options = {}

            # Check if model is already loaded
            if model_name in self.models:
                logger.warning(f"Model {model_name} is already loaded")
                return {
                    "model_name": model_name,
                    "status": "already_loaded",
                    "device": str(next(self.models[model_name].parameters()).device),
                    "memory_usage": self._get_model_memory_usage(model_name),
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Check if model is currently being loaded
            if model_name in self.loading_locks:
                logger.warning(f"Model {model_name} is currently being loaded")
                return {
                    "model_name": model_name,
                    "status": "loading",
                    "progress": self.loading_progress.get(model_name, 0),
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Create loading lock
            self.loading_locks[model_name] = threading.Lock()
            self.loading_progress[model_name] = 0

            # Determine model path
            if model_path is None:
                model_path = self.settings.get_model_path(model_name)

            # Check if model files exist
            model_path = Path(model_path)
            if not model_path.exists():
                logger.error(f"Model path does not exist: {model_path}")
                raise FileNotFoundError(f"Model files not found: {model_path}")

            # Load the model with progress tracking
            start_time = time.time()
            model = await self._load_model_files_with_progress(
                model_name, model_path, options, progress_callback
            )
            loading_time = time.time() - start_time

            # Store model
            self.models[model_name] = model
            self.model_info[model_name] = {
                "path": str(model_path),
                "loaded_at": datetime.utcnow().isoformat(),
                "loading_time": loading_time,
                "options": options,
                "device": str(next(model.parameters()).device) if hasattr(model, 'parameters') else "cpu"
            }

            # Create metadata
            self.model_metadata[model_name] = ModelMetadata(
                name=model_name,
                model_type=options.get("model_type", "unknown"),
                version=options.get("version", "1.0.0"),
                size_mb=self._get_model_memory_usage(model_name),
                device=self.model_info[model_name]["device"],
                loaded_at=datetime.utcnow().isoformat(),
                loading_time=loading_time,
                options=options
            )

            # Clean up loading state
            if model_name in self.loading_locks:
                del self.loading_locks[model_name]
            if model_name in self.loading_progress:
                del self.loading_progress[model_name]

            # Save model state to persistence
            await self.persistence_service.save_model_state(model_name, {
                "device": self.model_info[model_name]["device"],
                "memory_usage": self._get_model_memory_usage(model_name),
                "loaded_at": datetime.utcnow().isoformat(),
                "loading_time": loading_time,
                "options": options
            })

            logger.info(f"Model {model_name} loaded successfully in {loading_time:.2f}s")

            return {
                "model_name": model_name,
                "status": "loaded",
                "device": self.model_info[model_name]["device"],
                "memory_usage": self._get_model_memory_usage(model_name),
                "loading_time": loading_time,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            # Clean up loading state on error
            if model_name in self.loading_locks:
                del self.loading_locks[model_name]
            if model_name in self.loading_progress:
                del self.loading_progress[model_name]

            logger.error(f"Error loading model {model_name}: {e}")
            raise

    async def load_model_by_type(
        self,
        model_type: str,
        options: Dict[str, Any] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Load a model by its type (ai, tts, stt, etc.)

        Args:
            model_type: Type of model to load
            options: Loading options
            progress_callback: Optional callback for progress updates

        Returns:
            Loading result with model information
        """
        model_mapping = {
            "ai": "Qwen3-Omni-30B-A3B-Thinking",
            "tts": "VibeVoice",
            "stt": "MERaLiON",
            "whisper": "whisper-base",
            "xtts": "xtts-v2"
        }

        if model_type not in model_mapping:
            raise ValueError(f"Unknown model type: {model_type}")

        model_name = model_mapping[model_type]

        # Add model type to options
        if options is None:
            options = {}
        options["model_type"] = model_type

        return await self.load_model(model_name, None, options, progress_callback)

    async def get_loading_progress(self, model_name: str) -> Dict[str, Any]:
        """
        Get loading progress for a model

        Args:
            model_name: Name of the model

        Returns:
            Progress information
        """
        if model_name not in self.loading_progress:
            return {
                "model_name": model_name,
                "status": "not_loading",
                "progress": 0,
                "timestamp": datetime.utcnow().isoformat()
            }

        return {
            "model_name": model_name,
            "status": "loading",
            "progress": self.loading_progress[model_name],
            "timestamp": datetime.utcnow().isoformat()
        }

    async def cancel_loading(self, model_name: str) -> Dict[str, Any]:
        """
        Cancel model loading

        Args:
            model_name: Name of the model

        Returns:
            Cancellation result
        """
        if model_name not in self.loading_locks:
            return {
                "model_name": model_name,
                "status": "not_loading",
                "message": "Model is not being loaded",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Remove loading locks and progress
        if model_name in self.loading_locks:
            del self.loading_locks[model_name]
        if model_name in self.loading_progress:
            del self.loading_progress[model_name]

        return {
            "model_name": model_name,
            "status": "cancelled",
            "message": "Model loading cancelled",
            "timestamp": datetime.utcnow().isoformat()
        }

    async def get_system_memory_usage(self) -> Dict[str, Any]:
        """
        Get current system memory usage

        Returns:
            System memory information
        """
        try:
            import psutil

            memory = psutil.virtual_memory()
            return {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent_used": memory.percent,
                "models_loaded": len(self.models),
                "total_model_memory_gb": round(
                    sum(self._get_model_memory_usage(name) for name in self.models) / 1024, 2
                )
            }
        except ImportError:
            return {
                "total_gb": 0,
                "available_gb": 0,
                "used_gb": 0,
                "percent_used": 0,
                "models_loaded": len(self.models),
                "total_model_memory_gb": 0
            }

    async def set_auto_load(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable auto-loading of models

        Args:
            enabled: Whether to enable auto-loading

        Returns:
            Configuration result
        """
        self.auto_load_enabled = enabled
        logger.info(f"Auto-load {'enabled' if enabled else 'disabled'}")

        return {
            "auto_load_enabled": enabled,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def get_model_dependencies(self, model_name: str) -> List[str]:
        """
        Get dependencies for a model

        Args:
            model_name: Name of the model

        Returns:
            List of dependencies
        """
        dependencies = {
            "Qwen3-Omni-30B-A3B-Thinking": ["torch", "transformers", "accelerate"],
            "VibeVoice": ["torch", "torchaudio", "soundfile"],
            "MERaLiON": ["torch", "transformers", "datasets"],
            "whisper-base": ["torch", "openai-whisper"],
            "xtts-v2": ["torch", "torchaudio", "xtts"]
        }

        return dependencies.get(model_name, [])

    async def validate_model_requirements(self, model_name: str) -> Dict[str, Any]:
        """
        Validate system requirements for a model

        Args:
            model_name: Name of the model

        Returns:
            Validation result
        """
        try:
            # Get model requirements
            requirements = {
                "Qwen3-Omni-30B-A3B-Thinking": {"min_ram_gb": 16, "min_disk_gb": 20, "requires_gpu": True},
                "VibeVoice": {"min_ram_gb": 4, "min_disk_gb": 3, "requires_gpu": False},
                "MERaLiON": {"min_ram_gb": 8, "min_disk_gb": 2, "requires_gpu": False},
                "whisper-base": {"min_ram_gb": 2, "min_disk_gb": 1, "requires_gpu": False},
                "xtts-v2": {"min_ram_gb": 4, "min_disk_gb": 1, "requires_gpu": False}
            }

            if model_name not in requirements:
                return {
                    "model_name": model_name,
                    "valid": False,
                    "error": "Unknown model requirements",
                    "timestamp": datetime.utcnow().isoformat()
                }

            req = requirements[model_name]

            # Check system requirements
            import psutil
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            ram_ok = memory.total >= req["min_ram_gb"] * (1024**3)
            disk_ok = disk.free >= req["min_disk_gb"] * (1024**3)
            gpu_ok = not req["requires_gpu"] or torch.cuda.is_available()

            return {
                "model_name": model_name,
                "valid": ram_ok and disk_ok and gpu_ok,
                "requirements": req,
                "system_info": {
                    "ram_gb": round(memory.total / (1024**3), 2),
                    "disk_free_gb": round(disk.free / (1024**3), 2),
                    "gpu_available": torch.cuda.is_available()
                },
                "checks": {
                    "ram_ok": ram_ok,
                    "disk_ok": disk_ok,
                    "gpu_ok": gpu_ok
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "model_name": model_name,
                "valid": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def unload_model(self, model_name: str) -> Dict[str, Any]:
        """
        Unload a model from memory

        Args:
            model_name: Name of the model to unload

        Returns:
            Unloading result
        """
        try:
            logger.info(f"Unloading model: {model_name}")

            if model_name not in self.models:
                logger.warning(f"Model {model_name} is not loaded")
                return {
                    "model_name": model_name,
                    "status": "not_loaded",
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Get memory info before unloading
            memory_before = self._get_model_memory_usage(model_name)

            # Remove model from memory
            del self.models[model_name]
            model_info = self.model_info.pop(model_name, {})
            self.model_metadata.pop(model_name, {})

            # Remove from persistence
            await self.persistence_service.remove_model_state(model_name)

            # Force garbage collection
            import gc
            gc.collect()

            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"Model {model_name} unloaded successfully")

            return {
                "model_name": model_name,
                "status": "unloaded",
                "memory_freed": memory_before,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error unloading model {model_name}: {e}")
            raise

    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """
        Get information about a loaded model

        Args:
            model_name: Name of the model

        Returns:
            Model information
        """
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} is not loaded")

            model = self.models[model_name]
            info = self.model_info[model_name]

            # Get additional model information
            model_details = {}

            if hasattr(model, 'config'):
                model_details["config"] = model.config

            if hasattr(model, 'num_parameters'):
                model_details["num_parameters"] = model.num_parameters()

            if hasattr(model, 'dtype'):
                model_details["dtype"] = str(model.dtype)

            return {
                "model_name": model_name,
                "is_loaded": True,
                "device": info["device"],
                "memory_usage": self._get_model_memory_usage(model_name),
                "loaded_at": info["loaded_at"],
                "loading_time": info["loading_time"],
                "options": info["options"],
                "details": model_details,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting model info for {model_name}: {e}")
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available and loaded models

        Returns:
            List of model information
        """
        try:
            models = []

            # List loaded models
            for model_name, model in self.models.items():
                info = self.model_info[model_name]
                models.append({
                    "name": model_name,
                    "status": "loaded",
                    "device": info["device"],
                    "memory_usage": self._get_model_memory_usage(model_name),
                    "loaded_at": info["loaded_at"]
                })

            # List available but unloaded models
            available_models = await self._scan_available_models()
            for model_name in available_models:
                if model_name not in self.models:
                    models.append({
                        "name": model_name,
                        "status": "available",
                        "device": None,
                        "memory_usage": 0,
                        "loaded_at": None
                    })

            return models

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            raise

    async def optimize_model(self, model_name: str, optimization_options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a loaded model

        Args:
            model_name: Name of the model to optimize
            optimization_options: Optimization options

        Returns:
            Optimization result
        """
        try:
            logger.info(f"Optimizing model: {model_name}")

            if model_name not in self.models:
                raise ValueError(f"Model {model_name} is not loaded")

            model = self.models[model_name]

            # Apply optimizations (placeholder implementation)
            start_time = time.time()

            if optimization_options.get("quantization", False):
                # Apply quantization
                model = await self._quantize_model(model, optimization_options.get("quantization_bits", 8))

            if optimization_options.get("pruning", False):
                # Apply pruning
                model = await self._prune_model(model, optimization_options.get("pruning_ratio", 0.5))

            if optimization_options.get("half_precision", False):
                # Convert to half precision
                model = await self._convert_to_half_precision(model)

            optimization_time = time.time() - start_time

            # Update model with optimized version
            self.models[model_name] = model
            self.model_info[model_name]["optimized"] = True
            self.model_info[model_name]["optimization_time"] = optimization_time
            self.model_info[model_name]["optimization_options"] = optimization_options

            logger.info(f"Model {model_name} optimized in {optimization_time:.2f}s")

            return {
                "model_name": model_name,
                "status": "optimized",
                "optimization_time": optimization_time,
                "memory_usage": self._get_model_memory_usage(model_name),
                "optimizations_applied": optimization_options,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error optimizing model {model_name}: {e}")
            raise

    async def benchmark_model(self, model_name: str, benchmark_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Benchmark a loaded model

        Args:
            model_name: Name of the model to benchmark
            benchmark_data: Benchmark configuration

        Returns:
            Benchmark results
        """
        try:
            logger.info(f"Benchmarking model: {model_name}")

            if model_name not in self.models:
                raise ValueError(f"Model {model_name} is not loaded")

            model = self.models[model_name]

            # Run benchmark (placeholder implementation)
            results = await self._run_benchmark(model, benchmark_data)

            return {
                "model_name": model_name,
                "benchmark_results": results,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error benchmarking model {model_name}: {e}")
            raise

    # Private helper methods
    async def _load_model_files_with_progress(
        self,
        model_name: str,
        model_path: Path,
        options: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ):
        """Load model files with progress tracking"""
        logger.info(f"Loading model files from: {model_path}")

        # Simulate loading stages with progress
        stages = [
            ("Initializing", 10),
            ("Loading weights", 30),
            ("Building model", 50),
            ("Optimizing", 70),
            ("Finalizing", 90),
            ("Complete", 100)
        ]

        for stage_name, progress in stages:
            if model_name in self.loading_progress:
                self.loading_progress[model_name] = progress

            if progress_callback:
                progress_callback(model_name, progress, stage_name)

            # Simulate processing time
            await asyncio.sleep(0.5)

        # Create a mock model object
        class MockModel:
            def __init__(self):
                self.config = {"model_type": "mock", "name": model_name}
                self.parameters = lambda: [torch.randn(1000, 1000)]  # Mock parameters

        return MockModel()

    async def _scan_models(self):
        """Scan for available models"""
        logger.info("Scanning for available models")
        # Placeholder implementation
        await self._scan_available_models()

    async def _scan_available_models(self) -> List[str]:
        """Scan directory for available models"""
        available_models = []

        # Check model directory
        if self.settings.model_dir.exists():
            for item in self.settings.model_dir.iterdir():
                if item.is_dir():
                    available_models.append(item.name)

        # Add default models
        default_models = ["Qwen3-Omni-30B-A3B-Thinking", "whisper-base", "xtts-v2"]
        for model in default_models:
            if model not in available_models:
                available_models.append(model)

        return available_models

    async def _load_model_files(
        self,
        model_name: str,
        model_path: Path,
        options: Dict[str, Any]
    ):
        """Load model files (placeholder implementation)"""
        logger.info(f"Loading model files from: {model_path}")

        # Simulate model loading
        await asyncio.sleep(1)  # Simulate loading time

        # Create a mock model object
        class MockModel:
            def __init__(self):
                self.config = {"model_type": "mock", "name": model_name}
                self.parameters = lambda: [torch.randn(1000, 1000)]  # Mock parameters

        return MockModel()

    def _get_model_memory_usage(self, model_name: str) -> float:
        """Get memory usage of a loaded model"""
        if model_name not in self.models:
            return 0.0

        # This is a placeholder implementation
        # In production, you would calculate actual memory usage
        return 512.0  # MB

    async def _quantize_model(self, model, bits: int):
        """Quantize model to specified bits"""
        logger.info(f"Quantizing model to {bits} bits")
        await asyncio.sleep(0.5)  # Simulate quantization time
        return model

    async def _prune_model(self, model, ratio: float):
        """Prune model by specified ratio"""
        logger.info(f"Pruning model with ratio {ratio}")
        await asyncio.sleep(0.5)  # Simulate pruning time
        return model

    async def _convert_to_half_precision(self, model):
        """Convert model to half precision"""
        logger.info("Converting model to half precision")
        if hasattr(model, 'half'):
            model = model.half()
        return model

    async def _run_benchmark(self, model, benchmark_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run benchmark on model"""
        logger.info("Running model benchmark")

        # Simulate benchmark
        await asyncio.sleep(2)  # Simulate benchmark time

        return {
            "inference_time": 0.1,  # seconds
            "throughput": 100.0,  # samples/second
            "memory_usage": 512.0,  # MB
            "accuracy": 0.95,  # placeholder
            "benchmark_duration": 2.0  # seconds
        }

    async def _auto_load_models(self):
        """Auto-load models based on persistence configuration"""
        try:
            if not self.auto_load_enabled:
                logger.info("Auto-load disabled, skipping auto-loading models")
                return

            auto_load_config = await self.persistence_service.get_auto_load_config()
            if not auto_load_config.get("enabled", False):
                logger.info("Auto-load not enabled in configuration")
                return

            models_to_load = await self.persistence_service.get_models_to_auto_load()
            if not models_to_load:
                logger.info("No models configured for auto-loading")
                return

            logger.info(f"Auto-loading {len(models_to_load)} models...")

            for model_name in models_to_load:
                try:
                    # Check if model is already loaded
                    if model_name not in self.models:
                        logger.info(f"Auto-loading model: {model_name}")
                        await self.load_model(model_name)
                    else:
                        logger.debug(f"Model {model_name} already loaded")
                except Exception as e:
                    logger.error(f"Error auto-loading model {model_name}: {e}")

            logger.info("Auto-loading completed")

        except Exception as e:
            logger.error(f"Error during auto-loading models: {e}")

    async def restore_model_states(self):
        """Restore model states from persistence"""
        try:
            logger.info("Restoring model states...")

            model_states = await self.persistence_service.get_all_model_states()
            restored_count = 0

            for model_name, state_info in model_states.items():
                try:
                    state = state_info.get("state", {})
                    if state and model_name not in self.models:
                        logger.info(f"Restoring model: {model_name}")
                        await self.load_model(model_name, options=state.get("options", {}))
                        restored_count += 1
                except Exception as e:
                    logger.error(f"Error restoring model {model_name}: {e}")

            logger.info(f"Restored {restored_count} models")

        except Exception as e:
            logger.error(f"Error restoring model states: {e}")

    async def get_persistence_info(self) -> Dict[str, Any]:
        """Get persistence service information"""
        return await self.persistence_service.get_persistence_info()