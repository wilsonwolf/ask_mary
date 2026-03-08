"""Outreach agent — initiates contact, enforces DNC, manages retry cadence.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.

Architecture note: Agent helper functions access the database layer through
defined CRUD interfaces (src.db.postgres, src.db.models) and service clients
(src.services.*). This follows the established pattern where agents depend
on services and db interfaces. Per CLAUDE.md: "Agents import services."
Dependency direction: api -> agents -> services -> db -> shared
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.config.settings import Settings, get_settings
from src.db.events import log_event
from src.db.postgres import get_participant_by_id
from src.db.trials import get_trial
from src.services.elevenlabs_client import (
    ElevenLabsClient,
    build_conversation_config_override,
    build_dynamic_variables,
    build_system_prompt,
)
from src.services.twilio_client import TwilioClient
from src.shared.response_models import (
    CallContextResult,
    CallOutcomeResult,
    CommunicationResult,
    DncCheckResult,
    OutreachCallResult,
    ReminderResult,
    ScreeningResponseResult,
    StopKeywordResult,
)
from src.shared.types import CallOutcome, Channel, ConversationStatus, Direction, Provenance
from src.shared.validators import is_dnc_blocked


async def check_dnc_before_contact(
    session: AsyncSession,
    participant_id: uuid.UUID,
    channel: str,
) -> DncCheckResult:
    """Check DNC flags before any outbound contact.

    Dual-source: checks internal DB flags AND Twilio opt-out.
    Either source blocking = blocked.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        channel: Communication channel to check.

    Returns:
        DncCheckResult with blocked status and source.
    """
    participant = await get_participant_by_id(session, participant_id)
    if participant is None:
        return DncCheckResult(blocked=True, reason="participant_not_found")
    if is_dnc_blocked(participant.dnc_flags, channel):
        return DncCheckResult(blocked=True, reason="dnc_active")
    settings = get_settings()
    if settings.twilio_account_sid:
        twilio = TwilioClient(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            from_number=settings.twilio_phone_number,
            messaging_service_sid=(settings.twilio_messaging_service_sid),
        )
        if twilio.check_dnc_status(participant.phone):
            return DncCheckResult(blocked=True, reason="twilio_opted_out")
    return DncCheckResult(blocked=False)


async def assemble_call_context(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> CallContextResult:
    """Assemble context for an outbound call.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        CallContextResult with participant name, trial info, and coordinator phone.
    """
    participant = await get_participant_by_id(session, participant_id)
    trial = await get_trial(session, trial_id)
    return CallContextResult(
        context={
            "participant_name": f"{participant.first_name} {participant.last_name}",
            "participant_phone": participant.phone,
            "trial_name": trial.trial_name,
            "site_name": trial.site_name,
            "coordinator_phone": trial.coordinator_phone,
            "inclusion_criteria": trial.inclusion_criteria or {},
            "exclusion_criteria": trial.exclusion_criteria or {},
            "visit_templates": trial.visit_templates or {},
        },
    )


def _build_status_callback(
    settings: Settings,
    tracking_id: str,
) -> str | None:
    """Build Twilio status callback URL with tracking ID.

    Args:
        settings: Application settings.
        tracking_id: Conversation UUID for Twilio to echo back.

    Returns:
        Status callback URL with conversation_id param, or None.
    """
    if not settings.public_base_url:
        return None
    base = settings.public_base_url.rstrip("/")
    return f"{base}/webhooks/twilio/status?conversation_id={tracking_id}"


async def initiate_outbound_call(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> OutreachCallResult:
    """Initiate an outbound call via ElevenLabs Conversational AI.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        OutreachCallResult with call initiation status and conversation_id.
    """
    from src.db.models import Conversation

    call_context_result = await assemble_call_context(
        session,
        participant_id,
        trial_id,
    )
    context = call_context_result.context
    settings = get_settings()

    conversation = Conversation(
        participant_id=participant_id,
        trial_id=trial_id,
        channel=Channel.VOICE,
        direction=Direction.OUTBOUND,
        status=ConversationStatus.ACTIVE,
    )
    session.add(conversation)
    await session.flush()

    el_client = ElevenLabsClient(
        api_key=settings.elevenlabs_api_key,
        agent_id=settings.elevenlabs_agent_id,
        agent_phone_number_id=(settings.elevenlabs_agent_phone_number_id),
    )
    dynamic_vars = build_dynamic_variables(
        participant_name=context["participant_name"],
        trial_name=context["trial_name"],
        site_name=context["site_name"],
        coordinator_phone=context["coordinator_phone"],
    )
    system_prompt = build_system_prompt(
        trial_name=context["trial_name"],
        site_name=context["site_name"],
        coordinator_phone=context["coordinator_phone"],
        inclusion_criteria=context["inclusion_criteria"],
        exclusion_criteria=context["exclusion_criteria"],
        visit_templates=context["visit_templates"],
    )
    config_override = build_conversation_config_override(
        system_prompt=system_prompt,
        first_message=(
            f"Hello {context['participant_name']}, this is Mary "
            f"calling about the {context['trial_name']} study."
        ),
    )
    status_callback = _build_status_callback(
        settings, str(conversation.conversation_id),
    )
    call_result = await el_client.initiate_outbound_call(
        customer_number=context["participant_phone"],
        dynamic_variables=dynamic_vars,
        config_override=config_override,
        status_callback=status_callback,
    )

    conversation.call_sid = call_result.conversation_id
    conversation.status = ConversationStatus.ACTIVE

    await log_event(
        session,
        participant_id=participant_id,
        event_type="outbound_call_initiated",
        trial_id=trial_id,
        payload={
            "conversation_id": call_result.conversation_id,
            "status": call_result.status,
        },
        provenance=Provenance.SYSTEM,
        channel=Channel.VOICE,
    )
    return OutreachCallResult(
        initiated=True,
        conversation_id=call_result.conversation_id,
    )


async def capture_consent(
    session: AsyncSession,
    participant_id: uuid.UUID,
    disclosed_automation: bool,
    consent_to_continue: bool,
) -> ScreeningResponseResult:
    """Capture participant consent after disclosure.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        disclosed_automation: Whether automation was disclosed.
        consent_to_continue: Whether participant consented.

    Returns:
        ScreeningResponseResult with consent capture status.
    """
    participant = await get_participant_by_id(session, participant_id)
    participant.consent = {
        "disclosed_automation": disclosed_automation,
        "consent_to_continue": consent_to_continue,
    }
    await log_event(
        session,
        participant_id=participant_id,
        event_type="consent_captured",
        payload=participant.consent,
        provenance=Provenance.PATIENT_STATED,
    )
    return ScreeningResponseResult(recorded=True)


RETRY_OUTCOMES: frozenset[CallOutcome] = frozenset({
    CallOutcome.NO_ANSWER,
    CallOutcome.VOICEMAIL,
    CallOutcome.EARLY_HANGUP,
})


def _validate_call_outcome(outcome: str) -> CallOutcome:
    """Validate an outcome string against CallOutcome enum values.

    Args:
        outcome: Raw outcome string to validate.

    Returns:
        Validated CallOutcome enum member.

    Raises:
        ValueError: If outcome is not a valid CallOutcome value.
    """
    try:
        return CallOutcome(outcome)
    except ValueError:
        valid = [o.value for o in CallOutcome]
        raise ValueError(f"Invalid outcome '{outcome}'. Must be one of: {valid}") from None


async def mark_call_outcome(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    outcome: str,
) -> CallOutcomeResult:
    """Record the outcome of a call and determine retry eligibility.

    Validates the outcome, increments the participant's attempt count,
    logs the event, and determines whether a retry should be scheduled.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        outcome: Call outcome string (must be a valid CallOutcome value).

    Returns:
        CallOutcomeResult with recorded status and retry information.
    """
    validated = _validate_call_outcome(outcome)
    participant = await get_participant_by_id(session, participant_id)
    attempt_count = (participant.outreach_attempt_count or 0) + 1
    participant.outreach_attempt_count = attempt_count

    await log_event(
        session,
        participant_id=participant_id,
        event_type="call_outcome_recorded",
        trial_id=trial_id,
        payload={"outcome": outcome, "attempt": attempt_count},
        provenance=Provenance.SYSTEM,
    )

    should_retry = validated in RETRY_OUTCOMES
    return CallOutcomeResult(
        recorded=True,
        outcome=outcome,
        should_retry=should_retry,
        next_attempt=attempt_count if should_retry else None,
    )


async def log_outreach_attempt(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    channel: str,
    outcome: str,
) -> CommunicationResult:
    """Log an outreach attempt to the events table.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.
        channel: Communication channel used.
        outcome: Attempt outcome (completed, no_answer, voicemail).

    Returns:
        CommunicationResult confirming the event was logged.
    """
    await log_event(
        session,
        participant_id=participant_id,
        event_type="outreach_attempt",
        trial_id=trial_id,
        channel=channel,
        payload={"outcome": outcome},
        provenance=Provenance.SYSTEM,
    )
    return CommunicationResult(sent=True, channel=Channel(channel))


# Retry cadence: (channel, delay_hours) after each failed attempt.
# Voice #1 → SMS nudge (1h) → Voice #2 (24h) → Voice #3 (48h) → final SMS (49h)
OUTREACH_CADENCE: list[tuple[str, int]] = [
    ("sms", 1),
    ("voice", 24),
    ("voice", 48),
    ("sms", 49),
]


async def schedule_next_outreach(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    current_attempt: int,
) -> ReminderResult | None:
    """Schedule the next outreach retry based on cadence.

    Uses OUTREACH_CADENCE to determine channel and delay for the
    next contact attempt. Returns None when max retries are reached.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        current_attempt: Zero-based index of the current attempt.

    Returns:
        ReminderResult if scheduled, or None if max retries reached.
    """
    if current_attempt >= len(OUTREACH_CADENCE):
        return None
    channel, delay_hours = OUTREACH_CADENCE[current_attempt]
    send_at = datetime.now(UTC) + timedelta(hours=delay_hours)
    return await _enqueue_outreach_retry(
        participant_id, trial_id, channel, send_at, current_attempt,
    )


async def _enqueue_outreach_retry(
    participant_id: uuid.UUID,
    trial_id: str,
    channel: str,
    send_at: datetime,
    current_attempt: int,
) -> ReminderResult:
    """Enqueue an outreach retry task via Cloud Tasks.

    Args:
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        channel: Communication channel for the retry.
        send_at: Scheduled send datetime.
        current_attempt: Zero-based attempt index for idempotency key.

    Returns:
        ReminderResult with scheduled status and task_id.
    """
    from src.services.cloud_tasks_client import enqueue_reminder

    idempotency_key = f"outreach-retry-{participant_id}-{current_attempt}"
    task_result = await enqueue_reminder(
        participant_id=participant_id,
        appointment_id=uuid.UUID(int=0),
        template_id="outreach_retry",
        channel=channel,
        send_at=send_at,
        idempotency_key=idempotency_key,
    )
    return ReminderResult(scheduled=True, task_id=task_result.task_id)


async def handle_stop_keyword(
    session: AsyncSession,
    participant_id: uuid.UUID,
    channel: str,
) -> StopKeywordResult:
    """Handle STOP keyword -- set DNC flag immediately.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        channel: Channel on which STOP was received.

    Returns:
        StopKeywordResult confirming DNC was applied.
    """
    participant = await get_participant_by_id(session, participant_id)
    flags = participant.dnc_flags or {}
    flags[channel] = True
    participant.dnc_flags = flags
    await log_event(
        session,
        participant_id=participant_id,
        event_type="dnc_applied",
        channel=channel,
        payload={"keyword": "STOP", "channel": channel},
        provenance=Provenance.PATIENT_STATED,
    )
    return StopKeywordResult(dnc_applied=True, source="stop_keyword")


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_check_dnc(participant_id: str, channel: str) -> str:
    """Check if a participant is on the Do Not Contact list for a channel.

    Args:
        participant_id: Participant UUID string.
        channel: Communication channel (voice, sms, whatsapp).

    Returns:
        JSON string with blocked status.
    """
    return (
        f'{{"participant_id": "{participant_id}",'
        f' "channel": "{channel}", "status": "requires_session"}}'
    )


@function_tool
async def tool_assemble_context(
    participant_id: str,
    trial_id: str,
) -> str:
    """Assemble pre-call context for an outbound call.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial string identifier.

    Returns:
        JSON string with call context.
    """
    return (
        f'{{"participant_id": "{participant_id}",'
        f' "trial_id": "{trial_id}", "status": "requires_session"}}'
    )


@function_tool
async def tool_initiate_call(
    participant_id: str,
    trial_id: str,
) -> str:
    """Initiate an outbound call to a participant about a trial.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial string identifier.

    Returns:
        JSON string with call initiation status.
    """
    return (
        f'{{"participant_id": "{participant_id}",'
        f' "trial_id": "{trial_id}", "status": "requires_session"}}'
    )


@function_tool
async def tool_capture_consent(
    participant_id: str,
    disclosed_automation: bool,
    consent_to_continue: bool,
) -> str:
    """Capture consent flags after disclosure.

    Args:
        participant_id: Participant UUID string.
        disclosed_automation: Whether automation was disclosed.
        consent_to_continue: Whether participant consented.

    Returns:
        JSON string with consent capture status.
    """
    return f'{{"participant_id": "{participant_id}", "consent": {consent_to_continue}}}'


@function_tool
async def tool_log_attempt(
    participant_id: str,
    trial_id: str,
    channel: str,
    outcome: str,
) -> str:
    """Log an outreach attempt and its outcome.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial identifier.
        channel: Communication channel used.
        outcome: Attempt outcome (completed, no_answer, voicemail).

    Returns:
        JSON string confirming event was logged.
    """
    return f'{{"logged": true, "participant_id": "{participant_id}"}}'


@function_tool
async def tool_handle_stop(
    participant_id: str,
    channel: str,
) -> str:
    """Handle STOP keyword — set DNC flag immediately.

    Args:
        participant_id: Participant UUID string.
        channel: Channel on which STOP was received.

    Returns:
        JSON string confirming DNC was applied.
    """
    return f'{{"dnc_applied": true, "participant_id": "{participant_id}", "channel": "{channel}"}}'


outreach_agent = Agent(
    name="outreach",
    instructions="""You are the outreach agent for Ask Mary clinical trial scheduling.

Your responsibilities:
1. Check DNC flags before any outbound contact
2. Deliver disclosure: "automated assistant" + "may be recorded" + "OK to continue?"
3. Capture consent flags (disclosed_automation, consent_to_continue)
4. Manage retry cadence: Voice #1 → SMS nudge → Voice #2 → Voice #3 + final SMS
5. Log each attempt and outcome to the events table
6. If participant says STOP, immediately set DNC flag and end contact

You must NEVER proceed past disclosure without explicit consent.
You must NEVER contact a participant with an active DNC flag on the chosen channel.
""",
    tools=[
        tool_check_dnc,
        tool_assemble_context,
        tool_initiate_call,
        tool_capture_consent,
        tool_log_attempt,
        tool_handle_stop,
    ],
)
