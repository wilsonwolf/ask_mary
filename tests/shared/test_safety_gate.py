"""Tests for the safety gate inline check."""

import pytest

from src.shared.safety_gate import SafetyResult, evaluate_safety


class TestSafetyGateTriggers:
    """Safety gate detects all required trigger types."""

    async def test_medical_advice_triggers(self) -> None:
        """Medical advice language triggers HANDOFF_NOW."""
        result = await evaluate_safety("You should take ibuprofen for the pain")
        assert result.triggered is True
        assert result.trigger_type == "medical_advice"
        assert result.severity == "HANDOFF_NOW"

    async def test_severe_symptoms_triggers(self) -> None:
        """Severe symptom mention triggers HANDOFF_NOW."""
        result = await evaluate_safety("I'm having chest pain right now")
        assert result.triggered is True
        assert result.trigger_type == "severe_symptoms"
        assert result.severity == "HANDOFF_NOW"

    async def test_consent_withdrawal_triggers(self) -> None:
        """Consent withdrawal triggers STOP_CONTACT."""
        result = await evaluate_safety("I want to withdraw my consent")
        assert result.triggered is True
        assert result.trigger_type == "consent_withdrawal"
        assert result.severity == "STOP_CONTACT"

    async def test_anger_threats_triggers(self) -> None:
        """Anger/threats trigger HANDOFF_NOW."""
        result = await evaluate_safety("I'll sue you for this")
        assert result.triggered is True
        assert result.trigger_type == "anger_threats"
        assert result.severity == "HANDOFF_NOW"

    async def test_benign_response_no_trigger(self) -> None:
        """Normal conversation does not trigger."""
        result = await evaluate_safety(
            "Your appointment is scheduled for Tuesday at 10 AM."
        )
        assert result.triggered is False
        assert result.trigger_type is None

    async def test_case_insensitive(self) -> None:
        """Triggers are case-insensitive."""
        result = await evaluate_safety("I'm having CHEST PAIN")
        assert result.triggered is True


class TestSafetyGateLatency:
    """Safety gate timing is instrumented."""

    async def test_elapsed_ms_populated(self) -> None:
        """elapsed_ms is always set."""
        result = await evaluate_safety("Hello, how are you?")
        assert result.elapsed_ms >= 0

    async def test_under_hard_ceiling(self) -> None:
        """Safety gate completes well under 1000ms hard ceiling."""
        result = await evaluate_safety("I'm having chest pain")
        assert result.elapsed_ms < 1000


class TestSafetyResult:
    """SafetyResult dataclass behavior."""

    def test_defaults(self) -> None:
        """Default SafetyResult is not triggered."""
        result = SafetyResult(triggered=False)
        assert result.trigger_type is None
        assert result.severity is None
        assert result.elapsed_ms == 0.0
