"""Evaluation metrics -- scoring, failure checking, aggregation."""


def score_scenario(result: dict) -> float:
    """Score a scenario result as pass rate.

    Args:
        result: Scenario result dict from run_scenario.

    Returns:
        Float between 0.0 and 1.0.
    """
    total = result.get("total_steps", 0)
    if total == 0:
        return 0.0
    passed = sum(1 for s in result.get("steps", []) if s.get("passed"))
    return passed / total


def check_failures(result: dict) -> list[str]:
    """Extract failure descriptions from scenario result.

    Args:
        result: Scenario result dict.

    Returns:
        List of failure description strings.
    """
    failures: list[str] = []
    for i, step in enumerate(result.get("steps", [])):
        if not step.get("passed"):
            error = step.get("error", "assertion mismatch")
            failures.append(f"Step {i}: {error}")
    return failures


def aggregate(results: list[dict]) -> dict:
    """Aggregate multiple scenario results.

    Args:
        results: List of scenario result dicts.

    Returns:
        Dict with total/passed/failed counts and per-scenario scores.
    """
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    scores = {r["scenario"]: score_scenario(r) for r in results}
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "scores": scores,
    }
