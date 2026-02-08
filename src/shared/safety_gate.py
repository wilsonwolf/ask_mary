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
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OnTriggerCallback = Callable[["SafetyResult"], Awaitable[None]]

SAFETY_TRIGGERS = [
    "medical_advice",
    "severe_symptoms",
    "adverse_event",
    "consent_withdrawal",
    "anger_threats",
    "repeated_misunderstanding",
    "language_mismatch",
]

HARD_CEILING_MS = 1000


@dataclass
class SafetyResult:
    """Result of a safety gate evaluation.

    Attributes:
        triggered: Whether a safety trigger was detected.
        trigger_type: Which trigger fired, if any.
        severity: HANDOFF_NOW, CALLBACK_TICKET, or STOP_CONTACT.
        elapsed_ms: Time taken for the evaluation.
    """

    triggered: bool
    trigger_type: str | None = None
    severity: str | None = None
    elapsed_ms: float = 0.0


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
    result.elapsed_ms = elapsed_ms

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


def _check_triggers(response: str, context: dict) -> SafetyResult:
    """Check response against safety trigger patterns.

    Args:
        response: Agent response text.
        context: Conversation context.

    Returns:
        SafetyResult indicating if a trigger was detected.
    """
    text_lower = response.lower()

    if _matches_medical_advice(text_lower):
        return SafetyResult(
            triggered=True,
            trigger_type="medical_advice",
            severity="HANDOFF_NOW",
        )

    if _matches_severe_symptoms(text_lower):
        return SafetyResult(
            triggered=True,
            trigger_type="severe_symptoms",
            severity="HANDOFF_NOW",
        )

    if _matches_consent_withdrawal(text_lower):
        return SafetyResult(
            triggered=True,
            trigger_type="consent_withdrawal",
            severity="STOP_CONTACT",
        )

    if _matches_anger_threats(text_lower):
        return SafetyResult(
            triggered=True,
            trigger_type="anger_threats",
            severity="HANDOFF_NOW",
        )

    if _matches_adverse_event(text_lower):
        return SafetyResult(
            triggered=True,
            trigger_type="adverse_event",
            severity="HANDOFF_NOW",
        )

    if _matches_repeated_misunderstanding(context):
        return SafetyResult(
            triggered=True,
            trigger_type="repeated_misunderstanding",
            severity="CALLBACK_TICKET",
        )

    if _matches_language_mismatch(context):
        return SafetyResult(
            triggered=True,
            trigger_type="language_mismatch",
            severity="CALLBACK_TICKET",
        )

    return SafetyResult(triggered=False)


def _matches_medical_advice(text: str) -> bool:
    """Detect medical advice patterns.

    Args:
        text: Lowercased response text.

    Returns:
        True if medical advice pattern detected.
    """
    patterns = [
        "you should take",
        "i recommend",
        "my medical advice",
        "increase your dose",
        "stop taking",
        "prescribe",
    ]
    return any(p in text for p in patterns)


def _matches_severe_symptoms(text: str) -> bool:
    """Detect severe symptom mentions.

    Args:
        text: Lowercased response text.

    Returns:
        True if severe symptom pattern detected.
    """
    patterns = [
        "chest pain",
        "difficulty breathing",
        "shortness of breath",
        "severe bleeding",
        "loss of consciousness",
        "seizure",
        "suicidal",
        "self-harm",
    ]
    return any(p in text for p in patterns)


def _matches_consent_withdrawal(text: str) -> bool:
    """Detect consent withdrawal language.

    Args:
        text: Lowercased response text.

    Returns:
        True if consent withdrawal detected.
    """
    patterns = [
        "i want to withdraw",
        "i don't consent",
        "stop the study",
        "i want out",
        "withdraw my consent",
    ]
    return any(p in text for p in patterns)


def _matches_anger_threats(text: str) -> bool:
    """Detect anger or threat language.

    Args:
        text: Lowercased response text.

    Returns:
        True if anger/threats detected.
    """
    patterns = [
        "i'll sue",
        "lawyer",
        "report you",
        "threatening",
        "going to hurt",
    ]
    return any(p in text for p in patterns)


def _matches_adverse_event(text: str) -> bool:
    """Detect adverse event reports.

    Args:
        text: Lowercased response text.

    Returns:
        True if adverse event pattern detected.
    """
    patterns = [
        "adverse reaction",
        "adverse event",
        "side effect",
        "allergic reaction",
        "got worse",
        "bad reaction",
    ]
    return any(p in text for p in patterns)


def _matches_repeated_misunderstanding(context: dict) -> bool:
    """Detect repeated misunderstanding from context.

    Args:
        context: Conversation context with misunderstanding_count.

    Returns:
        True if misunderstanding count exceeds threshold.
    """
    return context.get("misunderstanding_count", 0) >= 3


def _matches_language_mismatch(context: dict) -> bool:
    """Detect language mismatch from context.

    Args:
        context: Conversation context with language info.

    Returns:
        True if detected language differs from expected.
    """
    detected = context.get("detected_language")
    expected = context.get("expected_language")
    if detected and expected:
        return detected != expected
    return False
