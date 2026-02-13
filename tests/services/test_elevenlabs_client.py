"""Tests for the ElevenLabs service client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.elevenlabs_client import (
    CallResult,
    ElevenLabsClient,
    build_conversation_config_override,
    build_dynamic_variables,
    build_system_prompt,
)


class TestBuildDynamicVariables:
    """Pure function: build_dynamic_variables."""

    def test_returns_expected_keys(self) -> None:
        """Dynamic variables contain all required keys."""
        result = build_dynamic_variables(
            participant_name="Jane Doe",
            trial_name="Diabetes Study A",
            site_name="OHSU Research Center",
            coordinator_phone="+15035551234",
            participant_id="pid-123",
            trial_id="trial-abc",
        )
        assert result["participant_name"] == "Jane Doe"
        assert result["trial_name"] == "Diabetes Study A"
        assert result["site_name"] == "OHSU Research Center"
        assert result["coordinator_phone"] == "+15035551234"
        assert result["participant_id"] == "pid-123"
        assert result["trial_id"] == "trial-abc"

    def test_returns_dict(self) -> None:
        """Return type is a plain dict."""
        result = build_dynamic_variables(
            participant_name="A",
            trial_name="B",
            site_name="C",
            coordinator_phone="D",
        )
        assert isinstance(result, dict)

    def test_defaults_participant_id_and_trial_id(self) -> None:
        """participant_id and trial_id default to empty string."""
        result = build_dynamic_variables(
            participant_name="A",
            trial_name="B",
            site_name="C",
            coordinator_phone="D",
        )
        assert result["participant_id"] == ""
        assert result["trial_id"] == ""


class TestBuildConversationConfigOverride:
    """Pure function: build_conversation_config_override."""

    def test_returns_agent_and_first_message(self) -> None:
        """Config override contains agent prompt and first message."""
        result = build_conversation_config_override(
            system_prompt="You are Mary.",
            first_message="Hello, this is Mary.",
        )
        assert result["agent"]["prompt"]["prompt"] == "You are Mary."
        assert result["agent"]["first_message"] == "Hello, this is Mary."


class TestBuildSystemPrompt:
    """Pure function: build_system_prompt."""

    def test_includes_trial_criteria(self) -> None:
        """System prompt contains inclusion/exclusion criteria."""
        result = build_system_prompt(
            trial_name="Diabetes Study A",
            site_name="OHSU",
            coordinator_phone="+15035551234",
            inclusion_criteria={"age": "18-65", "diagnosis": "Type 2 Diabetes"},
            exclusion_criteria={"pregnancy": "excluded"},
            visit_templates={"screening": "60 min"},
        )
        assert "INCLUSION CRITERIA" in result
        assert "age: 18-65" in result
        assert "EXCLUSION CRITERIA" in result
        assert "pregnancy: excluded" in result
        assert "VISIT SCHEDULE" in result
        assert "screening: 60 min" in result
        assert "Diabetes Study A" in result
        assert "+15035551234" in result

    def test_handles_empty_criteria(self) -> None:
        """System prompt handles empty criteria gracefully."""
        result = build_system_prompt(
            trial_name="Study B",
            site_name="Site B",
            coordinator_phone="+10000000000",
            inclusion_criteria={},
            exclusion_criteria={},
            visit_templates={},
        )
        assert "None specified" in result
        assert "No visit schedule defined" in result


class TestCallResult:
    """CallResult dataclass."""

    def test_fields(self) -> None:
        """CallResult stores conversation_id and status."""
        result = CallResult(
            conversation_id="conv-123",
            status="initiated",
        )
        assert result.conversation_id == "conv-123"
        assert result.status == "initiated"


class TestInitiateOutboundCall:
    """ElevenLabs outbound call initiation."""

    @pytest.fixture
    def client(self) -> ElevenLabsClient:
        """Provide an ElevenLabsClient with test config."""
        return ElevenLabsClient(
            api_key="test-key",
            agent_id="test-agent-id",
            agent_phone_number_id="test-phone-id",
        )

    async def test_returns_call_result(self, client: ElevenLabsClient) -> None:
        """initiate_outbound_call returns a CallResult on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "conversation_id": "conv-abc",
            "status": "initiated",
        }

        with patch("src.services.elevenlabs_client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.initiate_outbound_call(
                customer_number="+15035551234",
                dynamic_variables={"participant_name": "Test"},
                config_override={"agent": {"prompt": {"prompt": "Hi"}}},
            )

        assert isinstance(result, CallResult)
        assert result.conversation_id == "conv-abc"
        assert result.status == "initiated"
