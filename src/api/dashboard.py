"""Dashboard REST API and WebSocket endpoint for the coordinator UI.

Provides read-only views of participants, appointments, handoffs,
conversations, events, and aggregate analytics. Also exposes a
demo trigger endpoint and a WebSocket for real-time event streaming.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.event_bus import broadcast_event, connect, disconnect
from src.db.models import (
    Appointment,
    Conversation,
    Event,
    HandoffQueue,
    Participant,
    ParticipantTrial,
)
from src.db.postgres import get_participant_by_id
from src.db.session import get_async_session
from src.db.trials import get_trial
from src.shared.types import (
    AppointmentStatus,
    Channel,
    ConversationStatus,
    Direction,
    HandoffStatus,
    Provenance,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])
ws_router = APIRouter(tags=["websocket"])


# --- Request / Response Models ---


class DemoCallRequest(BaseModel):
    """Request body for starting a demo call.

    Attributes:
        participant_id: Target participant UUID.
        trial_id: Trial to demo.
    """

    participant_id: str
    trial_id: str


class ResolveHandoffRequest(BaseModel):
    """Request body for resolving a handoff ticket.

    Attributes:
        resolution: Description of how the handoff was resolved.
        resolved_by: Name of the person who resolved it.
    """

    resolution: str
    resolved_by: str


class AssignHandoffRequest(BaseModel):
    """Request body for assigning a handoff ticket.

    Attributes:
        assigned_to: Name of the coordinator to assign to.
    """

    assigned_to: str


# --- List Endpoints ---


@router.get("/participants")
async def list_participants(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """List participants (limit 50).

    Args:
        session: Injected database session.

    Returns:
        List of participant summary dicts.
    """
    result = await session.execute(select(Participant).limit(50))
    rows = result.scalars().all()
    return [_serialize_participant(p) for p in rows]


@router.get("/participants/{participant_id}")
async def get_participant(
    participant_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get participant detail with nested related data.

    Args:
        participant_id: Participant UUID string.
        session: Injected database session.

    Returns:
        Participant detail dict with trials, conversations, appointments.
    """
    participant = await get_participant_by_id(
        session, uuid.UUID(participant_id),
    )
    if participant is None:
        return {"error": "not_found"}
    detail = _serialize_participant(participant)
    detail["trials"] = _serialize_trials(participant.trials)
    detail["conversations"] = _serialize_recent_conversations(
        participant.conversations,
    )
    detail["appointments"] = _serialize_upcoming_appointments(
        participant.appointments,
    )
    return detail


