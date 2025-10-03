"""
WebSocket connection manager for real-time communication
"""

import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manages WebSocket connections and message broadcasting
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection"""
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.connection_metadata[client_id] = {
                "connected_at": datetime.utcnow().isoformat(),
                "client_id": client_id,
                "ip": websocket.client.host if websocket.client else "unknown"
            }
            logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection for client {client_id}: {e}")
            raise

    def disconnect(self, client_id: str):
        """Disconnect a WebSocket client"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                if websocket.client_state == WebSocketState.CONNECTED:
                    import asyncio
                    asyncio.create_task(websocket.close())
            except Exception as e:
                logger.error(f"Error closing WebSocket connection for client {client_id}: {e}")
            finally:
                del self.active_connections[client_id]
                if client_id in self.connection_metadata:
                    del self.connection_metadata[client_id]
                logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_message(self, client_id: str, message: dict):
        """Send a message to a specific client"""
        if client_id not in self.active_connections:
            logger.warning(f"Client {client_id} not found in active connections")
            return False

        try:
            websocket = self.active_connections[client_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps(message))
                return True
            else:
                self.disconnect(client_id)
                return False
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(self, message: dict, exclude_client: str = None):
        """Broadcast a message to all connected clients"""
        disconnected_clients = []

        for client_id, websocket in self.active_connections.items():
            if client_id == exclude_client:
                continue

            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps(message))
                else:
                    disconnected_clients.append(client_id)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_client: str = None):
        """Broadcast a message to all clients in a specific room"""
        # This is a placeholder for room-based broadcasting
        # In a real implementation, you'd maintain room memberships
        await self.broadcast(message, exclude_client)

    async def send_error(self, client_id: str, error_message: str, error_code: str = "UNKNOWN_ERROR"):
        """Send an error message to a client"""
        error_response = {
            "type": "error",
            "code": error_code,
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_message(client_id, error_response)

    async def send_success(self, client_id: str, data: dict, message: str = "Success"):
        """Send a success message to a client"""
        success_response = {
            "type": "success",
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_message(client_id, success_response)

    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)

    def get_connection_info(self, client_id: str) -> dict:
        """Get metadata for a specific connection"""
        return self.connection_metadata.get(client_id, {})

    def get_all_connections(self) -> List[str]:
        """Get list of all connected client IDs"""
        return list(self.active_connections.keys())

    def is_connected(self, client_id: str) -> bool:
        """Check if a client is connected"""
        return client_id in self.active_connections

    async def ping_all(self):
        """Ping all connected clients to check connectivity"""
        ping_message = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        }

        for client_id in self.active_connections:
            await self.send_message(client_id, ping_message)

    async def close_all(self):
        """Close all WebSocket connections"""
        for client_id, websocket in list(self.active_connections.items()):
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
            except Exception as e:
                logger.error(f"Error closing connection for client {client_id}: {e}")
            finally:
                self.disconnect(client_id)

# Import datetime here to avoid circular imports
from datetime import datetime

# Global WebSocket manager instance
websocket_manager = WebSocketManager()