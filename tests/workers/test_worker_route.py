"""Tests for Cloud Tasks worker HTTP route."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.db.session import get_async_session


@pytest.fixture
def app():
    """Create test FastAPI app with worker router."""
    return create_app()


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_worker_route_calls_handler(
    app, mock_session,
) -> None:
    """POST /workers/reminders routes to handle_reminder_task."""
    app.dependency_overrides[get_async_session] = lambda: mock_session
    payload = {
        "participant_id": str(uuid.uuid4()),
        "template_id": "confirmation_check",
        "channel": "system",
        "idempotency_key": "test-key-1",
    }
    with patch(
        "src.api.worker_routes.handle_reminder_task",
        new_callable=AsyncMock,
        return_value={"processed": True, "status": "no_response"},
    ) as mock_handler:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/workers/reminders", json=payload,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] is True
    mock_handler.assert_awaited_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_worker_route_returns_handler_error(
    app, mock_session,
) -> None:
    """POST /workers/reminders returns error for unknown template."""
    app.dependency_overrides[get_async_session] = lambda: mock_session
    payload = {
        "participant_id": str(uuid.uuid4()),
        "template_id": "nonexistent",
        "channel": "system",
    }
    with patch(
        "src.api.worker_routes.handle_reminder_task",
        new_callable=AsyncMock,
        return_value={
            "processed": False,
            "reason": "unknown_template: nonexistent",
        },
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/workers/reminders", json=payload,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_worker_route_returns_duplicate(
    app, mock_session,
) -> None:
    """POST /workers/reminders returns duplicate when dedup fires."""
    app.dependency_overrides[get_async_session] = lambda: mock_session
    payload = {
        "participant_id": str(uuid.uuid4()),
        "template_id": "confirmation_check",
        "channel": "system",
        "idempotency_key": "dup-key",
    }
    with patch(
        "src.api.worker_routes.handle_reminder_task",
        new_callable=AsyncMock,
        return_value={"processed": False, "reason": "duplicate"},
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/workers/reminders", json=payload,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processed"] is False
    assert data["reason"] == "duplicate"
    app.dependency_overrides.clear()
