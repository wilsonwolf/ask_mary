"""Shared input validators for the Ask Mary application."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid

from src.shared.types import Channel

_VALID_CHANNELS = {ch.value for ch in Channel if ch != Channel.SYSTEM}


def validate_phone(phone: str) -> bool:
    """Validate a phone number has at least 10 digits.

    Args:
        phone: Raw phone input.

    Returns:
        True if the phone has at least 10 digits.
    """
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10


def validate_zip_code(zip_code: str) -> bool:
    """Validate a 5-digit US ZIP code.

    Args:
        zip_code: ZIP code string.

    Returns:
        True if exactly 5 digits.
    """
    return bool(re.fullmatch(r"\d{5}", zip_code))


def validate_dob_year(year: int) -> bool:
    """Validate a date-of-birth year is reasonable.

    Args:
        year: 4-digit year.

    Returns:
        True if between 1900 and the current year (inclusive).
    """
    current_year = datetime.now().year
    return 1900 <= year <= current_year


def is_dnc_blocked(
    dnc_flags: dict | None,
    channel: str,
) -> bool:
    """Check if a participant is on the Do Not Contact list.

    Args:
        dnc_flags: JSONB DNC flags from participant record.
        channel: Communication channel to check.

    Returns:
        True if contact is blocked on the given channel.
    """
    if not dnc_flags:
        return False
    if dnc_flags.get("all_channels"):
        return True
    return bool(dnc_flags.get(channel))


def validate_channel(channel: str) -> bool:
    """Validate a communication channel.

    Args:
        channel: Channel name to validate.

    Returns:
        True if the channel is a valid outbound channel.
    """
    return channel in _VALID_CHANNELS


async def get_participant_by_id(
    session: Any,
    participant_id: uuid.UUID,
) -> Any:
    """Fetch participant by ID for gate validation.

    Patchable function reference for unit testing gate checks.
    Production wiring injects the real DB lookup at startup.

    Args:
        session: Database session object.
        participant_id: Participant UUID.

    Returns:
        Participant object.

    Raises:
        NotImplementedError: If not patched or wired.
    """
    raise NotImplementedError("Wire to DB layer at startup")


async def check_identity_gate(
    session: Any,
    participant_id: uuid.UUID,
) -> dict:
    """Check if participant identity has been verified.

    Blocks PHI sharing until identity_status == "verified".

    Args:
        session: Database session object.
        participant_id: Participant UUID.

    Returns:
        Dict with 'passed' boolean.
    """
    participant = await get_participant_by_id(session, participant_id)
    is_verified = participant.identity_status == "verified"
    return {"passed": is_verified}


async def check_disclosure_gate(
    session: Any,
    participant_id: uuid.UUID,
) -> dict:
    """Check if automation disclosure and consent were captured.

    Blocks proceeding until disclosed_automation=True AND
    consent_to_continue=True.

    Args:
        session: Database session object.
        participant_id: Participant UUID.

    Returns:
        Dict with 'passed' boolean.
    """
    participant = await get_participant_by_id(session, participant_id)
    consent = participant.consent or {}
    is_disclosed = consent.get("disclosed_automation") is True
    has_consent = consent.get("consent_to_continue") is True
    return {"passed": is_disclosed and has_consent}
