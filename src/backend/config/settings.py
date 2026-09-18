"""
Configuration settings for AI Math Tutor Backend
"""

import sys
from pathlib import Path
from typing import List, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Every field can be overridden through an environment variable of the same
    name (case-insensitive) or a ``.env`` file in the backend directory.
    """

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    app_name: str = "AI Math Tutor Backend"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Server Settings. Bind to loopback by default: this backend is a local
    # companion process for the desktop app, not a public service.
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "app://.",
        "file://",
        # Chromium sends ``Origin: null`` for pages loaded from file:// (the
        # packaged Electron renderer).
        "null",
    ]
    # The backend only listens on loopback, so any local page (CRA dev server on
    # another port, a static preview build, ...) is an acceptable origin.
    cors_origin_regex: Optional[str] = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

    # Database Settings
    database_url: str = "sqlite:///./math_tutor.db"
    database_echo: bool = False

    # Filesystem layout (all relative to the backend directory unless overridden)
    model_dir: Path = Field(default_factory=lambda: BACKEND_ROOT / "models")
    model_cache_dir: Path = Field(default_factory=lambda: BACKEND_ROOT / "models" / "cache")
    data_dir: Path = Field(default_factory=lambda: BACKEND_ROOT / "data")
    log_dir: Path = Field(default_factory=lambda: BACKEND_ROOT / "logs")
    upload_dir: Path = Field(default_factory=lambda: BACKEND_ROOT / "uploads")
    temp_dir: Path = Field(default_factory=lambda: BACKEND_ROOT / "temp")

    # AI Model Configuration
    ai_model_name: str = "Qwen3-Omni-30B-A3B-Thinking"
    ai_model_path: Optional[str] = None
    ai_temperature: float = 0.7
    ai_max_tokens: int = 2048
    ai_use_gpu: bool = True
    ai_device: Optional[str] = None  # resolved from ai_use_gpu when not set explicitly

    # Whether heavy ML services should be preloaded in the background at startup.
    # Off by default so the desktop app is usable immediately without the ML stack.
    preload_models: bool = False

    # Optional OpenAI-compatible chat endpoint (OpenAI, Azure, Ollama, LM Studio,
    # vLLM, ...). Used for word problems / practice generation when no local
    # reasoning model is loaded. Off unless a base URL is configured.
    llm_api_base_url: Optional[str] = None  # e.g. https://api.openai.com/v1 or http://localhost:11434/v1
    llm_api_key: Optional[str] = None
    llm_api_model: str = "gpt-4o-mini"
    llm_api_timeout_seconds: float = 60.0

    # Course-material knowledge base (Chroma vector store)
    knowledge_dir: Optional[Path] = None  # defaults to <data_dir>/knowledge
    knowledge_embedding: str = "auto"  # auto | minilm | hashing
    knowledge_chunk_chars: int = 900
    knowledge_chunk_overlap_chars: int = 150
    knowledge_max_upload_bytes: int = 25 * 1024 * 1024
    knowledge_max_document_chars: int = 2_000_000

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
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5

    # WebSocket Settings
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 10
    max_websocket_connections: int = 100
    # Upper bound on a single inbound WebSocket frame (base64 canvas PNGs can be large)
    max_websocket_message_bytes: int = 8 * 1024 * 1024

    # File Upload Settings
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = ["png", "jpg", "jpeg", "gif", "bmp", "pdf"]

    # Performance Settings
    max_concurrent_requests: int = 50
    request_timeout: int = 30
    cache_ttl: int = 3600  # 1 hour
    # Symbolic computations are CPU bound; cap the time spent on a single problem.
    solver_timeout_seconds: float = 10.0
    solution_history_size: int = 200

    # Windows-specific Settings
    windows_install_dir: Optional[str] = None
    windows_service_name: str = "AIMathTutorBackend"

    @model_validator(mode="after")
    def _resolve_derived_values(self) -> "Settings":
        if self.ai_device is None:
            self.ai_device = "cuda" if self.ai_use_gpu else "cpu"
        if self.knowledge_dir is None:
            self.knowledge_dir = Path(self.data_dir) / "knowledge"
        if self.llm_api_base_url:
            self.llm_api_base_url = self.llm_api_base_url.rstrip("/")
        return self

    @property
    def remote_llm_configured(self) -> bool:
        return bool(self.llm_api_base_url)

    def ensure_directories(self) -> None:
        """Create the runtime directories the backend writes to."""
        for directory in (
            self.model_dir,
            self.model_cache_dir,
            self.data_dir,
            self.log_dir,
            self.upload_dir,
            self.temp_dir,
            self.knowledge_dir,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        return Path(self.log_dir) / self.log_file

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_windows(self) -> bool:
        return sys.platform == "win32"

    def get_model_path(self, model_name: str) -> Path:
        return Path(self.model_dir) / model_name

    def get_cache_path(self, model_name: str) -> Path:
        return Path(self.model_cache_dir) / model_name


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (created lazily)."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings


def create_settings(**kwargs) -> Settings:
    """Create a new settings instance with overrides (used by tests/tools)."""
    return Settings(**kwargs)
