"""Immutable safety tests: disclosure gate blocks without consent."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.shared.validators import check_disclosure_gate


class TestDisclosureBeforeProceed:
    """Participant must consent after disclosure before proceeding."""

    async def test_blocks_without_disclosure(self) -> None:
        """Gate blocks when disclosure not given."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.consent = {}
        with patch(
            "src.shared.validators.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_disclosure_gate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["passed"] is False

    async def test_blocks_without_consent_to_continue(self) -> None:
        """Gate blocks when disclosed but no consent to continue."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.consent = {
            "disclosed_automation": True,
            "consent_to_continue": False,
        }
        with patch(
            "src.shared.validators.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_disclosure_gate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["passed"] is False

    async def test_allows_with_full_consent(self) -> None:
        """Gate allows when disclosure given and consent captured."""
        mock_session = AsyncMock()
        participant = MagicMock()
        participant.consent = {
            "disclosed_automation": True,
            "consent_to_continue": True,
        }
        with patch(
            "src.shared.validators.get_participant_by_id",
            return_value=participant,
        ):
            result = await check_disclosure_gate(
                mock_session,
                uuid.uuid4(),
            )
        assert result["passed"] is True
