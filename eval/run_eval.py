"""Evaluation runner -- loads YAML scenarios, executes steps, reports results."""

import dataclasses
import importlib
import inspect
import uuid
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def load_scenario(scenario_name: str) -> dict:
    """Load a YAML scenario file.

    Args:
        scenario_name: Name of scenario (without .yaml extension).

    Returns:
        Parsed scenario dict.

    Raises:
        FileNotFoundError: If scenario file doesn't exist.
    """
    path = SCENARIOS_DIR / f"{scenario_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario {scenario_name} not found")
    with open(path) as f:
        return yaml.safe_load(f)


def build_mock_participant(participant_data: dict) -> MagicMock:
    """Build a mock participant from scenario data.

    Args:
        participant_data: Dict with participant fields.

    Returns:
        MagicMock configured as a participant.
    """
    participant = MagicMock()
    participant.participant_id = uuid.uuid4()
    participant.first_name = participant_data.get("first_name", "Jane")
    participant.last_name = participant_data.get("last_name", "Doe")
    participant.phone = participant_data.get("phone", "+15035551234")
    participant.address_zip = participant_data.get("zip", "97201")
    participant.distance_to_site_km = participant_data.get("distance_km")
    dob_str = participant_data.get("dob", "1985-01-01")
    participant.date_of_birth = date.fromisoformat(dob_str)
    participant.identity_status = "unverified"
    participant.dnc_flags = {}
    participant.consent = {}
    participant.contactability = {}
    return participant


def build_mock_trial(
    trial_id: str | None,
    trial_data: dict | None = None,
) -> MagicMock:
    """Build a mock trial from scenario data.

    Args:
        trial_id: Trial identifier string.
        trial_data: Optional dict with trial-specific fields.

    Returns:
        MagicMock configured as a trial.
    """
    trial = MagicMock()
    trial.trial_id = trial_id
    data = trial_data or {}
    trial.max_distance_km = data.get("max_distance_km", 80.0)
    trial.inclusion_criteria = data.get("inclusion_criteria", {})
    trial.exclusion_criteria = data.get("exclusion_criteria", {})
    return trial


def _build_db_patches(
    steps: list[dict],
    participant: MagicMock,
    trial: MagicMock,
) -> list:
    """Build unittest.mock patches for DB functions in step modules.

    Imports each step module and patches any DB helper functions
    (get_participant_by_id, get_trial, log_event, create_appointment)
    with mocks that return the scenario's participant/trial.

    Args:
        steps: List of step dicts from scenario.
        participant: Mock participant to return from DB queries.
        trial: Mock trial to return from DB queries.

    Returns:
        List of patch context managers.
    """
    mock_funcs = {
        "get_participant_by_id": AsyncMock(return_value=participant),
        "get_trial": AsyncMock(return_value=trial),
        "log_event": AsyncMock(return_value=None),
        "create_appointment": AsyncMock(
            return_value=MagicMock(appointment_id=uuid.uuid4()),
        ),
    }

    patches: list = []
    seen_modules: set[str] = set()

    for step in steps:
        mod_path = step["module"]
        if mod_path in seen_modules:
            continue
        seen_modules.add(mod_path)
        mod = importlib.import_module(mod_path)
        for func_name, mock in mock_funcs.items():
            if hasattr(mod, func_name):
                patches.append(
                    patch(f"{mod_path}.{func_name}", new=mock)
                )

    return patches


def _apply_step_mock_data(
    step: dict,
    session: AsyncMock,
) -> None:
    """Configure session mock based on step-level mock_data.

    Some steps (e.g., detect_deception) use direct session.execute()
    queries instead of helper functions. This seeds the session mock
    so those queries return realistic data.

    Args:
        step: Step dict, may contain 'mock_data.session_result'.
        session: AsyncMock session to configure.
    """
    mock_data = step.get("mock_data")
    if not mock_data or "session_result" not in mock_data:
        return

    mock_obj = MagicMock()
    for key, value in mock_data["session_result"].items():
        setattr(mock_obj, key, value)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_obj
    session.execute.return_value = result_mock


async def execute_step(
    step: dict,
    session: AsyncMock,
    participant_id: uuid.UUID | None = None,
    trial_id: str | None = None,
) -> dict:
    """Execute a single scenario step.

    Args:
        step: Step dict with action, module, params, expect.
        session: Mock database session.
        participant_id: Participant UUID for this scenario.
        trial_id: Trial identifier from the scenario.

    Returns:
        Dict with 'passed' bool and actual result.
    """
    if step["action"] == "placeholder":
        return {"passed": True, "skipped": True}

    _apply_step_mock_data(step, session)

    module = importlib.import_module(step["module"])
    func = getattr(module, step["action"])
    params = step.get("params", {})
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    args: list[object] = []
    if "session" in param_names:
        args.append(session)
    if "participant_id" in param_names:
        args.append(participant_id or uuid.uuid4())
    if "trial_id" in param_names and trial_id is not None:
        args.append(trial_id)

    result = await func(*args, **params)

    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        result = dataclasses.asdict(result)
    elif not isinstance(result, dict):
        result = dict(result)

    expected = step.get("expect", {})
    passed = all(result.get(k) == v for k, v in expected.items())

    return {"passed": passed, "expected": expected, "actual": result}


async def run_scenario(scenario_name: str) -> dict:
    """Run a complete evaluation scenario.

    Args:
        scenario_name: Name of the scenario to run.

    Returns:
        Dict with scenario results.
    """
    scenario = load_scenario(scenario_name)
    session = AsyncMock()
    participant = build_mock_participant(scenario.get("participant", {}))
    trial_id = scenario.get("trial_id")
    trial = build_mock_trial(trial_id, scenario.get("trial"))

    steps = scenario.get("steps", [])
    patches = _build_db_patches(steps, participant, trial)

    results: list[dict] = []
    all_passed = True

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        for step in steps:
            try:
                step_result = await execute_step(
                    step,
                    session,
                    participant_id=participant.participant_id,
                    trial_id=trial_id,
                )
                results.append(step_result)
                if not step_result["passed"]:
                    all_passed = False
            except Exception as exc:
                results.append({"passed": False, "error": str(exc)})
                all_passed = False

    return {
        "scenario": scenario_name,
        "passed": all_passed,
        "steps": results,
        "total_steps": len(results),
    }
