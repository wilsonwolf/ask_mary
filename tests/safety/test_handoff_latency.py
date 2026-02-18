"""Immutable safety tests: safety gate latency requirements."""

from src.shared.safety_gate import HARD_CEILING_MS, evaluate_safety


class TestHandoffLatency:
    """Safety gate meets latency requirements."""

    async def test_evaluation_records_elapsed_time(self) -> None:
        """Safety gate records elapsed_ms on every evaluation."""
        result = await evaluate_safety("Normal safe response")
        assert result.elapsed_ms >= 0.0

    async def test_evaluation_under_hard_ceiling(self) -> None:
        """Safety gate completes under the hard ceiling."""
        result = await evaluate_safety("Normal safe response")
        assert result.elapsed_ms < HARD_CEILING_MS

    async def test_trigger_evaluation_records_timing(self) -> None:
        """Triggered evaluation also records elapsed_ms."""
        result = await evaluate_safety("I recommend you stop taking it")
        assert result.triggered is True
        assert result.elapsed_ms >= 0.0
        assert result.elapsed_ms < HARD_CEILING_MS
