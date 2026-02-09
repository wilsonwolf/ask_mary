"""Tests for the safety service — safety gate → handoff_queue wiring."""

import uuid
from unittest.mock import AsyncMock, patch

from src.services.safety_service import (
    build_safety_callback,
    run_safety_gate,
)
from src.shared.safety_gate import SafetyResult


class TestBuildSafetyCallback:
    """Callback builder creates working handoff writer."""

    async def test_callback_writes_handoff(self) -> None:
        """Callback creates handoff_queue entry on trigger."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        trial_id = "trial-1"
        conversation_id = uuid.uuid4()

        callback = build_safety_callback(
            mock_session,
            participant_id,
            trial_id,
            conversation_id,
        )

        result = SafetyResult(
            triggered=True,
            trigger_type="severe_symptoms",
            severity="HANDOFF_NOW",
        )

        with patch(
            "src.services.safety_service.create_handoff",
            new_callable=AsyncMock,
        ) as mock_create:
            await callback(result)
            mock_create.assert_called_once_with(
                mock_session,
                participant_id=participant_id,
                reason="severe_symptoms",
                severity="HANDOFF_NOW",
                conversation_id=conversation_id,
                trial_id=trial_id,
                summary="Safety gate: severe_symptoms",
            )


class TestRunSafetyGate:
    """End-to-end safety gate with handoff wiring."""

    async def test_trigger_creates_handoff(self) -> None:
        """Triggered safety gate writes to handoff_queue."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()

        with patch(
            "src.services.safety_service.create_handoff",
            new_callable=AsyncMock,
        ) as mock_create:
            result = await run_safety_gate(
                "I have severe chest pain",
                mock_session,
                participant_id,
                trial_id="trial-1",
            )
        assert result.triggered is True
        assert result.trigger_type == "severe_symptoms"
        mock_create.assert_called_once()

    async def test_safe_response_no_handoff(self) -> None:
        """Safe response does not write to handoff_queue."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()

        with patch(
            "src.services.safety_service.create_handoff",
            new_callable=AsyncMock,
        ) as mock_create:
            result = await run_safety_gate(
                "Your appointment is next Tuesday at 10am.",
                mock_session,
                participant_id,
            )
        assert result.triggered is False
        mock_create.assert_not_called()
