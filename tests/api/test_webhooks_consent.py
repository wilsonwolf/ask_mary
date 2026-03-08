"""Tests for extended consent and contactability capture in webhooks."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


class TestCaptureConsentExtended:
    """Extended consent and contactability field capture."""

    async def test_capture_consent_stores_sms_consent(
        self, app
    ) -> None:
        """consent_sms=true is stored in participant.consent JSONB."""
        participant_id = str(uuid.uuid4())
        mock_participant = MagicMock()
        mock_participant.consent = {}
        mock_participant.contactability = {}

        with (
            patch(
                "src.api.webhooks.get_participant_by_id",
                new_callable=AsyncMock,
                return_value=mock_participant,
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
                        "tool_name": "capture_consent",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "disclosed_automation": "true",
                            "consent_to_continue": "true",
                            "consent_sms": "true",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["consent_recorded"] is True
        assert data["consent_sms"] is True
        assert mock_participant.consent["consent_sms"] is True

    async def test_capture_consent_stores_future_trials(
        self, app
    ) -> None:
        """consent_future_trials=true is stored in participant.consent."""
        participant_id = str(uuid.uuid4())
        mock_participant = MagicMock()
        mock_participant.consent = {}
        mock_participant.contactability = {}

        with (
            patch(
                "src.api.webhooks.get_participant_by_id",
                new_callable=AsyncMock,
                return_value=mock_participant,
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
                        "tool_name": "capture_consent",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "disclosed_automation": "true",
                            "consent_to_continue": "true",
                            "consent_future_trials": "true",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["consent_recorded"] is True
        assert data["consent_future_trials"] is True
        assert mock_participant.consent["consent_future_trials"] is True

    async def test_capture_consent_stores_contactability(
        self, app
    ) -> None:
        """ok_to_leave_voicemail and permitted_voicemail_name stored in contactability."""
        participant_id = str(uuid.uuid4())
        mock_participant = MagicMock()
        mock_participant.consent = {}
        mock_participant.contactability = {}

        with (
            patch(
                "src.api.webhooks.get_participant_by_id",
                new_callable=AsyncMock,
                return_value=mock_participant,
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
                        "tool_name": "capture_consent",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "disclosed_automation": "true",
                            "consent_to_continue": "true",
                            "ok_to_leave_voicemail": "true",
                            "permitted_voicemail_name": "Jane",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["consent_recorded"] is True
        assert data["ok_to_leave_voicemail"] is True
        assert data["permitted_voicemail_name"] == "Jane"
        assert mock_participant.contactability["ok_to_leave_voicemail"] is True
        assert mock_participant.contactability["permitted_voicemail_name"] == "Jane"

    async def test_capture_consent_preserves_existing_fields(
        self, app
    ) -> None:
        """New consent fields do not overwrite existing ones."""
        participant_id = str(uuid.uuid4())
        mock_participant = MagicMock()
        mock_participant.consent = {
            "disclosed_automation": True,
            "consent_to_continue": True,
        }
        mock_participant.contactability = {
            "preferred_channel": "voice",
        }

        with (
            patch(
                "src.api.webhooks.get_participant_by_id",
                new_callable=AsyncMock,
                return_value=mock_participant,
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
                        "tool_name": "capture_consent",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "consent_sms": "false",
                            "ok_to_leave_voicemail": "true",
                        },
                    },
                )
        assert response.status_code == 200
        # Existing consent fields preserved
        assert mock_participant.consent["disclosed_automation"] is True
        assert mock_participant.consent["consent_to_continue"] is True
        # New consent field added
        assert mock_participant.consent["consent_sms"] is False
        # Existing contactability field preserved
        assert mock_participant.contactability["preferred_channel"] == "voice"
        # New contactability field added
        assert mock_participant.contactability["ok_to_leave_voicemail"] is True
