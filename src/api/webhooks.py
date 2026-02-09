"""Webhook endpoints for ElevenLabs server tools and Twilio.

ElevenLabs Server Tools call these endpoints during a conversation
when the agent needs to execute our backend tools (identity verification,
screening, scheduling, etc.).

Twilio webhooks handle DTMF digit capture for identity verification.

Architecture note: api/ imports from agents/ per the established dependency
direction: api -> agents -> services -> db -> shared. These webhooks are
the integration point between ElevenLabs server tools and our agent logic.
"""

import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.identity import detect_duplicate, verify_identity
from src.agents.screening import (
    check_hard_excludes,
    determine_eligibility,
    get_screening_criteria,
)
from src.config.settings import get_settings
from src.db.session import get_async_session
from src.services.gcs_client import (
    build_object_path,
    generate_signed_url,
    upload_audio,
)
from src.services.safety_service import run_safety_gate

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

    return await handler(session, params)


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
    return await verify_identity(
        session,
        uuid.UUID(params["participant_id"]),
        int(params["dob_year"]),
        params["zip_code"],
    )


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
    return await detect_duplicate(
        session,
        uuid.UUID(params["participant_id"]),
    )


async def _handle_get_screening_criteria(
    session: AsyncSession,
    params: dict,
) -> dict:
    """Handle trial criteria lookup server tool call.

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
    return await determine_eligibility(
        session,
        uuid.UUID(params["participant_id"]),
        params["trial_id"],
    )


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
    result = await run_safety_gate(
        params["response"],
        session,
        uuid.UUID(params["participant_id"]),
        trial_id=params.get("trial_id"),
        context=params.get("context"),
    )
    return {
        "triggered": result.triggered,
        "trigger_type": result.trigger_type,
        "severity": result.severity,
    }


TOOL_HANDLERS = {
    "verify_identity": _handle_verify_identity,
    "detect_duplicate": _handle_detect_duplicate,
    "get_screening_criteria": _handle_get_screening_criteria,
    "check_hard_excludes": _handle_check_hard_excludes,
    "determine_eligibility": _handle_determine_eligibility,
    "safety_check": _handle_safety_check,
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
    from sqlalchemy import select

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
    """Handle call completion — upload audio to GCS.

    Uploads audio recording to GCS and stores the object path
    in the conversations table.

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
