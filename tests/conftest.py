"""Shared test fixtures for Ask Mary test suite."""

import pytest

from src.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    """Provide test settings with safe defaults.

    Returns:
        Settings configured for testing (no real API calls).
    """
    return Settings(
        gcp_project_id="test-project",
        cloud_sql_password="test-password",
        cloud_sql_database="ask_mary_test",
        mary_id_pepper="test-pepper-do-not-use-in-production",
        openai_api_key="sk-test-fake-key",
    )
