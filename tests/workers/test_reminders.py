"""Tests for Cloud Tasks reminder worker routing."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.workers.reminders import handle_reminder_task


class TestHandleReminderTask:
    """Cloud Tasks worker routing by template_id."""

    async def test_dedup_skips_existing_key(self) -> None:
        """Duplicate idempotency_key returns already_processed."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-1",
            "participant_id": str(uuid.uuid4()),
            "template_id": "confirmation_check",
        }

        with patch(
            "src.workers.reminders._is_duplicate",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is False
        assert result["reason"] == "duplicate"

    async def test_confirmation_check_routes(self) -> None:
        """confirmation_check template routes to its handler."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-2",
            "participant_id": str(uuid.uuid4()),
            "appointment_id": str(uuid.uuid4()),
            "template_id": "confirmation_check",
        }
        mock_handler = AsyncMock(return_value={"status": "confirmed"})

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"confirmation_check": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["status"] == "confirmed"
        mock_handler.assert_called_once_with(mock_session, payload)

    async def test_slot_release_routes(self) -> None:
        """slot_release template routes to its handler."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-3",
            "participant_id": str(uuid.uuid4()),
            "appointment_id": str(uuid.uuid4()),
            "template_id": "slot_release",
        }
        mock_handler = AsyncMock(return_value={"released": True})

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"slot_release": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["released"] is True
        mock_handler.assert_called_once()

    async def test_reminder_routes(self) -> None:
        """Generic reminder template routes to reminder handler."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-4",
            "participant_id": str(uuid.uuid4()),
            "template_id": "appointment_reminder",
            "channel": "sms",
        }
        mock_handler = AsyncMock(return_value={"sent": True})

        with (
            patch(
                "src.workers.reminders._is_duplicate",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.dict(
                "src.workers.reminders.TASK_HANDLERS",
                {"appointment_reminder": mock_handler},
            ),
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
        assert result["sent"] is True
        mock_handler.assert_called_once()

    async def test_unknown_template_returns_error(self) -> None:
        """Unknown template_id returns error without crashing."""
        mock_session = AsyncMock()
        payload = {
            "idempotency_key": "key-5",
            "participant_id": str(uuid.uuid4()),
            "template_id": "nonexistent_template",
        }

        with patch(
            "src.workers.reminders._is_duplicate",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is False
        assert "unknown_template" in result["reason"]

    async def test_missing_key_skips_dedup(self) -> None:
        """Missing idempotency_key skips dedup and processes."""
        mock_session = AsyncMock()
        payload = {
            "participant_id": str(uuid.uuid4()),
            "template_id": "confirmation_check",
            "appointment_id": str(uuid.uuid4()),
        }
        mock_handler = AsyncMock(return_value={"status": "confirmed"})

        with patch.dict(
            "src.workers.reminders.TASK_HANDLERS",
            {"confirmation_check": mock_handler},
        ):
            result = await handle_reminder_task(mock_session, payload)

        assert result["processed"] is True
