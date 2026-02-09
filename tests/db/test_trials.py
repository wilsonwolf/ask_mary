"""Tests for the Trial model and TrialRepository CRUD operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models import Trial
from src.db.trials import (
    create_trial,
    get_trial,
    get_trial_criteria,
    list_active_trials,
    seed_diabetes_study_a,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Provide a mock async database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestTrialModel:
    """Trial ORM model is correctly defined."""

    def test_trial_table_name(self) -> None:
        """Trial model maps to correct table."""
        assert Trial.__tablename__ == "trials"

    def test_trial_has_jsonb_fields(self) -> None:
        """Trial has JSONB columns for criteria and templates."""
        columns = Trial.__table__.c
        assert columns.inclusion_criteria is not None
        assert columns.exclusion_criteria is not None
        assert columns.visit_templates is not None
        assert columns.operating_hours is not None


class TestCreateTrial:
    """create_trial persists a Trial record."""

    async def test_creates_trial_record(self, mock_session: AsyncMock) -> None:
        """create_trial returns a Trial with correct fields."""
        trial = await create_trial(
            mock_session,
            trial_name="Diabetes Study A",
            pi_name="Dr. Smith",
            coordinator_name="Jane Doe",
            coordinator_phone="+15551234567",
            site_address="123 Main St, Portland OR 97201",
            site_name="Portland Research Center",
            inclusion_criteria={"min_age": 18, "diagnosis": "type_2_diabetes"},
            exclusion_criteria={"pregnant": True},
        )
        assert trial.trial_name == "Diabetes Study A"
        assert trial.pi_name == "Dr. Smith"
        assert trial.active is True
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()


class TestGetTrial:
    """get_trial retrieves by ID."""

    async def test_returns_trial_when_found(self, mock_session: AsyncMock) -> None:
        """get_trial returns the Trial if it exists."""
        trial_id = "test-trial-1"
        fake_trial = Trial(trial_id=trial_id, trial_name="Test Trial")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_trial
        mock_session.execute.return_value = result_mock

        result = await get_trial(mock_session, trial_id)
        assert result is not None
        assert result.trial_name == "Test Trial"

    async def test_returns_none_when_not_found(self, mock_session: AsyncMock) -> None:
        """get_trial returns None for missing trial."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        result = await get_trial(mock_session, "nonexistent-trial")
        assert result is None


class TestGetTrialCriteria:
    """get_trial_criteria returns inclusion + exclusion criteria."""

    async def test_returns_criteria_dict(self, mock_session: AsyncMock) -> None:
        """Returns both inclusion and exclusion criteria."""
        trial_id = "test-trial-1"
        fake_trial = Trial(
            trial_id=trial_id,
            trial_name="Test",
            inclusion_criteria={"min_age": 18},
            exclusion_criteria={"pregnant": True},
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fake_trial
        mock_session.execute.return_value = result_mock

        criteria = await get_trial_criteria(mock_session, trial_id)
        assert criteria["inclusion"]["min_age"] == 18
        assert criteria["exclusion"]["pregnant"] is True


class TestListActiveTrials:
    """list_active_trials returns only active trials."""

    async def test_returns_active_only(self, mock_session: AsyncMock) -> None:
        """Only active trials are returned."""
        active = Trial(trial_id="active-trial", trial_name="Active", active=True)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [active]
        mock_session.execute.return_value = result_mock

        trials = await list_active_trials(mock_session)
        assert len(trials) == 1
        assert trials[0].trial_name == "Active"


class TestSeedDiabetesStudyA:
    """seed_diabetes_study_a creates the demo trial."""

    async def test_seed_creates_trial(self, mock_session: AsyncMock) -> None:
        """Seed creates a trial with Diabetes Study A data."""
        trial = await seed_diabetes_study_a(mock_session)
        assert trial.trial_name == "Diabetes Study A"
        assert trial.pi_name is not None
        assert trial.inclusion_criteria is not None
        assert trial.exclusion_criteria is not None
        mock_session.add.assert_called_once()
