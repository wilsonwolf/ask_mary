"""Immutable safety tests: DNC enforcement blocks outbound contact."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.outreach import check_dnc_before_contact
from src.shared.validators import is_dnc_blocked


class TestDncEnforcement:
    """DNC enforcement prevents contact on blocked channels."""

    async def test_blocks_voice_when_dnc_active(self) -> None:
        """Voice contact blocked when DNC flag set for voice."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {"voice": True}
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_dnc_before_contact(
                mock_session,
                uuid.uuid4(),
                "voice",
            )
        assert result["blocked"] is True
        assert result["reason"] == "dnc_active"

    async def test_blocks_sms_when_all_channels_dnc(self) -> None:
        """SMS contact blocked when all_channels DNC flag set."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {"all_channels": True}
        with patch(
            "src.agents.outreach.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_dnc_before_contact(
                mock_session,
                uuid.uuid4(),
                "sms",
            )
        assert result["blocked"] is True

    async def test_allows_contact_when_no_dnc(self) -> None:
        """Contact allowed when no DNC flags set."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {}
        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch(
                "src.agents.outreach.get_settings",
                return_value=MagicMock(twilio_account_sid=None),
            ),
        ):
            result = await check_dnc_before_contact(
                mock_session,
                uuid.uuid4(),
                "voice",
            )
        assert result["blocked"] is False

    def test_is_dnc_blocked_validator(self) -> None:
        """Validator correctly interprets DNC flags."""
        assert is_dnc_blocked({"voice": True}, "voice") is True
        assert is_dnc_blocked({"voice": True}, "sms") is False
        assert is_dnc_blocked({"all_channels": True}, "sms") is True
        assert is_dnc_blocked(None, "voice") is False
        assert is_dnc_blocked({}, "voice") is False