@router.get("/participants/{participant_id}/adversarial-status")
async def get_adversarial_status(
    participant_id: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Get adversarial check status for a participant.

    Args:
        participant_id: Participant UUID string.
        session: Injected database session.

    Returns:
        Adversarial check status and results.
    """
    result = await session.execute(
        select(ParticipantTrial).where(
            ParticipantTrial.participant_id == uuid.UUID(participant_id),
        )
    )
    participant_trial = result.scalars().first()
    if participant_trial is None:
        return {"check_status": "pending"}
    return _build_adversarial_response(participant_trial)


@router.get("/appointments")
async def list_appointments(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """List appointments with status.

    Args:
        session: Injected database session.

    Returns:
        List of appointment summary dicts.
    """
    result = await session.execute(select(Appointment).limit(50))
    rows = result.scalars().all()
    return [_serialize_appointment(a) for a in rows]


@router.get("/handoff-queue")
async def list_handoffs(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """List active handoff tickets.

    Args:
        session: Injected database session.

    Returns:
        List of handoff summary dicts.
    """
    result = await session.execute(select(HandoffQueue).limit(50))
    rows = result.scalars().all()
    return [_serialize_handoff(h) for h in rows]


@router.post("/handoffs/{handoff_id}/resolve")
async def resolve_handoff(
    handoff_id: str,
    request: ResolveHandoffRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Resolve a handoff ticket with resolution details.

    Args:
        handoff_id: Handoff UUID string.
        request: Resolution details and resolver name.
        session: Injected database session.

    Returns:
        Updated handoff dict with resolved status.
    """
    result = await session.execute(
        select(HandoffQueue).where(
            HandoffQueue.handoff_id == uuid.UUID(handoff_id),
        )
    )
    handoff = result.scalar_one_or_none()
    if handoff is None:
        return {"error": "handoff_not_found"}
    return _apply_resolution(handoff, request)


@router.post("/handoffs/{handoff_id}/assign")
async def assign_handoff(
    handoff_id: str,
    request: AssignHandoffRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Assign a handoff ticket to a coordinator.

    Args:
        handoff_id: Handoff UUID string.
        request: Assignment details.
        session: Injected database session.

    Returns:
        Updated handoff dict with assigned status.
    """
    result = await session.execute(
        select(HandoffQueue).where(
            HandoffQueue.handoff_id == uuid.UUID(handoff_id),
        )
    )
    handoff = result.scalar_one_or_none()
    if handoff is None:
        return {"error": "handoff_not_found"}
    handoff.assigned_to = request.assigned_to
    handoff.status = HandoffStatus.ASSIGNED
    return _serialize_handoff(handoff)


@router.get("/conversations")
async def list_conversations(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """List recent conversations.

    Args:
        session: Injected database session.

    Returns:
        List of conversation summary dicts.
    """
    result = await session.execute(select(Conversation).limit(50))
    rows = result.scalars().all()
    return [_serialize_conversation(c) for c in rows]


@router.get("/events")
async def list_events(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    """Paginated events feed.

    Args:
        limit: Max events to return.
        offset: Pagination offset.
        session: Injected database session.

    Returns:
        List of event dicts.
    """
    result = await session.execute(select(Event).offset(offset).limit(limit))
    rows = result.scalars().all()
    return [_serialize_event(e) for e in rows]


@router.get("/analytics/summary")
async def analytics_summary(
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, int]:
    """Aggregate stats from Postgres (Databricks stubbed).

    Args:
        session: Injected database session.

    Returns:
        Summary counts for dashboard widgets.
    """
    total_participants = (
        await session.execute(select(func.count(Participant.participant_id)))
    ).scalar()
    total_appointments = (
        await session.execute(select(func.count(Appointment.appointment_id)))
    ).scalar()
    open_handoffs = (
        await session.execute(
            select(func.count(HandoffQueue.handoff_id)).where(
                HandoffQueue.status == HandoffStatus.OPEN,
            )
        )
    ).scalar()
    return {
        "total_participants": total_participants or 0,
        "total_appointments": total_appointments or 0,
        "open_handoffs": open_handoffs or 0,
    }


# --- Scheduled Tasks ---


@router.get("/tasks")
async def list_pending_tasks() -> list[dict[str, object]]:
    """List all in-memory scheduled tasks with their status.

    Returns:
        List of task dicts with task_id, template_id, status, send_at.
    """
    from src.services.cloud_tasks_client import get_pending_tasks

    return await get_pending_tasks()


# --- Trial Config ---


class UpdateTrialCoordinatorRequest(BaseModel):
    """Request body for updating trial coordinator phone.

    Attributes:
        coordinator_phone: New coordinator phone number.
    """

    coordinator_phone: str


@router.patch("/trials/{trial_id}/coordinator")
async def update_trial_coordinator(
    trial_id: str,
    request: UpdateTrialCoordinatorRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Update the coordinator phone for a trial.

    Allows dashboard users to set or override the coordinator
    phone number used for warm transfers.

    Args:
        trial_id: Trial identifier.
        request: Coordinator phone update request.
        session: Injected database session.

    Returns:
        Updated trial coordinator info.
    """
    trial = await get_trial(session, trial_id)
    if trial is None:
        return {"error": "trial_not_found"}

    trial.coordinator_phone = request.coordinator_phone
    return {
        "trial_id": trial_id,
        "coordinator_phone": trial.coordinator_phone,
        "updated": True,
    }


# --- Demo Trigger ---


@router.get("/demo/config")
async def get_demo_config(
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Return demo participant and trial info for the frontend.

    Looks up the demo participant by the configured phone number
    so the frontend can use real UUIDs instead of hardcoded values.

    Args:
        session: Injected database session.

    Returns:
        Dict with participant_id and trial_id for the demo.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    phone = settings.demo_participant_phone
    trial_id = settings.demo_trial_id

    if phone:
        result = await session.execute(
            select(Participant)
            .where(
                Participant.phone == phone,
            )
            .limit(1)
        )
        participant = result.scalars().first()
    else:
        result = await session.execute(
            select(Participant)
            .join(ParticipantTrial)
            .where(ParticipantTrial.trial_id == trial_id)
            .order_by(Participant.created_at)
            .limit(1)
        )
        participant = result.scalars().first()

    if participant is None:
        return {"error": "demo participant not found"}

    return {
        "participant_id": str(participant.participant_id),
        "trial_id": trial_id,
        "participant_name": (f"{participant.first_name} {participant.last_name}"),
        "phone": participant.phone,
    }


@router.post("/demo/start-call")
async def start_demo_call(
    request: DemoCallRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Trigger an outbound demo call via ElevenLabs.

    Looks up the participant's phone number, then calls the
    ElevenLabs service to initiate an outbound conversation.

    Args:
        request: Demo call request with participant and trial.
        session: Injected database session.

    Returns:
        Call initiation result with conversation_id.
    """
    participant_uuid = uuid.UUID(request.participant_id)
    participant = await get_participant_by_id(session, participant_uuid)
    if participant is None:
        return {"error": "participant_not_found"}

    call_result = await _call_elevenlabs(
        session,
        participant,
        participant_uuid,
        request.trial_id,
    )

    if "error" in call_result:
        return call_result

    from src.db.events import log_event

    event = await log_event(
        session,
        participant_id=participant_uuid,
        event_type="outbound_call_initiated",
        trial_id=request.trial_id,
        payload={
            "conversation_id": call_result.get("conversation_id"),
            "status": call_result.get("status"),
        },
        provenance=Provenance.SYSTEM,
        channel=Channel.VOICE,
    )

    event_id = str(event.event_id) if event else str(uuid.uuid4())
    await broadcast_event(
        {
            "type": "event",
            "data": {
                "event_id": event_id,
                "event_type": "outbound_call_initiated",
                "participant_id": request.participant_id,
                "trial_id": request.trial_id,
                "payload": {"phone": participant.phone},
                "created_at": str(datetime.now(UTC)),
            },
        }
    )

    return call_result


async def _call_elevenlabs(
    session: AsyncSession,
    participant: Participant,
    participant_id: uuid.UUID,
    trial_id: str,
) -> dict[str, Any]:
    """Assemble full context and call ElevenLabs outbound API.

    Mirrors the context assembly from the outreach agent:
    trial criteria, system prompt, conversation config override.

    Args:
        session: Active database session.
        participant: Participant ORM instance.
        participant_id: Participant UUID.
        trial_id: Trial identifier.

    Returns:
        Dict with call status and conversation ID.
    """
    from src.config.settings import get_settings
    from src.services.elevenlabs_client import (
        ElevenLabsClient,
        build_conversation_config_override,
        build_dynamic_variables,
        build_system_prompt,
    )

    trial = await get_trial(session, trial_id)
    if trial is None:
        return {"error": "trial_not_found"}

    settings = get_settings()
    name = f"{participant.first_name} {participant.last_name}"

    dynamic_vars = build_dynamic_variables(
        participant_name=name,
        trial_name=trial.trial_name,
        site_name=trial.site_name or "",
        coordinator_phone=trial.coordinator_phone or "",
        participant_id=str(participant_id),
        trial_id=trial_id,
    )
    system_prompt = build_system_prompt(
        trial_name=trial.trial_name,
        site_name=trial.site_name or "",
        coordinator_phone=trial.coordinator_phone or "",
        inclusion_criteria=trial.inclusion_criteria or {},
        exclusion_criteria=trial.exclusion_criteria or {},
        visit_templates=trial.visit_templates or {},
    )
    config_override = build_conversation_config_override(
        system_prompt=system_prompt,
        first_message=(f"Hello {name}, this is Mary calling about the {trial.trial_name} study."),
    )

    from src.db.models import Conversation

    conversation = Conversation(
        participant_id=participant_id,
        trial_id=trial_id,
        channel=Channel.VOICE,
        direction=Direction.OUTBOUND,
        status=ConversationStatus.ACTIVE,
    )
    session.add(conversation)
    await session.flush()

    status_callback = None
    if settings.public_base_url:
        base = settings.public_base_url.rstrip("/")
        tracking_id = str(conversation.conversation_id)
        status_callback = f"{base}/webhooks/twilio/status?conversation_id={tracking_id}"

    client = ElevenLabsClient(
        api_key=settings.elevenlabs_api_key,
        agent_id=settings.elevenlabs_agent_id,
        agent_phone_number_id=settings.elevenlabs_agent_phone_number_id,
    )
    call_result = await client.initiate_outbound_call(
        customer_number=participant.phone,
        dynamic_variables=dynamic_vars,
        config_override=config_override,
        status_callback=status_callback,
    )

    conversation.call_sid = call_result.conversation_id
    conversation.status = ConversationStatus.ACTIVE

    return {
        "status": call_result.status,
        "conversation_id": call_result.conversation_id,
        "participant_id": str(participant_id),
        "trial_id": trial_id,
    }


# --- WebSocket ---


@ws_router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """Real-time event stream to dashboard via WebSocket.

    Args:
        websocket: Incoming WebSocket connection.
    """
    await websocket.accept()
    connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        disconnect(websocket)


# --- Serializers ---


def _serialize_participant(participant: Participant) -> dict[str, Any]:
    """Convert Participant ORM to API dict.

    Args:
        participant: Participant model instance.

    Returns:
        JSON-serializable dict.
    """
    return {
        "participant_id": str(participant.participant_id),
        "first_name": participant.first_name,
        "last_name": participant.last_name,
        "phone": participant.phone,
        "identity_status": participant.identity_status,
        "created_at": str(participant.created_at),
    }


def _serialize_appointment(appointment: Appointment) -> dict[str, Any]:
    """Convert Appointment ORM to API dict.

    Args:
        appointment: Appointment model instance.

    Returns:
        JSON-serializable dict.
    """
    return {
        "appointment_id": str(appointment.appointment_id),
        "participant_id": str(appointment.participant_id),
        "trial_id": appointment.trial_id,
        "visit_type": appointment.visit_type,
        "scheduled_at": str(appointment.scheduled_at),
        "status": appointment.status,
        "site_name": appointment.site_name,
    }


def _serialize_handoff(handoff: HandoffQueue) -> dict[str, Any]:
    """Convert HandoffQueue ORM to API dict.

    Args:
        handoff: HandoffQueue model instance.

    Returns:
        JSON-serializable dict.
    """
    return {
        "handoff_id": str(handoff.handoff_id),
        "participant_id": str(handoff.participant_id),
        "reason": handoff.reason,
        "severity": handoff.severity,
        "status": handoff.status,
        "summary": handoff.summary,
        "coordinator_phone": handoff.coordinator_phone,
        "assigned_to": handoff.assigned_to,
        "created_at": str(handoff.created_at),
    }


def _serialize_conversation(conversation: Conversation) -> dict[str, Any]:
    """Convert Conversation ORM to API dict.

    Args:
        conversation: Conversation model instance.

    Returns:
        JSON-serializable dict.
    """
    return {
        "conversation_id": str(conversation.conversation_id),
        "participant_id": str(conversation.participant_id),
        "channel": conversation.channel,
        "direction": conversation.direction,
        "status": conversation.status,
        "started_at": str(conversation.started_at),
    }


def _serialize_event(event: Event) -> dict[str, Any]:
    """Convert Event ORM to API dict.

    Args:
        event: Event model instance.

    Returns:
        JSON-serializable dict.
    """
    return {
        "event_id": str(event.event_id),
        "participant_id": str(event.participant_id),
        "event_type": event.event_type,
        "trial_id": event.trial_id,
        "payload": event.payload,
        "created_at": str(event.created_at),
    }


def _serialize_trials(trials: list[ParticipantTrial]) -> list[dict[str, Any]]:
    """Serialize trial enrollments for participant detail.

    Args:
        trials: List of ParticipantTrial ORM instances.

    Returns:
        List of trial enrollment dicts.
    """
    return [
        {
            "trial_id": pt.trial_id,
            "pipeline_status": pt.pipeline_status,
            "eligibility_status": pt.eligibility_status,
        }
        for pt in trials
    ]


def _serialize_recent_conversations(
    conversations: list[Conversation],
) -> list[dict[str, Any]]:
    """Serialize last 10 conversations for participant detail.

    Args:
        conversations: List of Conversation ORM instances.

    Returns:
        List of conversation dicts (most recent 10).
    """
    recent = sorted(
        conversations,
        key=lambda c: str(c.started_at),
        reverse=True,
    )[:10]
    return [_serialize_conversation(c) for c in recent]


def _serialize_upcoming_appointments(
    appointments: list[Appointment],
) -> list[dict[str, Any]]:
    """Serialize upcoming appointments for participant detail.

    Args:
        appointments: List of Appointment ORM instances.

    Returns:
        List of appointment dicts with non-terminal status.
    """
    active_statuses = {
        AppointmentStatus.HELD,
        AppointmentStatus.BOOKED,
        AppointmentStatus.CONFIRMED,
    }
    upcoming = [
        a for a in appointments if str(a.status) in active_statuses
    ]
    return [_serialize_appointment(a) for a in upcoming]


def _build_adversarial_response(
    participant_trial: ParticipantTrial,
) -> dict[str, Any]:
    """Build adversarial check status response.

    Args:
        participant_trial: ParticipantTrial ORM instance.

    Returns:
        Dict with check_status and optional result details.
    """
    results = participant_trial.adversarial_results
    if not results:
        return {"check_status": "pending"}
    return {"check_status": "complete", **results}


def _apply_resolution(
    handoff: HandoffQueue,
    request: ResolveHandoffRequest,
) -> dict[str, Any]:
    """Apply resolution to a handoff ticket and return response.

    Args:
        handoff: HandoffQueue ORM instance to resolve.
        request: Resolution details from the API request.

    Returns:
        Updated handoff dict with resolution fields.
    """
    handoff.status = HandoffStatus.RESOLVED
    handoff.resolved_at = datetime.now(UTC)
    result = _serialize_handoff(handoff)
    result["resolution"] = request.resolution
    result["resolved_by"] = request.resolved_by
    return result
