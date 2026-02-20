"""Tests for the safety gate inline check."""

from unittest.mock import AsyncMock

from src.shared.safety_gate import SafetyResult, evaluate_safety
from src.shared.types import HandoffReason, HandoffSeverity


class TestSafetyGateTriggers:
    """Safety gate detects all required trigger types."""

    async def test_medical_advice_triggers(self) -> None:
        """Medical advice language triggers HANDOFF_NOW."""
        result = await evaluate_safety("You should take ibuprofen for the pain")
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.MEDICAL_ADVICE
        assert result.severity == HandoffSeverity.HANDOFF_NOW

    async def test_severe_symptoms_triggers(self) -> None:
        """Severe symptom mention triggers HANDOFF_NOW."""
        result = await evaluate_safety("I'm having chest pain right now")
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.SEVERE_SYMPTOMS
        assert result.severity == HandoffSeverity.HANDOFF_NOW

    async def test_consent_withdrawal_triggers(self) -> None:
        """Consent withdrawal triggers STOP_CONTACT."""
        result = await evaluate_safety("I want to withdraw my consent")
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.CONSENT_WITHDRAWAL
        assert result.severity == HandoffSeverity.STOP_CONTACT

    async def test_anger_threats_triggers(self) -> None:
        """Anger/threats trigger HANDOFF_NOW."""
        result = await evaluate_safety("I'll sue you for this")
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.ANGER_THREATS
        assert result.severity == HandoffSeverity.HANDOFF_NOW

    async def test_adverse_event_triggers(self) -> None:
        """Adverse event report triggers HANDOFF_NOW."""
        result = await evaluate_safety("I had an adverse reaction to the medication")
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.ADVERSE_EVENT
        assert result.severity == HandoffSeverity.HANDOFF_NOW

    async def test_repeated_misunderstanding_triggers(self) -> None:
        """Repeated misunderstanding triggers CALLBACK_TICKET."""
        context = {"misunderstanding_count": 3}
        result = await evaluate_safety("What do you mean?", context)
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.REPEATED_MISUNDERSTANDING
        assert result.severity == HandoffSeverity.CALLBACK_TICKET

    async def test_language_mismatch_triggers(self) -> None:
        """Language mismatch triggers CALLBACK_TICKET."""
        context = {"detected_language": "es", "expected_language": "en"}
        result = await evaluate_safety("No entiendo nada de lo que dices", context)
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.LANGUAGE_MISMATCH
        assert result.severity == HandoffSeverity.CALLBACK_TICKET

    async def test_misunderstanding_below_threshold_no_trigger(self) -> None:
        """Misunderstanding count below 3 does not trigger."""
        context = {"misunderstanding_count": 2}
        result = await evaluate_safety("What do you mean?", context)
        assert (
            result.trigger_type != HandoffReason.REPEATED_MISUNDERSTANDING or not result.triggered
        )

    async def test_matching_language_no_trigger(self) -> None:
        """Matching language does not trigger."""
        context = {"detected_language": "en", "expected_language": "en"}
        result = await evaluate_safety("Hello there", context)
        assert result.trigger_type != HandoffReason.LANGUAGE_MISMATCH or not result.triggered

    async def test_benign_response_no_trigger(self) -> None:
        """Normal conversation does not trigger."""
        result = await evaluate_safety("Your appointment is scheduled for Tuesday at 10 AM.")
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


class TestOnTriggerCallback:
    """Safety gate invokes on_trigger callback when triggered."""

    async def test_callback_invoked_on_trigger(self) -> None:
        """on_trigger callback is called when a trigger fires."""
        callback = AsyncMock()
        await evaluate_safety(
            "I had an adverse reaction",
            on_trigger=callback,
        )
        callback.assert_awaited_once()
        result = callback.call_args[0][0]
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.ADVERSE_EVENT

    async def test_callback_not_invoked_when_safe(self) -> None:
        """on_trigger callback is not called for safe responses."""
        callback = AsyncMock()
        await evaluate_safety(
            "Your appointment is Tuesday at 10 AM.",
            on_trigger=callback,
        )
        callback.assert_not_awaited()


class TestSafetyResult:
    """SafetyResult dataclass behavior."""

    def test_defaults(self) -> None:
        """Default SafetyResult is not triggered."""
        result = SafetyResult(triggered=False)
        assert result.trigger_type is None
        assert result.severity is None
        assert result.elapsed_ms == 0.0
