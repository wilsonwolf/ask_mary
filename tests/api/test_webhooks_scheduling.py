"""Tests for scheduling-related webhook handlers (check_availability, book_appointment)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


class TestCheckAvailabilityHandler:
    """check_availability server tool handler."""

    async def test_returns_available_slots(self, app) -> None:
        """Handler calls find_available_slots and returns slots."""
        participant_id = str(uuid.uuid4())
        mock_slots = {"slots": ["2026-03-10T09:00:00", "2026-03-11T09:00:00"]}

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.find_available_slots",
                new_callable=AsyncMock,
                return_value=mock_slots,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "check_availability",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "diabetes-study-a",
                            "preferred_dates": ["2026-03-10", "2026-03-11"],
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert "slots" in data
        assert len(data["slots"]) == 2

    async def test_broadcasts_availability_checked_event(self, app) -> None:
        """Handler broadcasts availability_checked via WebSocket."""
        participant_id = str(uuid.uuid4())
        mock_slots = {"slots": ["2026-03-10T09:00:00"]}

        mock_event = MagicMock()
        mock_event.event_id = uuid.uuid4()
        mock_event.created_at = "2026-03-01T00:00:00"

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.find_available_slots",
                new_callable=AsyncMock,
                return_value=mock_slots,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.api.webhooks.broadcast_event",
                new_callable=AsyncMock,
            ) as mock_broadcast,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "check_availability",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "diabetes-study-a",
                            "preferred_dates": ["2026-03-10"],
                        },
                    },
                )
        mock_broadcast.assert_called_once()
        broadcast_data = mock_broadcast.call_args[0][0]["data"]
        assert broadcast_data["event_type"] == "availability_checked"


class TestBookAppointmentHandler:
    """book_appointment server tool handler."""

    async def test_books_appointment_and_returns_result(self, app) -> None:
        """Handler calls book_appointment and returns booking result."""
        participant_id = str(uuid.uuid4())
        mock_result = {
            "booked": True,
            "appointment_id": str(uuid.uuid4()),
            "confirmation_due_at": "2026-03-10T21:00:00+00:00",
        }

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.book_appointment",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks._update_pipeline_status",
                new_callable=AsyncMock,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "book_appointment",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "diabetes-study-a",
                            "slot_datetime": "2026-03-10T09:00:00",
                            "visit_type": "screening",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["booked"] is True
        assert "appointment_id" in data

    async def test_broadcasts_appointment_booked_event(self, app) -> None:
        """Handler broadcasts appointment_booked via WebSocket."""
        participant_id = str(uuid.uuid4())
        appointment_id = str(uuid.uuid4())
        mock_result = {
            "booked": True,
            "appointment_id": appointment_id,
            "confirmation_due_at": "2026-03-10T21:00:00+00:00",
        }

        mock_event = MagicMock()
        mock_event.event_id = uuid.uuid4()
        mock_event.created_at = "2026-03-01T00:00:00"

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.book_appointment",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ),
            patch(
                "src.api.webhooks.broadcast_event",
                new_callable=AsyncMock,
            ) as mock_broadcast,
            patch(
                "src.api.webhooks._update_pipeline_status",
                new_callable=AsyncMock,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "book_appointment",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "diabetes-study-a",
                            "slot_datetime": "2026-03-10T09:00:00",
                            "visit_type": "screening",
                        },
                    },
                )
        mock_broadcast.assert_called_once()
        broadcast_data = mock_broadcast.call_args[0][0]["data"]
        assert broadcast_data["event_type"] == "appointment_booked"


class TestToolAliases:
    """ElevenLabs prompt-name aliases route to correct handlers."""

    async def test_record_screening_answer_alias(self, app) -> None:
        """record_screening_answer routes to record_screening_response."""
        participant_id = str(uuid.uuid4())
        mock_result = {"recorded": True}

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.record_screening_response",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "record_screening_answer",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "diabetes-study-a",
                            "question_key": "has_diabetes",
                            "answer": "yes",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["recorded"] is True

    async def test_check_eligibility_alias(self, app) -> None:
        """check_eligibility routes to determine_eligibility."""
        participant_id = str(uuid.uuid4())
        mock_result = {"eligible": True, "status": "eligible"}
        mock_trial = MagicMock()
        mock_trial.trial_name = "Diabetes Study A"

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.determine_eligibility",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.db.trials.get_trial",
                new_callable=AsyncMock,
                return_value=mock_trial,
            ),
            patch(
                "src.api.webhooks._update_pipeline_status",
                new_callable=AsyncMock,
            ),
            patch(
                "src.api.webhooks._log_agent_reasoning",
                new_callable=AsyncMock,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "check_eligibility",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "diabetes-study-a",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is True
