"""Safety trigger definitions — configurable handoff trigger registry.

Each trigger defines a pattern-matching strategy, the HandoffReason it
maps to, and the HandoffSeverity level. Triggers are evaluated in
priority order (first match wins).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from src.shared.types import HandoffReason, HandoffSeverity


@dataclass(frozen=True)
class SafetyTrigger:
    """A single safety trigger definition.

    Attributes:
        reason: The handoff reason enum value.
        severity: The handoff severity enum value.
        patterns: Keyword patterns for text matching.
        context_check: Optional context-based check function.
    """

    reason: HandoffReason
    severity: HandoffSeverity
    patterns: list[str] = field(default_factory=list)
    context_check: Callable[[dict], bool] | None = None


def _check_repeated_misunderstanding(context: dict) -> bool:
    """Check if misunderstanding count exceeds threshold.

    Args:
        context: Conversation context dict.

    Returns:
        True if misunderstanding count is 3 or more.
    """
    return context.get("misunderstanding_count", 0) >= 3


def _check_language_mismatch(context: dict) -> bool:
    """Check if detected language differs from expected.

    Args:
        context: Conversation context dict.

    Returns:
        True if languages differ.
    """
    detected = context.get("detected_language")
    expected = context.get("expected_language")
    if detected and expected:
        return detected != expected
    return False


def load_triggers() -> list[SafetyTrigger]:
    """Load the active safety trigger definitions.

    Returns the default trigger list. Designed to be replaced with
    config-file-based loading in a future iteration.

    Returns:
        List of SafetyTrigger definitions in priority order.
    """
    return list(DEFAULT_TRIGGERS)


DEFAULT_TRIGGERS: list[SafetyTrigger] = [
    SafetyTrigger(
        reason=HandoffReason.MEDICAL_ADVICE,
        severity=HandoffSeverity.HANDOFF_NOW,
        patterns=[
            "you should take",
            "i recommend",
            "my medical advice",
            "increase your dose",
            "stop taking",
            "prescribe",
        ],
    ),
    SafetyTrigger(
        reason=HandoffReason.SEVERE_SYMPTOMS,
        severity=HandoffSeverity.HANDOFF_NOW,
        patterns=[
            "chest pain",
            "difficulty breathing",
            "shortness of breath",
            "severe bleeding",
            "loss of consciousness",
            "seizure",
            "suicidal",
            "self-harm",
        ],
    ),
    SafetyTrigger(
        reason=HandoffReason.CONSENT_WITHDRAWAL,
        severity=HandoffSeverity.STOP_CONTACT,
        patterns=[
            "i want to withdraw",
            "i don't consent",
            "stop the study",
            "i want out",
            "withdraw my consent",
        ],
    ),
    SafetyTrigger(
        reason=HandoffReason.ANGER_THREATS,
        severity=HandoffSeverity.HANDOFF_NOW,
        patterns=[
            "i'll sue",
            "lawyer",
            "report you",
            "threatening",
            "going to hurt",
        ],
    ),
    SafetyTrigger(
        reason=HandoffReason.ADVERSE_EVENT,
        severity=HandoffSeverity.HANDOFF_NOW,
        patterns=[
            "adverse reaction",
            "adverse event",
            "side effect",
            "allergic reaction",
            "got worse",
            "bad reaction",
        ],
    ),
    SafetyTrigger(
        reason=HandoffReason.REPEATED_MISUNDERSTANDING,
        severity=HandoffSeverity.CALLBACK_TICKET,
        context_check=_check_repeated_misunderstanding,
    ),
    SafetyTrigger(
        reason=HandoffReason.LANGUAGE_MISMATCH,
        severity=HandoffSeverity.CALLBACK_TICKET,
        context_check=_check_language_mismatch,
    ),
]
