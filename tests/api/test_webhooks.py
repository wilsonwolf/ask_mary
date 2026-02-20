"""Tests for ElevenLabs server tool and Twilio DTMF webhooks."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.db.session import get_async_session
from src.shared.types import HandoffReason, HandoffSeverity


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

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.verify_identity",
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

    async def test_verify_identity_empty_dob_returns_error(self, app) -> None:
        """verify_identity with empty dob_year returns error, not 500."""
        participant_id = str(uuid.uuid4())

        with patch(
            "src.api.webhooks._enforce_pre_checks",
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
                            "dob_year": "",
                            "zip_code": "97201",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is False
        assert "error" in data

    async def test_gated_tool_blocked_by_dnc(self, app) -> None:
        """Gated tool returns error when DNC gate fails."""
        participant_id = str(uuid.uuid4())

        with patch(
            "src.api.webhooks._enforce_pre_checks",
            new_callable=AsyncMock,
            return_value={"error": "dnc_blocked", "channel": "voice"},
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
        data = response.json()
        assert data["error"] == "dnc_blocked"

    async def test_ungated_tool_skips_pre_checks(self, app) -> None:
        """safety_check (ungated) does not call _enforce_pre_checks."""
        participant_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.triggered = False
        mock_result.trigger_type = None
        mock_result.severity = None

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
            ) as mock_gate,
            patch(
                "src.api.webhooks.run_safety_gate",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks._resolve_call_sid",
                new_callable=AsyncMock,
                return_value=None,
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
                await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "safety_check",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "response": "I feel fine",
                        },
                    },
                )
        mock_gate.assert_not_called()

    async def test_safety_check_routes(self, app) -> None:
        """safety_check tool calls the safety service."""
        participant_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.triggered = True
        mock_result.trigger_type = HandoffReason.SEVERE_SYMPTOMS
        mock_result.severity = HandoffSeverity.HANDOFF_NOW

        with (
            patch(
                "src.api.webhooks.run_safety_gate",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks._resolve_call_sid",
                new_callable=AsyncMock,
                return_value=None,
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
        assert data["severity"] == HandoffSeverity.HANDOFF_NOW


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


class TestNormalizeTranscript:
    """Transcript normalization for supervisor compatibility."""

    def test_normalizes_list_to_entries_dict(self) -> None:
        """List of ElevenLabs turns becomes {entries: [...]}."""
        from src.api.webhooks import _normalize_transcript

        raw = [
            {"role": "agent", "message": "Hello, this is Mary."},
            {"role": "user", "message": "Hi Mary."},
        ]
        result = _normalize_transcript(raw)
        assert isinstance(result, dict)
        assert "entries" in result
        assert len(result["entries"]) == 2
        for entry in result["entries"]:
            assert "step" in entry
            assert "content" in entry

    def test_preserves_already_normalized(self) -> None:
        """Already-normalized dict passes through unchanged."""
        from src.api.webhooks import _normalize_transcript

        raw = {
            "entries": [
                {"step": "disclosure", "content": "I am an automated assistant."},
            ]
        }
        result = _normalize_transcript(raw)
        assert result == raw

    def test_handles_empty_list(self) -> None:
        """Empty list returns empty entries."""
        from src.api.webhooks import _normalize_transcript

        result = _normalize_transcript([])
        assert result == {"entries": []}

    def test_handles_none(self) -> None:
        """None returns empty entries."""
        from src.api.webhooks import _normalize_transcript

        result = _normalize_transcript(None)
        assert result == {"entries": []}

    def test_maps_role_to_step(self) -> None:
        """ElevenLabs role field maps to step."""
        from src.api.webhooks import _normalize_transcript

        raw = [{"role": "agent", "message": "Disclosure: I am AI."}]
        result = _normalize_transcript(raw)
        assert result["entries"][0]["step"] == "agent"
        assert result["entries"][0]["content"] == "Disclosure: I am AI."


class TestCallCompletionEndpoint:
    """ElevenLabs call completion webhook."""

    async def test_fetches_audio_and_uploads_to_gcs(self, app) -> None:
        """Fetches audio via API and uploads to GCS."""
        from src.services.gcs_client import UploadResult

        fake_audio = b"fake-wav-data"
        mock_result = UploadResult(
            gcs_path="trial-1/pid/cid.wav",
            bucket_name="ask-mary-audio",
        )

        with (
            patch(
                "src.api.webhooks._fetch_audio",
                new_callable=AsyncMock,
                return_value=fake_audio,
            ),
            patch(
                "src.api.webhooks.upload_audio",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_upload,
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
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] is True
        assert data["gcs_path"] == "trial-1/pid/cid.wav"
        mock_upload.assert_called_once()

    async def test_persists_gcs_path_on_conversation(self, app) -> None:
        """Fetches audio, uploads, and sets audio_gcs_path."""
        from src.services.gcs_client import UploadResult

        mock_result = UploadResult(
            gcs_path="trial-1/pid/cid.wav",
            bucket_name="ask-mary-audio",
        )
        mock_conversation = MagicMock()

        with (
            patch(
                "src.api.webhooks._fetch_audio",
                new_callable=AsyncMock,
                return_value=b"audio-bytes",
            ),
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
                        "conversation_id": str(uuid.uuid4()),
                        "participant_id": str(uuid.uuid4()),
                        "trial_id": "trial-1",
                    },
                )
        assert response.status_code == 200
        mock_get_or_create.assert_called_once()
        assert mock_conversation.audio_gcs_path == "trial-1/pid/cid.wav"

    async def test_fetches_and_stores_transcript(self, app) -> None:
        """Fetches transcript from ElevenLabs and stores on conversation."""
        mock_conversation = MagicMock()
        mock_conversation.conversation_id = uuid.uuid4()
        mock_conversation.full_transcript = None

        fake_transcript = [
            {"role": "agent", "message": "Hello, this is Mary."},
            {"role": "user", "message": "Hi Mary."},
        ]

        with (
            patch(
                "src.api.webhooks._get_or_create_conversation",
                new_callable=AsyncMock,
                return_value=mock_conversation,
            ),
            patch(
                "src.api.webhooks._fetch_transcript",
                new_callable=AsyncMock,
                return_value=fake_transcript,
            ) as mock_fetch,
            patch(
                "src.api.webhooks._fetch_audio",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks._trigger_post_call_checks",
                new_callable=AsyncMock,
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
                        "conversation_id": "conv-abc-123",
                        "participant_id": str(uuid.uuid4()),
                        "trial_id": "trial-1",
                    },
                )
        assert response.status_code == 200
        mock_fetch.assert_called_once_with("conv-abc-123")
        stored = mock_conversation.full_transcript
        assert isinstance(stored, dict)
        assert "entries" in stored
        assert len(stored["entries"]) == 2
        assert stored["entries"][0]["content"] == "Hello, this is Mary."

    async def test_audio_fetch_fails_still_runs_post_call(self, app) -> None:
        """Returns uploaded=False but still triggers post-call checks."""
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
            ) as mock_checks,
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
        mock_checks.assert_called_once()


class TestCaptureConsent:
    """capture_consent server tool webhook."""

    async def test_capture_consent_logs_event(self, app) -> None:
        """capture_consent logs consent_captured event and broadcasts."""
        participant_id = str(uuid.uuid4())
        mock_participant = MagicMock()
        mock_participant.consent = {}

        mock_event = MagicMock()
        mock_event.event_id = uuid.uuid4()
        mock_event.created_at = "2026-01-01T00:00:00"

        with (
            patch(
                "src.api.webhooks.get_participant_by_id",
                new_callable=AsyncMock,
                return_value=mock_participant,
            ),
            patch(
                "src.api.webhooks.log_event",
                new_callable=AsyncMock,
                return_value=mock_event,
            ) as mock_log,
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
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "capture_consent",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "disclosed_automation": "true",
                            "consent_to_continue": "true",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["consent_recorded"] is True
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        assert call_kwargs[1]["event_type"] == "consent_captured"
        mock_broadcast.assert_called_once()

    async def test_capture_consent_updates_participant(self, app) -> None:
        """capture_consent updates participant.consent JSONB."""
        participant_id = str(uuid.uuid4())
        mock_participant = MagicMock()
        mock_participant.consent = {}

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
                        },
                    },
                )
        assert response.status_code == 200
        assert mock_participant.consent["disclosed_automation"] is True
        assert mock_participant.consent["consent_to_continue"] is True


class TestGetVerificationPrompts:
    """get_verification_prompts server tool webhook."""

    async def test_get_verification_prompts_returns_results(
        self, app,
    ) -> None:
        """get_verification_prompts returns prompts from adversarial check."""
        from src.shared.response_models import VerificationPromptsResult
        from src.shared.types import AdversarialCheckStatus

        participant_id = str(uuid.uuid4())
        mock_result = VerificationPromptsResult(
            check_status=AdversarialCheckStatus.COMPLETE,
            prompts=["Could you confirm your date of birth one more time?"],
            discrepancies=[{"field": "dob", "stated": "1990", "ehr": "1985"}],
        )

        with patch(
            "src.agents.adversarial.generate_verification_prompts",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_gen:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "get_verification_prompts",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "trial-42",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["check_status"] == "complete"
        assert len(data["prompts"]) == 1
        mock_gen.assert_awaited_once()


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

    async def test_missing_gcs_path_returns_422(self, app) -> None:
        """Missing gcs_path in request body returns validation error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/audio/signed-url",
                json={},
            )
        assert response.status_code == 422

    async def test_signed_url_calls_generate(self, app) -> None:
        """Endpoint delegates to generate_signed_url with correct args."""
        with patch(
            "src.api.webhooks.generate_signed_url",
            return_value="https://storage.googleapis.com/bucket/obj?sig=abc",
        ) as mock_gen:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/audio/signed-url",
                    json={"gcs_path": "conversations/conv-123/audio.webm"},
                )
        assert response.status_code == 200
        mock_gen.assert_called_once()
        call_args = mock_gen.call_args
        assert call_args[0][1] == "conversations/conv-123/audio.webm"


