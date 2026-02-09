"""Tests for Databricks no-op stub connector."""

import logging

import pytest

from src.db.databricks import DatabricksConnector


class TestDatabricksConnector:
    """Verify all stub methods return empty results and log warnings."""

    @pytest.fixture
    def connector(self) -> DatabricksConnector:
        """Create a DatabricksConnector instance."""
        return DatabricksConnector()

    async def test_get_trial_returns_empty(
        self,
        connector: DatabricksConnector,
    ) -> None:
        """get_trial returns empty dict for any trial_id."""
        result = await connector.get_trial("diabetes-study-a")
        assert result == {}

    async def test_get_participant_ehr_returns_empty(
        self,
        connector: DatabricksConnector,
    ) -> None:
        """get_participant_ehr returns empty dict."""
        result = await connector.get_participant_ehr("mary-id-123")
        assert result == {}

    async def test_get_conversations_archive_returns_empty(
        self,
        connector: DatabricksConnector,
    ) -> None:
        """get_conversations_archive returns empty list."""
        result = await connector.get_conversations_archive("mary-id-123")
        assert result == []

    async def test_get_audit_log_returns_empty(
        self,
        connector: DatabricksConnector,
    ) -> None:
        """get_audit_log returns empty list."""
        result = await connector.get_audit_log(limit=100)
        assert result == []

    async def test_stub_logs_warning(
        self,
        connector: DatabricksConnector,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each stub method logs a warning about Databricks being stubbed."""
        with caplog.at_level(logging.WARNING):
            await connector.get_trial("any-trial")
        assert "databricks stubbed" in caplog.text.lower()
