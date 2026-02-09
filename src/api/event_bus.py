"""WebSocket event bus for real-time dashboard updates.

Manages connected WebSocket clients and broadcasts events
to all of them. Disconnected clients are cleaned up automatically.
"""

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_clients: set[WebSocket] = set()


def connect(websocket: WebSocket) -> None:
    """Register a WebSocket client for event broadcasts.

    Args:
        websocket: The WebSocket connection to add.
    """
    _clients.add(websocket)
    logger.info("ws_client_connected, total=%d", len(_clients))


def disconnect(websocket: WebSocket) -> None:
    """Remove a WebSocket client from the broadcast set.

    Args:
        websocket: The WebSocket connection to remove.
    """
    _clients.discard(websocket)
    logger.info("ws_client_disconnected, total=%d", len(_clients))


def get_clients() -> set[WebSocket]:
    """Return the current set of connected clients.

    Returns:
        Set of active WebSocket connections.
    """
    return _clients


async def broadcast_event(event_data: dict[str, Any]) -> None:
    """Send an event to all connected WebSocket clients.

    Clients that fail to receive the message are automatically
    removed from the broadcast set.

    Args:
        event_data: JSON-serializable event payload.
    """
    dead: list[WebSocket] = []
    for ws in _clients:
        try:
            await ws.send_json(event_data)
        except Exception:
            logger.warning("ws_client_send_failed, removing")
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)
