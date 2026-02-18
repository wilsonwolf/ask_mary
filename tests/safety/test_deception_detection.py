"""Immutable safety tests: adversarial deception detection."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.agents.adversarial import detect_deception


class TestDeceptionDetection:
    """Adversarial checker detects inconsistencies vs EHR data."""

    async def test_detects_mismatch_with_ehr(self) -> None:
        """Deception detected when screening differs from EHR."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {
            "pregnant_or_nursing": {
                "answer": "no",
                "provenance": "patient_stated",
            },
        }
        pt.ehr_discrepancies = {
            "pregnant_or_nursing": "yes",
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await detect_deception(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["deception_detected"] is True
        assert len(result["discrepancies"]) > 0

    async def test_no_deception_when_matching(self) -> None:
        """No deception when screening matches EHR."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {
            "pregnant_or_nursing": {
                "answer": "no",
                "provenance": "patient_stated",
            },
        }
        pt.ehr_discrepancies = {}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await detect_deception(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["deception_detected"] is False

    async def test_handles_missing_ehr_data(self) -> None:
        """No deception when EHR data is missing/None."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {
            "diagnosis": {
                "answer": "type_2",
                "provenance": "patient_stated",
            },
        }
        pt.ehr_discrepancies = None
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await detect_deception(
            mock_session,
            uuid.uuid4(),
            "trial-1",
        )
        assert result["deception_detected"] is False
        assert result["discrepancies"] == []
