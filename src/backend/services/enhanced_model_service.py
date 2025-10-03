"""
Enhanced model management service for AI models
Supports Qwen3-Omni, Microsoft VibeVoice, and MERaLiON-AudioLLM models
"""

import json
import logging
import time
import psutil
import platform
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime
import asyncio
import os
from pathlib import Path
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed

import torch
import numpy as np
from transformers import (
    AutoTokenizer, AutoModel, AutoModelForCausalLM,
    AutoModelForSpeechSeq2Seq, AutoProcessor,
    pipeline, AutoModelForTextToWaveform
)
import soundfile as sf
import librosa

from config.settings import get_settings
from services.model_config import (
    ModelRegistry, ModelConfig, ModelInstance, ModelStatus, ModelType,
    get_model_registry
)

logger = logging.getLogger(__name__)

class ModelLoadError(Exception):
    """Custom exception for model loading errors"""
    pass

class ModelInferenceError(Exception):
    """Custom exception for model inference errors"""
    pass

class EnhancedModelService:
    """
    Enhanced model management service with support for multiple AI models
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.model_registry = get_model_registry()
        self.models: Dict[str, ModelInstance] = {}
        self.active_models: Dict[ModelType, str] = {}
        self.is_initialized = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.model_locks: Dict[str, threading.Lock] = {}
        self.performance_metrics: Dict[str, Dict[str, Any]] = {}
        self._system_resources = self._get_system_resources()

    async def initialize(self):
        """Initialize the enhanced model service"""
        try:
            logger.info("Initializing Enhanced Model Service...")

            # Create model directories
            self.settings.model_dir.mkdir(parents=True, exist_ok=True)
            self.settings.model_cache_dir.mkdir(parents=True, exist_ok=True)

            # Initialize system monitoring
            self._start_system_monitoring()

            # Scan for existing models
            await self._scan_models()

            # Set primary models as active
            for model_type in ModelType:
                primary_model = self.model_registry.get_primary_model(model_type)
                if primary_model:
                    self.active_models[model_type] = primary_model.name

            self.is_initialized = True
            logger.info("Enhanced Model Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Enhanced Model Service: {e}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Cleaning up Enhanced Model Service...")

            # Stop monitoring
            self._stop_system_monitoring()

            # Unload all models
            for model_name in list(self.models.keys()):
                await self.unload_model(model_name)

            # Shutdown executor
            self.executor.shutdown(wait=True)

            self.is_initialized = False
            logger.info("Enhanced Model Service cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during Enhanced Model Service cleanup: {e}")

    def is_healthy(self) -> bool:
        """Check if the model service is healthy"""
        return self.is_initialized

    def get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource usage"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_available_gb": psutil.virtual_memory().available / (1024**3),
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "gpu_available": torch.cuda.is_available(),
            "gpu_memory_used": self._get_gpu_memory_used() if torch.cuda.is_available() else 0,
            "gpu_memory_total": self._get_gpu_memory_total() if torch.cuda.is_available() else 0,
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "torch_version": torch.__version__
        }

    async def load_model(
        self,
        model_name: str,
        options: Dict[str, Any] = None,
        force_reload: bool = False
    ) -> Dict[str, Any]:
        """
        Load a model with enhanced error handling and resource management

        Args:
            model_name: Name of the model to load
            options: Loading options including quantization, device, etc.
            force_reload: Force reload even if already loaded

        Returns:
            Loading result with model information
        """
        if options is None:
            options = {}

        try:
            # Get model configuration
            model_config = self.model_registry.get_model(model_name)
            if not model_config:
                raise ModelLoadError(f"Model configuration not found: {model_name}")

            # Check if model is already loaded
            if model_name in self.models and not force_reload:
                instance = self.models[model_name]
                if instance.status == ModelStatus.LOADED:
                    return self._create_loading_response(instance, "already_loaded")

            # Check system resources
            if not self._check_system_resources(model_config):
                raise ModelLoadError(f"Insufficient system resources for {model_name}")

            # Create model lock if not exists
            if model_name not in self.model_locks:
                self.model_locks[model_name] = threading.Lock()

            # Create or update model instance
            if model_name not in self.models:
                self.models[model_name] = ModelInstance(model_config)

            instance = self.models[model_name]

            # Load model in background thread
            return await self._load_model_async(instance, options)

        except Exception as e:
            logger.error(f"Error loading model {model_name}: {e}")
            raise ModelLoadError(f"Failed to load model {model_name}: {str(e)}")

    async def unload_model(self, model_name: str) -> Dict[str, Any]:
        """Unload a model and free resources"""
        try:
            if model_name not in self.models:
                return {
                    "model_name": model_name,
                    "status": "not_loaded",
                    "timestamp": datetime.utcnow().isoformat()
                }

            instance = self.models[model_name]
            memory_before = instance.memory_usage_mb

            # Unload model
            if instance.model_object is not None:
                del instance.model_object
                instance.model_object = None

            # Update instance
            instance.status = ModelStatus.NOT_LOADED
            instance.memory_usage_mb = 0.0
            instance.loaded_at = None
            instance.error_message = None

            # Force garbage collection
            import gc
            gc.collect()

            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"Model {model_name} unloaded successfully")

            return {
                "model_name": model_name,
                "status": "unloaded",
                "memory_freed_mb": memory_before,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error unloading model {model_name}: {e}")
            raise

    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get detailed information about a model"""
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} is not loaded")

            instance = self.models[model_name]
            config = instance.config

            return {
                "model_name": model_name,
                "status": instance.status.value,
                "device": instance.device,
                "memory_usage_mb": instance.memory_usage_mb,
                "loaded_at": instance.loaded_at,
                "loading_time": instance.loading_start_time,
                "error_message": instance.error_message,
                "optimization_applied": instance.optimization_applied,
                "config": {
                    "name": config.name,
                    "type": config.type.value,
                    "description": config.description,
                    "file_size_gb": config.file_size_gb,
                    "memory_required_gb": config.memory_required_gb,
                    "gpu_required": config.gpu_required,
                    "languages": config.languages,
                    "special_features": config.special_features
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting model info for {model_name}: {e}")
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        """List all models with their status"""
        try:
            models_info = []

            # List all configured models
            for model_config in self.model_registry.get_all_models():
                instance = self.models.get(model_config.name)

                if instance:
                    models_info.append({
                        "name": model_config.name,
                        "type": model_config.type.value,
                        "status": instance.status.value,
                        "device": instance.device,
                        "memory_usage_mb": instance.memory_usage_mb,
                        "loaded_at": instance.loaded_at,
                        "is_active": self.active_models.get(model_config.type) == model_config.name
                    })
                else:
                    models_info.append({
                        "name": model_config.name,
                        "type": model_config.type.value,
                        "status": "not_loaded",
                        "device": None,
                        "memory_usage_mb": 0,
                        "loaded_at": None,
                        "is_active": False
                    })

            return models_info

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            raise

    async def switch_model(self, model_type: ModelType, new_model_name: str) -> Dict[str, Any]:
        """Switch active model for a specific type"""
        try:
            # Validate model type
            if model_type not in ModelType:
                raise ValueError(f"Invalid model type: {model_type}")

            # Get model configuration
            new_config = self.model_registry.get_model(new_model_name)
            if not new_config or new_config.type != model_type:
                raise ValueError(f"Model {new_model_name} is not a {model_type.value} model")

            # Load the new model if not loaded
            if new_model_name not in self.models or self.models[new_model_name].status != ModelStatus.LOADED:
                await self.load_model(new_model_name)

            # Update active model
            old_model = self.active_models.get(model_type)
            self.active_models[model_type] = new_model_name

            # Unload old model if different and not primary
            if old_model and old_model != new_model_name:
                old_config = self.model_registry.get_model(old_model)
                if old_config and old_config.type != ModelType.REASONING:  # Keep reasoning models loaded
                    await self.unload_model(old_model)

            logger.info(f"Switched {model_type.value} model from {old_model} to {new_model_name}")

            return {
                "model_type": model_type.value,
                "old_model": old_model,
                "new_model": new_model_name,
                "status": "switched",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error switching model: {e}")
            raise

    async def run_inference(
        self,
        model_type: ModelType,
        input_data: Any,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Run inference using the active model for a specific type with fallback

        Args:
            model_type: Type of model to use
            input_data: Input data for inference
            options: Additional inference options

        Returns:
            Inference result with metadata
        """
        if options is None:
            options = {}

        try:
            # Get active model and fallback chain
            active_model_name = self.active_models.get(model_type)
            if not active_model_name:
                raise ModelInferenceError(f"No active model for type: {model_type.value}")

            fallback_chain = self.model_registry.get_fallback_chain(active_model_name)

            # Try each model in the fallback chain
            for model_name in fallback_chain:
                try:
                    instance = self.models.get(model_name)
                    if not instance or instance.status != ModelStatus.LOADED:
                        # Try to load the model
                        await self.load_model(model_name)
                        instance = self.models.get(model_name)

                    if instance and instance.status == ModelStatus.LOADED:
                        result = await self._run_model_inference(instance, input_data, options)

                        # Update active model if we used a fallback
                        if model_name != active_model_name:
                            self.active_models[model_type] = model_name

                        return result

                except Exception as model_error:
                    logger.warning(f"Model {model_name} failed: {model_error}")
                    continue

            raise ModelInferenceError(f"All models in fallback chain failed for {model_type.value}")

        except Exception as e:
            logger.error(f"Error running inference: {e}")
            raise

    async def optimize_model(
        self,
        model_name: str,
        optimization_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize a loaded model with various techniques"""
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} is not loaded")

            instance = self.models[model_name]
            if instance.status != ModelStatus.LOADED:
                raise ValueError(f"Model {model_name} is not loaded")

            instance.status = ModelStatus.OPTIMIZING

            # Apply optimizations
            if optimization_options.get("quantization", False):
                await self._quantize_model(instance, optimization_options.get("quantization_bits", 8))

            if optimization_options.get("half_precision", False):
                await self._convert_to_half_precision(instance)

            if optimization_options.get("pruning", False):
                await self._prune_model(instance, optimization_options.get("pruning_ratio", 0.5))

            instance.status = ModelStatus.LOADED

            return {
                "model_name": model_name,
                "status": "optimized",
                "optimizations_applied": instance.optimization_applied,
                "memory_usage_mb": instance.memory_usage_mb,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error optimizing model {model_name}: {e}")
            raise

    # Private helper methods
    def _get_system_resources(self) -> Dict[str, Any]:
        """Get system resource information"""
        return {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "platform": platform.system()
        }

    def _get_gpu_memory_used(self) -> float:
        """Get GPU memory usage in GB"""
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024**3)
        return 0.0

    def _get_gpu_memory_total(self) -> float:
        """Get total GPU memory in GB"""
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / (1024**3)
        return 0.0

    def _check_system_resources(self, model_config: ModelConfig) -> bool:
        """Check if system has sufficient resources for the model"""
        # Check memory
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        if available_memory_gb < model_config.memory_required_gb:
            logger.warning(f"Insufficient memory for {model_config.name}: need {model_config.memory_required_gb}GB, have {available_memory_gb}GB")
            return False

        # Check GPU requirement
        if model_config.gpu_required and not torch.cuda.is_available():
            logger.warning(f"GPU required for {model_config.name} but not available")
            return False

        # Check GPU memory if required
        if model_config.gpu_required and torch.cuda.is_available():
            available_gpu_memory_gb = (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated()) / (1024**3)
            if available_gpu_memory_gb < model_config.memory_required_gb * 0.8:  # Leave some buffer
                logger.warning(f"Insufficient GPU memory for {model_config.name}")
                return False

        return True

    async def _load_model_async(self, instance: ModelInstance, options: Dict[str, Any]) -> Dict[str, Any]:
        """Load model asynchronously"""
        instance.status = ModelStatus.LOADING
        instance.loading_start_time = time.time()

        # Determine device
        device = self._get_optimal_device(instance.config, options)

        # Load model in background thread
        loop = asyncio.get_event_loop()
        try:
            model_object = await loop.run_in_executor(
                self.executor,
                self._load_model_with_config,
                instance.config,
                device,
                options
            )

            # Update instance
            instance.model_object = model_object
            instance.status = ModelStatus.LOADED
            instance.device = device
            instance.loaded_at = time.time()
            instance.memory_usage_mb = self._estimate_model_memory(model_object)
            instance.last_used = time.time()

            loading_time = instance.loaded_at - instance.loading_start_time

            logger.info(f"Model {instance.config.name} loaded successfully in {loading_time:.2f}s")

            return self._create_loading_response(instance, "loaded", loading_time)

        except Exception as e:
            instance.status = ModelStatus.ERROR
            instance.error_message = str(e)
            raise ModelLoadError(f"Failed to load model {instance.config.name}: {str(e)}")

    def _load_model_with_config(self, config: ModelConfig, device: str, options: Dict[str, Any]):
        """Load model based on its type and configuration"""
        try:
            if config.type == ModelType.REASONING:
                return self._load_reasoning_model(config, device, options)
            elif config.type in [ModelType.STT, ModelType.FALLBACK_STT]:
                return self._load_stt_model(config, device, options)
            elif config.type in [ModelType.TTS, ModelType.FALLBACK_TTS]:
                return self._load_tts_model(config, device, options)
            else:
                raise ValueError(f"Unsupported model type: {config.type}")

        except Exception as e:
            logger.error(f"Error loading model {config.name}: {e}")
            raise

    def _load_reasoning_model(self, config: ModelConfig, device: str, options: Dict[str, Any]):
        """Load reasoning model (Qwen3-Omni)"""
        logger.info(f"Loading reasoning model: {config.name}")

        # Load tokenizer and model
        model_path = self.settings.get_model_path(config.name)
        if not model_path.exists():
            # Try to download from Hugging Face
            logger.info(f"Model not found locally, attempting to download: {config.model_id}")
            model_path = config.model_id

        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            cache_dir=self.settings.model_cache_dir
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
            trust_remote_code=True,
            cache_dir=self.settings.model_cache_dir
        )

        return {
            "tokenizer": tokenizer,
            "model": model,
            "type": "reasoning"
        }

    def _load_stt_model(self, config: ModelConfig, device: str, options: Dict[str, Any]):
        """Load speech-to-text model"""
        logger.info(f"Loading STT model: {config.name}")

        model_path = self.settings.get_model_path(config.name)
        if not model_path.exists():
            model_path = config.model_id

        processor = AutoProcessor.from_pretrained(
            model_path,
            cache_dir=self.settings.model_cache_dir
        )

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
            cache_dir=self.settings.model_cache_dir
        )

        return {
            "processor": processor,
            "model": model,
            "type": "stt"
        }

    def _load_tts_model(self, config: ModelConfig, device: str, options: Dict[str, Any]):
        """Load text-to-speech model"""
        logger.info(f"Loading TTS model: {config.name}")

        model_path = self.settings.get_model_path(config.name)
        if not model_path.exists():
            model_path = config.model_id

        processor = AutoProcessor.from_pretrained(
            model_path,
            cache_dir=self.settings.model_cache_dir
        )

        model = AutoModelForTextToWaveform.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
            cache_dir=self.settings.model_cache_dir
        )

        return {
            "processor": processor,
            "model": model,
            "type": "tts"
        }

    def _get_optimal_device(self, config: ModelConfig, options: Dict[str, Any]) -> str:
        """Determine optimal device for model loading"""
        requested_device = options.get("device")

        if requested_device:
            return requested_device

        if config.gpu_required and torch.cuda.is_available():
            return "cuda"

        if torch.cuda.is_available() and not options.get("force_cpu", False):
            return "cuda"

        return "cpu"

    def _estimate_model_memory(self, model_object: Any) -> float:
        """Estimate model memory usage in MB"""
        try:
            if isinstance(model_object, dict):
                model = model_object.get("model")
                if hasattr(model, 'num_parameters'):
                    param_count = model.num_parameters()
                    return (param_count * 4) / (1024 * 1024)  # Rough estimate in MB
            return 512.0  # Default estimate
        except Exception:
            return 512.0

    async def _run_model_inference(self, instance: ModelInstance, input_data: Any, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run inference on a specific model instance"""
        start_time = time.time()

        try:
            if instance.config.type == ModelType.REASONING:
                result = await self._run_reasoning_inference(instance, input_data, options)
            elif instance.config.type in [ModelType.STT, ModelType.FALLBACK_STT]:
                result = await self._run_stt_inference(instance, input_data, options)
            elif instance.config.type in [ModelType.TTS, ModelType.FALLBACK_TTS]:
                result = await self._run_tts_inference(instance, input_data, options)
            else:
                raise ValueError(f"Unsupported model type: {instance.config.type}")

            instance.last_used = time.time()

            return {
                "result": result,
                "model_used": instance.config.name,
                "model_type": instance.config.type.value,
                "processing_time": time.time() - start_time,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error running inference on {instance.config.name}: {e}")
            raise

    async def _run_reasoning_inference(self, instance: ModelInstance, input_data: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run reasoning inference"""
        # This is a placeholder - implement actual reasoning logic
        return {
            "response": f"Analyzing mathematical problem: {input_data[:100]}...",
            "confidence": 0.85
        }

    async def _run_stt_inference(self, instance: ModelInstance, input_data: bytes, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run speech-to-text inference"""
        # This is a placeholder - implement actual STT logic
        return {
            "text": "Recognized speech from audio",
            "confidence": 0.90
        }

    async def _run_tts_inference(self, instance: ModelInstance, input_data: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run text-to-speech inference"""
        # This is a placeholder - implement actual TTS logic
        return {
            "audio_data": b"mock_audio_data",
            "duration": 2.5
        }

    async def _quantize_model(self, instance: ModelInstance, bits: int):
        """Apply quantization to model"""
        logger.info(f"Quantizing model {instance.config.name} to {bits} bits")
        # Implementation would depend on model type
        instance.optimization_applied.append(f"quantization_{bits}bits")

    async def _convert_to_half_precision(self, instance: ModelInstance):
        """Convert model to half precision"""
        logger.info(f"Converting model {instance.config.name} to half precision")
        # Implementation would convert model to float16
        instance.optimization_applied.append("half_precision")

    async def _prune_model(self, instance: ModelInstance, ratio: float):
        """Apply pruning to model"""
        logger.info(f"Pruning model {instance.config.name} with ratio {ratio}")
        # Implementation would apply pruning
        instance.optimization_applied.append(f"pruning_{ratio}")

    def _create_loading_response(self, instance: ModelInstance, status: str, loading_time: float = 0.0) -> Dict[str, Any]:
        """Create loading response"""
        return {
            "model_name": instance.config.name,
            "status": status,
            "device": instance.device,
            "memory_usage_mb": instance.memory_usage_mb,
            "loading_time": loading_time,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _scan_models(self):
        """Scan for existing models in model directory"""
        logger.info("Scanning for existing models")
        # Implementation would scan model directory and update registry
        pass

    def _start_system_monitoring(self):
        """Start system resource monitoring"""
        logger.info("Starting system monitoring")
        # Implementation would start monitoring thread
        pass

    def _stop_system_monitoring(self):
        """Stop system resource monitoring"""
        logger.info("Stopping system monitoring")
        # Implementation would stop monitoring thread
        pass