"""Tests for ElevenLabs server tool and Twilio DTMF webhooks."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
def app():
    """Create test FastAPI app."""
    return create_app()


class TestServerToolEndpoint:
    """ElevenLabs server tool webhook."""

    async def test_unknown_tool_returns_error(self, app) -> None:
        """Unknown tool name returns error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/elevenlabs/server-tool",
                json={
                    "tool_name": "nonexistent_tool",
                    "conversation_id": "conv-123",
                    "parameters": {},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "unknown_tool" in data["error"]

    async def test_verify_identity_routes(self, app) -> None:
        """verify_identity tool calls the identity agent."""
        participant_id = str(uuid.uuid4())
        mock_result = {"verified": True, "attempts": 1}

        with patch(
            "src.api.webhooks.verify_identity",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "src.api.webhooks.log_event",
            new_callable=AsyncMock,
            return_value=None,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "verify_identity",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "dob_year": "1985",
                            "zip_code": "97201",
                        },
                    },
                )
        assert response.status_code == 200
        assert response.json()["verified"] is True

    async def test_safety_check_routes(self, app) -> None:
        """safety_check tool calls the safety service."""
        participant_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.triggered = True
        mock_result.trigger_type = "severe_symptoms"
        mock_result.severity = "HANDOFF_NOW"

        with patch(
            "src.api.webhooks.run_safety_gate",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "src.api.webhooks.log_event",
            new_callable=AsyncMock,
            return_value=None,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "safety_check",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "response": "I have chest pain",
                            "participant_id": participant_id,
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["triggered"] is True
        assert data["severity"] == "HANDOFF_NOW"


class TestDtmfEndpoint:
    """Twilio DTMF capture webhook."""

    async def test_captures_dob_year(self, app) -> None:
        """4 digits captured as DOB year."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/twilio/dtmf",
                json={
                    "CallSid": "CA123",
                    "Digits": "1985",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "captured_dob_year"
        assert data["dob_year"] == 1985

    async def test_captures_zip_code(self, app) -> None:
        """5 digits captured as ZIP code without participant context."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/twilio/dtmf",
                json={
                    "CallSid": "CA123",
                    "Digits": "97201",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "captured_zip_code"
        assert data["zip_code"] == "97201"

    async def test_auto_verifies_when_all_fields_present(self, app) -> None:
        """Auto-calls verify_identity when participant, DOB, ZIP present."""
        participant_id = str(uuid.uuid4())
        mock_result = {"verified": True, "attempts": 1}

        with patch(
            "src.api.webhooks.verify_identity",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/twilio/dtmf",
                    json={
                        "CallSid": "CA123",
                        "Digits": "97201",
                        "participant_id": participant_id,
                        "dob_year": 1985,
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "verified"
        assert data["verified"] is True

    async def test_invalid_digits(self, app) -> None:
        """Wrong digit count returns invalid_input."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/twilio/dtmf",
                json={
                    "CallSid": "CA123",
                    "Digits": "12",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "invalid_input"

    async def test_dtmf_verify_calls_identity(self, app) -> None:
        """DTMF verify endpoint calls verify_identity."""
        participant_id = str(uuid.uuid4())
        mock_result = {"verified": True, "attempts": 1}

        with patch(
            "src.api.webhooks.verify_identity",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/twilio/dtmf-verify",
                    params={
                        "participant_id": participant_id,
                        "dob_year": 1985,
                        "zip_code": "97201",
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True


class TestCallCompletionEndpoint:
    """ElevenLabs call completion webhook."""

    async def test_uploads_audio_to_gcs(self, app) -> None:
        """Uploads audio and returns GCS path."""
        import base64

        from src.services.gcs_client import UploadResult

        fake_audio = base64.b64encode(b"fake-wav-data").decode()
        mock_result = UploadResult(
            gcs_path="trial-1/pid/cid.wav",
            bucket_name="ask-mary-audio",
        )

        with (
            patch(
                "src.api.webhooks.upload_audio",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks._get_or_create_conversation",
                new_callable=AsyncMock,
                return_value=MagicMock(),
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
                        "audio_data_base64": fake_audio,
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] is True
        assert data["gcs_path"] == "trial-1/pid/cid.wav"

    async def test_creates_conversation_and_persists_gcs_path(
        self,
        app,
    ) -> None:
        """Creates conversation row and sets audio_gcs_path."""
        import base64

        from src.services.gcs_client import UploadResult

        fake_audio = base64.b64encode(b"fake-wav-data").decode()
        conversation_id = str(uuid.uuid4())
        mock_result = UploadResult(
            gcs_path="trial-1/pid/cid.wav",
            bucket_name="ask-mary-audio",
        )

        mock_conversation = MagicMock()

        with (
            patch(
                "src.api.webhooks.upload_audio",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks._get_or_create_conversation",
                new_callable=AsyncMock,
                return_value=mock_conversation,
            ) as mock_get_or_create,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/call-complete",
                    json={
                        "conversation_id": conversation_id,
                        "participant_id": str(uuid.uuid4()),
                        "trial_id": "trial-1",
                        "audio_data_base64": fake_audio,
                    },
                )
        assert response.status_code == 200
        mock_get_or_create.assert_called_once()
        assert mock_conversation.audio_gcs_path == "trial-1/pid/cid.wav"

    async def test_no_audio_returns_not_uploaded(self, app) -> None:
        """Returns uploaded=False when no audio data provided."""
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


class TestSignedUrlEndpoint:
    """Audio signed URL generation."""

    async def test_returns_signed_url(self, app) -> None:
        """Generates a signed URL for audio playback."""
        with patch(
            "src.api.webhooks.generate_signed_url",
            return_value="https://storage.googleapis.com/signed",
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/audio/signed-url",
                    json={"gcs_path": "trial-1/pid/cid.wav"},
                )
        assert response.status_code == 200
        data = response.json()
        assert data["url"] == "https://storage.googleapis.com/signed"
        assert data["ttl_seconds"] == 3600
