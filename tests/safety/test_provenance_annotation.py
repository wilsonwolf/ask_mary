"""Immutable safety tests: provenance annotation, not overwrite."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from src.agents.screening import record_screening_response


class TestProvenanceAnnotation:
    """Screening responses annotate with provenance, preserve history."""

    async def test_records_with_provenance(self) -> None:
        """Response is recorded with provenance tag."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {}
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await record_screening_response(
            mock_session,
            uuid.uuid4(),
            "trial-1",
            "diagnosis",
            "type_2",
            "patient_stated",
        )
        assert result["recorded"] is True
        stored = pt.screening_responses["diagnosis"]
        assert stored["provenance"] == "patient_stated"
        assert stored["answer"] == "type_2"

    async def test_preserves_history_on_update(self) -> None:
        """Updating a response preserves the old value in history."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {
            "diagnosis": {
                "answer": "type_2",
                "provenance": "patient_stated",
            },
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await record_screening_response(
            mock_session,
            uuid.uuid4(),
            "trial-1",
            "diagnosis",
            "type_1",
            "ehr",
        )
        assert result["recorded"] is True
        current = pt.screening_responses["diagnosis"]
        assert current["answer"] == "type_1"
        assert current["provenance"] == "ehr"
        history = pt.screening_responses["diagnosis_history"]
        assert len(history) >= 1
        assert history[0]["answer"] == "type_2"
        assert history[0]["provenance"] == "patient_stated"

    async def test_accumulates_history_entries(self) -> None:
        """Multiple updates accumulate in history list."""
        mock_session = AsyncMock()
        pt = MagicMock()
        pt.screening_responses = {
            "diagnosis": {
                "answer": "type_2",
                "provenance": "patient_stated",
            },
            "diagnosis_history": [
                {"answer": "unknown", "provenance": "system"},
            ],
        }
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = pt
        mock_session.execute.return_value = result_mock

        result = await record_screening_response(
            mock_session,
            uuid.uuid4(),
            "trial-1",
            "diagnosis",
            "type_1",
            "ehr",
        )
        assert result["recorded"] is True
        history = pt.screening_responses["diagnosis_history"]
        assert len(history) == 2
        assert history[1]["answer"] == "type_2"
