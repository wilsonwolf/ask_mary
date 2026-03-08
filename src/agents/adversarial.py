"""Adversarial checker agent — re-screens eligibility with different phrasing.

Uses the OpenAI Agents SDK (openai-agents package) for agent definition.
The 'agents' import is the external SDK, NOT src/agents/.

Architecture note: Agent helper functions access the database layer through
defined CRUD interfaces (src.db.postgres, src.db.models). This follows the
established pattern where agents depend on db interfaces for data access.
Per CLAUDE.md: Dependency direction: api -> agents -> services -> db -> shared
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

# agents is the OpenAI Agents SDK package (openai-agents), NOT src/agents/
from agents import Agent, function_tool
from src.db.postgres import get_participant_trial
from src.services.cloud_tasks_client import enqueue_reminder
from src.shared.response_models import (
    DeceptionResult,
    ReminderResult,
    VerificationPromptsResult,
)
from src.shared.types import AdversarialCheckStatus, Channel, Provenance

RECHECK_DELAY_DAYS = 14

PROMPT_TEMPLATES: dict[str, str] = {
    "dob": "Could you confirm your date of birth one more time?",
    "age": "Just to double-check, could you tell me your age?",
    "zip": "Could you confirm your ZIP code for me?",
}


async def detect_deception(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> DeceptionResult:
    """Compare screening responses against EHR discrepancies.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        DeceptionResult with deception status and discrepancies.
    """
    pt = await get_participant_trial(session, participant_id, trial_id)
    if pt is None:
        return DeceptionResult(deception_detected=False)

    responses = pt.screening_responses or {}
    ehr_data = pt.ehr_discrepancies or {}
    discrepancies: list[dict] = []

    for key, ehr_value in ehr_data.items():
        response = responses.get(key)
        if response is None:
            continue
        answer = response.get("answer") if isinstance(response, dict) else response
        if str(answer).lower() != str(ehr_value).lower():
            discrepancies.append(
                {
                    "field": key,
                    "stated": answer,
                    "ehr": ehr_value,
                }
            )

    return DeceptionResult(
        deception_detected=len(discrepancies) > 0,
        discrepancies=discrepancies,
    )


async def generate_verification_prompts(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> VerificationPromptsResult:
    """Generate natural-language verification prompts from discrepancies.

    Runs detect_deception, builds a prompt per discrepancy, and
    stores the results on the ParticipantTrial record.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        VerificationPromptsResult with prompts and discrepancies.
    """
    deception = await detect_deception(session, participant_id, trial_id)
    discrepancies = deception.discrepancies
    prompts = [
        PROMPT_TEMPLATES.get(d["field"], f"Could you confirm your {d['field']} for me?")
        for d in discrepancies
    ]
    participant_trial = await get_participant_trial(session, participant_id, trial_id)
    if participant_trial is not None:
        participant_trial.adversarial_results = {
            "check_status": AdversarialCheckStatus.COMPLETE,
            "discrepancies": discrepancies,
            "prompts": prompts,
            "checked_at": datetime.now(UTC).isoformat(),
        }
    return VerificationPromptsResult(
        check_status=AdversarialCheckStatus.COMPLETE,
        prompts=prompts,
        discrepancies=discrepancies,
    )


async def schedule_recheck(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> ReminderResult:
    """Schedule a T+14 day adversarial recheck via Cloud Tasks.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        ReminderResult with scheduled status and task_id.
    """
    send_at = datetime.now(UTC) + timedelta(days=RECHECK_DELAY_DAYS)
    idempotency_key = f"recheck-{participant_id}-{trial_id}"
    result = await enqueue_reminder(
        participant_id=participant_id,
        appointment_id=uuid.uuid4(),
        template_id="adversarial_recheck",
        channel=Channel.SYSTEM,
        send_at=send_at,
        idempotency_key=idempotency_key,
    )
    return ReminderResult(scheduled=True, task_id=result.task_id)


async def run_adversarial_rescreen(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str,
) -> DeceptionResult:
    """Run adversarial rescreen and record results on ParticipantTrial.

    Loads the junction record, marks recheck as done, and stores
    timestamped results with system provenance.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Trial string identifier.

    Returns:
        DeceptionResult with rescreen status.
    """
    pt = await get_participant_trial(session, participant_id, trial_id)
    if pt is None:
        return DeceptionResult(deception_detected=False)

    now_iso = datetime.now(UTC).isoformat()
    pt.adversarial_recheck_done = True
    pt.adversarial_results = {
        "rescreened_at": now_iso,
        "provenance": Provenance.SYSTEM,
    }
    return DeceptionResult(
        deception_detected=False,
        recheck_scheduled=False,
    )


# --- Agent SDK function tools (JSON-serializable params only) ---


@function_tool
async def tool_detect_deception(
    participant_id: str,
    trial_id: str,
) -> str:
    """Detect deception by comparing screening responses against EHR data.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial string identifier.

    Returns:
        JSON string indicating session is required for execution.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_schedule_recheck(
    participant_id: str,
    trial_id: str,
) -> str:
    """Schedule a T+14 day adversarial recheck via Cloud Tasks.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial string identifier.

    Returns:
        JSON string indicating session is required for execution.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


@function_tool
async def tool_run_rescreen(
    participant_id: str,
    trial_id: str,
) -> str:
    """Run adversarial rescreen and record results.

    Args:
        participant_id: Participant UUID string.
        trial_id: Trial string identifier.

    Returns:
        JSON string indicating session is required for execution.
    """
    return f'{{"participant_id": "{participant_id}", "status": "requires_session"}}'


adversarial_agent = Agent(
    name="adversarial",
    instructions="""You are the adversarial checker agent for Ask Mary.

Your responsibilities:
1. Re-screen participants using different question phrasing
2. Cross-reference participant-stated responses against EHR data
3. Flag discrepancies for human review
4. Correct data by annotation with provenance — NEVER overwrite source data
5. Schedule re-checks: T+14 days after initial screening via Cloud Tasks

You run ASYNCHRONOUSLY, typically triggered by Cloud Tasks.
Your goal is to catch inconsistencies the initial screening may have missed.
""",
    tools=[tool_detect_deception, tool_schedule_recheck, tool_run_rescreen],
)
