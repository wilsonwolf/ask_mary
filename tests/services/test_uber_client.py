"""Tests for the mock Uber Health client."""



from src.services.uber_client import (
    MockUberHealthClient,
    RideBookingResult,
    RideEstimate,
)


class TestRideEstimate:
    """RideEstimate dataclass."""

    def test_fields(self) -> None:
        """RideEstimate stores estimate details."""
        estimate = RideEstimate(
            estimated_minutes=25,
            estimated_cost_usd=18.50,
        )
        assert estimate.estimated_minutes == 25
        assert estimate.estimated_cost_usd == 18.50


class TestMockUberHealthClient:
    """Mock Uber Health client for MVP."""

    async def test_get_estimate_returns_estimate(self) -> None:
        """get_estimate returns a RideEstimate."""
        client = MockUberHealthClient()
        estimate = await client.get_estimate(
            pickup="123 Main St",
            dropoff="456 Oak Ave",
        )
        assert isinstance(estimate, RideEstimate)
        assert estimate.estimated_minutes > 0

    async def test_book_ride_returns_result(self) -> None:
        """book_ride returns a RideBookingResult."""
        client = MockUberHealthClient()
        result = await client.book_ride(
            pickup="123 Main St",
            dropoff="456 Oak Ave",
            scheduled_at="2026-03-16T09:00:00Z",
        )
        assert isinstance(result, RideBookingResult)
        assert result.uber_ride_id.startswith("mock-ride-")
        assert result.status == "confirmed"
