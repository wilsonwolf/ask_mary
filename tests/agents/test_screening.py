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
from src.shared.types import EligibilityStatus, Provenance


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

    async def test_returns_criteria_with_trial_name(self) -> None:
        """Returns inclusion, exclusion criteria, and trial name."""
        mock_session = AsyncMock()
        mock_trial = MagicMock()
        mock_trial.trial_name = "Test Trial"
        with (
            patch(
                "src.db.trials.get_trial",
                return_value=mock_trial,
            ),
            patch(
                "src.agents.screening.get_trial_criteria",
                return_value={
                    "inclusion": {"min_age": 18},
                    "exclusion": {"pregnant": True},
                },
            ),
        ):
            result = await get_screening_criteria(mock_session, "trial-1")
        assert result["inclusion"]["min_age"] == 18
        assert result["exclusion"]["pregnant"] is True
        assert result["trial_name"] == "Test Trial"


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
            Provenance.PATIENT_STATED,
        )
        assert result["recorded"] is True


class TestDetermineEligibility:
    """Eligibility determination with real nested response format."""

    def _make_pt(self, responses: dict) -> MagicMock:
        """Create a mock participant_trial with screening responses."""
        pt = MagicMock()
        pt.screening_responses = responses
        pt.eligibility_status = EligibilityStatus.PENDING
        return pt

    def _make_session(self, pt: MagicMock) -> AsyncMock:
        """Create a mock session that returns the given participant_trial."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        session.execute.return_value = result_mock
        return session

    def _resp(self, answer: str, provenance: str = "patient_stated") -> dict:
        """Build a nested screening response as record_screening_response creates."""
        return {"answer": answer, "provenance": provenance}

    async def test_eligible_with_nested_responses(self) -> None:
        """Returns eligible when nested responses satisfy all criteria."""
        pt = self._make_pt(
            {
                "age": self._resp("45"),
                "diagnosis": self._resp("yes, type 2 diabetes"),
                "hba1c": self._resp("8.2"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {
                    "min_age": 18,
                    "max_age": 75,
                    "diagnosis": "type_2_diabetes",
                    "hba1c_min": 7.0,
                    "hba1c_max": 10.5,
                },
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True

    async def test_excluded_by_affirmative_answer(self) -> None:
        """Returns ineligible when participant answers yes to exclusion."""
        pt = self._make_pt(
            {
                "pregnant_or_nursing": self._resp("yes"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {},
                "exclusion": {"pregnant_or_nursing": True},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is False
        assert "pregnant_or_nursing" in result["reason"]

    async def test_exclusion_not_triggered_by_negative(self) -> None:
        """Participant answering no to exclusion is not excluded."""
        pt = self._make_pt(
            {
                "pregnant_or_nursing": self._resp("no"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {},
                "exclusion": {"pregnant_or_nursing": True},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True

    async def test_age_below_minimum_ineligible(self) -> None:
        """Returns ineligible when age is below min_age."""
        pt = self._make_pt(
            {
                "age": self._resp("15"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"min_age": 18},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is False

    async def test_age_above_maximum_ineligible(self) -> None:
        """Returns ineligible when age exceeds max_age."""
        pt = self._make_pt(
            {
                "age": self._resp("80"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"max_age": 75},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is False

    async def test_missing_responses_returns_incomplete(self) -> None:
        """Returns incomplete (not needs_human) when responses missing."""
        pt = self._make_pt({})
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"min_age": 18, "diagnosis": "type_2_diabetes"},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is False
        assert "missing" in result["reason"].lower()

    async def test_grouped_key_lookup(self) -> None:
        """Response under 'age' satisfies both min_age and max_age."""
        pt = self._make_pt(
            {
                "age": self._resp("45"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"min_age": 18, "max_age": 75},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True

    async def test_diagnosis_match(self) -> None:
        """Diagnosis answer containing expected value passes."""
        pt = self._make_pt(
            {
                "diagnosis": self._resp("yes I have type 2 diabetes"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {"diagnosis": "type_2_diabetes"},
                "exclusion": {},
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True

    async def test_full_diabetes_trial_eligible(self) -> None:
        """Full Diabetes Study A criteria with realistic answers — eligible."""
        pt = self._make_pt(
            {
                "age": self._resp("54"),
                "diagnosis": self._resp("yes, type 2 diabetes"),
                "hba1c": self._resp("8.2"),
                "pregnant_or_nursing": self._resp("no"),
                "insulin_dependent": self._resp("no"),
                "egfr_below_30": self._resp("no"),
                "active_cancer_treatment": self._resp("no"),
            }
        )
        session = self._make_session(pt)
        with patch(
            "src.agents.screening.get_trial_criteria",
            return_value={
                "inclusion": {
                    "min_age": 18,
                    "max_age": 75,
                    "diagnosis": "type_2_diabetes",
                    "hba1c_min": 7.0,
                    "hba1c_max": 10.5,
                },
                "exclusion": {
                    "pregnant_or_nursing": True,
                    "insulin_dependent": True,
                    "egfr_below_30": True,
                    "active_cancer_treatment": True,
                },
            },
        ):
            result = await determine_eligibility(session, uuid.uuid4(), "trial-1")
        assert result["eligible"] is True


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
