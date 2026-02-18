"""Tests for the agent pipeline assembly."""

from src.agents.pipeline import build_pipeline


def test_pipeline_builds() -> None:
    """Pipeline assembles without errors."""
    orch = build_pipeline()
    assert orch.name == "orchestrator"


def test_pipeline_has_all_handoffs() -> None:
    """Pipeline includes all 8 specialized agents."""
    orch = build_pipeline()
    handoff_names = [h.name for h in orch.handoffs]
    expected = [
        "outreach",
        "identity",
        "screening",
        "scheduling",
        "transport",
        "comms",
        "supervisor",
        "adversarial",
    ]
    assert handoff_names == expected


def test_agents_have_instructions() -> None:
    """Every agent in the pipeline has non-empty instructions."""
    orch = build_pipeline()
    assert orch.instructions
    for agent in orch.handoffs:
        assert agent.instructions, f"{agent.name} has no instructions"
