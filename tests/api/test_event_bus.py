"""Tests for WebSocket event bus module."""

from unittest.mock import AsyncMock

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
        """broadcast_event sends JSON to every connected client."""
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
