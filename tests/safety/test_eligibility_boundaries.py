"""Immutable safety tests: eligibility boundary enforcement."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.screening import check_hard_excludes, determine_eligibility


class TestEligibilityBoundaries:
    """Hard exclusion criteria and eligibility determination."""

    async def test_excludes_on_hard_criteria_match(self) -> None:
        """Participant matching hard exclusion is excluded."""
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
        assert "pregnant_or_nursing" in result["matched_criteria"]

    async def test_passes_when_no_exclusion_match(self) -> None:
        """Participant not matching exclusion passes."""
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

    async def test_determine_eligible_with_all_criteria(self) -> None:
        """Participant with all inclusion criteria met is eligible."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {"min_age": "yes", "diagnosis": "yes"}
        pt.eligibility_status = "pending"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"min_age": 18, "diagnosis": "type_2"},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(
                mock_session,
                uuid.uuid4(),
                "trial-1",
            )
        assert result["status"] == "eligible"

    async def test_determine_ineligible_on_exclusion(self) -> None:
        """Participant matching exclusion is ineligible."""
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
            result = await determine_eligibility(
                mock_session,
                uuid.uuid4(),
                "trial-1",
            )
        assert result["status"] == "ineligible"
