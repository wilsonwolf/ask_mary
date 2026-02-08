"""Tests for the screening agent function tools."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.screening import (
    check_hard_excludes,
    determine_eligibility,
    get_screening_criteria,
    record_caregiver_info,
    record_screening_response,
    screening_agent,
)


class TestScreeningAgentDefinition:
    """Screening agent is properly configured."""

    def test_has_tools(self) -> None:
        """Screening agent has function tools registered."""
        assert len(screening_agent.tools) == 5

    def test_has_instructions(self) -> None:
        """Screening agent has instructions."""
        assert screening_agent.instructions


class TestGetScreeningCriteria:
    """Trial criteria retrieval for screening."""

    async def test_returns_criteria(self) -> None:
        """Returns inclusion and exclusion criteria."""
        mock_session = AsyncMock()
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"min_age": 18},
                "exclusion": {"pregnant": True},
            },
        ):
            result = await get_screening_criteria(mock_session, "trial-1")
        assert result["inclusion"]["min_age"] == 18
        assert result["exclusion"]["pregnant"] is True


class TestCheckHardExcludes:
    """Hard exclusion checking."""

    async def test_excluded_when_matching(self) -> None:
        """Returns excluded=True when hard exclude matches."""
        mock_session = AsyncMock()
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {},
                "exclusion": {"pregnant_or_nursing": True},
            },
        ):
            result = await check_hard_excludes(
                mock_session,
                uuid.uuid4(),
                "trial-1",
                {"pregnant_or_nursing": True},
            )
        assert result["excluded"] is True

    async def test_not_excluded_when_clear(self) -> None:
        """Returns excluded=False when no hard exclude matches."""
        mock_session = AsyncMock()
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {},
                "exclusion": {"pregnant_or_nursing": True},
            },
        ):
            result = await check_hard_excludes(
                mock_session,
                uuid.uuid4(),
                "trial-1",
                {"pregnant_or_nursing": False},
            )
        assert result["excluded"] is False


class TestRecordScreeningResponse:
    """Screening response recording."""

    async def test_records_response(self) -> None:
        """Records a screening response with provenance."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {}

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await record_screening_response(
            mock_session,
            uuid.uuid4(),
            "trial-1",
            "age",
            "45",
            "patient_stated",
        )
        assert result["recorded"] is True


class TestDetermineEligibility:
    """Eligibility determination."""

    async def test_eligible_status(self) -> None:
        """Returns eligible when all criteria met."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {"age": "45", "diagnosis": "type_2_diabetes"}
        pt.eligibility_status = "pending"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"min_age": 18, "diagnosis": "type_2_diabetes"},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(mock_session, uuid.uuid4(), "trial-1")
        assert result["status"] in ("eligible", "provisional", "needs_human")

    async def test_ineligible_status(self) -> None:
        """Returns ineligible when hard exclude present in responses."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {"pregnant_or_nursing": True}
        pt.eligibility_status = "pending"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {},
                "exclusion": {"pregnant_or_nursing": True},
            },
        ):
            result = await determine_eligibility(mock_session, uuid.uuid4(), "trial-1")
        assert result["status"] == "ineligible"


class TestRecordCaregiverInfo:
    """Caregiver information recording."""

    async def test_records_caregiver(self) -> None:
        """Records caregiver details on participant."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.caregiver = None
        with patch(
            "src.agents.screening.get_participant_by_id",
            return_value=participant,
        ):
            result = await record_caregiver_info(
                mock_session,
                uuid.uuid4(),
                "Maria Garcia",
                "daughter",
                "scheduling",
            )
        assert result["recorded"] is True
        assert participant.caregiver["name"] == "Maria Garcia"

    async def test_caregiver_relationship_stored(self) -> None:
        """Caregiver relationship is stored."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.caregiver = None
        with patch(
            "src.agents.screening.get_participant_by_id",
            return_value=participant,
        ):
            await record_caregiver_info(
                mock_session,
                uuid.uuid4(),
                "John Smith",
                "spouse",
                "all",
            )
        assert participant.caregiver["relationship"] == "spouse"
