"""Identity agent — verifies participant identity via DOB year + ZIP.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.events import log_event
from src.db.models import Participant
from src.db.postgres import get_participant_by_id

MAX_IDENTITY_ATTEMPTS = 2


async def verify_identity(
    session: AsyncSession,
    participant_id: uuid.UUID,
    dob_year: int,
    zip_code: str,
) -> dict:
    """Verify participant identity via DOB year and ZIP code.

    Tracks attempt count. After MAX_IDENTITY_ATTEMPTS failures,
    returns handoff_required=True so the orchestrator creates a
    handoff ticket.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        dob_year: 4-digit birth year provided by participant.
        zip_code: 5-digit ZIP code provided by participant.

    Returns:
        Dict with 'verified' boolean or 'error' string.
    """
    participant = await get_participant_by_id(session, participant_id)
    if participant is None:
        return {"error": "participant_not_found"}

    expected_year = participant.date_of_birth.year
    expected_zip = participant.address_zip

    # Track attempts via contactability JSONB
    identity_data = participant.contactability or {}
    attempts = identity_data.get("identity_attempts", 0) + 1
    identity_data["identity_attempts"] = attempts
    participant.contactability = identity_data

    if dob_year == expected_year and zip_code == expected_zip:
        participant.identity_status = "verified"
        await log_event(
            session,
            participant_id=participant_id,
            event_type="identity_verified",
            provenance="patient_stated",
        )
        return {"verified": True, "attempts": attempts}

    await log_event(
        session,
        participant_id=participant_id,
        event_type="identity_failed",
        payload={"attempt": attempts},
        provenance="patient_stated",
    )

    if attempts >= MAX_IDENTITY_ATTEMPTS:
        return {
            "verified": False,
            "reason": "max_attempts_exceeded",
            "handoff_required": True,
            "attempts": attempts,
        }

    return {
        "verified": False,
        "reason": "mismatch",
        "attempts": attempts,
    }


async def detect_duplicate(
    session: AsyncSession,
    participant_id: uuid.UUID,
) -> dict:
    """Check for duplicate participants matching DOB + ZIP + phone.

    Looks for other participants with the same date_of_birth,
    address_zip, and phone as the given participant.

    Args:
        session: Active database session.
        participant_id: Participant UUID to check against.

    Returns:
        Dict with 'is_duplicate' bool and list of matching IDs.
    """
    participant = await get_participant_by_id(session, participant_id)
    if participant is None:
        return {"error": "participant_not_found"}

    result = await session.execute(
        select(Participant.participant_id).where(
            Participant.date_of_birth == participant.date_of_birth,
            Participant.address_zip == participant.address_zip,
            Participant.phone == participant.phone,
            Participant.participant_id != participant_id,
        )
    )
    duplicates = [str(row[0]) for row in result.all()]

    if duplicates:
        await log_event(
            session,
            participant_id=participant_id,
            event_type="duplicate_detected",
            payload={"duplicate_ids": duplicates},
            provenance="system",
        )

    return {
        "is_duplicate": len(duplicates) > 0,
        "duplicate_ids": duplicates,
    }


async def mark_wrong_person(
    session: AsyncSession,
    participant_id: uuid.UUID,
) -> dict:
    """Mark participant as wrong person and suppress outreach.

    Args:
        session: Active database session.
        participant_id: Participant UUID.

    Returns:
        Dict confirming the marking.
    """
    participant = await get_participant_by_id(session, participant_id)
    participant.identity_status = "wrong_person"
    flags = participant.dnc_flags or {}
    flags["all_channels"] = True
    participant.dnc_flags = flags
    await log_event(
        session,
        participant_id=participant_id,
        event_type="wrong_person_marked",
        provenance="system",
    )
    return {"marked": True}


async def update_identity_status(
    session: AsyncSession,
    participant_id: uuid.UUID,
    status: str,
) -> dict:
    """Update participant identity verification status.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        status: New identity status (unverified, verified, wrong_person).

    Returns:
        Dict confirming the update.
    """
    participant = await get_participant_by_id(session, participant_id)
    participant.identity_status = status
    return {"updated": True}


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_verify_identity(
    participant_id: str,
    dob_year: int,
    zip_code: str,
) -> str:
    """Verify participant identity using DOB year and ZIP code.

    Args:
        participant_id: Participant UUID string.
        dob_year: 4-digit birth year.
        zip_code: 5-digit ZIP code.

    Returns:
        JSON string with verification result.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_mark_wrong_person(participant_id: str) -> str:
    """Mark participant as wrong person and suppress all outreach.

    Args:
        participant_id: Participant UUID string.

    Returns:
        JSON string confirming wrong person marking.
    """
    return f'{{"participant_id": "{participant_id}", "marked": "wrong_person"}}'


@function_tool
async def tool_update_identity_status(
    participant_id: str,
    status: str,
) -> str:
    """Update participant identity verification status.

    Args:
        participant_id: Participant UUID string.
        status: New status (unverified, verified, wrong_person).

    Returns:
        JSON string confirming update.
    """
    return f'{{"participant_id": "{participant_id}", "status": "{status}"}}'


identity_agent = Agent(
    name="identity",
    instructions="""You are the identity verification agent for Ask Mary.

Your responsibilities:
1. Prompt participant for DOB year (4 digits via DTMF on voice, text on SMS)
2. Prompt participant for ZIP code (5 digits via DTMF on voice, text on SMS)
3. Validate DOB year + ZIP against the participant record in the database
4. Detect duplicates using full DOB + ZIP + phone from the DB record
5. If wrong person: mark wrong_person, suppress further outreach, do NOT disclose any details

You must NEVER share trial details, disease details, or any PHI before identity is verified.
If verification fails after 2 attempts, create a handoff ticket.
""",
    tools=[
        tool_verify_identity,
        tool_mark_wrong_person,
        tool_update_identity_status,
    ],
)
