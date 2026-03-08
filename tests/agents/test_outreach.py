"""Tests for the outreach agent function tools.

Tests the internal helper functions (with mocked sessions) and verifies
the agent has proper tool registration. The internal functions are the
business logic; the @function_tool wrappers are the SDK integration layer.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.outreach import (
    OUTREACH_CADENCE,
    assemble_call_context,
    capture_consent,
    check_dnc_before_contact,
    handle_stop_keyword,
    initiate_outbound_call,
    log_outreach_attempt,
    mark_call_outcome,
    outreach_agent,
    schedule_next_outreach,
)
from src.shared.types import Channel


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
            result = await check_dnc_before_contact(mock_session, uuid.uuid4(), Channel.VOICE)
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
            result = await check_dnc_before_contact(mock_session, uuid.uuid4(), Channel.VOICE)
        assert result["blocked"] is False

    async def test_returns_blocked_when_participant_missing(self) -> None:
        """Returns blocked=True when participant not found."""
        mock_session = AsyncMock()
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=None,
        ):
            result = await check_dnc_before_contact(mock_session, uuid.uuid4(), Channel.VOICE)
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
                mock_session,
                uuid.uuid4(),
                Channel.SMS,
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
            result = await assemble_call_context(mock_session, uuid.uuid4(), "trial-1")
        context = result["context"]
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
            patch("src.agents.outreach.ElevenLabsClient") as mock_el_cls,
            patch("src.agents.outreach.log_event"),
        ):
            mock_el = AsyncMock()
            mock_el.initiate_outbound_call.return_value = mock_call_result
            mock_el_cls.return_value = mock_el

            result = await initiate_outbound_call(
                mock_session,
                uuid.uuid4(),
                "trial-1",
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
        assert result["recorded"] is True


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
            result = await handle_stop_keyword(mock_session, uuid.uuid4(), Channel.SMS)
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
                Channel.VOICE,
                "completed",
            )
        assert result["sent"] is True
        mock_log.assert_awaited_once()


class TestScheduleNextOutreach:
    """Outreach retry scheduling with cadence-based logic."""

    async def test_first_retry_schedules_sms(self) -> None:
        """First retry after failed voice schedules SMS in 1 hour."""
        mock_session = AsyncMock()
        mock_task = MagicMock()
        mock_task.task_id = "task-abc"
        participant_id = uuid.uuid4()

        with patch(
            "src.services.cloud_tasks_client.enqueue_reminder",
            new_callable=AsyncMock,
            return_value=mock_task,
        ) as mock_enqueue:
            before = datetime.now(UTC)
            result = await schedule_next_outreach(
                mock_session, participant_id, "trial-1", 0,
            )
            after = datetime.now(UTC)

        assert result is not None
        assert result.scheduled is True
        assert result.task_id == "task-abc"
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["channel"] == "sms"
        scheduled_at = call_kwargs["send_at"]
        assert before + timedelta(hours=1) <= scheduled_at
        assert scheduled_at <= after + timedelta(hours=1)

    async def test_second_retry_schedules_voice(self) -> None:
        """Second retry schedules voice call 24 hours later."""
        mock_session = AsyncMock()
        mock_task = MagicMock()
        mock_task.task_id = "task-def"

        with patch(
            "src.services.cloud_tasks_client.enqueue_reminder",
            new_callable=AsyncMock,
            return_value=mock_task,
        ) as mock_enqueue:
            result = await schedule_next_outreach(
                mock_session, uuid.uuid4(), "trial-1", 1,
            )

        assert result is not None
        assert result.scheduled is True
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["channel"] == "voice"

    async def test_third_retry_schedules_voice_48h(self) -> None:
        """Third retry schedules voice call 48 hours later."""
        mock_session = AsyncMock()
        mock_task = MagicMock()
        mock_task.task_id = "task-ghi"

        with patch(
            "src.services.cloud_tasks_client.enqueue_reminder",
            new_callable=AsyncMock,
            return_value=mock_task,
        ) as mock_enqueue:
            result = await schedule_next_outreach(
                mock_session, uuid.uuid4(), "trial-1", 2,
            )

        assert result is not None
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["channel"] == "voice"

    async def test_fourth_retry_schedules_final_sms(self) -> None:
        """Fourth retry schedules final SMS 49 hours later."""
        mock_session = AsyncMock()
        mock_task = MagicMock()
        mock_task.task_id = "task-jkl"

        with patch(
            "src.services.cloud_tasks_client.enqueue_reminder",
            new_callable=AsyncMock,
            return_value=mock_task,
        ) as mock_enqueue:
            result = await schedule_next_outreach(
                mock_session, uuid.uuid4(), "trial-1", 3,
            )

        assert result is not None
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["channel"] == "sms"

    async def test_exceeds_max_attempts_returns_none(self) -> None:
        """Returns None when current_attempt exceeds cadence length."""
        mock_session = AsyncMock()
        result = await schedule_next_outreach(
            mock_session,
            uuid.uuid4(),
            "trial-1",
            len(OUTREACH_CADENCE),
        )
        assert result is None

    async def test_idempotency_key_includes_attempt(self) -> None:
        """Idempotency key contains participant_id and attempt number."""
        mock_session = AsyncMock()
        mock_task = MagicMock()
        mock_task.task_id = "task-xyz"
        participant_id = uuid.uuid4()

        with patch(
            "src.services.cloud_tasks_client.enqueue_reminder",
            new_callable=AsyncMock,
            return_value=mock_task,
        ) as mock_enqueue:
            await schedule_next_outreach(
                mock_session, participant_id, "trial-1", 0,
            )

        call_kwargs = mock_enqueue.call_args.kwargs
        expected_key = f"outreach-retry-{participant_id}-0"
        assert call_kwargs["idempotency_key"] == expected_key

    async def test_uses_sentinel_appointment_id(self) -> None:
        """Uses UUID(int=0) sentinel for appointment_id."""
        mock_session = AsyncMock()
        mock_task = MagicMock()
        mock_task.task_id = "task-sentinel"

        with patch(
            "src.services.cloud_tasks_client.enqueue_reminder",
            new_callable=AsyncMock,
            return_value=mock_task,
        ) as mock_enqueue:
            await schedule_next_outreach(
                mock_session, uuid.uuid4(), "trial-1", 0,
            )

        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["appointment_id"] == uuid.UUID(int=0)


class TestMarkCallOutcome:
    """Call outcome recording and retry determination."""

    async def test_mark_call_outcome_completed(self) -> None:
        """Records completed outcome, should_retry=False."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.outreach_attempt_count = 0

        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch("src.agents.outreach.log_event", return_value=MagicMock()),
        ):
            result = await mark_call_outcome(
                mock_session, uuid.uuid4(), "trial-1", "completed",
            )
        assert result["recorded"] is True
        assert result["outcome"] == "completed"
        assert result["should_retry"] is False
        assert result["next_attempt"] is None

    async def test_mark_call_outcome_no_answer_triggers_retry(self) -> None:
        """Records no_answer outcome, should_retry=True."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.outreach_attempt_count = 1

        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch("src.agents.outreach.log_event", return_value=MagicMock()),
        ):
            result = await mark_call_outcome(
                mock_session, uuid.uuid4(), "trial-1", "no_answer",
            )
        assert result["recorded"] is True
        assert result["outcome"] == "no_answer"
        assert result["should_retry"] is True
        assert result["next_attempt"] == 2

    async def test_mark_call_outcome_voicemail_triggers_retry(self) -> None:
        """Records voicemail outcome, should_retry=True."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.outreach_attempt_count = 0

        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch("src.agents.outreach.log_event", return_value=MagicMock()),
        ):
            result = await mark_call_outcome(
                mock_session, uuid.uuid4(), "trial-1", "voicemail",
            )
        assert result["recorded"] is True
        assert result["outcome"] == "voicemail"
        assert result["should_retry"] is True
        assert result["next_attempt"] == 1
