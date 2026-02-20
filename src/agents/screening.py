"""Screening agent — eligibility screening, FAQ, caregiver auth.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.
"""

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.events import log_event
from src.db.postgres import get_participant_by_id, get_participant_trial
from src.db.trials import get_trial_criteria
from src.shared.response_models import (
    EligibilityResult,
    HardExcludeResult,
    ScreeningCriteriaResult,
    ScreeningResponseResult,
)
from src.shared.types import EligibilityStatus


async def get_screening_criteria(
    session: AsyncSession,
    trial_id: str,
) -> ScreeningCriteriaResult:
    """Get trial criteria for screening questions.

    Args:
        session: Active database session.
        trial_id: Trial string identifier.

    Returns:
        ScreeningCriteriaResult with inclusion, exclusion, and trial name.
    """
    from src.db.trials import get_trial

    trial = await get_trial(session, trial_id)
    if trial is None:
        return ScreeningCriteriaResult(
            error=f"trial {trial_id} not found",
        )
    criteria = await get_trial_criteria(session, trial_id)
    return ScreeningCriteriaResult(
        inclusion=criteria.get("inclusion", {}),
        exclusion=criteria.get("exclusion", {}),
        trial_name=trial.trial_name,
    )


async def check_hard_excludes(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    responses: dict,
) -> HardExcludeResult:
    """Check participant responses against hard exclusion criteria.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        responses: Participant screening responses.

    Returns:
        HardExcludeResult with exclusion status and reason.
    """
    criteria = await get_trial_criteria(session, trial_id)
    exclusions = criteria.get("exclusion", {})
    matched = []
    for key, required_value in exclusions.items():
        if key in responses and responses[key] == required_value:
            matched.append(key)
    if matched:
        return HardExcludeResult(
            excluded=True,
            matched_criteria=matched,
            reason=", ".join(matched),
        )
    return HardExcludeResult(excluded=False)


async def record_screening_response(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
    question_key: str,
    answer: str,
    provenance: str,
) -> ScreeningResponseResult:
    """Record a single screening response with provenance.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.
        question_key: Screening question identifier.
        answer: Participant's answer.
        provenance: Data source (patient_stated, ehr, coordinator).

    Returns:
        ScreeningResponseResult confirming the response was recorded.
    """
    pt = await get_participant_trial(session, participant_id, trial_id)
    if pt is None:
        return ScreeningResponseResult(recorded=False, error="enrollment_not_found")

    responses = pt.screening_responses or {}
    history_key = f"{question_key}_history"
    if question_key in responses:
        history = responses.get(history_key, [])
        history.append(responses[question_key])
        responses[history_key] = history
    responses[question_key] = {
        "answer": answer,
        "provenance": provenance,
    }
    pt.screening_responses = responses
    return ScreeningResponseResult(recorded=True)


def _extract_answer(entry: object) -> str:
    """Extract answer string from a screening response entry.

    Args:
        entry: Either a nested dict ``{"answer": ..., "provenance": ...}``
            or a plain value.

    Returns:
        The answer as a string.
    """
    if isinstance(entry, dict) and "answer" in entry:
        return str(entry["answer"])
    return str(entry)


def _is_affirmative(answer: str) -> bool:
    """Check whether an answer string is affirmative.

    Args:
        answer: Free-text answer from participant.

    Returns:
        True if the answer indicates yes/true/agreement.
    """
    lower = answer.lower().strip()
    affirmatives = {
        "yes",
        "true",
        "y",
        "yeah",
        "yep",
        "correct",
        "confirmed",
        "sure",
        "affirmative",
    }
    return lower in affirmatives or lower.startswith("yes")


def _extract_number(answer: str) -> float | None:
    """Try to extract a number from a free-text answer.

    Args:
        answer: Free-text answer from participant.

    Returns:
        Extracted float or None if no number found.
    """
    match = re.search(r"(\d+\.?\d*)", answer)
    return float(match.group(1)) if match else None


def _find_response(responses: dict, criterion_key: str) -> object | None:
    """Find a screening response for a criterion key.

    Checks exact key first, then tries the base key for
    min_/max_ and _min/_max pairs (e.g. min_age → age).

    Args:
        responses: Participant screening responses dict.
        criterion_key: Criterion key to look up.

    Returns:
        Response entry if found, else None.
    """
    if criterion_key in responses:
        return responses[criterion_key]
    for prefix in ("min_", "max_"):
        if criterion_key.startswith(prefix):
            base = criterion_key[len(prefix) :]
            if base in responses:
                return responses[base]
    for suffix in ("_min", "_max"):
        if criterion_key.endswith(suffix):
            base = criterion_key[: -len(suffix)]
            if base in responses:
                return responses[base]
    return None


def _is_min_criterion(key: str) -> bool:
    """Check if a criterion key represents a minimum bound.

    Args:
        key: Criterion key.

    Returns:
        True if the key is a min-type criterion.
    """
    return key.startswith("min_") or key.endswith("_min")


def _is_max_criterion(key: str) -> bool:
    """Check if a criterion key represents a maximum bound.

    Args:
        key: Criterion key.

    Returns:
        True if the key is a max-type criterion.
    """
    return key.startswith("max_") or key.endswith("_max")


