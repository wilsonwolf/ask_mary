"""Webhook endpoints for ElevenLabs server tools and Twilio.

ElevenLabs Server Tools call these endpoints during a conversation
when the agent needs to execute our backend tools (identity verification,
screening, scheduling, etc.).

Twilio webhooks handle DTMF digit capture for identity verification.

Architecture note: api/ imports from agents/ per the established dependency
direction: api -> agents -> services -> db -> shared. These webhooks are
the integration point between ElevenLabs server tools and our agent logic.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Form, Query
from pydantic import BaseModel
from sqlalchemy import select

from src.agents.comms import schedule_reminder
from src.agents.identity import detect_duplicate, mark_wrong_person, verify_identity
from src.agents.outreach import mark_call_outcome, schedule_next_outreach
from src.agents.scheduling import (
    book_appointment,
    check_geo_eligibility,
    find_available_slots,
    hold_slot,
    verify_teach_back,
)
from src.agents.screening import (
    check_hard_excludes,
    determine_eligibility,
    get_screening_criteria,
    record_screening_response,
)
from src.agents.transport import book_transport
from src.api.event_bus import broadcast_event
from src.config.settings import get_settings
from src.db.events import log_event
from src.db.models import AgentReasoning, Event
from src.db.postgres import create_handoff, get_participant_by_id, get_participant_trial
from src.db.session import get_async_session
from src.services.gcs_client import (
    build_object_path,
    generate_signed_url,
    upload_audio,
)
from src.services.safety_service import run_safety_gate
from src.shared.types import (
    Channel,
    ConversationStatus,
    Direction,
    HandoffReason,
    HandoffSeverity,
    PipelineStatus,
    Provenance,
)
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.db.models import Conversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

class ServerToolRequest(BaseModel):
    """ElevenLabs server tool webhook payload.

    Attributes:
        tool_name: Name of the tool being called.
        conversation_id: ElevenLabs conversation ID.
        parameters: Tool-specific parameters.
    """

    tool_name: str
    conversation_id: str
    parameters: dict[str, Any]


class DtmfWebhookPayload(BaseModel):
    """Twilio DTMF capture webhook payload.

    Attributes:
        CallSid: Twilio call SID.
        Digits: Captured DTMF digits.
        participant_id: Participant UUID (optional, from Twilio Studio).
        dob_year: Previously captured DOB year (optional, from Twilio Studio).
    """

    CallSid: str
    Digits: str
    participant_id: str | None = None
    dob_year: int | None = None


# --- ElevenLabs Server Tool Endpoint ---


@router.post("/elevenlabs/server-tool")
async def handle_server_tool(
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Handle ElevenLabs server tool callbacks.

    Accepts both our canonical format (tool_name + parameters dict)
    and ElevenLabs' flat webhook format (tool_name + params at top level).

    Args:
        body: Raw JSON body from ElevenLabs.
        session: Injected database session.

    Returns:
        Tool execution result.
    """
    tool_name = body.get("tool_name", "")
    conversation_id = body.get("conversation_id", "")

    # Support both nested (parameters: {}) and flat format
    if "parameters" in body and isinstance(body["parameters"], dict):
        params = body["parameters"]
    else:
        params = {k: v for k, v in body.items() if k not in ("tool_name", "conversation_id")}

    logger.info(
        "server_tool_called",
        extra={
            "tool_name": tool_name,
            "conversation_id": conversation_id,
            "param_keys": list(params.keys()),
        },
    )

    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"unknown_tool: {tool_name}"}

    params["_conversation_id"] = conversation_id

    try:
        result = await handler(session, params)
        if hasattr(result, "model_dump"):
            return result.model_dump(exclude_none=True)
        return result
    except (ValueError, KeyError, TypeError) as exc:
        logger.exception(
            "server_tool_handler_error",
            extra={"tool_name": tool_name, "error": str(exc)},
        )
        return {"error": f"Invalid parameters for {tool_name}: {exc}"}


