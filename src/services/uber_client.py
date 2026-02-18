"""Mock Uber Health client for MVP transport integration."""

import uuid
from dataclasses import dataclass


@dataclass
class RideEstimate:
    """Estimated ride details.

    Attributes:
        estimated_minutes: Estimated travel time.
        estimated_cost_usd: Estimated cost in USD.
    """

    estimated_minutes: int
    estimated_cost_usd: float


@dataclass
class RideBookingResult:
    """Result of a ride booking.

    Attributes:
        uber_ride_id: External ride identifier.
        status: Booking status.
    """

    uber_ride_id: str
    status: str


class MockUberHealthClient:
    """Mock Uber Health API client for MVP.

    Returns deterministic fake data for testing and demo.
    """

    async def get_estimate(
        self,
        *,
        pickup: str,
        dropoff: str,
    ) -> RideEstimate:
        """Get a ride estimate between two addresses.

        Args:
            pickup: Pickup address.
            dropoff: Dropoff address.

        Returns:
            RideEstimate with mock data.
        """
        return RideEstimate(
            estimated_minutes=25,
            estimated_cost_usd=18.50,
        )

    async def book_ride(
        self,
        *,
        pickup: str,
        dropoff: str,
        scheduled_at: str,
    ) -> RideBookingResult:
        """Book a ride.

        Args:
            pickup: Pickup address.
            dropoff: Dropoff address.
            scheduled_at: ISO datetime string for pickup.

        Returns:
            RideBookingResult with mock ride ID.
        """
        return RideBookingResult(
            uber_ride_id=f"mock-ride-{uuid.uuid4().hex[:8]}",
            status="confirmed",
        )
