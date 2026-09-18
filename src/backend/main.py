"""
AI Math Tutor Backend Server
FastAPI application with WebSocket support for real-time communication.
"""

from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, ValidationError

# Allow ``python main.py`` from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import Settings, get_settings  # noqa: E402
from api.dependencies import ServiceContainer, get_container, set_container  # noqa: E402
from api.routes import audio_api, drawing_api, knowledge_api, math_api, model_api, practice_api, system_api  # noqa: E402
from services.common import utc_now_iso  # noqa: E402
from services.drawing_service import DrawingDecodeError  # noqa: E402

logger = logging.getLogger("backend")


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    if getattr(root, "_math_tutor_configured", False):
        return
    root.setLevel(settings.log_level.upper())
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    try:
        settings.ensure_directories()
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as exc:  # read-only install dir etc.
        logger.warning("File logging disabled: %s", exc)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    root._math_tutor_configured = True  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #


async def _background_model_preloading(container: ServiceContainer) -> None:
    """Optionally warm heavy models after the UI is already usable."""
    await asyncio.sleep(5)
    logger.info("Background model preloading started")
    try:
        await container.model_service.initialize()
    except Exception as exc:
        logger.error("Background model preloading failed: %s", exc)
    else:
        logger.info("Background model preloading finished")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    container = ServiceContainer.create(settings)
    set_container(container)
    app.state.container = container

    logger.info("Starting %s v%s (%s)", settings.app_name, settings.version, settings.environment)
    await container.start()

    preload_task: Optional[asyncio.Task] = None
    if settings.preload_models:
        preload_task = asyncio.create_task(_background_model_preloading(container))

    try:
        yield
    finally:
        logger.info("Shutting down backend")
        if preload_task is not None and not preload_task.done():
            preload_task.cancel()
        await container.stop()
        set_container(None)


# --------------------------------------------------------------------------- #
# Application factory
# --------------------------------------------------------------------------- #


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        description="Local backend for the AI Math Tutor desktop application",
        version=settings.version,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    app.include_router(math_api.router, prefix="/api/math", tags=["Math"])
    app.include_router(audio_api.router, prefix="/api/audio", tags=["Audio"])
    app.include_router(drawing_api.router, prefix="/api/drawing", tags=["Drawing"])
    app.include_router(system_api.router, prefix="/api/system", tags=["System"])
    app.include_router(model_api.router, prefix="/api", tags=["Models"])
    app.include_router(knowledge_api.router, prefix="/api/knowledge", tags=["Knowledge"])
    app.include_router(practice_api.router, prefix="/api/practice", tags=["Practice"])

    _register_core_routes(app)
    return app


def _register_core_routes(app: FastAPI) -> None:
    @app.get("/health", tags=["System"])
    async def health_check():
        container = get_container()
        return {
            "status": "healthy",
            "timestamp": utc_now_iso(),
            "version": container.settings.version,
            "services": {
                "ai_service": container.ai_service.is_healthy(),
                "audio_service": container.audio_service.is_healthy(),
                "drawing_service": container.drawing_service.is_healthy(),
                "model_service": container.model_service.is_healthy(),
                "knowledge_service": container.knowledge_service.is_healthy(),
                "practice_service": container.practice_service.is_healthy(),
            },
            "websocket_connections": container.websocket_manager.get_connection_count(),
        }

    @app.get("/", tags=["System"])
    async def root():
        settings = get_container().settings
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs_url": "/api/docs",
            "health_check": "/health",
            "websocket": "/ws/{client_id}",
        }

    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        await handle_websocket(websocket, client_id)


# --------------------------------------------------------------------------- #
# WebSocket protocol
# --------------------------------------------------------------------------- #


class WSBase(BaseModel):
    request_id: Optional[str] = None


