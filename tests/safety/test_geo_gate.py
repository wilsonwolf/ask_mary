"""Immutable safety tests: geo/distance gate enforcement."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.scheduling import check_geo_eligibility


class TestGeoGate:
    """Geo gate blocks participants outside protocol max distance."""

    async def test_eligible_within_max_distance(self) -> None:
        """Participant within max_distance_km is eligible."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.distance_to_site_km = 30.0
        trial = MagicMock()
        trial.max_distance_km = 80.0
        with (
            patch(
                "src.agents.scheduling.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.scheduling.get_trial",
                return_value=trial,
            ),
        ):
            result = await check_geo_eligibility(
                mock_session,
                uuid.uuid4(),
                "trial-1",
            )
        assert result["eligible"] is True

    async def test_ineligible_beyond_max_distance(self) -> None:
        """Participant beyond max_distance_km is ineligible."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.distance_to_site_km = 100.0
        trial = MagicMock()
        trial.max_distance_km = 80.0
        with (
            patch(
                "src.agents.scheduling.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.scheduling.get_trial",
                return_value=trial,
            ),
        ):
            result = await check_geo_eligibility(
                mock_session,
                uuid.uuid4(),
                "trial-1",
            )
        assert result["eligible"] is False
        assert result["distance_km"] == 100.0

    async def test_eligible_when_distance_unknown(self) -> None:
        """Unknown distance defaults to eligible."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.distance_to_site_km = None
        trial = MagicMock()
        trial.max_distance_km = 80.0
        with (
            patch(
                "src.agents.scheduling.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.scheduling.get_trial",
                return_value=trial,
            ),
        ):
            result = await check_geo_eligibility(
                mock_session,
                uuid.uuid4(),
                "trial-1",
            )
        assert result["eligible"] is True
        assert result["reason"] == "distance_unknown"
