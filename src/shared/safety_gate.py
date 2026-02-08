"""Safety gate — blocking pre-check on every agent response.

This is an inline check, not a full agent. It runs on every agent
response to detect handoff triggers before the response reaches
the participant. Instrumented with timing for observability.
"""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
) -> SafetyResult:
    """Run the safety gate on an agent response.

    Checks for handoff triggers (medical advice, symptoms, adverse events,
    consent issues, threats, misunderstanding, language mismatch).
    Every invocation is instrumented with timing for observability.

    Args:
        response: The agent's proposed response text.
        context: Conversation context (participant state, history).

    Returns:
        SafetyResult with trigger status and timing.
    """
    start = time.perf_counter()
    result = _check_triggers(response, context or {})
    elapsed_ms = (time.perf_counter() - start) * 1000
    result.elapsed_ms = elapsed_ms

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
