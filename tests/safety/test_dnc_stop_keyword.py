"""Immutable safety tests: STOP keyword triggers DNC immediately."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.outreach import handle_stop_keyword


class TestDncStopKeyword:
    """STOP keyword sets DNC flag and logs the event."""

    async def test_sets_dnc_flag_on_voice(self) -> None:
        """STOP on voice sets voice DNC flag."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {}
        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch("src.agents.outreach.log_event", return_value=MagicMock()),
        ):
            result = await handle_stop_keyword(
                mock_session,
                uuid.uuid4(),
                "voice",
            )
        assert result["dnc_applied"] is True
        assert participant.dnc_flags["voice"] is True

    async def test_sets_dnc_flag_on_sms(self) -> None:
        """STOP on sms sets sms DNC flag."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {}
        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch("src.agents.outreach.log_event", return_value=MagicMock()),
        ):
            result = await handle_stop_keyword(
                mock_session,
                uuid.uuid4(),
                "sms",
            )
        assert result["dnc_applied"] is True
        assert participant.dnc_flags["sms"] is True

    async def test_preserves_existing_dnc_flags(self) -> None:
        """STOP on new channel preserves existing DNC flags."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.dnc_flags = {"voice": True}
        with (
            patch(
                "src.agents.outreach.get_participant_by_id",
                return_value=participant,
            ),
            patch("src.agents.outreach.log_event", return_value=MagicMock()),
        ):
            result = await handle_stop_keyword(
                mock_session,
                uuid.uuid4(),
                "sms",
            )
        assert result["dnc_applied"] is True
        assert participant.dnc_flags["voice"] is True
        assert participant.dnc_flags["sms"] is True
