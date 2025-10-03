"""
Enhanced model configuration for AI Math Tutor
Supports multiple AI models with fallback mechanisms
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

class ModelType(Enum):
    """Model types supported by the system"""
    REASONING = "reasoning"  # Qwen3-Omni-30B-A3B-Thinking
    STT = "stt"  # MERaLiON-AudioLLM-Whisper-SEA-LION
    TTS = "tts"  # Microsoft VibeVoice-1.5B
    FALLBACK_STT = "fallback_stt"  # OpenAI Whisper
    FALLBACK_TTS = "fallback_tts"  # Coqui XTTS-v2

class ModelStatus(Enum):
    """Model status states"""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"
    OPTIMIZING = "optimizing"

@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    name: str
    type: ModelType
    model_id: str
    description: str
    file_size_gb: float
    memory_required_gb: float
    gpu_required: bool = False
    quantization_supported: bool = True
    languages: List[str] = field(default_factory=lambda: ["en"])
    special_features: List[str] = field(default_factory=list)
    fallback_models: List[str] = field(default_factory=list)
    loading_timeout: int = 300  # seconds

@dataclass
class ModelInstance:
    """Runtime instance of a loaded model"""
    config: ModelConfig
    status: ModelStatus = ModelStatus.NOT_LOADED
    model_object: Any = None
    loading_start_time: Optional[float] = None
    loaded_at: Optional[float] = None
    memory_usage_mb: float = 0.0
    device: str = "cpu"
    last_used: Optional[float] = None
    error_message: Optional[str] = None
    optimization_applied: List[str] = field(default_factory=list)

class ModelRegistry:
    """Registry of all supported models"""

    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._load_default_models()

    def _load_default_models(self):
        """Load default model configurations"""

        # Primary reasoning model
        self._models["Qwen3-Omni-30B-A3B-Thinking"] = ModelConfig(
            name="Qwen3-Omni-30B-A3B-Thinking",
            type=ModelType.REASONING,
            model_id="Qwen/Qwen3-Omni-30B-A3B-Thinking",
            description="Advanced reasoning model for mathematical problem solving with thinking capabilities",
            file_size_gb=58.0,
            memory_required_gb=32.0,
            gpu_required=True,
            quantization_supported=True,
            languages=["en", "zh", "es", "fr", "de", "ja", "ko"],
            special_features=["chain_of_thought", "mathematical_reasoning", "step_by_step"],
            fallback_models=["gpt-4", "claude-3.5-sonnet"]
        )

        # STT model - MERaLiON-AudioLLM
        self._models["MERaLiON-AudioLLM-Whisper-SEA-LION"] = ModelConfig(
            name="MERaLiON-AudioLLM-Whisper-SEA-LION",
            type=ModelType.STT,
            model_id="MERaLiON/MERaLiON-AudioLLM-Whisper-SEA-LION",
            description="Enhanced speech recognition model optimized for Southeast Asian languages and educational content",
            file_size_gb=2.8,
            memory_required_gb=6.0,
            gpu_required=False,
            quantization_supported=True,
            languages=["en", "zh", "ms", "id", "th", "vi", "tl", "ja", "ko"],
            special_features=["educational_content", "mathematical_terms", "classroom_noise_filtering"],
            fallback_models=["whisper-large", "whisper-medium"]
        )

        # TTS model - Microsoft VibeVoice
        self._models["Microsoft-VibeVoice-1.5B"] = ModelConfig(
            name="Microsoft-VibeVoice-1.5B",
            type=ModelType.TTS,
            model_id="Microsoft/VibeVoice-1.5B",
            description="Natural sounding text-to-speech model with educational voice optimization",
            file_size_gb=3.2,
            memory_required_gb=4.0,
            gpu_required=False,
            quantization_supported=True,
            languages=["en", "zh", "es", "fr", "de", "ja", "ko"],
            special_features=["educational_tone", "clarity", "mathematical_pronunciation"],
            fallback_models=["xtts-v2", "edge-tts"]
        )

        # Fallback models
        self._models["whisper-large"] = ModelConfig(
            name="whisper-large",
            type=ModelType.FALLBACK_STT,
            model_id="openai/whisper-large",
            description="OpenAI Whisper large model for speech recognition",
            file_size_gb=3.0,
            memory_required_gb=6.0,
            gpu_required=False,
            quantization_supported=True,
            languages=["multilingual"],
            fallback_models=["whisper-medium", "whisper-base"]
        )

        self._models["xtts-v2"] = ModelConfig(
            name="xtts-v2",
            type=ModelType.FALLBACK_TTS,
            model_id="coqui/XTTS-v2",
            description="Coqui TTS v2 multilingual text-to-speech model",
            file_size_gb=2.5,
            memory_required_gb=4.0,
            gpu_required=False,
            quantization_supported=True,
            languages=["multilingual"],
            fallback_models=["edge-tts"]
        )

    def get_model(self, model_name: str) -> Optional[ModelConfig]:
        """Get model configuration by name"""
        return self._models.get(model_name)

    def get_models_by_type(self, model_type: ModelType) -> List[ModelConfig]:
        """Get all models of a specific type"""
        return [model for model in self._models.values() if model.type == model_type]

    def get_all_models(self) -> List[ModelConfig]:
        """Get all available model configurations"""
        return list(self._models.values())

    def get_primary_model(self, model_type: ModelType) -> Optional[ModelConfig]:
        """Get the primary model for a specific type"""
        primary_models = {
            ModelType.REASONING: "Qwen3-Omni-30B-A3B-Thinking",
            ModelType.STT: "MERaLiON-AudioLLM-Whisper-SEA-LION",
            ModelType.TTS: "Microsoft-VibeVoice-1.5B",
            ModelType.FALLBACK_STT: "whisper-large",
            ModelType.FALLBACK_TTS: "xtts-v2"
        }
        primary_name = primary_models.get(model_type)
        return self._models.get(primary_name) if primary_name else None

    def get_fallback_chain(self, model_name: str) -> List[str]:
        """Get the fallback chain for a model"""
        model = self.get_model(model_name)
        if not model:
            return []

        fallback_chain = [model_name]
        current_fallbacks = model.fallback_models

        while current_fallbacks:
            next_fallback = current_fallbacks[0]
            if next_fallback not in fallback_chain:
                fallback_chain.append(next_fallback)
                next_model = self.get_model(next_fallback)
                if next_model:
                    current_fallbacks = next_model.fallback_models
                else:
                    break
            else:
                break

        return fallback_chain

    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to dictionary for serialization"""
        return {
            model_name: {
                "name": model.name,
                "type": model.type.value,
                "model_id": model.model_id,
                "description": model.description,
                "file_size_gb": model.file_size_gb,
                "memory_required_gb": model.memory_required_gb,
                "gpu_required": model.gpu_required,
                "quantization_supported": model.quantization_supported,
                "languages": model.languages,
                "special_features": model.special_features,
                "fallback_models": model.fallback_models,
                "loading_timeout": model.loading_timeout
            }
            for model_name, model in self._models.items()
        }

# Global registry instance
model_registry = ModelRegistry()

def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance"""
    return model_registry