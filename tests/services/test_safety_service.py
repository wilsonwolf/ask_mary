"""Tests for the safety service — safety gate → handoff_queue wiring."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.safety_service import (
    build_safety_callback,
    run_safety_gate,
)
from src.shared.safety_gate import SafetyResult
from src.shared.types import HandoffReason, HandoffSeverity


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
            trigger_type=HandoffReason.SEVERE_SYMPTOMS,
            severity=HandoffSeverity.HANDOFF_NOW,
        )

        with (
            patch(
                "src.services.safety_service._get_coordinator_phone",
                new_callable=AsyncMock,
                return_value="+15551234567",
            ),
            patch(
                "src.services.safety_service._build_handoff_packet",
                new_callable=AsyncMock,
                return_value={"identity_status": "verified"},
            ),
            patch(
                "src.services.safety_service.create_handoff",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ) as mock_create,
            patch(
                "src.services.safety_service._initiate_warm_transfer",
                new_callable=AsyncMock,
            ),
        ):
            await callback(result)
            mock_create.assert_called_once_with(
                mock_session,
                participant_id=participant_id,
                reason=HandoffReason.SEVERE_SYMPTOMS,
                severity=HandoffSeverity.HANDOFF_NOW,
                conversation_id=conversation_id,
                trial_id=trial_id,
                summary="Safety gate: severe_symptoms",
                coordinator_phone="+15551234567",
            )

    async def test_handoff_now_triggers_warm_transfer(self) -> None:
        """HANDOFF_NOW with call_sid initiates warm transfer."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        call_sid = "CA123"

        callback = build_safety_callback(
            mock_session,
            participant_id,
            trial_id="trial-1",
            call_sid=call_sid,
        )

        result = SafetyResult(
            triggered=True,
            trigger_type=HandoffReason.SEVERE_SYMPTOMS,
            severity=HandoffSeverity.HANDOFF_NOW,
        )

        with (
            patch(
                "src.services.safety_service._get_coordinator_phone",
                new_callable=AsyncMock,
                return_value="+15551234567",
            ),
            patch(
                "src.services.safety_service._build_handoff_packet",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "src.services.safety_service.create_handoff",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "src.services.safety_service._initiate_warm_transfer",
                new_callable=AsyncMock,
            ) as mock_transfer,
        ):
            await callback(result)
            mock_transfer.assert_called_once_with(
                call_sid,
                "+15551234567",
            )

    async def test_no_transfer_without_call_sid(self) -> None:
        """No warm transfer when call_sid is missing."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()

        callback = build_safety_callback(
            mock_session,
            participant_id,
            trial_id="trial-1",
        )

        result = SafetyResult(
            triggered=True,
            trigger_type=HandoffReason.SEVERE_SYMPTOMS,
            severity=HandoffSeverity.HANDOFF_NOW,
        )

        with (
            patch(
                "src.services.safety_service._get_coordinator_phone",
                new_callable=AsyncMock,
                return_value="+15551234567",
            ),
            patch(
                "src.services.safety_service._build_handoff_packet",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "src.services.safety_service.create_handoff",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "src.services.safety_service._initiate_warm_transfer",
                new_callable=AsyncMock,
            ) as mock_transfer,
        ):
            await callback(result)
            mock_transfer.assert_not_called()


class TestRunSafetyGate:
    """End-to-end safety gate with handoff wiring."""

    async def test_trigger_creates_handoff(self) -> None:
        """Triggered safety gate writes to handoff_queue."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()

        with (
            patch(
                "src.services.safety_service._get_coordinator_phone",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "src.services.safety_service._build_handoff_packet",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "src.services.safety_service.create_handoff",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ) as mock_create,
        ):
            result = await run_safety_gate(
                "I have severe chest pain",
                mock_session,
                participant_id,
                trial_id="trial-1",
            )
        assert result.triggered is True
        assert result.trigger_type == HandoffReason.SEVERE_SYMPTOMS
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
