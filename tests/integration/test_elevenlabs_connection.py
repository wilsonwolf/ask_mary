"""Integration tests for ElevenLabs client construction."""

from src.services.elevenlabs_client import ElevenLabsClient


class TestElevenLabsConnection:
    """ElevenLabs client setup and configuration."""

    def test_client_construction(self) -> None:
        """Client constructs with required parameters."""
        client = ElevenLabsClient(
            api_key="test-key",
            agent_id="test-agent",
            agent_phone_number_id="test-phone",
        )
        assert client.api_key == "test-key"
        assert client.agent_id == "test-agent"

    def test_client_stores_phone_number_id(self) -> None:
        """Client stores the agent phone number ID."""
        client = ElevenLabsClient(
            api_key="test-key",
            agent_id="test-agent",
            agent_phone_number_id="test-phone",
        )
        assert client.agent_phone_number_id == "test-phone"
