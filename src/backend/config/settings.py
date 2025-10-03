"""
Configuration settings for AI Math Tutor Backend
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
from pydantic.types import DirectoryPath

class Settings(BaseSettings):
    """
    Application settings with environment variable support
    """

    # Application Settings
    app_name: str = "AI Math Tutor Backend"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["*"]

    # Database Settings
    database_url: str = "sqlite:///./math_tutor.db"
    database_echo: bool = False

    # Model Settings
    model_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent / "models")
    model_cache_dir: DirectoryPath = Field(default_factory=lambda: Path(__file__).parent.parent / "models" / "cache")

    # AI Model Configuration
    ai_model_name: str = "Qwen3-Omni-30B-A3B-Thinking"
    ai_model_path: Optional[str] = None
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2048
    ai_use_gpu: bool = True
    ai_device: str = "cuda" if ai_use_gpu else "cpu"

    # Whisper Settings (Speech-to-Text)
    whisper_model: str = "base"  # Options: tiny, base, small, medium, large
    whisper_language: str = "en"
    whisper_use_gpu: bool = True

    # TTS Settings (Text-to-Speech)
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_voice: str = "default"
    tts_language: str = "en"
    tts_sample_rate: int = 22050

    # Drawing Processing Settings
    canvas_width: int = 800
    canvas_height: int = 600
    drawing_min_stroke_length: int = 5
    drawing_smoothing_factor: float = 0.1

    # Audio Settings
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    audio_chunk_size: int = 1024
    audio_format: str = "float32"

    # Security Settings
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Logging Settings
    log_level: str = "INFO"
    log_file: str = "backend.log"
    log_max_size: str = "10MB"
    log_backup_count: int = 5

    # WebSocket Settings
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 10
    max_websocket_connections: int = 100

    # File Upload Settings
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = ["png", "jpg", "jpeg", "gif", "bmp", "pdf"]

    # Performance Settings
    max_concurrent_requests: int = 50
    request_timeout: int = 30
    cache_ttl: int = 3600  # 1 hour

    # Windows-specific Settings
    windows_install_dir: Optional[str] = None
    windows_service_name: str = "AIMathTutorBackend"

    # Data directory for model persistence
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_paths()

    def _setup_paths(self):
        """Ensure all required directories exist"""
        directories = [
            self.model_dir,
            self.model_cache_dir,
            self.data_dir,
            Path(self.database_url).parent,
            Path("logs"),
            Path("uploads"),
            Path("temp"),
        ]

        for directory in directories:
            if not str(directory).startswith(('sqlite:', 'postgresql:', 'mysql:')):
                directory.mkdir(parents=True, exist_ok=True)

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"

    @property
    def is_windows(self) -> bool:
        """Check if running on Windows"""
        return sys.platform == "win32"

    def get_model_path(self, model_name: str) -> Path:
        """Get full path for a model file"""
        return self.model_dir / model_name

    def get_cache_path(self, model_name: str) -> Path:
        """Get cache path for a model"""
        return self.model_cache_dir / model_name


# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def create_settings(**kwargs) -> Settings:
    """Create a new settings instance with overrides"""
    return Settings(**kwargs)