"""Tests for the supervisor agent — transcript audit and compliance checks.

Tests the internal audit functions with mocked sessions.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.agents.supervisor import (
    audit_provenance,
    audit_transcript,
    check_phi_leak,
    detect_answer_inconsistencies,
    supervisor_agent,
)


class TestSupervisorAgentDefinition:
    """Supervisor agent is properly configured."""

    def test_has_tools(self) -> None:
        """Supervisor agent has 4 function tools registered."""
        assert len(supervisor_agent.tools) == 4

    def test_has_instructions(self) -> None:
        """Supervisor agent has instructions."""
        assert supervisor_agent.instructions


class TestAuditTranscript:
    """Transcript compliance audit."""

    async def test_audit_compliant_transcript(self) -> None:
        """Transcript with all required steps returns risk_level=LOW."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {
            "entries": [
                {"step": "disclosure", "timestamp": "2026-01-01T10:00:00", "content": "..."},
                {"step": "consent", "timestamp": "2026-01-01T10:01:00", "content": "..."},
                {
                    "step": "identity_verified",
                    "timestamp": "2026-01-01T10:02:00",
                    "content": "...",
                },
            ]
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await audit_transcript(mock_session, uuid.uuid4())
        assert result["compliant"] is True
        assert result["risk_level"] == "LOW"
        assert result["missing_steps"] == []

    async def test_audit_missing_disclosure(self) -> None:
        """Transcript missing disclosure returns risk_level=HIGH."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {
            "entries": [
                {"step": "consent", "timestamp": "2026-01-01T10:01:00", "content": "..."},
                {
                    "step": "identity_verified",
                    "timestamp": "2026-01-01T10:02:00",
                    "content": "...",
                },
            ]
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await audit_transcript(mock_session, uuid.uuid4())
        assert result["compliant"] is False
        assert result["risk_level"] == "HIGH"
        assert "disclosure" in result["missing_steps"]

    async def test_audit_handles_entries_without_step_key(self) -> None:
        """Entries missing step key are skipped, not KeyError."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {
            "entries": [
                {"step": "disclosure", "content": "..."},
                {"content": "some text without step"},
                {"step": "consent", "content": "..."},
                {"step": "identity_verified", "content": "..."},
            ]
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await audit_transcript(mock_session, uuid.uuid4())
        assert result["compliant"] is True

    async def test_audit_handles_empty_transcript(self) -> None:
        """Empty transcript returns non-compliant without crashing."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {"entries": []}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await audit_transcript(mock_session, uuid.uuid4())
        assert result["compliant"] is False
        assert len(result["missing_steps"]) == 3


class TestCheckPhiLeak:
    """PHI leak detection in transcripts."""

    async def test_phi_leak_detected_before_identity(self) -> None:
        """PHI keyword before identity_verified step flags phi_leaked=True."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {
            "entries": [
                {"step": "disclosure", "timestamp": "2026-01-01T10:00:00", "content": "..."},
                {
                    "step": "screening",
                    "timestamp": "2026-01-01T10:01:00",
                    "content": "discussed date of birth details",
                },
                {
                    "step": "identity_verified",
                    "timestamp": "2026-01-01T10:02:00",
                    "content": "...",
                },
            ]
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await check_phi_leak(mock_session, uuid.uuid4())
        assert result["phi_leaked"] is True
        assert len(result["details"]) > 0

    async def test_no_phi_leak_in_compliant_call(self) -> None:
        """PHI only after identity_verified step returns phi_leaked=False."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {
            "entries": [
                {"step": "disclosure", "timestamp": "2026-01-01T10:00:00", "content": "hello"},
                {"step": "consent", "timestamp": "2026-01-01T10:01:00", "content": "yes"},
                {"step": "identity_verified", "timestamp": "2026-01-01T10:02:00", "content": "ok"},
                {
                    "step": "screening",
                    "timestamp": "2026-01-01T10:03:00",
                    "content": "date of birth confirmed as correct",
                },
            ]
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await check_phi_leak(mock_session, uuid.uuid4())
        assert result["phi_leaked"] is False
        assert result["details"] == []

    async def test_phi_leak_handles_entries_without_step(self) -> None:
        """Entries missing step key don't crash PHI scan."""
        mock_session = AsyncMock()
        conversation = MagicMock()
        conversation.full_transcript = {
            "entries": [
                {"content": "discussed date of birth details"},
                {"step": "identity_verified", "content": "ok"},
            ]
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = conversation
        mock_session.execute.return_value = result_mock

        result = await check_phi_leak(mock_session, uuid.uuid4())
        assert result["phi_leaked"] is True
        assert len(result["details"]) > 0


class TestDetectAnswerInconsistencies:
    """Screening answer inconsistency detection."""

    async def test_inconsistent_answers_detected(self) -> None:
        """Same question answered differently by different sources is flagged."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "diagnosis": [
                {"answer": "type_2", "provenance": "patient_stated"},
                {"answer": "type_1", "provenance": "ehr"},
            ],
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await detect_answer_inconsistencies(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["inconsistencies_found"] is True
        assert "diagnosis" in result["flagged_questions"]

    async def test_consistent_answers_clean(self) -> None:
        """All answers consistent across sources returns clean."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "diagnosis": [
                {"answer": "type_2", "provenance": "patient_stated"},
                {"answer": "type_2", "provenance": "ehr"},
            ],
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await detect_answer_inconsistencies(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["inconsistencies_found"] is False
        assert result["flagged_questions"] == []


class TestAuditProvenance:
    """Provenance validation for screening responses."""

    async def test_all_provenance_present(self) -> None:
        """All responses have valid provenance returns all_valid=True."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "diagnosis": {"answer": "type_2", "provenance": "patient_stated"},
            "medication": {"answer": "metformin", "provenance": "ehr"},
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await audit_provenance(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["all_valid"] is True
        assert result["missing_provenance"] == []

    async def test_missing_provenance_flagged(self) -> None:
        """Response without provenance field is flagged."""
        mock_session = AsyncMock()
        participant_trial = MagicMock()
        participant_trial.screening_responses = {
            "diagnosis": {"answer": "type_2", "provenance": "patient_stated"},
            "medication": {"answer": "metformin"},
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = participant_trial
        mock_session.execute.return_value = result_mock

        result = await audit_provenance(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["all_valid"] is False
        assert "medication" in result["missing_provenance"]
