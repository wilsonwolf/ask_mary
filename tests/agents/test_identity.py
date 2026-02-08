"""Tests for the identity agent function tools.

Tests the internal verification functions with mocked sessions.
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.identity import (
    identity_agent,
    mark_wrong_person,
    update_identity_status,
    verify_identity,
)


class TestIdentityAgentDefinition:
    """Identity agent is properly configured."""

    def test_has_tools(self) -> None:
        """Identity agent has function tools registered."""
        assert len(identity_agent.tools) == 3

    def test_has_instructions(self) -> None:
        """Identity agent has instructions."""
        assert identity_agent.instructions


class TestVerifyIdentity:
    """Identity verification via DOB year + ZIP."""

    async def test_verified_with_matching_data(self) -> None:
        """Returns verified when DOB year and ZIP match."""
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
            result = await verify_identity(mock_session, uuid.uuid4(), 1985, "97201")
        assert result["verified"] is True
        assert participant.identity_status == "verified"
        assert result["attempts"] == 1

    async def test_rejected_with_wrong_dob(self) -> None:
        """Returns unverified when DOB year does not match."""
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
            result = await verify_identity(mock_session, uuid.uuid4(), 1990, "97201")
        assert result["verified"] is False

    async def test_rejected_with_wrong_zip(self) -> None:
        """Returns unverified when ZIP does not match."""
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
            result = await verify_identity(mock_session, uuid.uuid4(), 1985, "97202")
        assert result["verified"] is False

    async def test_handoff_after_max_attempts(self) -> None:
        """Returns handoff_required after 2 failed attempts."""
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
                mock_session, uuid.uuid4(), 1990, "97201",
            )
        assert result["verified"] is False
        assert result["handoff_required"] is True
        assert result["attempts"] == 2

    async def test_returns_error_when_not_found(self) -> None:
        """Returns error when participant not found."""
        mock_session = AsyncMock()
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=None,
        ):
            result = await verify_identity(
                mock_session, uuid.uuid4(), 1985, "97201",
            )
        assert result["error"] == "participant_not_found"

    async def test_tracks_attempt_count(self) -> None:
        """Attempt count increments on each call."""
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
                mock_session, uuid.uuid4(), 1990, "97201",
            )
        assert result["attempts"] == 1
        assert result["verified"] is False
        assert "handoff_required" not in result


class TestMarkWrongPerson:
    """Wrong person detection and suppression."""

    async def test_sets_wrong_person_and_dnc(self) -> None:
        """Wrong person sets identity_status + DNC all_channels."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.identity_status = "unverified"
        participant.dnc_flags = {}
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=participant,
        ):
            result = await mark_wrong_person(mock_session, uuid.uuid4())
        assert participant.identity_status == "wrong_person"
        assert participant.dnc_flags["all_channels"] is True
        assert result["marked"] is True


class TestUpdateIdentityStatus:
    """Identity status updates."""

    async def test_updates_status(self) -> None:
        """Updates the identity_status field."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.identity_status = "unverified"
        with patch(
            "src.agents.identity.get_participant_by_id",
            return_value=participant,
        ):
            result = await update_identity_status(mock_session, uuid.uuid4(), "verified")
        assert participant.identity_status == "verified"
        assert result["updated"] is True
