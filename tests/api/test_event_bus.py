"""Tests for WebSocket event bus module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.event_bus import broadcast_event, connect, disconnect, get_clients


class TestEventBusConnect:
    """WebSocket client connection management."""

    async def test_connect_adds_client(self) -> None:
        """connect() adds a WebSocket to the client set."""
        ws = AsyncMock()
        connect(ws)
        assert ws in get_clients()
        disconnect(ws)

    async def test_disconnect_removes_client(self) -> None:
        """disconnect() removes a WebSocket from the client set."""
        ws = AsyncMock()
        connect(ws)
        disconnect(ws)
        assert ws not in get_clients()


class TestEventBusBroadcast:
    """Event broadcasting to connected clients."""

    async def test_broadcast_sends_to_all_clients(self) -> None:
        """broadcast_event sends JSON to every connected client when no Redis."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        connect(ws1)
        connect(ws2)

        event_data = {"type": "event", "data": {"event_type": "TEST"}}
        await broadcast_event(event_data)

        ws1.send_json.assert_called_once_with(event_data)
        ws2.send_json.assert_called_once_with(event_data)

        disconnect(ws1)
        disconnect(ws2)

    async def test_broadcast_cleans_up_disconnected(self) -> None:
        """broadcast_event removes clients that raise on send."""
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = Exception("disconnected")

        connect(good_ws)
        connect(bad_ws)

        await broadcast_event({"type": "event", "data": {}})

        good_ws.send_json.assert_called_once()
        assert bad_ws not in get_clients()

        disconnect(good_ws)


class TestEventBusRedis:
    """Redis pub/sub broadcast path."""

    async def test_broadcast_publishes_to_redis_when_configured(self) -> None:
        """broadcast_event publishes JSON to Redis channel when Redis is set."""
        import src.api.event_bus as event_bus_module

        mock_redis = AsyncMock()
        event_data = {"type": "event", "data": {"event_type": "identity_verified"}}

        original = event_bus_module._redis_client
        event_bus_module._redis_client = mock_redis
        try:
            await broadcast_event(event_data)
        finally:
            event_bus_module._redis_client = original

        mock_redis.publish.assert_called_once()
        channel, payload = mock_redis.publish.call_args[0]
        assert channel == "ask-mary:events"
        parsed = json.loads(payload)
        assert parsed["data"]["event_type"] == "identity_verified"

    async def test_broadcast_does_not_push_locally_when_redis_configured(self) -> None:
        """When Redis is active, broadcast skips the local send_json loop."""
        import src.api.event_bus as event_bus_module

        mock_redis = AsyncMock()
        ws = AsyncMock()
        connect(ws)

        original = event_bus_module._redis_client
        event_bus_module._redis_client = mock_redis
        try:
            await broadcast_event({"type": "event", "data": {}})
        finally:
            event_bus_module._redis_client = original
            disconnect(ws)

        ws.send_json.assert_not_called()

    async def test_startup_sets_redis_client_when_url_configured(self) -> None:
        """startup() creates a Redis client when REDIS_URL is set."""
        import src.api.event_bus as event_bus_module
        from src.api.event_bus import startup

        mock_redis_instance = AsyncMock()
        mock_from_url = MagicMock(return_value=mock_redis_instance)

        original = event_bus_module._redis_client
        event_bus_module._redis_client = None
        try:
            with (
                patch("src.api.event_bus.get_settings") as mock_settings,
                patch("redis.asyncio.Redis.from_url", mock_from_url),
                patch("src.api.event_bus.asyncio.create_task") as mock_create_task,
            ):
                mock_settings.return_value.redis_url = "redis://localhost:6379"
                mock_create_task.return_value = AsyncMock()
                await startup()

            mock_from_url.assert_called_once_with("redis://localhost:6379")
            assert event_bus_module._redis_client is mock_redis_instance
        finally:
            event_bus_module._redis_client = original

    async def test_startup_skips_redis_when_url_empty(self) -> None:
        """startup() leaves _redis_client as None when REDIS_URL is empty."""
        import src.api.event_bus as event_bus_module
        from src.api.event_bus import startup

        original = event_bus_module._redis_client
        event_bus_module._redis_client = None
        try:
            with patch("src.api.event_bus.get_settings") as mock_settings:
                mock_settings.return_value.redis_url = ""
                await startup()

            assert event_bus_module._redis_client is None
        finally:
            event_bus_module._redis_client = original

    async def test_push_to_local_clients_sends_to_all_connected(self) -> None:
        """_push_to_local_clients sends JSON to every local WebSocket."""
        from src.api.event_bus import _push_to_local_clients

        ws1 = AsyncMock()
        ws2 = AsyncMock()
        connect(ws1)
        connect(ws2)

        event_data = {"type": "event", "data": {"event_type": "TEST"}}
        await _push_to_local_clients(event_data)

        ws1.send_json.assert_called_once_with(event_data)
        ws2.send_json.assert_called_once_with(event_data)

        disconnect(ws1)
        disconnect(ws2)

    async def test_push_to_local_clients_removes_dead_connections(self) -> None:
        """_push_to_local_clients removes clients that fail to send."""
        from src.api.event_bus import _push_to_local_clients

        good_ws = AsyncMock()
        dead_ws = AsyncMock()
        dead_ws.send_json.side_effect = Exception("gone")
        connect(good_ws)
        connect(dead_ws)

        await _push_to_local_clients({"type": "event", "data": {}})

        assert dead_ws not in get_clients()
        disconnect(good_ws)
