"""Immutable safety tests: no PHI shared before identity verification."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.shared.validators import check_identity_gate


class TestNoPhiBeforeIdentity:
    """PHI must not be shared before identity is verified."""

    async def test_blocks_unverified_participant(self) -> None:
        """Identity gate blocks unverified participants."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.identity_status = "unverified"
        with patch(
            "src.shared.validators.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_identity_gate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["passed"] is False

    async def test_allows_verified_participant(self) -> None:
        """Identity gate allows verified participants."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.identity_status = "verified"
        with patch(
            "src.shared.validators.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_identity_gate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["passed"] is True

    async def test_blocks_wrong_person(self) -> None:
        """Identity gate blocks wrong_person status."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.identity_status = "wrong_person"
        with patch(
            "src.shared.validators.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_identity_gate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["passed"] is False