class MathInputMessage(WSBase):
    type: Literal["math_input"]
    content: str = Field(min_length=1, max_length=4000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifyMessage(WSBase):
    type: Literal["verify"]
    problem: str = Field(min_length=1, max_length=4000)
    solution: str = Field(min_length=1, max_length=4000)


class DrawingMessage(WSBase):
    type: Literal["drawing"]
    # Either a base64 string / data URL, or an object with an ``image`` key.
    data: Union[str, Dict[str, Any]]
    analysis_type: str = "equation_recognition"


class AudioMessage(WSBase):
    type: Literal["audio"]
    data: str = Field(min_length=1)
    language: str = "en"
    format: str = "wav"


class PingMessage(WSBase):
    type: Literal["ping"]


class InboundMessage(BaseModel):
    message: Union[MathInputMessage, VerifyMessage, DrawingMessage, AudioMessage, PingMessage] = Field(
        discriminator="type"
    )


async def handle_websocket(websocket: WebSocket, client_id: str) -> None:
    container = get_container()
    manager = container.websocket_manager
    settings = container.settings

    if len(client_id) > 128:
        await websocket.close(code=1008, reason="client_id too long")
        return
    if not await manager.connect(websocket, client_id):
        return

    await manager.send_message(
        client_id,
        {
            "type": "connected",
            "client_id": client_id,
            "server_version": settings.version,
            "capabilities": {
                "symbolic_solver": True,
                "llm": container.ai_service.any_llm_available,
                "llm_name": container.ai_service.llm_name,
                "speech": bool(getattr(container.audio_service, "meralion_service", None)),
                "drawing_recognition": container.ai_service.llm_ready,
                "knowledge_base": container.knowledge_service.is_healthy(),
                "practice": container.practice_service.is_healthy(),
            },
            "timestamp": utc_now_iso(),
        },
    )

    try:
        while True:
            raw = await websocket.receive_text()
            manager.record_received(client_id)
            if len(raw) > settings.max_websocket_message_bytes:
                await manager.send_error(client_id, "Message too large", "MESSAGE_TOO_LARGE")
                continue
            try:
                message = InboundMessage(message=json.loads(raw)).message
            except json.JSONDecodeError:
                await manager.send_error(client_id, "Message is not valid JSON", "INVALID_JSON")
                continue
            except ValidationError as exc:
                await manager.send_error(client_id, f"Invalid message: {exc.errors()[0].get('msg', 'schema error')}", "INVALID_MESSAGE")
                continue

            await _dispatch(container, client_id, message)
    except WebSocketDisconnect:
        logger.info("Client %s disconnected", client_id)
    except Exception as exc:
        logger.exception("WebSocket failure for %s: %s", client_id, exc)
    finally:
        await manager.disconnect(client_id)


async def _dispatch(container: ServiceContainer, client_id: str, message: WSBase) -> None:
    manager = container.websocket_manager
    request_id = message.request_id
    try:
        if isinstance(message, PingMessage):
            await manager.send_message(client_id, {"type": "pong", "request_id": request_id, "timestamp": utc_now_iso()})

        elif isinstance(message, MathInputMessage):
            solution = await container.ai_service.solve_math_problem(message.content, message.metadata)
            await manager.send_message(
                client_id,
                {"type": "math_solution", "solution": solution, "request_id": request_id, "timestamp": utc_now_iso()},
            )
            if message.metadata.get("enable_tts", False) and solution.get("confidence", 0) > 0:
                audio = await container.audio_service.text_to_speech(solution["solution"])
                if audio.get("available"):
                    await manager.send_message(
                        client_id,
                        {"type": "audio_response", "data": audio, "request_id": request_id, "timestamp": utc_now_iso()},
                    )

        elif isinstance(message, VerifyMessage):
            verdict = await container.ai_service.verify_solution(message.problem, message.solution)
            await manager.send_message(
                client_id,
                {"type": "verification", "data": verdict, "request_id": request_id, "timestamp": utc_now_iso()},
            )

        elif isinstance(message, DrawingMessage):
            image = message.data if isinstance(message.data, str) else message.data.get("image") or message.data.get("data")
            if not isinstance(image, str):
                await manager.send_error(client_id, "Drawing message needs an 'image' string", "INVALID_MESSAGE", request_id)
                return
            processed = await container.drawing_service.process_drawing(image, message.analysis_type)
            analysis = await container.ai_service.analyze_drawing(image)
            analysis["image_analysis"] = processed["data"]["image_analysis"]
            await manager.send_message(
                client_id,
                {"type": "drawing_analysis", "data": analysis, "request_id": request_id, "timestamp": utc_now_iso()},
            )

        elif isinstance(message, AudioMessage):
            import base64

            try:
                audio_bytes = base64.b64decode(message.data, validate=False)
            except Exception:
                await manager.send_error(client_id, "Audio data is not valid base64", "INVALID_MESSAGE", request_id)
                return
            result = await container.audio_service.speech_to_text(audio_bytes, language=message.language)
            await manager.send_message(
                client_id,
                {
                    "type": "audio_transcription",
                    "text": result.get("text", ""),
                    "confidence": result.get("confidence", 0.0),
                    "available": result.get("available", False),
                    "message": result.get("message"),
                    "request_id": request_id,
                    "timestamp": utc_now_iso(),
                },
            )
    except DrawingDecodeError as exc:
        await manager.send_error(client_id, str(exc), "INVALID_IMAGE", request_id)
    except ValueError as exc:
        await manager.send_error(client_id, str(exc), "BAD_REQUEST", request_id)
    except Exception as exc:
        logger.exception("Error handling %s from %s", type(message).__name__, client_id)
        await manager.send_error(client_id, f"Internal error: {exc}", "INTERNAL_ERROR", request_id)


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()
    uvicorn.run(
        "main:app",
        host=_settings.host,
        port=_settings.port,
        reload=_settings.debug,
        log_level=_settings.log_level.lower(),
        ws_ping_interval=_settings.websocket_ping_interval,
        ws_ping_timeout=_settings.websocket_ping_timeout,
        ws_max_size=_settings.max_websocket_message_bytes,
    )
