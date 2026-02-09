"""Immutable safety tests: identity verification gates."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.identity import (
    detect_duplicate,
    mark_wrong_person,
    verify_identity,
)


class TestIdentityVerification:
    """Identity verification ensures only the correct person proceeds."""

    async def test_verifies_with_correct_dob_and_zip(self) -> None:
        """Correct DOB year and ZIP verifies identity."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.date_of_birth = date(1985, 6, 15)
        participant.address_zip = "97201"
        participant.identity_status = "unverified"
        participant.contactability = {}
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=participant,
        ):
            result = await verify_identity(
                mock_session,
                uuid.uuid4(),
                1985,
                "97201",
            )
        assert result["verified"] is True
        assert participant.identity_status == "verified"

    async def test_rejects_wrong_dob_year(self) -> None:
        """Wrong DOB year rejects identity."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.date_of_birth = date(1985, 6, 15)
        participant.address_zip = "97201"
        participant.identity_status = "unverified"
        participant.contactability = {}
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=participant,
        ):
            result = await verify_identity(
                mock_session,
                uuid.uuid4(),
                1990,
                "97201",
            )
        assert result["verified"] is False

    async def test_handoff_after_max_attempts(self) -> None:
        """Handoff required after 2 failed identity attempts."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.date_of_birth = date(1985, 6, 15)
        participant.address_zip = "97201"
        participant.identity_status = "unverified"
        participant.contactability = {"identity_attempts": 1}
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=participant,
        ):
            result = await verify_identity(
                mock_session,
                uuid.uuid4(),
                1990,
                "97201",
            )
        assert result["handoff_required"] is True
        assert result["attempts"] == 2

    async def test_mark_wrong_person_sets_dnc(self) -> None:
        """Wrong person marking sets DNC on all channels."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.identity_status = "unverified"
        participant.dnc_flags = {}
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=participant,
        ):
            result = await mark_wrong_person(
                mock_session,
                uuid.uuid4(),
            )
        assert result["marked"] is True
        assert participant.identity_status == "wrong_person"
        assert participant.dnc_flags["all_channels"] is True

    async def test_detect_duplicate_flags_match(self) -> None:
        """Duplicate detection finds matching participants."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.date_of_birth = date(1985, 6, 15)
        participant.address_zip = "97201"
        participant.phone = "+15035551234"
        dup_id = uuid.uuid4()
        result_mock = MagicMock()
        result_mock.all.return_value = [(dup_id,)]
        mock_session.execute.return_value = result_mock
        with (
            patch(
                "src.agents.identity.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.identity.log_event",
                return_value=MagicMock(),
            ),
        ):
            result = await detect_duplicate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["is_duplicate"] is True
