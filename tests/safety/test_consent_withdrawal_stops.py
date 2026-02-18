"""Immutable safety tests: consent withdrawal stops all contact."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.safety_service import run_safety_gate
from src.shared.safety_gate import evaluate_safety


class TestConsentWithdrawalStops:
    """Consent withdrawal produces STOP_CONTACT severity."""

    async def test_withdrawal_language_triggers_stop(self) -> None:
        """Withdrawal language triggers STOP_CONTACT."""
        result = await evaluate_safety("I don't consent anymore")
        assert result.triggered is True
        assert result.severity == "STOP_CONTACT"

    async def test_explicit_withdrawal_triggers_stop(self) -> None:
        """Explicit consent withdrawal triggers stop."""
        result = await evaluate_safety("I want to withdraw")
        assert result.triggered is True
        assert result.trigger_type == "consent_withdrawal"

    async def test_safety_service_creates_handoff_on_withdrawal(
        self,
    ) -> None:
        """run_safety_gate creates handoff entry on consent withdrawal."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        mock_handoff = MagicMock()
        with patch(
            "src.services.safety_service.create_handoff",
            return_value=mock_handoff,
        ) as create_mock:
            result = await run_safety_gate(
                "I want to withdraw my consent",
                mock_session,
                participant_id,
            )
        assert result.triggered is True
        assert result.severity == "STOP_CONTACT"
        create_mock.assert_called_once()
        call_kwargs = create_mock.call_args
        assert call_kwargs.kwargs["severity"] == "STOP_CONTACT"
