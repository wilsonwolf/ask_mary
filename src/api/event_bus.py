"""WebSocket event bus for real-time dashboard updates.

Manages connected WebSocket clients and broadcasts events
to all of them. Disconnected clients are cleaned up automatically.
"""

import json
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


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert non-serializable objects to strings.

    Args:
        obj: Object to sanitize for JSON serialization.

    Returns:
        JSON-safe version of the object.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    return str(obj)


async def broadcast_event(event_data: dict[str, Any]) -> None:
    """Send an event to all connected WebSocket clients.

    Sanitizes event data to ensure JSON serializability before
    sending. Clients that fail to receive are logged and removed.

    Args:
        event_data: Event payload (sanitized before sending).
    """
    safe_data = _make_json_safe(event_data)
    try:
        json.dumps(safe_data)
    except (TypeError, ValueError):
        logger.error(
            "broadcast_payload_not_serializable",
            extra={"event_type": event_data.get("data", {}).get("event_type")},
        )
        return

    dead: list[WebSocket] = []
    for ws in _clients:
        try:
            await ws.send_json(safe_data)
        except Exception:
            logger.warning(
                "ws_client_send_failed, removing",
                exc_info=True,
            )
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)
