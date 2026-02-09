"""Safety service — wires safety gate to handoff_queue writes.

This service bridges the safety gate (shared/) with the database
layer (db/) to write handoff_queue entries when triggers fire.
Lives in services/ because it depends on both shared/ and db/.

When severity is HANDOFF_NOW, initiates a Twilio warm transfer
to bridge the coordinator into the active call.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.postgres import create_handoff, get_participant_trial
from src.shared.safety_gate import SafetyResult, evaluate_safety

logger = logging.getLogger(__name__)


def build_safety_callback(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None = None,
    conversation_id: uuid.UUID | None = None,
    call_sid: str | None = None,
):
    """Build a safety gate callback that writes to handoff_queue.

    When severity is HANDOFF_NOW, also initiates a Twilio warm
    transfer to bridge the coordinator into the active call.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Optional trial identifier.
        conversation_id: Optional conversation UUID.
        call_sid: Active Twilio call SID for warm transfer.

    Returns:
        Async callback compatible with OnTriggerCallback.
    """

    async def _on_trigger(result: SafetyResult) -> None:
        """Write handoff_queue entry and trigger warm transfer.

        Args:
            result: Safety gate evaluation result.
        """
        coordinator_phone = await _safe_get_coordinator(
            session, trial_id,
        )
        handoff_packet = await _safe_build_packet(
            session, participant_id, trial_id,
        )
        handoff = await create_handoff(
            session,
            participant_id=participant_id,
            reason=result.trigger_type or "unknown",
            severity=result.severity or "HANDOFF_NOW",
            conversation_id=conversation_id,
            trial_id=trial_id,
            summary=f"Safety gate: {result.trigger_type}",
            coordinator_phone=coordinator_phone,
        )
        handoff.handoff_packet = handoff_packet

        if (
            result.severity == "HANDOFF_NOW"
            and call_sid
            and coordinator_phone
        ):
            await _initiate_warm_transfer(
                call_sid, coordinator_phone,
            )

    return _on_trigger


async def _safe_get_coordinator(
    session: AsyncSession,
    trial_id: str | None,
) -> str | None:
    """Get coordinator phone, returning None on failure.

    Args:
        session: Active database session.
        trial_id: Trial identifier.

    Returns:
        Coordinator phone number or None.
    """
    try:
        return await _get_coordinator_phone(session, trial_id)
    except Exception:
        logger.debug("coordinator_phone_lookup_failed")
        return None


async def _safe_build_packet(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None,
) -> dict:
    """Build handoff packet, returning empty dict on failure.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.

    Returns:
        Handoff context dict, empty on failure.
    """
    try:
        return await _build_handoff_packet(
            session, participant_id, trial_id,
        )
    except Exception:
        logger.debug("handoff_packet_build_failed")
        return {}


async def _get_coordinator_phone(
    session: AsyncSession,
    trial_id: str | None,
) -> str | None:
    """Look up coordinator phone from trial record.

    Args:
        session: Active database session.
        trial_id: Trial identifier.

    Returns:
        Coordinator phone number or None.
    """
    if not trial_id:
        return None
    from src.db.trials import get_trial

    trial = await get_trial(session, trial_id)
    if trial is None:
        return None
    return trial.coordinator_phone


async def _build_handoff_packet(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None,
) -> dict:
    """Assemble context data for the coordinator handoff.

    Includes identity status, consent status, and screening
    responses so the coordinator has full context.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.

    Returns:
        Dict with identity, consent, and screening context.
    """
    from src.db.postgres import get_participant_by_id

    packet: dict = {}
    participant = await get_participant_by_id(session, participant_id)
    if participant:
        packet["identity_status"] = participant.identity_status
        packet["phone"] = participant.phone
        packet["name"] = f"{participant.first_name} {participant.last_name}"
        packet["consent"] = participant.consent or {}
        packet["dnc_flags"] = participant.dnc_flags or {}

    if trial_id:
        participant_trial = await get_participant_trial(
            session, participant_id, trial_id,
        )
        if participant_trial:
            packet["eligibility_status"] = (
                participant_trial.eligibility_status
            )
            packet["screening_responses"] = (
                participant_trial.screening_responses or {}
            )
            packet["pipeline_status"] = participant_trial.pipeline_status

    return packet


async def _initiate_warm_transfer(
    call_sid: str,
    coordinator_phone: str,
) -> None:
    """Initiate Twilio warm transfer to coordinator.

    Args:
        call_sid: Active Twilio call SID.
        coordinator_phone: Coordinator phone number.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning(
            "warm_transfer_skipped",
            extra={"reason": "twilio_not_configured"},
        )
        return

    from src.services.twilio_client import TwilioClient

    client = TwilioClient(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        from_number=settings.twilio_phone_number,
    )
    try:
        await client.initiate_warm_transfer(
            participant_call_sid=call_sid,
            coordinator_phone=coordinator_phone,
        )
    except Exception:
        logger.exception("warm_transfer_failed")


async def run_safety_gate(
    response: str,
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None = None,
    conversation_id: uuid.UUID | None = None,
    context: dict | None = None,
    call_sid: str | None = None,
) -> SafetyResult:
    """Run safety gate with handoff_queue callback wired.

    This is the entry point for running the safety gate with
    automatic handoff_queue writes and warm transfer on trigger.

    Args:
        response: Agent response text to check.
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Optional trial identifier.
        conversation_id: Optional conversation UUID.
        context: Optional conversation context.
        call_sid: Active Twilio call SID for warm transfer.

    Returns:
        SafetyResult with trigger status and timing.
    """
    callback = build_safety_callback(
        session,
        participant_id,
        trial_id,
        conversation_id,
        call_sid,
    )
    return await evaluate_safety(
        response,
        context,
        on_trigger=callback,
    )
