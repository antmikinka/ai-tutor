"""
WebSocket connection manager for real-time communication.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from services.common import utc_now_iso

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Tracks live connections and serialises outbound messages."""

    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        # One lock per client so concurrent handlers never interleave frames.
        self._send_locks: Dict[str, asyncio.Lock] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        if len(self.active_connections) >= self.max_connections:
            logger.warning("Rejecting %s: connection limit (%d) reached", client_id, self.max_connections)
            await websocket.close(code=1013, reason="Too many connections")
            return False

        # A reconnecting client re-uses its id; drop the stale socket first.
        stale = self.active_connections.pop(client_id, None)
        if stale is not None:
            await self._close_quietly(stale)

        await websocket.accept()
        self.active_connections[client_id] = websocket
        self._send_locks[client_id] = asyncio.Lock()
        self.connection_metadata[client_id] = {
            "connected_at": utc_now_iso(),
            "client_id": client_id,
            "ip": websocket.client.host if websocket.client else "unknown",
            "messages_received": 0,
            "messages_sent": 0,
        }
        logger.info("Client %s connected (%d active)", client_id, len(self.active_connections))
        return True

    async def disconnect(self, client_id: str) -> None:
        websocket = self.active_connections.pop(client_id, None)
        self.connection_metadata.pop(client_id, None)
        self._send_locks.pop(client_id, None)
        if websocket is not None:
            await self._close_quietly(websocket)
            logger.info("Client %s disconnected (%d active)", client_id, len(self.active_connections))

    @staticmethod
    async def _close_quietly(websocket: WebSocket) -> None:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception as exc:  # already closed by the peer
            logger.debug("Ignoring close error: %s", exc)

    def record_received(self, client_id: str) -> None:
        meta = self.connection_metadata.get(client_id)
        if meta:
            meta["messages_received"] += 1

    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        websocket = self.active_connections.get(client_id)
        if websocket is None:
            logger.debug("Client %s not connected; dropping %s", client_id, message.get("type"))
            return False
        lock = self._send_locks.get(client_id)
        try:
            if websocket.client_state != WebSocketState.CONNECTED:
                await self.disconnect(client_id)
                return False
            payload = json.dumps(message, default=str)
            if lock is not None:
                async with lock:
                    await websocket.send_text(payload)
            else:
                await websocket.send_text(payload)
            meta = self.connection_metadata.get(client_id)
            if meta:
                meta["messages_sent"] += 1
            return True
        except Exception as exc:
            logger.warning("Send to %s failed: %s", client_id, exc)
            await self.disconnect(client_id)
            return False

    async def broadcast(self, message: Dict[str, Any], exclude_client: Optional[str] = None) -> None:
        targets = [cid for cid in self.active_connections if cid != exclude_client]
        await asyncio.gather(*(self.send_message(cid, message) for cid in targets), return_exceptions=True)

    async def send_error(self, client_id: str, error_message: str, error_code: str = "UNKNOWN_ERROR",
                         request_id: Optional[str] = None) -> None:
        await self.send_message(
            client_id,
            {
                "type": "error",
                "code": error_code,
                "message": error_message,
                "request_id": request_id,
                "timestamp": utc_now_iso(),
            },
        )

    def get_connection_count(self) -> int:
        return len(self.active_connections)

    def get_connection_info(self, client_id: str) -> Dict[str, Any]:
        return dict(self.connection_metadata.get(client_id, {}))

    def get_all_connections(self) -> List[str]:
        return list(self.active_connections.keys())

    def is_connected(self, client_id: str) -> bool:
        return client_id in self.active_connections

    async def close_all(self) -> None:
        for client_id in list(self.active_connections):
            await self.disconnect(client_id)
