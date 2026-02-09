"""Safety service — wires safety gate to handoff_queue writes.

This service bridges the safety gate (shared/) with the database
layer (db/) to write handoff_queue entries when triggers fire.
Lives in services/ because it depends on both shared/ and db/.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.postgres import create_handoff
from src.shared.safety_gate import SafetyResult, evaluate_safety


def build_safety_callback(
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None = None,
    conversation_id: uuid.UUID | None = None,
):
    """Build a safety gate callback that writes to handoff_queue.

    Args:
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Optional trial identifier.
        conversation_id: Optional conversation UUID.

    Returns:
        Async callback compatible with OnTriggerCallback.
    """

    async def _on_trigger(result: SafetyResult) -> None:
        """Write handoff_queue entry when safety gate fires.

        Args:
            result: Safety gate evaluation result.
        """
        await create_handoff(
            session,
            participant_id=participant_id,
            reason=result.trigger_type or "unknown",
            severity=result.severity or "HANDOFF_NOW",
            conversation_id=conversation_id,
            trial_id=trial_id,
            summary=f"Safety gate: {result.trigger_type}",
        )

    return _on_trigger


async def run_safety_gate(
    response: str,
    session: AsyncSession,
    participant_id: uuid.UUID,
    trial_id: str | None = None,
    conversation_id: uuid.UUID | None = None,
    context: dict | None = None,
) -> SafetyResult:
    """Run safety gate with handoff_queue callback wired.

    This is the entry point for running the safety gate with
    automatic handoff_queue writes on trigger.

    Args:
        response: Agent response text to check.
        session: Active database session.
        participant_id: Participant UUID.
        trial_id: Optional trial identifier.
        conversation_id: Optional conversation UUID.
        context: Optional conversation context.

    Returns:
        SafetyResult with trigger status and timing.
    """
    callback = build_safety_callback(
        session,
        participant_id,
        trial_id,
        conversation_id,
    )
    return await evaluate_safety(
        response,
        context,
        on_trigger=callback,
    )
