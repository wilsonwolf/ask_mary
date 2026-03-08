"""Safety gate — blocking pre-check on every agent response.

This is an inline check, not a full agent. It runs on every agent
response to detect handoff triggers before the response reaches
the participant. Instrumented with timing for observability.

When a trigger fires and an on_trigger callback is provided, the
gate invokes the callback with the SafetyResult. The caller (e.g.
orchestrator) provides the callback to write handoff_queue entries.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from src.safety.triggers import SafetyTrigger, load_triggers
from src.shared.response_models import SafetyGateResult

logger = logging.getLogger(__name__)

OnTriggerCallback = Callable[["SafetyResult"], Awaitable[None]]

SAFETY_TRIGGERS: list[str] = [
    trigger.reason.value for trigger in load_triggers()
]

HARD_CEILING_MS = 1000


class SafetyResult(SafetyGateResult):
    """Safety gate evaluation result with response text.

    Extends SafetyGateResult with a response field for backward
    compatibility. Inherits triggered, trigger_type, severity,
    and elapsed_ms from SafetyGateResult.

    Attributes:
        response: The original agent response text that was checked.
    """

    response: str = ""


async def evaluate_safety(
    response: str,
    context: dict | None = None,
    *,
    on_trigger: OnTriggerCallback | None = None,
) -> SafetyResult:
    """Run the safety gate on an agent response.

    Checks for handoff triggers (medical advice, symptoms, adverse events,
    consent issues, threats, misunderstanding, language mismatch).
    Every invocation is instrumented with timing for observability.

    When on_trigger is provided, it is called with the SafetyResult on
    any trigger. The orchestrator uses this to write handoff_queue entries.

    Args:
        response: The agent's proposed response text.
        context: Conversation context (participant state, history).
        on_trigger: Optional async callback invoked on trigger.

    Returns:
        SafetyResult with trigger status and timing.
    """
    start = time.perf_counter()
    result = _check_triggers(response, context or {})
    elapsed_ms = (time.perf_counter() - start) * 1000
    result = result.model_copy(update={"elapsed_ms": elapsed_ms})

    if result.triggered and on_trigger:
        await on_trigger(result)

    logger.info(
        "safety_gate",
        extra={
            "elapsed_ms": elapsed_ms,
            "triggered": result.triggered,
            "trigger_type": result.trigger_type,
            "severity": result.severity,
        },
    )

    return result


def _check_triggers(
    response: str,
    context: dict,
    triggers: list[SafetyTrigger] | None = None,
) -> SafetyResult:
    """Check response against safety trigger definitions.

    Iterates through trigger definitions in priority order.
    First match wins. Text-based triggers match keyword patterns;
    context-based triggers inspect the conversation context.

    Args:
        response: Agent response text.
        context: Conversation context.
        triggers: Trigger list to evaluate (defaults to DEFAULT_TRIGGERS).

    Returns:
        SafetyResult indicating if a trigger was detected.
    """
    active_triggers = triggers or load_triggers()
    text_lower = response.lower()

    for trigger in active_triggers:
        if _trigger_matches(trigger, text_lower, context):
            return SafetyResult(
                triggered=True,
                trigger_type=trigger.reason,
                severity=trigger.severity,
            )

    return SafetyResult(triggered=False)


def _trigger_matches(
    trigger: SafetyTrigger,
    text_lower: str,
    context: dict,
) -> bool:
    """Check if a single trigger matches the response or context.

    Text-based triggers match any pattern against lowercased text.
    Context-based triggers invoke their context_check callable.

    Args:
        trigger: The trigger definition to evaluate.
        text_lower: Lowercased response text.
        context: Conversation context dict.

    Returns:
        True if the trigger matches.
    """
    if trigger.patterns and any(
        pattern in text_lower for pattern in trigger.patterns
    ):
        return True
    if trigger.context_check is not None:
        return trigger.context_check(context)
    return False