async def _resolve_call_sid(
    session: AsyncSession,
    conversation_id: str | None,
) -> str | None:
    """Resolve Twilio call_sid from ElevenLabs conversation_id.

    Looks up the conversation record to find a stored Twilio
    call SID. For full functionality, the ElevenLabs agent must
    include twilio_call_sid in its dynamic variables so it
    appears in server tool params directly.

    Args:
        session: Active database session.
        conversation_id: ElevenLabs conversation ID string.

    Returns:
        Twilio call SID or None if not found.
    """
    if not conversation_id:
        return None
    from src.db.models import Conversation

    result = await session.execute(
        select(Conversation).where(
            Conversation.call_sid == conversation_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation and conversation.twilio_call_sid:
        return conversation.twilio_call_sid
    logger.debug(
        "call_sid_not_resolved",
        extra={"conversation_id": conversation_id},
    )
    return None


async def _resolve_conversation_row(
    session: AsyncSession,
    conversation_id_str: str | None,
) -> Conversation | None:
    """Resolve a Conversation model row from ElevenLabs conversation_id.

    Args:
        session: Active database session.
        conversation_id_str: ElevenLabs conversation ID string.

    Returns:
        Conversation model instance or None if not found.
    """
    if not conversation_id_str:
        return None
    from src.db.models import Conversation

    result = await session.execute(
        select(Conversation).where(
            Conversation.call_sid == conversation_id_str,
        )
    )
    return result.scalar_one_or_none()


async def _log_agent_reasoning(
    session: AsyncSession,
    conversation_id_str: str | None,
    participant_id: uuid.UUID,
    agent_name: str,
    reasoning_data: dict[str, Any],
) -> None:
    """Persist an agent reasoning trace to the database.

    Non-fatal: logs warning and continues if conversation row
    cannot be resolved or the insert fails.

    Args:
        session: Active database session.
        conversation_id_str: ElevenLabs conversation ID string.
        participant_id: Participant UUID.
        agent_name: Name of the agent making the decision.
        reasoning_data: Decision data to persist as JSON.
    """
    conversation = await _resolve_conversation_row(
        session,
        conversation_id_str,
    )
    if conversation is None:
        logger.debug(
            "agent_reasoning_skipped_no_conversation",
            extra={"conversation_id": conversation_id_str},
        )
        return
    reasoning = AgentReasoning(
        conversation_id=conversation.conversation_id,
        participant_id=participant_id,
        agent_name=agent_name,
        reasoning_trace=reasoning_data,
    )
    session.add(reasoning)


async def _update_pipeline_status(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None,
    new_status: str,
) -> None:
    """Update the pipeline_status on a ParticipantTrial row.

    Non-fatal: logs warning and continues if the enrollment
    record is not found.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        new_status: New PipelineStatus enum value.
    """
    if not trial_id:
        return
    participant_trial = await get_participant_trial(
        session,
        participant_id,
        trial_id,
    )
    if participant_trial is None:
        logger.debug(
            "pipeline_status_update_skipped",
            extra={
                "participant_id": str(participant_id),
                "trial_id": trial_id,
            },
        )
        return
    participant_trial.pipeline_status = new_status


async def _log_and_broadcast(
    session: AsyncSession,
    participant_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    trial_id: str | None = None,
) -> None:
    """Persist a canonical event and broadcast via WebSocket.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        event_type: Canonical event type string.
        payload: Event payload dict.
        trial_id: Related trial identifier.
    """
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(exclude_none=True)
    event = await log_event(
        session,
        participant_id=participant_id,
        event_type=event_type,
        trial_id=trial_id,
        payload=payload,
        provenance=Provenance.SYSTEM,
        channel=Channel.VOICE,
    )
    if event is None:
        return
    await broadcast_event(
        {
            "type": "event",
            "data": {
                "event_id": str(event.event_id),
                "event_type": event_type,
                "participant_id": str(participant_id),
                "trial_id": trial_id,
                "payload": payload,
                "created_at": str(event.created_at),
            },
        }
    )


async def _handle_verify_identity(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle identity verification server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, dob_year, zip_code.

    Returns:
        Identity verification result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    dob_raw = params.get("dob_year", "")
    zip_raw = params.get("zip_code", "")
    if not dob_raw or not zip_raw:
        return {
            "verified": False,
            "error": "Missing dob_year or zip_code. Ask the participant again.",
        }
    try:
        dob_year = int(dob_raw)
    except ValueError:
        return {
            "verified": False,
            "error": f"Invalid dob_year: '{dob_raw}'. Must be a 4-digit year.",
        }
    result = await verify_identity(
        session,
        participant_id,
        dob_year,
        zip_raw,
    )
    is_verified = result.get("verified", False)
    event_type = "identity_verified" if is_verified else "identity_failed"
    await _log_and_broadcast(
        session,
        participant_id,
        event_type,
        result,
        trial_id=params.get("trial_id"),
    )
    if is_verified:
        await _update_pipeline_status(
            session,
            participant_id,
            params.get("trial_id"),
            PipelineStatus.SCREENING,
        )
    return result


async def _handle_detect_duplicate(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle duplicate detection server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id.

    Returns:
        Duplicate detection result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    result = await detect_duplicate(session, participant_id)
    await _log_and_broadcast(
        session,
        participant_id,
        "duplicate_detected",
        result,
        trial_id=params.get("trial_id"),
    )
    return result


async def _handle_get_screening_criteria(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle trial criteria lookup server tool call.

    Read-only lookup — no business event persisted or broadcast.

    Args:
        session: Active database session.
        params: Tool parameters with trial_id.

    Returns:
        Trial criteria result.
    """
    return await get_screening_criteria(session, params["trial_id"])


async def _handle_check_hard_excludes(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle hard exclude check server tool call.

    Intermediate check — no business event persisted or broadcast.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id, responses.

    Returns:
        Hard exclude check result.
    """
    return await check_hard_excludes(
        session,
        uuid.UUID(params["participant_id"]),
        params["trial_id"],
        params.get("responses", {}),
    )


async def _handle_determine_eligibility(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle eligibility determination server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id.

    Returns:
        Eligibility determination result.
    """
    from src.db.trials import get_trial

    participant_id = uuid.UUID(params["participant_id"])
    trial_id = params["trial_id"]
    result = await determine_eligibility(
        session,
        participant_id,
        trial_id,
    )
    if "enrollment_not_found" in result.get("reason", ""):
        event_type = "screening_error"
    else:
        event_type = "screening_completed"
    trial = await get_trial(session, trial_id)
    trial_name = trial.trial_name if trial else trial_id
    payload = {**result, "trial_name": trial_name}
    await _log_and_broadcast(
        session,
        participant_id,
        event_type,
        payload,
        trial_id=trial_id,
    )
    is_eligible = result.get("eligible", False)
    if event_type != "screening_error":
        new_status = (
            PipelineStatus.SCHEDULING
            if is_eligible
            else PipelineStatus.INELIGIBLE
        )
        await _update_pipeline_status(
            session,
            participant_id,
            trial_id,
            new_status,
        )
    await _log_agent_reasoning(
        session,
        params.get("_conversation_id"),
        participant_id,
        "screening",
        {
            "decision": "eligibility_determination",
            "eligible": is_eligible,
            "status": result.get("status"),
            "reason": result.get("reason"),
            "trial_id": trial_id,
        },
    )
    try:
        import asyncio as _asyncio

        from src.agents.adversarial import (
            generate_verification_prompts as _gen_prompts,
        )

        _asyncio.create_task(
            _gen_prompts(session, participant_id, trial_id),
        )
    except Exception:
        logger.warning("adversarial_background_task_failed_to_start")
    return result


async def _handle_record_screening_response(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle screening response recording server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id,
            question_key, answer, provenance.

    Returns:
        Recording result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    result = await record_screening_response(
        session,
        participant_id,
        params["trial_id"],
        params["question_key"],
        params["answer"],
        params.get("provenance", "patient_stated"),
    )
    await _log_and_broadcast(
        session,
        participant_id,
        "screening_response_recorded",
        {
            "question_key": params["question_key"],
            "answer": params["answer"],
        },
        trial_id=params.get("trial_id"),
    )
    return result


async def _handle_check_availability(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle availability check server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with trial_id, preferred_dates,
            participant_id.

    Returns:
        Dict with available slots.
    """
    participant_id = uuid.UUID(params["participant_id"])
    trial_id = params["trial_id"]
    raw_dates = params.get("preferred_dates", [])
    if isinstance(raw_dates, str):
        preferred_dates = [d.strip() for d in raw_dates.split(",") if d.strip()]
    else:
        preferred_dates = raw_dates
    result = await find_available_slots(
        session,
        trial_id,
        preferred_dates,
    )
    await _log_and_broadcast(
        session,
        participant_id,
        "availability_checked",
        {"slots": result.get("slots", [])},
        trial_id=trial_id,
    )
    return result


async def _handle_book_appointment(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle appointment booking server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id,
            slot_datetime, visit_type.

    Returns:
        Appointment booking result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    trial_id = params["trial_id"]
    slot_dt = datetime.fromisoformat(params["slot_datetime"])
    result = await book_appointment(
        session,
        participant_id,
        trial_id,
        slot_dt,
        params.get("visit_type", "screening"),
    )
    if result.get("booked"):
        await _log_and_broadcast(
            session,
            participant_id,
            "appointment_booked",
            {
                "appointment_id": result.get("appointment_id"),
                "confirmation_due_at": result.get("confirmation_due_at"),
                "slot_datetime": params["slot_datetime"],
            },
            trial_id=trial_id,
        )
        await _update_pipeline_status(
            session,
            participant_id,
            trial_id,
            PipelineStatus.BOOKED,
        )
        appointment_id_str = result.get("appointment_id")
        if appointment_id_str:
            asyncio.create_task(
                _schedule_comms_cadence(
                    session,
                    participant_id,
                    uuid.UUID(appointment_id_str),
                    slot_dt,
                )
            )
    return result


COMMS_CADENCE: list[tuple[str, timedelta]] = [
    ("prep_instructions", timedelta(hours=48)),
    ("confirmation_prompt", timedelta(hours=24)),
    ("day_of_checkin", timedelta(hours=2)),
]


async def _schedule_single_reminder(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    template_id: str,
    send_at: datetime,
) -> None:
    """Enqueue one comms cadence reminder, logging errors.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        template_id: Reminder template identifier.
        send_at: Scheduled send datetime.
    """
    try:
        await schedule_reminder(
            session,
            participant_id=participant_id,
            appointment_id=appointment_id,
            template_id=template_id,
            channel=Channel.SMS,
            send_at=send_at,
        )
    except Exception:
        logger.warning(
            "comms_cadence_enqueue_failed",
            extra={"template_id": template_id},
        )


async def _schedule_comms_cadence(
    session: AsyncSession,
    participant_id: uuid.UUID,
    appointment_id: uuid.UUID,
    scheduled_at: datetime,
) -> None:
    """Enqueue prep, confirmation, and day-of reminders.

    Calculates send times relative to the appointment datetime.
    Skips reminders whose send_at is already in the past.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        appointment_id: Appointment UUID.
        scheduled_at: Appointment datetime.
    """
    now = datetime.now(UTC)
    aware_at = scheduled_at.replace(tzinfo=UTC) if scheduled_at.tzinfo is None else scheduled_at
    for template_id, offset in COMMS_CADENCE:
        send_at = aware_at - offset
        if send_at <= now:
            continue
        await _schedule_single_reminder(
            session,
            participant_id,
            appointment_id,
            template_id,
            send_at,
        )


async def _handle_book_transport(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle transport booking server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, appointment_id,
            pickup_address.

    Returns:
        Transport booking result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    result = await book_transport(
        session,
        participant_id,
        uuid.UUID(params["appointment_id"]),
        params["pickup_address"],
    )
    if result.get("booked"):
        pickup = params.get("pickup_address", "")
        zip_code = pickup.split()[-1] if pickup else ""
        await _log_and_broadcast(
            session,
            participant_id,
            "transport_booked",
            {
                "ride_id": result.get("ride_id"),
                "appointment_id": params["appointment_id"],
                "pickup_address": result.get("pickup_address", ""),
                "zip": zip_code,
                "eta": result.get("scheduled_pickup_at", ""),
            },
            trial_id=params.get("trial_id"),
        )
    return result


async def _handle_safety_check(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle safety gate check server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with response, participant_id, context.

    Returns:
        Safety gate result as dict.
    """
    participant_id = uuid.UUID(params["participant_id"])
    call_sid = params.get("call_sid")
    if not call_sid:
        call_sid = await _resolve_call_sid(
            session,
            params.get("_conversation_id"),
        )
    result = await run_safety_gate(
        params["response"],
        session,
        participant_id,
        trial_id=params.get("trial_id"),
        context=params.get("context"),
        call_sid=call_sid,
    )
    result_dict = {
        "triggered": result.triggered,
        "trigger_type": result.trigger_type,
        "severity": result.severity,
    }
    if result.triggered:
        await _log_agent_reasoning(
            session,
            params.get("_conversation_id"),
            participant_id,
            "safety_gate",
            {
                "decision": "safety_check",
                "triggered": result.triggered,
                "trigger_type": result.trigger_type,
                "severity": result.severity,
            },
        )
        await _log_and_broadcast(
            session,
            participant_id,
            "safety_triggered",
            result_dict,
            trial_id=params.get("trial_id"),
        )
    return result_dict


def _parse_bool_param(params: dict[str, Any], key: str) -> bool | None:
    """Parse a boolean parameter from string, returning None if absent.

    Args:
        params: Dictionary of tool parameters.
        key: Parameter key to look up.

    Returns:
        Parsed boolean, or None if key is absent.
    """
    value = params.get(key)
    if value is None:
        return None
    return str(value).lower() == "true"


def _build_consent_data(
    existing: dict[str, Any] | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Merge new consent fields into existing consent JSONB.

    Args:
        existing: Current consent dict from participant.
        params: Tool parameters with consent fields.

    Returns:
        Updated consent dictionary.
    """
    consent_keys = [
        "disclosed_automation",
        "consent_to_continue",
        "consent_sms",
        "consent_future_trials",
    ]
    data = dict(existing or {})
    for key in consent_keys:
        if key in params:
            data[key] = _parse_bool_param(params, key)
    return data


def _build_contactability_data(
    existing: dict[str, Any] | None,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    """Merge new contactability fields into existing JSONB.

    Args:
        existing: Current contactability dict from participant.
        params: Tool parameters with contactability fields.

    Returns:
        Updated contactability dict, or None if no fields present.
    """
    has_voicemail = "ok_to_leave_voicemail" in params
    has_name = "permitted_voicemail_name" in params
    if not has_voicemail and not has_name:
        return None
    data = dict(existing or {})
    if has_voicemail:
        data["ok_to_leave_voicemail"] = _parse_bool_param(
            params, "ok_to_leave_voicemail"
        )
    if has_name:
        data["permitted_voicemail_name"] = params["permitted_voicemail_name"]
    return data


async def _handle_capture_consent(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle consent capture server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with consent and contactability fields.

    Returns:
        Consent recording result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    participant = await get_participant_by_id(session, participant_id)

    consent_data = _build_consent_data(
        participant.consent if participant else None, params
    )
    contact_data = _build_contactability_data(
        participant.contactability if participant else None, params
    )

    if participant is not None:
        participant.consent = consent_data
        if contact_data is not None:
            participant.contactability = contact_data

    payload = {k: v for k, v in consent_data.items()}
    if contact_data is not None:
        payload.update(contact_data)
    await _log_and_broadcast(
        session,
        participant_id,
        "consent_captured",
        payload,
        trial_id=params.get("trial_id"),
    )
    return {"consent_recorded": True, **payload}


async def _handle_get_verification_prompts(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle get_verification_prompts server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id.

    Returns:
        Verification prompts result as dict.
    """
    from src.agents.adversarial import (
        generate_verification_prompts as _gen_prompts,
    )

    participant_id = uuid.UUID(params["participant_id"])
    trial_id = params["trial_id"]
    result = await _gen_prompts(
        session, participant_id, trial_id,
    )
    return {**result}


async def _handle_check_geo(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle geographic eligibility check server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id.

    Returns:
        Geographic eligibility result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    trial_id = params["trial_id"]
    result = await check_geo_eligibility(
        session, participant_id, trial_id,
    )
    if not result.get("eligible", True):
        await create_handoff(
            session,
            participant_id=participant_id,
            reason=HandoffReason.GEO_INELIGIBLE,
            severity=HandoffSeverity.CALLBACK_TICKET,
            summary=f"Participant outside max distance for trial {trial_id}",
            trial_id=trial_id,
        )
    return {**result}


async def _handle_verify_teach_back(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle teach-back verification server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, appointment_id,
            date_response, time_response, location_response.

    Returns:
        Teach-back verification result.
    """
    result = await verify_teach_back(
        session,
        uuid.UUID(params["participant_id"]),
        uuid.UUID(params["appointment_id"]),
        params["date_response"],
        params["time_response"],
        params["location_response"],
    )
    return {**result}


async def _handle_hold_slot(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle slot hold server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id,
            slot_datetime.

    Returns:
        Slot hold result.
    """
    slot_dt = datetime.fromisoformat(params["slot_datetime"])
    result = await hold_slot(
        session,
        uuid.UUID(params["participant_id"]),
        params["trial_id"],
        slot_dt,
    )
    return {**result}


async def _handle_mark_wrong_person(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle mark wrong person server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id.

    Returns:
        Identity verification result confirming wrong person marking.
    """
    participant_id = uuid.UUID(params["participant_id"])
    result = await mark_wrong_person(session, participant_id)
    return {**result}


async def _handle_mark_call_outcome(
    session: AsyncSession,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Handle mark_call_outcome server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, trial_id, outcome.

    Returns:
        Call outcome result as dict.
    """
    participant_id = uuid.UUID(params["participant_id"])
    result = await mark_call_outcome(
        session,
        participant_id,
        params["trial_id"],
        params["outcome"],
    )
    return {**result}


TOOL_HANDLERS = {
    "verify_identity": _handle_verify_identity,
    "detect_duplicate": _handle_detect_duplicate,
    "get_screening_criteria": _handle_get_screening_criteria,
    "check_hard_excludes": _handle_check_hard_excludes,
    "determine_eligibility": _handle_determine_eligibility,
    "record_screening_response": _handle_record_screening_response,
    "check_availability": _handle_check_availability,
    "book_appointment": _handle_book_appointment,
    "book_transport": _handle_book_transport,
    "safety_check": _handle_safety_check,
    "capture_consent": _handle_capture_consent,
    "get_verification_prompts": _handle_get_verification_prompts,
    "check_geo_eligibility": _handle_check_geo,
    "verify_teach_back": _handle_verify_teach_back,
    "hold_slot": _handle_hold_slot,
    "mark_wrong_person": _handle_mark_wrong_person,
    "mark_call_outcome": _handle_mark_call_outcome,
    # Aliases: ElevenLabs prompt names → existing handlers
    "record_screening_answer": _handle_record_screening_response,
    "check_eligibility": _handle_determine_eligibility,
}


async def _get_or_create_conversation(
    session: AsyncSession,
    participant_id: uuid.UUID,
    conversation_id_str: str,
    trial_id: str,
) -> Conversation:
    """Find or create a conversation row by call_sid.

    Uses the ElevenLabs conversation_id as call_sid for unique lookup.
    Creates the row if it does not exist (call-complete is often the
    first time we persist the conversation record).

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        conversation_id_str: ElevenLabs conversation ID string.
        trial_id: Trial string identifier.

    Returns:
        Conversation model instance (existing or newly created).
    """
    from src.db.models import Conversation

    result = await session.execute(
        select(Conversation).where(
            Conversation.call_sid == conversation_id_str,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is not None:
        return conversation

    conversation = Conversation(
        participant_id=participant_id,
        trial_id=trial_id,
        channel=Channel.VOICE,
        direction=Direction.OUTBOUND,
        call_sid=conversation_id_str,
        status=ConversationStatus.COMPLETED,
    )
    session.add(conversation)
    return conversation


def _normalize_transcript(raw: object) -> dict[str, Any]:
    """Normalize transcript into the shape the supervisor expects.

    Converts ElevenLabs list-of-turns format into the canonical
    ``{"entries": [...]}`` dict format with ``step`` and ``content``
    keys on each entry.

    Args:
        raw: Raw transcript — list from ElevenLabs, or already-
            normalized dict, or None.

    Returns:
        Dict with ``entries`` list.
    """
    if isinstance(raw, dict) and "entries" in raw:
        return raw
    if isinstance(raw, list):
        entries = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            entries.append(
                {
                    "step": (
                        item.get("step") or item.get("role") or item.get("label") or "unknown"
                    ),
                    "content": (
                        item.get("content") or item.get("message") or item.get("text") or ""
                    ),
                    **{k: v for k, v in item.items() if k not in ("step", "content")},
                }
            )
        return {"entries": entries}
    return {"entries": []}


async def _fetch_transcript(
    conversation_id: str,
) -> list[dict[str, Any]]:
    """Fetch conversation transcript from ElevenLabs API.

    Args:
        conversation_id: ElevenLabs conversation ID string.

    Returns:
        List of transcript turn dicts, or empty list on failure.
    """
    from src.services.elevenlabs_client import ElevenLabsClient

    settings = get_settings()
    client = ElevenLabsClient(
        api_key=settings.elevenlabs_api_key,
        agent_id=settings.elevenlabs_agent_id,
        agent_phone_number_id=settings.elevenlabs_agent_phone_number_id,
    )
    data = await client.get_conversation(conversation_id)
    return data.get("transcript", [])


async def _fetch_audio(
    conversation_id: str,
) -> bytes | None:
    """Fetch conversation audio recording from ElevenLabs API.

    Args:
        conversation_id: ElevenLabs conversation ID string.

    Returns:
        Raw audio bytes or None on failure.
    """
    from src.services.elevenlabs_client import ElevenLabsClient

    settings = get_settings()
    client = ElevenLabsClient(
        api_key=settings.elevenlabs_api_key,
        agent_id=settings.elevenlabs_agent_id,
        agent_phone_number_id=settings.elevenlabs_agent_phone_number_id,
    )
    return await client.get_conversation_audio(conversation_id)


async def _trigger_post_call_checks(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    conversation_id: uuid.UUID,
) -> None:
    """Trigger supervisor audit and adversarial recheck after call.

    Non-fatal: logs and continues if either check fails.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        conversation_id: Conversation UUID.
    """
    try:
        from src.agents.supervisor import audit_transcript

        audit = await audit_transcript(session, conversation_id)
        await _log_and_broadcast(
            session,
            participant_id,
            "supervisor_audit_completed",
            audit,
            trial_id=trial_id,
        )
        if not audit.get("compliant", True):
            await _log_and_broadcast(
                session,
                participant_id,
                "compliance_gap_detected",
                audit,
                trial_id=trial_id,
            )
    except Exception:
        logger.debug("post_call_audit_failed")

    try:
        from src.agents.supervisor import check_phi_leak

        phi_result = await check_phi_leak(session, conversation_id)
        await _log_and_broadcast(
            session,
            participant_id,
            "phi_leak_check_completed",
            phi_result,
            trial_id=trial_id,
        )
        if phi_result.get("phi_leaked", False):
            await _log_and_broadcast(
                session,
                participant_id,
                "phi_leak_detected",
                phi_result,
                trial_id=trial_id,
            )
    except Exception:
        logger.debug("phi_leak_check_failed")

    try:
        from src.agents.adversarial import schedule_recheck

        await schedule_recheck(session, participant_id, trial_id)
    except Exception:
        logger.debug("adversarial_recheck_schedule_failed")


RETRY_OUTCOMES: frozenset[str] = frozenset({
    "no_answer",
    "voicemail",
    "early_hangup",
})


async def _get_latest_outcome_event(
    session: AsyncSession,
    participant_id: uuid.UUID,
) -> Event | None:
    """Query the most recent call_outcome_recorded event.

    Args:
        session: Active database session.
        participant_id: Participant UUID.

    Returns:
        Most recent call_outcome_recorded Event, or None.
    """
    result = await session.execute(
        select(Event)
        .where(Event.participant_id == participant_id)
        .where(Event.event_type == "call_outcome_recorded")
        .order_by(Event.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _check_and_schedule_retry(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> None:
    """Check call outcome and schedule retry if needed.

    Queries the most recent call_outcome_recorded event and, if the
    outcome is retryable, schedules the next outreach attempt.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
    """
    event = await _get_latest_outcome_event(session, participant_id)
    if event is None:
        logger.warning(
            "no_call_outcome_event_found",
            extra={"participant_id": str(participant_id)},
        )
        return
    payload = event.payload or {}
    outcome = payload.get("outcome", "")
    attempt = payload.get("attempt", 0)
    if outcome not in RETRY_OUTCOMES:
        return
    await schedule_next_outreach(
        session, participant_id, trial_id, attempt,
    )
    logger.info(
        "outreach_retry_scheduled",
        extra={
            "participant_id": str(participant_id),
            "trial_id": trial_id,
            "outcome": outcome,
            "attempt": attempt,
        },
    )


# --- ElevenLabs Call Completion ---


class CallCompletionPayload(BaseModel):
    """ElevenLabs call completion webhook payload.

    Attributes:
        conversation_id: ElevenLabs conversation ID.
        participant_id: Participant UUID string (optional, looked up from DB).
        trial_id: Trial identifier (optional, looked up from DB).
    """

    conversation_id: str
    participant_id: str | None = None
    trial_id: str | None = None


@router.post("/elevenlabs/call-complete")
async def handle_call_completion(
    payload: CallCompletionPayload,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Handle call completion — fetch audio, upload to GCS, run checks.

    Fetches the audio recording from ElevenLabs API, uploads to GCS,
    stores the object path in the conversations table, fetches the
    transcript, then triggers supervisor audit and adversarial recheck.

    Args:
        payload: Call completion payload.
        session: Injected database session.

    Returns:
        Dict with upload status and GCS path.
    """
    conversation_id_str = payload.conversation_id

    # ElevenLabs may only send conversation_id — look up from DB
    participant_id_str = payload.participant_id
    trial_id = payload.trial_id
    if not participant_id_str or not trial_id:
        existing = await _resolve_conversation_row(
            session, conversation_id_str,
        )
        if existing is not None:
            if not participant_id_str:
                participant_id_str = str(existing.participant_id)
            if not trial_id:
                trial_id = existing.trial_id
    if not participant_id_str:
        logger.warning(
            "call_complete_missing_participant_id",
            extra={"conversation_id": conversation_id_str},
        )
        return {"error": "participant_id_not_resolved"}
    participant_id = uuid.UUID(participant_id_str)
    trial_id = trial_id or ""

    conversation = await _get_or_create_conversation(
        session,
        participant_id,
        conversation_id_str,
        trial_id,
    )

    gcs_path = None
    audio_bytes = await _fetch_audio(conversation_id_str)
    if audio_bytes:
        settings = get_settings()
        object_path = build_object_path(
            trial_id,
            participant_id,
            uuid.UUID(conversation_id_str) if len(conversation_id_str) == 36 else uuid.uuid4(),
        )
        result = await upload_audio(
            audio_bytes,
            settings.gcs_audio_bucket,
            object_path,
        )
        conversation.audio_gcs_path = result.gcs_path
        gcs_path = result.gcs_path
    else:
        logger.warning(
            "call_complete_audio_fetch_failed",
            extra={
                "conversation_id": conversation_id_str,
                "participant_id": str(participant_id),
            },
        )

    raw_transcript = await _fetch_transcript(conversation_id_str)
    conversation.full_transcript = _normalize_transcript(raw_transcript)

    await _trigger_post_call_checks(
        session,
        participant_id,
        trial_id,
        conversation.conversation_id,
    )

    try:
        await _check_and_schedule_retry(
            session, participant_id, trial_id,
        )
    except Exception:
        logger.warning(
            "retry_scheduling_failed",
            extra={
                "participant_id": str(participant_id),
                "trial_id": trial_id,
            },
        )

    logger.info(
        "call_completion_processed",
        extra={
            "conversation_id": conversation_id_str,
            "gcs_path": gcs_path,
            "had_audio": audio_bytes is not None,
        },
    )

    return {
        "uploaded": gcs_path is not None,
        "gcs_path": gcs_path,
    }


class SignedUrlRequest(BaseModel):
    """Request for a signed URL for audio playback.

    Attributes:
        gcs_path: GCS object path for the audio file.
    """

    gcs_path: str


@router.post("/audio/signed-url")
async def get_audio_signed_url(request: SignedUrlRequest) -> dict[str, Any]:
    """Generate a signed URL for audio playback.

    Args:
        request: Signed URL request with GCS path.

    Returns:
        Dict with signed URL and TTL.
    """
    settings = get_settings()
    url = generate_signed_url(
        settings.gcs_audio_bucket,
        request.gcs_path,
        ttl_seconds=settings.gcs_signed_url_ttl_seconds,
    )
    return {
        "url": url,
        "ttl_seconds": settings.gcs_signed_url_ttl_seconds,
    }


# --- Twilio DTMF Webhook ---


@router.post("/twilio/dtmf")
async def handle_dtmf(
    payload: DtmfWebhookPayload,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Handle Twilio DTMF digit capture for identity verification.

    Two-step flow:
    1. Capture 4 digits as DOB year → return prompt_for_zip
    2. Capture 5 digits as ZIP → if participant_id provided, verify

    Args:
        payload: DTMF webhook payload from Twilio.
        session: Injected database session.

    Returns:
        Verification result or next prompt instruction.
    """
    digits = payload.Digits
    logger.info(
        "dtmf_received",
        extra={
            "call_sid": payload.CallSid,
            "digits_length": len(digits),
        },
    )

    if len(digits) == 4:
        return {
            "action": "captured_dob_year",
            "dob_year": int(digits),
            "next": "prompt_for_zip",
        }

    if len(digits) == 5:
        if payload.participant_id and payload.dob_year:
            result = await verify_identity(
                session,
                uuid.UUID(payload.participant_id),
                payload.dob_year,
                digits,
            )
            return {"action": "verified", **result}
        return {
            "action": "captured_zip_code",
            "zip_code": digits,
            "next": "verify_identity",
        }

    return {
        "action": "invalid_input",
        "digits_length": len(digits),
        "next": "retry_prompt",
    }


@router.post("/twilio/dtmf-verify")
async def handle_dtmf_verify(
    participant_id: str,
    dob_year: int,
    zip_code: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Verify identity using captured DTMF digits.

    Called after both DOB year and ZIP code are captured.
    Routes to the identity agent's verify_identity helper.

    Args:
        participant_id: Participant UUID string.
        dob_year: 4-digit birth year from DTMF.
        zip_code: 5-digit ZIP from DTMF.
        session: Injected database session.

    Returns:
        Identity verification result.
    """
    return await verify_identity(
        session,
        uuid.UUID(participant_id),
        dob_year,
        zip_code,
    )


# --- Twilio Status Callback ---


@router.post("/twilio/status")
async def handle_twilio_status(
    call_sid: str = Form(..., alias="CallSid"),
    call_status: str = Form(..., alias="CallStatus"),
    conversation_id: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Capture Twilio CallSid and associate with conversation.

    Twilio POSTs form-encoded data (CallSid, CallStatus). The
    conversation_id is a URL query parameter (set when building
    the status_callback URL). Updates the conversation row with
    the Twilio CallSid so warm transfer can resolve it mid-call.

    Args:
        call_sid: Twilio call SID (form field).
        call_status: Twilio call status (form field).
        conversation_id: Conversation UUID from query string.
        session: Injected database session.

    Returns:
        Acknowledgement dict.
    """
    if not conversation_id:
        return {"ok": True, "updated": False}

    from src.db.models import Conversation

    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        return {"ok": True, "updated": False}

    result = await session.execute(
        select(Conversation).where(
            Conversation.conversation_id == conv_uuid,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.twilio_call_sid = call_sid
        logger.info(
            "twilio_call_sid_captured",
            extra={
                "conversation_id": conversation_id,
                "twilio_call_sid": call_sid,
                "call_status": call_status,
            },
        )
        return {"ok": True, "updated": True}

    return {"ok": True, "updated": False}
