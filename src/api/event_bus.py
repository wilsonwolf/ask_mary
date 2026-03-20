"""WebSocket event bus for real-time dashboard updates.

Manages connected WebSocket clients and broadcasts events to all of them.

When REDIS_URL is configured, events are published to a Redis pub/sub channel
so all Cloud Run instances receive every event — fixing the multi-instance
problem where webhooks and WebSocket connections land on different instances.

When REDIS_URL is empty the bus falls back to direct in-memory broadcasting,
which works fine for single-instance local development.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis

from fastapi import WebSocket
from src.config.settings import get_settings

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "ask-mary:events"

_clients: set[WebSocket] = set()
_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]
_subscriber_task: asyncio.Task[None] | None = None


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


async def startup() -> None:
    """Initialise Redis connection and start the subscriber loop if configured.

    Reads REDIS_URL from settings. If empty, the bus operates in
    single-instance in-memory mode with no Redis dependency.
    """
    global _redis_client, _subscriber_task

    settings = get_settings()
    if not settings.redis_url:
        logger.info("event_bus: no REDIS_URL — using in-memory broadcast")
        return

    _redis_client = redis.Redis.from_url(settings.redis_url)
    _subscriber_task = asyncio.create_task(_redis_subscriber_loop())
    logger.info("event_bus: Redis pub/sub enabled on %s", settings.redis_url)


async def shutdown() -> None:
    """Cancel the subscriber task and close the Redis connection.

    Safe to call even when Redis was not configured.
    """
    global _redis_client, _subscriber_task

    if _subscriber_task is not None:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        _subscriber_task = None

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("event_bus: Redis connection closed")


async def _redis_subscriber_loop() -> None:
    """Subscribe to the Redis channel and push messages to local WebSocket clients.

    Runs as a background task for the lifetime of the process.
    Reconnects automatically on transient errors.
    """
    assert _redis_client is not None
    while True:
        try:
            async with _redis_client.pubsub() as pubsub:
                await pubsub.subscribe(REDIS_CHANNEL)
                logger.info("event_bus: subscribed to Redis channel %s", REDIS_CHANNEL)
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("event_bus: malformed Redis message")
                        continue
                    await _push_to_local_clients(data)
        except asyncio.CancelledError:
            raise
        except redis.RedisError:
            logger.warning("event_bus: Redis subscriber error — reconnecting in 1s", exc_info=True)
            await asyncio.sleep(1)


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


async def _push_to_local_clients(event_data: dict[str, Any]) -> None:
    """Send an event payload to all locally connected WebSocket clients.

    Called either directly (in-memory mode) or from the Redis subscriber
    loop (Redis mode). Removes clients that fail to receive.

    Args:
        event_data: Already-sanitized event payload dict.
    """
    dead: list[WebSocket] = []
    for ws in _clients:
        try:
            await ws.send_json(event_data)
        except Exception:
            logger.warning("ws_client_send_failed, removing", exc_info=True)
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def broadcast_event(event_data: dict[str, Any]) -> None:
    """Send an event to all connected WebSocket clients across all instances.

    When Redis is configured, publishes to the shared Redis channel so every
    instance's subscriber loop delivers it to its own local clients.
    Falls back to direct local delivery when Redis is not configured.

    Args:
        event_data: Event payload (sanitized before sending/publishing).
    """
    safe_data = _make_json_safe(event_data)
    try:
        serialized = json.dumps(safe_data)
    except (TypeError, ValueError):
        logger.error(
            "broadcast_payload_not_serializable",
            extra={"event_type": event_data.get("data", {}).get("event_type")},
        )
        return

    if _redis_client is not None:
        await _redis_client.publish(REDIS_CHANNEL, serialized)
        return

    await _push_to_local_clients(safe_data)
