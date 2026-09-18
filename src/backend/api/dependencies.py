"""
Process-wide service container.

Every API router and the WebSocket handler must share the *same* service
instances (one model cache, one connection registry). Routers therefore never
construct services themselves; they declare ``Depends(get_ai_service)`` etc.
and the container hands back the singletons created in ``main.lifespan``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from config.settings import Settings, get_settings
from api.websocket_manager import WebSocketManager
from services.ai_service import AIService
from services.audio_service import AudioService
from services.drawing_service import DrawingService
from services.knowledge_service import KnowledgeService
from services.model_service import ModelService
from services.practice_service import PracticeService

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    settings: Settings
    ai_service: AIService
    audio_service: AudioService
    drawing_service: DrawingService
    model_service: ModelService
    knowledge_service: KnowledgeService
    practice_service: PracticeService
    websocket_manager: WebSocketManager = field(default_factory=WebSocketManager)

    @classmethod
    def create(cls, settings: Optional[Settings] = None) -> "ServiceContainer":
        settings = settings or get_settings()
        model_service = ModelService(settings)
        ai_service = AIService(settings, model_service=model_service)
        knowledge_service = KnowledgeService(settings)
        return cls(
            settings=settings,
            ai_service=ai_service,
            audio_service=AudioService(settings),
            drawing_service=DrawingService(settings),
            model_service=model_service,
            knowledge_service=knowledge_service,
            practice_service=PracticeService(settings, knowledge=knowledge_service, ai=ai_service),
        )

    async def start(self) -> None:
        """Bring up the lightweight parts of every service. Never raises."""
        for name, service in (
            ("model_service", self.model_service),
            ("ai_service", self.ai_service),
            ("drawing_service", self.drawing_service),
            ("audio_service", self.audio_service),
            ("knowledge_service", self.knowledge_service),
            ("practice_service", self.practice_service),
        ):
            try:
                await service.initialize()
            except Exception as exc:  # a broken optional feature must not kill the server
                logger.error("%s failed to initialize: %s", name, exc)

    async def stop(self) -> None:
        await self.websocket_manager.close_all()
        for name, service in (
            ("practice_service", self.practice_service),
            ("knowledge_service", self.knowledge_service),
            ("audio_service", self.audio_service),
            ("ai_service", self.ai_service),
            ("drawing_service", self.drawing_service),
            ("model_service", self.model_service),
        ):
            try:
                await service.cleanup()
            except Exception as exc:
                logger.error("%s failed to clean up: %s", name, exc)


_container: Optional[ServiceContainer] = None


def set_container(container: Optional[ServiceContainer]) -> None:
    global _container
    _container = container


def get_container() -> ServiceContainer:
    global _container
    if _container is None:
        # Routers imported outside of the FastAPI lifespan (tests, scripts)
        # still get a fully wired container.
        _container = ServiceContainer.create()
    return _container


def get_ai_service() -> AIService:
    return get_container().ai_service


def get_audio_service() -> AudioService:
    return get_container().audio_service


def get_drawing_service() -> DrawingService:
    return get_container().drawing_service


def get_model_service() -> ModelService:
    return get_container().model_service


def get_knowledge_service() -> KnowledgeService:
    return get_container().knowledge_service


def get_practice_service() -> PracticeService:
    return get_container().practice_service


def get_websocket_manager() -> WebSocketManager:
    return get_container().websocket_manager
