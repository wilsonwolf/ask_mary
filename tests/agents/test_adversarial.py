"""Tests for the adversarial checker agent helper functions and tools.

Tests deception detection, recheck scheduling, and adversarial rescreen
with mocked database sessions and external service clients.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.adversarial import (
    adversarial_agent,
    detect_deception,
    run_adversarial_rescreen,
    schedule_recheck,
)


class TestDetectDeception:
    """Deception detection compares screening responses vs EHR data."""

    async def test_detects_deception_with_mismatched_data(self) -> None:
        """Deception detected when screening says 'no' but EHR says 'yes'."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "pregnant_or_nursing": {
                "answer": "no",
                "provenance": "patient_stated",
            },
        }
        participant_trial.ehr_discrepancies = {
            "pregnant_or_nursing": "yes",
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await detect_deception(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["deception_detected"] is True
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["field"] == "pregnant_or_nursing"
        assert result["discrepancies"][0]["stated"] == "no"
        assert result["discrepancies"][0]["ehr"] == "yes"

    async def test_no_deception_with_matching_data(self) -> None:
        """No deception when EHR discrepancies dict is empty."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "diagnosis": {
                "answer": "type_2",
                "provenance": "patient_stated",
            },
        }
        participant_trial.ehr_discrepancies = {}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await detect_deception(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["deception_detected"] is False
        assert result["discrepancies"] == []

    async def test_handles_missing_ehr_gracefully(self) -> None:
        """No crash and no deception when ehr_discrepancies is None."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "diagnosis": {
                "answer": "type_2",
                "provenance": "patient_stated",
            },
        }
        participant_trial.ehr_discrepancies = None
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await detect_deception(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["deception_detected"] is False
        assert result["discrepancies"] == []


class TestScheduleRecheck:
    """Recheck scheduling enqueues a Cloud Tasks reminder."""

    async def test_schedule_recheck_enqueues_task(self) -> None:
        """Calls enqueue_reminder and returns the task_id."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        trial_id = "trial-42"
        mock_result = MagicMock()
        mock_result.task_id = "task-abc-123"

        with patch(
            "src.agents.adversarial.enqueue_reminder",
            return_value=mock_result,
        ) as mock_enqueue:
            result = await schedule_recheck(
                mock_session,
                participant_id,
                trial_id,
            )

        assert result["scheduled"] is True
        assert result["task_id"] == "task-abc-123"
        mock_enqueue.assert_awaited_once()
        call_kwargs = mock_enqueue.call_args.kwargs
        assert call_kwargs["participant_id"] == participant_id
        assert call_kwargs["template_id"] == "adversarial_recheck"
        assert call_kwargs["channel"] == "system"
        assert call_kwargs["idempotency_key"] == f"recheck-{participant_id}-{trial_id}"


class TestRunAdversarialRescreen:
    """Adversarial rescreen updates the ParticipantTrial record."""

    async def test_rescreen_records_results(self) -> None:
        """Sets adversarial_recheck_done=True and provenance='system'."""
        mock_session = AsyncMock()
        participant_id = uuid.uuid4()
        trial_id = "trial-42"
        participant_trial = MagicMock()
        participant_trial.adversarial_recheck_done = False
        participant_trial.adversarial_results = None

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        with patch(
            "src.agents.adversarial.datetime",
        ) as mock_dt:
            fake_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            result = await run_adversarial_rescreen(
                mock_session,
                participant_id,
                trial_id,
            )

        assert participant_trial.adversarial_recheck_done is True
        assert participant_trial.adversarial_results["provenance"] == "system"
        assert "rescreened_at" in participant_trial.adversarial_results
        assert result["rescreened"] is True
        assert result["results"] == participant_trial.adversarial_results


class TestAdversarialAgentDefinition:
    """Adversarial agent is properly configured with tools."""

    def test_agent_has_correct_tool_count(self) -> None:
        """Adversarial agent has exactly 3 function tools registered."""
        assert len(adversarial_agent.tools) == 3
