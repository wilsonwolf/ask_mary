"""Tests for the outreach agent function tools.

Tests the internal helper functions (with mocked sessions) and verifies
the agent has proper tool registration. The internal functions are the
business logic; the @function_tool wrappers are the SDK integration layer.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.outreach import (
    assemble_call_context,
    capture_consent,
    check_dnc_before_contact,
    handle_stop_keyword,
    initiate_outbound_call,
    log_outreach_attempt,
    outreach_agent,
)


class TestOutreachAgentDefinition:
    """Outreach agent is properly configured."""

    def test_has_tools(self) -> None:
        """Outreach agent has function tools registered."""
        assert len(outreach_agent.tools) == 6

    def test_has_instructions(self) -> None:
        """Outreach agent has instructions."""
        assert outreach_agent.instructions


class TestCheckDncBeforeContact:
    """DNC pre-check before any outreach."""

    async def test_blocked_by_internal_dnc(self) -> None:
        """Returns blocked=True when internal DNC flags block channel."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {"voice": True}
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_dnc_before_contact(mock_session, uuid.uuid4(), "voice")
        assert result["blocked"] is True

    async def test_not_blocked_when_clear(self) -> None:
        """Returns blocked=False when no DNC flags."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {}
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_dnc_before_contact(mock_session, uuid.uuid4(), "voice")
        assert result["blocked"] is False

    async def test_returns_blocked_when_participant_missing(self) -> None:
        """Returns blocked=True when participant not found."""
        mock_session = AsyncMock()
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=None,
        ):
            result = await check_dnc_before_contact(mock_session, uuid.uuid4(), "voice")
        assert result["blocked"] is True


    async def test_blocked_by_twilio_opt_out(self) -> None:
        """Returns blocked=True when Twilio opt-out is active."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {}
        participant.phone = "+15035559999"

        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.outreach.TwilioClient",
            ) as mock_twilio_cls,
        ):
            mock_twilio = MagicMock()
            mock_twilio.check_dnc_status.return_value = True
            mock_twilio_cls.return_value = mock_twilio

            result = await check_dnc_before_contact(
                mock_session, uuid.uuid4(), "sms",
            )
        assert result["blocked"] is True
        assert result["reason"] == "twilio_opted_out"


class TestAssembleCallContext:
    """Pre-call context assembly."""

    async def test_returns_context_dict(self) -> None:
        """Returns participant + trial context for ElevenLabs."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.first_name = "Jane"
        participant.last_name = "Doe"
        participant.phone = "+15035559999"
        trial = MagicMock()
        trial.trial_name = "Diabetes Study A"
        trial.site_name = "OHSU"
        trial.coordinator_phone = "+15035551234"
        trial.inclusion_criteria = {"min_age": 18}
        trial.exclusion_criteria = {"pregnant": True}
        trial.visit_templates = {"screening": {"duration_min": 90}}

        with (
            patch("src.agents.outreach.get_participant_by_id", return_value=participant),
            patch("src.agents.outreach.get_trial", return_value=trial),
        ):
            context = await assemble_call_context(mock_session, uuid.uuid4(), "trial-1")
        assert context["participant_name"] == "Jane Doe"
        assert context["trial_name"] == "Diabetes Study A"
        assert context["participant_phone"] == "+15035559999"
        assert "inclusion_criteria" in context
        assert "visit_templates" in context


class TestInitiateOutboundCall:
    """Outbound call initiation via ElevenLabs."""

    async def test_calls_elevenlabs(self) -> None:
        """initiate_outbound_call calls ElevenLabs client."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.first_name = "Jane"
        participant.last_name = "Doe"
        participant.phone = "+15035559999"
        trial = MagicMock()
        trial.trial_name = "Diabetes Study A"
        trial.site_name = "OHSU"
        trial.coordinator_phone = "+15035551234"
        trial.inclusion_criteria = {}
        trial.exclusion_criteria = {}
        trial.visit_templates = {}

        mock_call_result = MagicMock()
        mock_call_result.conversation_id = "conv-123"
        mock_call_result.status = "initiated"

        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.outreach.get_trial",
                return_value=trial,
            ),
            patch(
                "src.agents.outreach.ElevenLabsClient"
            ) as mock_el_cls,
            patch("src.agents.outreach.log_event"),
        ):
            mock_el = AsyncMock()
            mock_el.initiate_outbound_call.return_value = (
                mock_call_result
            )
            mock_el_cls.return_value = mock_el

            result = await initiate_outbound_call(
                mock_session, uuid.uuid4(), "trial-1",
            )

        assert result["initiated"] is True
        assert result["conversation_id"] == "conv-123"
        mock_el.initiate_outbound_call.assert_awaited_once()


class TestCaptureConsent:
    """Consent capture after disclosure."""

    async def test_captures_consent_flags(self) -> None:
        """Records consent flags on the participant."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.consent = {}
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=participant,
        ):
            result = await capture_consent(mock_session, uuid.uuid4(), True, True)
        assert result["consent_captured"] is True


class TestHandleStopKeyword:
    """STOP keyword handling."""

    async def test_sets_dnc_flag(self) -> None:
        """STOP sets DNC flag on the channel."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {}
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=participant,
        ):
            result = await handle_stop_keyword(mock_session, uuid.uuid4(), "sms")
        assert result["dnc_applied"] is True


class TestLogOutreachAttempt:
    """Outreach attempt event logging."""

    async def test_logs_event(self) -> None:
        """Logs an outreach attempt event."""
        mock_session = AsyncMock()
        with patch("src.agents.outreach.log_event", return_value=MagicMock()) as mock_log:
            result = await log_outreach_attempt(
                mock_session,
                uuid.uuid4(),
                "trial-123",
                "voice",
                "completed",
            )
        assert result["logged"] is True
        mock_log.assert_awaited_once()
