"""Immutable safety tests: safety gate handoff triggers."""

from src.shared.safety_gate import evaluate_safety


class TestHandoffTriggers:
    """Safety gate detects all 7 trigger types."""

    async def test_medical_advice_triggers_handoff(self) -> None:
        """Medical advice language triggers HANDOFF_NOW."""
        result = await evaluate_safety("I recommend you increase your dose")
        assert result.triggered is True
        assert result.trigger_type == "medical_advice"
        assert result.severity == "HANDOFF_NOW"

    async def test_severe_symptoms_triggers_handoff(self) -> None:
        """Severe symptom mention triggers HANDOFF_NOW."""
        result = await evaluate_safety("I'm having chest pain")
        assert result.triggered is True
        assert result.trigger_type == "severe_symptoms"
        assert result.severity == "HANDOFF_NOW"

    async def test_consent_withdrawal_triggers_stop(self) -> None:
        """Consent withdrawal triggers STOP_CONTACT."""
        result = await evaluate_safety("I want to withdraw my consent")
        assert result.triggered is True
        assert result.trigger_type == "consent_withdrawal"
        assert result.severity == "STOP_CONTACT"

    async def test_anger_threats_triggers_handoff(self) -> None:
        """Threat language triggers HANDOFF_NOW."""
        result = await evaluate_safety("I'll sue you for this")
        assert result.triggered is True
        assert result.trigger_type == "anger_threats"
        assert result.severity == "HANDOFF_NOW"

    async def test_adverse_event_triggers_handoff(self) -> None:
        """Adverse event report triggers HANDOFF_NOW."""
        result = await evaluate_safety("I had an adverse reaction")
        assert result.triggered is True
        assert result.trigger_type == "adverse_event"
        assert result.severity == "HANDOFF_NOW"

    async def test_repeated_misunderstanding_triggers_callback(
        self,
    ) -> None:
        """Repeated misunderstanding triggers CALLBACK_TICKET."""
        context = {"misunderstanding_count": 3}
        result = await evaluate_safety("I still don't understand", context)
        assert result.triggered is True
        assert result.trigger_type == "repeated_misunderstanding"
        assert result.severity == "CALLBACK_TICKET"

    async def test_safe_response_no_trigger(self) -> None:
        """Normal safe response does not trigger."""
        result = await evaluate_safety(
            "Your appointment is scheduled for Monday at 10 AM.",
        )
        assert result.triggered is False
        assert result.trigger_type is None
