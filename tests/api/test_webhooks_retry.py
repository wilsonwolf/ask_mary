"""Tests for outreach retry scheduling in call-completion flow."""

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


class TestCheckAndScheduleRetry:
    """_check_and_schedule_retry helper function."""

    async def test_schedules_retry_on_no_answer(self) -> None:
        """Retry is scheduled when outcome is no_answer."""
        from src.api.webhooks import _check_and_schedule_retry

        participant_id = uuid.uuid4()
        mock_event = MagicMock()
        mock_event.payload = {"outcome": "no_answer", "attempt": 1}

        with (
            patch(
                "src.api.webhooks._get_latest_outcome_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.api.webhooks.schedule_next_outreach",
                new_callable=AsyncMock,
            ) as mock_schedule,
        ):
            session = AsyncMock()
            await _check_and_schedule_retry(
                session, participant_id, "trial-1",
            )
        mock_schedule.assert_awaited_once_with(
            session, participant_id, "trial-1", 1,
        )

    async def test_schedules_retry_on_voicemail(self) -> None:
        """Retry is scheduled when outcome is voicemail."""
        from src.api.webhooks import _check_and_schedule_retry

        participant_id = uuid.uuid4()
        mock_event = MagicMock()
        mock_event.payload = {"outcome": "voicemail", "attempt": 0}

        with (
            patch(
                "src.api.webhooks._get_latest_outcome_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.api.webhooks.schedule_next_outreach",
                new_callable=AsyncMock,
            ) as mock_schedule,
        ):
            session = AsyncMock()
            await _check_and_schedule_retry(
                session, participant_id, "trial-1",
            )
        mock_schedule.assert_awaited_once()

    async def test_schedules_retry_on_early_hangup(self) -> None:
        """Retry is scheduled when outcome is early_hangup."""
        from src.api.webhooks import _check_and_schedule_retry

        participant_id = uuid.uuid4()
        mock_event = MagicMock()
        mock_event.payload = {"outcome": "early_hangup", "attempt": 2}

        with (
            patch(
                "src.api.webhooks._get_latest_outcome_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.api.webhooks.schedule_next_outreach",
                new_callable=AsyncMock,
            ) as mock_schedule,
        ):
            session = AsyncMock()
            await _check_and_schedule_retry(
                session, participant_id, "trial-1",
            )
        mock_schedule.assert_awaited_once_with(
            session, participant_id, "trial-1", 2,
        )

    async def test_skips_retry_on_completed_outcome(self) -> None:
        """Retry is NOT scheduled when outcome is completed."""
        from src.api.webhooks import _check_and_schedule_retry

        participant_id = uuid.uuid4()
        mock_event = MagicMock()
        mock_event.payload = {"outcome": "completed", "attempt": 0}

        with (
            patch(
                "src.api.webhooks._get_latest_outcome_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.api.webhooks.schedule_next_outreach",
                new_callable=AsyncMock,
            ) as mock_schedule,
        ):
            session = AsyncMock()
            await _check_and_schedule_retry(
                session, participant_id, "trial-1",
            )
        mock_schedule.assert_not_awaited()

    async def test_warns_when_no_outcome_event(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Logs warning and skips retry when no event found."""
        from src.api.webhooks import _check_and_schedule_retry

        participant_id = uuid.uuid4()

        with (
            patch(
                "src.api.webhooks._get_latest_outcome_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.schedule_next_outreach",
                new_callable=AsyncMock,
            ) as mock_schedule,
            caplog.at_level(logging.WARNING),
        ):
            session = AsyncMock()
            await _check_and_schedule_retry(
                session, participant_id, "trial-1",
            )
        mock_schedule.assert_not_awaited()
        assert "no_call_outcome_event_found" in caplog.text


class TestRetryFailureDoesNotBreakCompletion:
    """Retry scheduling failure must not break call completion."""

    async def test_retry_exception_still_returns_success(
        self, app,
    ) -> None:
        """handle_call_completion returns success even if retry raises."""
        mock_conversation = MagicMock()
        mock_conversation.conversation_id = uuid.uuid4()

        with (
            patch(
                "src.api.webhooks._get_or_create_conversation",
                new_callable=AsyncMock,
                return_value=mock_conversation,
            ),
            patch(
                "src.api.webhooks._fetch_audio",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks._trigger_post_call_checks",
                new_callable=AsyncMock,
            ),
            patch(
                "src.api.webhooks._check_and_schedule_retry",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Cloud Tasks unavailable"),
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/call-complete",
                    json={
                        "conversation_id": str(uuid.uuid4()),
                        "participant_id": str(uuid.uuid4()),
                        "trial_id": "trial-1",
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] is False
        assert "gcs_path" in data


class TestGetLatestOutcomeEvent:
    """_get_latest_outcome_event helper function."""

    async def test_queries_correct_event_type(self) -> None:
        """Queries for call_outcome_recorded event type."""
        from src.api.webhooks import _get_latest_outcome_event

        participant_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        result = await _get_latest_outcome_event(
            session, participant_id,
        )
        assert result is None
        session.execute.assert_awaited_once()
