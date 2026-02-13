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

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Form, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.identity import detect_duplicate, verify_identity
from src.agents.scheduling import book_appointment, find_available_slots
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
from src.db.session import get_async_session
from src.services.gcs_client import (
    build_object_path,
    generate_signed_url,
    upload_audio,
)
from src.services.safety_service import run_safety_gate

if TYPE_CHECKING:
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
    parameters: dict


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
    request: ServerToolRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Handle ElevenLabs server tool callbacks.

    Routes tool calls to the appropriate agent helper function.
    Business-event handlers persist canonical events to the DB
    and broadcast them via WebSocket.

    Args:
        request: Server tool request payload.
        session: Injected database session.

    Returns:
        Tool execution result.
    """
    tool_name = request.tool_name
    params = request.parameters
    logger.info(
        "server_tool_called",
        extra={
            "tool_name": tool_name,
            "conversation_id": request.conversation_id,
        },
    )

    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"unknown_tool: {tool_name}"}

    params["_conversation_id"] = request.conversation_id
    return await handler(session, params)


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


async def _log_and_broadcast(
    session: AsyncSession,
    participant_id: uuid.UUID,
    event_type: str,
    payload: dict,
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
    event = await log_event(
        session,
        participant_id=participant_id,
        event_type=event_type,
        trial_id=trial_id,
        payload=payload,
        provenance="system",
        channel="voice",
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
    params: dict,
) -> dict:
    """Handle identity verification server tool call.

    Args:
        session: Active database session.
        params: Tool parameters with participant_id, dob_year, zip_code.

    Returns:
        Identity verification result.
    """
    participant_id = uuid.UUID(params["participant_id"])
    result = await verify_identity(
        session,
        participant_id,
        int(params["dob_year"]),
        params["zip_code"],
    )
    event_type = "identity_verified" if result.get("verified") else "identity_failed"
    await _log_and_broadcast(
        session,
        participant_id,
        event_type,
        result,
        trial_id=params.get("trial_id"),
    )
    return result


async def _handle_detect_duplicate(
    session: AsyncSession,
    params: dict,
) -> dict:
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
    params: dict,
) -> dict:
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
    params: dict,
) -> dict:
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
    params: dict,
) -> dict:
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
    if "error" in result:
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
    return result


async def _handle_record_screening_response(
    session: AsyncSession,
    params: dict,
) -> dict:
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
    params: dict,
) -> dict:
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
    params: dict,
) -> dict:
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
    return result


async def _handle_book_transport(
    session: AsyncSession,
    params: dict,
) -> dict:
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
    params: dict,
) -> dict:
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
        await _log_and_broadcast(
            session,
            participant_id,
            "safety_triggered",
            result_dict,
            trial_id=params.get("trial_id"),
        )
    return result_dict


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
    # Aliases: ElevenLabs prompt names → existing handlers
    "record_screening_answer": _handle_record_screening_response,
    "check_eligibility": _handle_determine_eligibility,
}


async def _get_or_create_conversation(
    session: AsyncSession,
    participant_id: uuid.UUID,
    conversation_id_str: str,
    trial_id: str,
) -> "Conversation":
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
        channel="voice",
        direction="outbound",
        call_sid=conversation_id_str,
        status="completed",
    )
    session.add(conversation)
    return conversation


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
        from src.agents.adversarial import schedule_recheck

        await schedule_recheck(session, participant_id, trial_id)
    except Exception:
        logger.debug("adversarial_recheck_schedule_failed")


# --- ElevenLabs Call Completion ---


class CallCompletionPayload(BaseModel):
    """ElevenLabs call completion webhook payload.

    Attributes:
        conversation_id: ElevenLabs conversation ID.
        participant_id: Participant UUID string.
        trial_id: Trial identifier.
        audio_data_base64: Base64-encoded audio data.
    """

    conversation_id: str
    participant_id: str
    trial_id: str
    audio_data_base64: str | None = None


@router.post("/elevenlabs/call-complete")
async def handle_call_completion(
    payload: CallCompletionPayload,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Handle call completion — upload audio, trigger post-call checks.

    Uploads audio recording to GCS, stores the object path in the
    conversations table, then triggers supervisor audit and adversarial
    recheck scheduling.

    Args:
        payload: Call completion payload.
        session: Injected database session.

    Returns:
        Dict with upload status and GCS path.
    """
    import base64

    participant_id = uuid.UUID(payload.participant_id)
    conversation_id_str = payload.conversation_id

    if not payload.audio_data_base64:
        return {"uploaded": False, "reason": "no_audio_data"}

    audio_bytes = base64.b64decode(payload.audio_data_base64)
    settings = get_settings()
    object_path = build_object_path(
        payload.trial_id,
        participant_id,
        uuid.UUID(conversation_id_str) if len(conversation_id_str) == 36 else uuid.uuid4(),
    )

    result = await upload_audio(
        audio_bytes,
        settings.gcs_audio_bucket,
        object_path,
    )

    conversation = await _get_or_create_conversation(
        session,
        participant_id,
        conversation_id_str,
        payload.trial_id,
    )
    conversation.audio_gcs_path = result.gcs_path

    await _trigger_post_call_checks(
        session,
        participant_id,
        payload.trial_id,
        conversation.conversation_id,
    )

    logger.info(
        "call_audio_uploaded",
        extra={
            "conversation_id": conversation_id_str,
            "gcs_path": result.gcs_path,
        },
    )

    return {
        "uploaded": True,
        "gcs_path": result.gcs_path,
        "bucket": result.bucket_name,
    }


class SignedUrlRequest(BaseModel):
    """Request for a signed URL for audio playback.

    Attributes:
        gcs_path: GCS object path for the audio file.
    """

    gcs_path: str


@router.post("/audio/signed-url")
async def get_audio_signed_url(request: SignedUrlRequest) -> dict:
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
) -> dict:
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
) -> dict:
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
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    conversation_id: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Capture Twilio CallSid and associate with conversation.

    Twilio POSTs form-encoded data (CallSid, CallStatus). The
    conversation_id is a URL query parameter (set when building
    the status_callback URL). Updates the conversation row with
    the Twilio CallSid so warm transfer can resolve it mid-call.

    Args:
        CallSid: Twilio call SID (form field).
        CallStatus: Twilio call status (form field).
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
        conversation.twilio_call_sid = CallSid
        logger.info(
            "twilio_call_sid_captured",
            extra={
                "conversation_id": conversation_id,
                "twilio_call_sid": CallSid,
                "call_status": CallStatus,
            },
        )
        return {"ok": True, "updated": True}

    return {"ok": True, "updated": False}
