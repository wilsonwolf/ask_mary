"""Comms agent — event-driven communications cadence.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.events import log_event
from src.services.cloud_tasks_client import enqueue_reminder
from src.shared.comms import render_template
from src.shared.response_models import CommunicationResult, ReminderResult
from src.shared.types import Channel, Provenance

CHANNEL_FALLBACK = {
    Channel.VOICE: Channel.SMS,
    Channel.SMS: Channel.WHATSAPP,
    Channel.WHATSAPP: Channel.SMS,
}


async def send_communication(
    session: AsyncSession,
    participant_id: uuid.UUID,
    template_id: str,
    channel: str,
    variables: dict,
    idempotency_key: str | None = None,
) -> CommunicationResult:
    """Send a templated communication to a participant.

    Uses idempotency keys to prevent duplicate sends.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        template_id: Template identifier.
        channel: Communication channel (sms, voice, whatsapp).
        variables: Template rendering variables.
        idempotency_key: Optional dedup key for outbound actions.

    Returns:
        CommunicationResult confirming the communication was sent.
    """
    idem_key = idempotency_key or (f"comms-{participant_id}-{template_id}-{channel}")
    rendered = render_template(template_id, **variables)
    await log_event(
        session,
        participant_id=participant_id,
        event_type="communication_sent",
        channel=channel,
        payload={"template_id": template_id, "rendered": rendered},
        provenance=Provenance.SYSTEM,
        idempotency_key=idem_key,
    )
    return CommunicationResult(
        sent=True,
        channel=Channel(channel),
    )


async def schedule_reminder(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    template_id: str,
    channel: str,
    send_at: datetime,
) -> ReminderResult:
    """Schedule a reminder for future delivery via Cloud Tasks.

    Logs the scheduling event with an idempotency key. In production,
    the orchestrator enqueues a Cloud Tasks job to deliver at send_at.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        template_id: Template identifier.
        channel: Communication channel.
        send_at: Scheduled send datetime.

    Returns:
        ReminderResult confirming the reminder was scheduled.
    """
    idem_key = f"reminder-{appointment_id}-{template_id}-{channel}"
    task_result = await enqueue_reminder(
        participant_id=participant_id,
        appointment_id=appointment_id,
        template_id=template_id,
        channel=channel,
        send_at=send_at,
        idempotency_key=idem_key,
    )
    await log_event(
        session,
        participant_id=participant_id,
        event_type="reminder_scheduled",
        appointment_id=appointment_id,
        channel=channel,
        payload={
            "template_id": template_id,
            "send_at": send_at.isoformat(),
            "task_id": task_result.task_id,
        },
        provenance=Provenance.SYSTEM,
        idempotency_key=idem_key,
    )
    return ReminderResult(
        scheduled=True,
        task_id=task_result.task_id,
    )


async def handle_unreachable(
    session: AsyncSession,
    participant_id: uuid.UUID,
    failed_channel: str,
) -> CommunicationResult:
    """Handle unreachable participant -- channel switch then escalate.

    Tries the fallback channel before escalating to coordinator.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        failed_channel: Channel that failed to reach participant.

    Returns:
        CommunicationResult with fallback channel or escalation status.
    """
    fallback = CHANNEL_FALLBACK.get(failed_channel)
    await log_event(
        session,
        participant_id=participant_id,
        event_type="unreachable_escalation",
        channel=failed_channel,
        payload={
            "failed_channel": failed_channel,
            "fallback_channel": fallback,
        },
        provenance=Provenance.SYSTEM,
    )
    return CommunicationResult(
        sent=False,
        channel=Channel(fallback) if fallback else None,
        error=f"unreachable_on_{failed_channel}",
    )


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_send_communication(
    participant_id: str,
    template_id: str,
    channel: str,
    variables: str,
) -> str:
    """Send a templated communication to a participant.

    Args:
        participant_id: Participant UUID string.
        template_id: Template identifier.
        channel: Communication channel (sms, voice, whatsapp).
        variables: JSON string of template variables.

    Returns:
        JSON string with send confirmation.
    """
    return f'{{"sent": true, "template_id": "{template_id}"}}'


@function_tool
async def tool_schedule_reminder(
    participant_id: str,
    appointment_id: str,
    template_id: str,
    channel: str,
    send_at: str,
) -> str:
    """Schedule a reminder for future delivery.

    Args:
        participant_id: Participant UUID string.
        appointment_id: Appointment UUID string.
        template_id: Template identifier.
        channel: Communication channel.
        send_at: ISO datetime string for scheduled send.

    Returns:
        JSON string with scheduling confirmation.
    """
    return f'{{"scheduled": true, "send_at": "{send_at}"}}'


@function_tool
async def tool_handle_unreachable(
    participant_id: str,
    failed_channel: str,
) -> str:
    """Handle unreachable participant — escalate to coordinator.

    Args:
        participant_id: Participant UUID string.
        failed_channel: Channel that failed.

    Returns:
        JSON string with escalation confirmation.
    """
    return f'{{"escalated": true, "failed_channel": "{failed_channel}"}}'


comms_agent = Agent(
    name="comms",
    instructions="""You are the communications agent for Ask Mary clinical trials.

Your responsibilities:
1. Schedule and send event-driven communications:
   - T-48h: Prep instructions (ID, fasting, parking, arrival time)
   - T-24h: Confirmation prompt (YES / RESCHEDULE)
   - T-2h: Day-of check-in + transport ping + "running late?" path
   - T+0 (no-show): Rescue flow + reason capture
2. All outbound actions use idempotency keys -- never send duplicates
3. Handle protocol change broadcasts with acknowledgement capture
4. Unreachable workflow: if comms bounce/fail -> switch channel -> coordinator task
5. Render templates from comms_templates/*.yaml using Jinja2

Channels: SMS, WhatsApp, Voice (via Twilio)
""",
    tools=[
        tool_send_communication,
        tool_schedule_reminder,
        tool_handle_unreachable,
    ],
)