class TestTwilioStatusCallback:
    """Twilio status callback for CallSid capture."""

    async def test_twilio_status_updates_call_sid(self, app) -> None:
        """Form-encoded POST updates conversation with CallSid."""
        conv_id = uuid.uuid4()
        conversation = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = conversation

        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        async def override_session():
            yield session

        app.dependency_overrides[get_async_session] = override_session
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    f"/webhooks/twilio/status?conversation_id={conv_id}",
                    data={"CallSid": "CA123", "CallStatus": "in-progress"},
                )
            assert response.status_code == 200
            assert response.json()["updated"] is True
            assert conversation.twilio_call_sid == "CA123"
        finally:
            app.dependency_overrides.clear()

    async def test_twilio_status_no_conversation_id(self, app) -> None:
        """Returns updated=False when no conversation_id query param."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/twilio/status",
                data={"CallSid": "CA123", "CallStatus": "in-progress"},
            )
        assert response.status_code == 200
        assert response.json()["updated"] is False


class TestCheckGeoEligibility:
    """check_geo_eligibility server tool webhook."""

    async def test_eligible_returns_result(self, app) -> None:
        """Eligible participant returns geo result without handoff."""
        from src.shared.response_models import GeoEligibilityResult

        participant_id = str(uuid.uuid4())
        mock_result = GeoEligibilityResult(
            eligible=True, distance_km=25.0,
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.check_geo_eligibility",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.create_handoff",
                new_callable=AsyncMock,
            ) as mock_handoff,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "check_geo_eligibility",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "trial-1",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is True
        mock_handoff.assert_not_called()

    async def test_ineligible_creates_handoff(self, app) -> None:
        """Ineligible participant triggers handoff creation."""
        from src.shared.response_models import GeoEligibilityResult

        participant_id = str(uuid.uuid4())
        mock_result = GeoEligibilityResult(
            eligible=False, distance_km=150.0, max_km=80.0,
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.check_geo_eligibility",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "src.api.webhooks.create_handoff",
                new_callable=AsyncMock,
            ) as mock_handoff,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "check_geo_eligibility",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "trial-1",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is False
        mock_handoff.assert_called_once()


class TestVerifyTeachBack:
    """verify_teach_back server tool webhook."""

    async def test_passed_teach_back(self, app) -> None:
        """Successful teach-back returns passed=True."""
        from src.shared.response_models import TeachBackResult

        participant_id = str(uuid.uuid4())
        appointment_id = str(uuid.uuid4())
        mock_result = TeachBackResult(
            passed=True, attempts=1,
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.verify_teach_back",
                new_callable=AsyncMock,
                return_value=mock_result,
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
                        "tool_name": "verify_teach_back",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "appointment_id": appointment_id,
                            "date_response": "January 15th",
                            "time_response": "9 AM",
                            "location_response": "City Hospital",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["passed"] is True
        assert data["attempts"] == 1

    async def test_failed_teach_back(self, app) -> None:
        """Failed teach-back returns passed=False."""
        from src.shared.response_models import TeachBackResult

        participant_id = str(uuid.uuid4())
        appointment_id = str(uuid.uuid4())
        mock_result = TeachBackResult(
            passed=False, handoff_required=True, attempts=2,
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.verify_teach_back",
                new_callable=AsyncMock,
                return_value=mock_result,
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
                        "tool_name": "verify_teach_back",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "appointment_id": appointment_id,
                            "date_response": "Monday",
                            "time_response": "afternoon",
                            "location_response": "somewhere",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["passed"] is False
        assert data["handoff_required"] is True


class TestHoldSlot:
    """hold_slot server tool webhook."""

    async def test_hold_slot_success(self, app) -> None:
        """Successful slot hold returns held=True."""
        from src.shared.response_models import SlotHoldResult

        participant_id = str(uuid.uuid4())
        mock_result = SlotHoldResult(
            held=True, appointment_id=str(uuid.uuid4()),
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.hold_slot",
                new_callable=AsyncMock,
                return_value=mock_result,
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
                        "tool_name": "hold_slot",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "trial-1",
                            "slot_datetime": "2026-03-01T09:00:00",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["held"] is True
        assert data["appointment_id"] is not None

    async def test_hold_slot_taken(self, app) -> None:
        """Slot already taken returns held=False."""
        from src.shared.response_models import SlotHoldResult

        participant_id = str(uuid.uuid4())
        mock_result = SlotHoldResult(
            held=False, error="slot_taken",
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.hold_slot",
                new_callable=AsyncMock,
                return_value=mock_result,
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
                        "tool_name": "hold_slot",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "trial-1",
                            "slot_datetime": "2026-03-01T09:00:00",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["held"] is False
        assert data["error"] == "slot_taken"


class TestMarkCallOutcome:
    """mark_call_outcome server tool webhook."""

    async def test_mark_call_outcome_handler(self, app) -> None:
        """mark_call_outcome routes to outreach agent and returns result."""
        from src.shared.response_models import CallOutcomeResult

        participant_id = str(uuid.uuid4())
        mock_result = CallOutcomeResult(
            recorded=True,
            outcome="no_answer",
            should_retry=True,
            next_attempt=1,
        )

        with patch(
            "src.api.webhooks.mark_call_outcome",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_fn:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/elevenlabs/server-tool",
                    json={
                        "tool_name": "mark_call_outcome",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                            "trial_id": "trial-1",
                            "outcome": "no_answer",
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["recorded"] is True
        assert data["outcome"] == "no_answer"
        assert data["should_retry"] is True
        assert data["next_attempt"] == 1
        mock_fn.assert_awaited_once()


class TestMarkWrongPerson:
    """mark_wrong_person server tool webhook."""

    async def test_mark_wrong_person_success(self, app) -> None:
        """Wrong person marking returns verified=False, marked=True."""
        from src.shared.response_models import IdentityVerificationResult

        participant_id = str(uuid.uuid4())
        mock_result = IdentityVerificationResult(
            verified=False, marked=True, reason="wrong_person",
        )

        with (
            patch(
                "src.api.webhooks._enforce_pre_checks",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.api.webhooks.mark_wrong_person",
                new_callable=AsyncMock,
                return_value=mock_result,
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
                        "tool_name": "mark_wrong_person",
                        "conversation_id": "conv-123",
                        "parameters": {
                            "participant_id": participant_id,
                        },
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is False
        assert data["marked"] is True
        assert data["reason"] == "wrong_person"