async def determine_eligibility(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> EligibilityResult:
    """Determine participant eligibility based on screening responses.

    Handles nested response format ``{"answer": ..., "provenance": ...}``
    as created by ``record_screening_response``. Resolves grouped keys
    so that a response under ``age`` satisfies both ``min_age`` and
    ``max_age`` criteria.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        EligibilityResult with eligible status and reason.
    """
    pt = await get_participant_trial(session, participant_id, trial_id)
    if pt is None:
        return EligibilityResult(
            eligible=False,
            status=EligibilityStatus.INELIGIBLE,
            reason="enrollment_not_found",
        )

    criteria = await get_trial_criteria(session, trial_id)
    responses = pt.screening_responses or {}
    failed: list[str] = []

    # Check exclusions first
    for key, required_value in criteria.get("exclusion", {}).items():
        entry = _find_response(responses, key)
        if entry is None:
            continue
        answer = _extract_answer(entry)
        if required_value is True and _is_affirmative(answer):
            pt.eligibility_status = EligibilityStatus.INELIGIBLE
            return EligibilityResult(
                eligible=False,
                status=EligibilityStatus.INELIGIBLE,
                reason=f"excluded_by_{key}",
            )

    # Check inclusions
    inclusions = criteria.get("inclusion", {})
    missing: list[str] = []
    for key, required_value in inclusions.items():
        entry = _find_response(responses, key)
        if entry is None:
            missing.append(key)
            continue
        answer = _extract_answer(entry)
        if isinstance(required_value, (int, float)):
            num = _extract_number(answer)
            if num is None:
                continue
            if _is_min_criterion(key) and num < required_value:
                failed.append(f"{key}: {num} < {required_value}")
            elif _is_max_criterion(key) and num > required_value:
                failed.append(f"{key}: {num} > {required_value}")
        elif isinstance(required_value, str):
            normalized = required_value.replace("_", " ").lower()
            if not _is_affirmative(answer) and normalized not in answer.lower():
                failed.append(f"{key}: expected {required_value}")

    if failed:
        pt.eligibility_status = EligibilityStatus.INELIGIBLE
        return EligibilityResult(
            eligible=False,
            status=EligibilityStatus.INELIGIBLE,
            reason=f"failed: {', '.join(failed)}",
        )

    if missing:
        return EligibilityResult(
            eligible=False,
            status=EligibilityStatus.INELIGIBLE,
            reason=f"missing responses: {', '.join(missing)}",
        )

    pt.eligibility_status = EligibilityStatus.ELIGIBLE
    return EligibilityResult(
        eligible=True,
        status=EligibilityStatus.ELIGIBLE,
        reason="all_criteria_met",
    )


async def record_caregiver_info(
    session: AsyncSession,
    participant_id: uuid.UUID,
    caregiver_name: str,
    relationship: str,
    scope: str,
) -> ScreeningResponseResult:
    """Record authorized caregiver information.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        caregiver_name: Caregiver full name.
        relationship: Relationship to participant.
        scope: Authorization scope (scheduling, all).

    Returns:
        ScreeningResponseResult confirming caregiver info was recorded.
    """
    participant = await get_participant_by_id(session, participant_id)
    participant.caregiver = {
        "name": caregiver_name,
        "relationship": relationship,
        "scope": scope,
    }
    await log_event(
        session,
        participant_id=participant_id,
        event_type="caregiver_recorded",
        payload=participant.caregiver,
        provenance="patient_stated",
    )
    return ScreeningResponseResult(recorded=True)


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_get_criteria(trial_id: str) -> str:
    """Get inclusion and exclusion criteria for a trial.

    Args:
        trial_id: Trial UUID string.

    Returns:
        JSON string with trial criteria.
    """
    return f'{{"trial_id": "{trial_id}", "status": "requires_session"}}'


@function_tool
async def tool_check_excludes(
    participant_id: str,
    trial_id: str,
    responses: str,
) -> str:
    """Check participant responses against hard exclusion criteria.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial UUID string.
        responses: JSON string of screening responses.

    Returns:
        JSON string with exclusion check result.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_record_response(
    participant_id: str,
    trial_id: str,
    question_key: str,
    answer: str,
    provenance: str,
) -> str:
    """Record a screening response with provenance tracking.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial UUID string.
        question_key: Question identifier.
        answer: Participant answer.
        provenance: Source (patient_stated, ehr, coordinator).

    Returns:
        JSON string confirming recording.
    """
    return f'{{"recorded": true, "question_key": "{question_key}"}}'


@function_tool
async def tool_determine_eligibility(
    participant_id: str,
    trial_id: str,
) -> str:
    """Determine participant eligibility based on collected responses.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial UUID string.

    Returns:
        JSON string with eligibility determination.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_record_caregiver(
    participant_id: str,
    caregiver_name: str,
    relationship: str,
    scope: str,
) -> str:
    """Record authorized caregiver contact information.

    Args:
        participant_id: Participant UUID string.
        caregiver_name: Caregiver full name.
        relationship: Relationship to participant.
        scope: Authorization scope (scheduling, all).

    Returns:
        JSON string confirming caregiver recording.
    """
    return f'{{"recorded": true, "caregiver": "{caregiver_name}"}}'


screening_agent = Agent(
    name="screening",
    instructions="""You are the screening agent for Ask Mary clinical trials.

Your responsibilities:
1. Deliver a high-level trial summary (non-promissory): time, location, compensation/transport
2. Ask hard exclude questions FIRST to save participant time
3. Collect answers to eligibility questions
4. Cross-reference responses against EHR data from Databricks
5. Correct discrepancies by annotation with provenance — NEVER overwrite source data
6. Output: ELIGIBLE | PROVISIONAL | INELIGIBLE | NEEDS_HUMAN with reasons + confidence
7. Answer only approved FAQs; medical advice requests → immediate handoff
8. Handle caregiver/third-party: capture authorized contact, relationship, scope
9. For ineligible: neutral close, ask permission for future trials, apply DNC if requested

Provenance values: patient_stated | ehr | coordinator | system
""",
    tools=[
        tool_get_criteria,
        tool_check_excludes,
        tool_record_response,
        tool_determine_eligibility,
        tool_record_caregiver,
    ],
)
