"""Tests for the evaluation framework runner."""

import dataclasses
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from eval.metrics import aggregate, check_failures, score_scenario
from eval.run_eval import (
    _apply_step_mock_data,
    _build_db_patches,
    build_mock_participant,
    build_mock_trial,
    execute_step,
    load_scenario,
)


class TestLoadScenario:
    """Scenario YAML loading."""

    def test_loads_valid_scenario(self) -> None:
        """Loads happy_path scenario successfully."""
        scenario = load_scenario("happy_path")
        assert scenario["scenario"] == "happy_path"
        assert "steps" in scenario
        assert len(scenario["steps"]) > 0

    def test_raises_on_missing_scenario(self) -> None:
        """Raises FileNotFoundError for nonexistent scenario."""
        with pytest.raises(FileNotFoundError):
            load_scenario("nonexistent_scenario")

    def test_scenario_has_trial_id(self) -> None:
        """Scenario includes trial_id at top level."""
        scenario = load_scenario("happy_path")
        assert "trial_id" in scenario
        assert isinstance(scenario["trial_id"], str)


class TestBuildMockParticipant:
    """Mock participant construction."""

    def test_builds_from_data(self) -> None:
        """Builds mock participant with expected fields."""
        data = {"first_name": "Jane", "zip": "97201", "distance_km": 30.0}
        participant = build_mock_participant(data)
        assert participant.first_name == "Jane"
        assert participant.address_zip == "97201"
        assert participant.distance_to_site_km == 30.0

    def test_includes_date_of_birth(self) -> None:
        """Builds participant with proper date_of_birth object."""
        data = {"dob": "1985-06-15"}
        participant = build_mock_participant(data)
        assert participant.date_of_birth == date(1985, 6, 15)
        assert participant.date_of_birth.year == 1985

    def test_default_dnc_flags_empty(self) -> None:
        """Default dnc_flags is empty dict, not MagicMock."""
        participant = build_mock_participant({})
        assert participant.dnc_flags == {}


class TestBuildMockTrial:
    """Mock trial construction."""

    def test_builds_with_defaults(self) -> None:
        """Builds trial with default max_distance_km."""
        trial = build_mock_trial("test-trial")
        assert trial.trial_id == "test-trial"
        assert trial.max_distance_km == 80.0

    def test_builds_with_custom_distance(self) -> None:
        """Builds trial with custom max_distance_km."""
        trial = build_mock_trial("test-trial", {"max_distance_km": 100.0})
        assert trial.max_distance_km == 100.0


class TestBuildDbPatches:
    """DB function patching."""

    def test_patches_known_db_functions(self) -> None:
        """Creates patches for DB functions found in step modules."""
        steps = [
            {"action": "verify_identity", "module": "src.agents.identity"},
        ]
        participant = MagicMock()
        trial = MagicMock()
        patches = _build_db_patches(steps, participant, trial)
        assert len(patches) > 0

    def test_skips_duplicate_modules(self) -> None:
        """Only patches each module once."""
        steps = [
            {"action": "verify_identity", "module": "src.agents.identity"},
            {"action": "mark_wrong_person", "module": "src.agents.identity"},
        ]
        participant = MagicMock()
        trial = MagicMock()
        patches_once = _build_db_patches(steps[:1], participant, trial)
        patches_twice = _build_db_patches(steps, participant, trial)
        assert len(patches_once) == len(patches_twice)


class TestApplyStepMockData:
    """Step-level mock_data configuration."""

    def test_no_mock_data_is_noop(self) -> None:
        """Step without mock_data leaves session unchanged."""
        session = AsyncMock()
        original = session.execute
        _apply_step_mock_data({"action": "test"}, session)
        assert session.execute is original

    def test_seeds_session_from_mock_data(self) -> None:
        """Step with mock_data configures session.execute result."""
        session = AsyncMock()
        step = {
            "action": "detect_deception",
            "mock_data": {
                "session_result": {
                    "screening_responses": {"q1": {"answer": "no"}},
                    "ehr_discrepancies": {"q1": "yes"},
                },
            },
        }
        _apply_step_mock_data(step, session)
        result = session.execute.return_value
        obj = result.scalar_one_or_none()
        assert obj.screening_responses == {"q1": {"answer": "no"}}
        assert obj.ehr_discrepancies == {"q1": "yes"}


class TestExecuteStep:
    """Step execution."""

    @pytest.mark.asyncio
    async def test_placeholder_skipped(self) -> None:
        """Placeholder steps return passed + skipped."""
        step = {
            "action": "placeholder",
            "module": "src.agents.scheduling",
            "params": {},
            "expect": {"placeholder": True},
        }
        result = await execute_step(step, AsyncMock())
        assert result["passed"] is True
        assert result["skipped"] is True

    @pytest.mark.asyncio
    async def test_handles_dataclass_result(self) -> None:
        """Converts dataclass results to dict for comparison."""

        @dataclasses.dataclass
        class FakeResult:
            triggered: bool = True
            severity: str = "HANDOFF_NOW"

        async def fake_func(response: str) -> FakeResult:
            return FakeResult()

        import types

        fake_mod = types.ModuleType("fake_mod")
        fake_mod.fake_action = fake_func

        import sys

        sys.modules["fake_mod"] = fake_mod
        try:
            step = {
                "action": "fake_action",
                "module": "fake_mod",
                "params": {"response": "test"},
                "expect": {"triggered": True, "severity": "HANDOFF_NOW"},
            }
            result = await execute_step(step, AsyncMock())
            assert result["passed"] is True
            assert result["actual"]["triggered"] is True
        finally:
            del sys.modules["fake_mod"]


class TestMetrics:
    """Scoring and aggregation."""

    def test_score_all_passed(self) -> None:
        """Score is 1.0 when all steps pass."""
        result = {
            "scenario": "test",
            "passed": True,
            "total_steps": 2,
            "steps": [{"passed": True}, {"passed": True}],
        }
        assert score_scenario(result) == 1.0

    def test_score_partial_pass(self) -> None:
        """Score reflects partial pass rate."""
        result = {
            "scenario": "test",
            "passed": False,
            "total_steps": 4,
            "steps": [
                {"passed": True},
                {"passed": False},
                {"passed": True},
                {"passed": False},
            ],
        }
        assert score_scenario(result) == 0.5

    def test_score_empty_steps(self) -> None:
        """Score is 0.0 when there are no steps."""
        result = {
            "scenario": "test",
            "passed": False,
            "total_steps": 0,
            "steps": [],
        }
        assert score_scenario(result) == 0.0

    def test_check_failures_extracts_errors(self) -> None:
        """Failure descriptions extracted from failed steps."""
        result = {
            "steps": [
                {"passed": True},
                {"passed": False, "error": "timeout"},
                {"passed": False},
            ],
        }
        failures = check_failures(result)
        assert len(failures) == 2
        assert "Step 1: timeout" in failures
        assert "Step 2: assertion mismatch" in failures

    def test_aggregate_multiple_scenarios(self) -> None:
        """Aggregation counts pass/fail correctly."""
        results = [
            {
                "scenario": "a",
                "passed": True,
                "total_steps": 1,
                "steps": [{"passed": True}],
            },
            {
                "scenario": "b",
                "passed": False,
                "total_steps": 1,
                "steps": [{"passed": False}],
            },
        ]
        agg = aggregate(results)
        assert agg["total"] == 2
        assert agg["passed"] == 1
        assert agg["failed"] == 1
        assert agg["scores"]["a"] == 1.0
        assert agg["scores"]["b"] == 0.0
