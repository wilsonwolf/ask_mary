"""Supervisor agent — post-call transcript audit and compliance check."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.models import Conversation
from src.db.postgres import get_participant_trial

REQUIRED_STEPS = ["disclosure", "consent", "identity_verified"]

PHI_KEYWORDS = [
    "date of birth",
    "diagnosis",
    "medical history",
    "test result",
    "medication",
]

VALID_PROVENANCES = {
    "patient_stated",
    "ehr",
    "coordinator",
    "system",
}


async def audit_transcript(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> dict:
    """Audit a conversation transcript for required compliance steps.

    Checks that disclosure, consent, and identity_verified steps are
    all present in the transcript.

    Args:
        session: Active database session.
        conversation_id: Conversation UUID to audit.

    Returns:
        Dict with compliant bool, risk_level, and missing_steps list.
    """
    result = await session.execute(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
        )
    )
    conversation = result.scalar_one_or_none()

    transcript = conversation.full_transcript or {}
    entries = transcript.get("entries", [])
    found_steps = {entry["step"] for entry in entries}

    missing_steps = [step for step in REQUIRED_STEPS if step not in found_steps]

    is_compliant = len(missing_steps) == 0
    risk_level = "LOW" if is_compliant else "HIGH"

    return {
        "compliant": is_compliant,
        "risk_level": risk_level,
        "missing_steps": missing_steps,
    }


async def check_phi_leak(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> dict:
    """Check for PHI keywords disclosed before identity verification.

    Scans transcript entries that occur before the identity_verified
    step for any PHI keyword matches.

    Args:
        session: Active database session.
        conversation_id: Conversation UUID to check.

    Returns:
        Dict with phi_leaked bool and details list.
    """
    result = await session.execute(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
        )
    )
    conversation = result.scalar_one_or_none()

    transcript = conversation.full_transcript or {}
    entries = transcript.get("entries", [])

    pre_identity_entries = _extract_pre_identity_entries(entries)
    details = _scan_entries_for_phi(pre_identity_entries)

    return {
        "phi_leaked": len(details) > 0,
        "details": details,
    }


def _extract_pre_identity_entries(entries: list[dict]) -> list[dict]:
    """Return transcript entries before the identity_verified step.

    Args:
        entries: List of transcript entry dicts.

    Returns:
        List of entries occurring before identity_verified.
    """
    pre_identity: list[dict] = []
    for entry in entries:
        if entry["step"] == "identity_verified":
            break
        pre_identity.append(entry)
    return pre_identity


def _scan_entries_for_phi(entries: list[dict]) -> list[dict]:
    """Scan entries for PHI keyword matches.

    Args:
        entries: List of transcript entry dicts to scan.

    Returns:
        List of detail dicts describing each PHI leak found.
    """
    details: list[dict] = []
    for entry in entries:
        content = entry.get("content", "").lower()
        for keyword in PHI_KEYWORDS:
            if keyword in content:
                details.append(
                    {
                        "step": entry["step"],
                        "keyword": keyword,
                    }
                )
    return details


async def detect_answer_inconsistencies(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> dict:
    """Detect contradictory screening answers from different sources.

    Compares answers for each screening question. When the same
    question has different answers from different provenances, it
    is flagged as inconsistent.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.

    Returns:
        Dict with inconsistencies_found bool and flagged_questions list.
    """
    participant_trial = await get_participant_trial(
        session, participant_id, trial_id,
    )

    responses = participant_trial.screening_responses or {}
    flagged_questions: list[str] = []

    for question, value in responses.items():
        if _has_inconsistent_answers(value):
            flagged_questions.append(question)

    return {
        "inconsistencies_found": len(flagged_questions) > 0,
        "flagged_questions": flagged_questions,
    }


def _has_inconsistent_answers(value: dict | list) -> bool:
    """Check if a screening response has inconsistent answers.

    Args:
        value: Single response dict or list of response dicts.

    Returns:
        True if different answers exist across entries.
    """
    if isinstance(value, list) and len(value) > 1:
        answers = {entry.get("answer") for entry in value}
        return len(answers) > 1
    return False


async def audit_provenance(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> dict:
    """Verify all screening responses have valid provenance.

    Valid provenances are: patient_stated, ehr, coordinator, system.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial identifier.

    Returns:
        Dict with all_valid bool and missing_provenance list.
    """
    participant_trial = await get_participant_trial(
        session, participant_id, trial_id,
    )

    responses = participant_trial.screening_responses or {}
    missing_provenance: list[str] = []

    for question, value in responses.items():
        if not _has_valid_provenance(value):
            missing_provenance.append(question)

    return {
        "all_valid": len(missing_provenance) == 0,
        "missing_provenance": missing_provenance,
    }


def _has_valid_provenance(value: dict | list) -> bool:
    """Check if a screening response has valid provenance.

    Args:
        value: Single response dict or list of response dicts.

    Returns:
        True if all entries have valid provenance.
    """
    if isinstance(value, list):
        return all(entry.get("provenance") in VALID_PROVENANCES for entry in value)
    return value.get("provenance") in VALID_PROVENANCES


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_audit_transcript(conversation_id: str) -> str:
    """Audit a conversation transcript for compliance steps.

    Args:
        conversation_id: Conversation UUID string.

    Returns:
        JSON string with audit status.
    """
    return f'{{"conversation_id": "{conversation_id}", "status": "requires_session"}}'


@function_tool
async def tool_check_phi_leak(conversation_id: str) -> str:
    """Check a conversation transcript for PHI leaks before identity verification.

    Args:
        conversation_id: Conversation UUID string.

    Returns:
        JSON string with PHI check status.
    """
    return f'{{"conversation_id": "{conversation_id}", "status": "requires_session"}}'


@function_tool
async def tool_detect_inconsistencies(
    participant_id: str,
    trial_id: str,
) -> str:
    """Detect inconsistent screening answers across data sources.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial identifier string.

    Returns:
        JSON string with inconsistency check status.
    """
    return (
        f'{{"participant_id": "{participant_id}", '
        f'"trial_id": "{trial_id}", "status": "requires_session"}}'
    )


@function_tool
async def tool_audit_provenance(
    participant_id: str,
    trial_id: str,
) -> str:
    """Audit provenance validity for all screening responses.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial identifier string.

    Returns:
        JSON string with provenance audit status.
    """
    return (
        f'{{"participant_id": "{participant_id}", '
        f'"trial_id": "{trial_id}", "status": "requires_session"}}'
    )


supervisor_agent = Agent(
    name="supervisor",
    instructions="""You are the supervisor agent for Ask Mary clinical trials.

Your responsibilities:
1. Audit conversation transcripts after each call
2. Compliance check: verify disclosure was given, consent captured, identity verified
3. PHI leak detection: ensure no PHI was shared before identity verification
4. Deception analysis: flag inconsistent screening answers
5. Provenance audit: verify data corrections use annotation, never overwrites
6. Write findings to audit_log in Databricks
7. If risk_level=HIGH -> alert coordinator via handoff_queue

This agent runs ASYNCHRONOUSLY after calls, not in the live conversation path.
""",
    tools=[
        tool_audit_transcript,
        tool_check_phi_leak,
        tool_detect_inconsistencies,
        tool_audit_provenance,
    ],
)
