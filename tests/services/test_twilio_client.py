"""Tests for the Twilio service client."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.twilio_client import TwilioClient


@pytest.fixture
def twilio_client() -> TwilioClient:
    """Provide a TwilioClient with test credentials."""
    return TwilioClient(
        account_sid="ACtest123",
        auth_token="test-token",
        from_number="+15035550000",
    )


class TestCheckDncStatus:
    """DNC status check via Twilio."""

    def test_returns_false_when_not_opted_out(self, twilio_client: TwilioClient) -> None:
        """Non-opted-out number returns False."""
        with patch.object(twilio_client, "_check_opt_out", return_value=False):
            result = twilio_client.check_dnc_status("+15035551234")
        assert result is False

    def test_returns_true_when_opted_out(self, twilio_client: TwilioClient) -> None:
        """Opted-out number returns True."""
        with patch.object(twilio_client, "_check_opt_out", return_value=True):
            result = twilio_client.check_dnc_status("+15035551234")
        assert result is True


class TestSendSms:
    """SMS sending via Twilio."""

    async def test_send_sms_returns_sid(self, twilio_client: TwilioClient) -> None:
        """send_sms returns message SID on success."""
        mock_message = MagicMock()
        mock_message.sid = "SM1234567890"
        with patch.object(twilio_client, "_client") as mock_client:
            mock_client.messages.create.return_value = mock_message
            result = await twilio_client.send_sms(
                to="+15035551234",
                body="Hello from Ask Mary",
            )
        assert result == "SM1234567890"


class TestInitiateWarmTransfer:
    """Warm transfer to coordinator."""

    async def test_warm_transfer_returns_call_sid(self, twilio_client: TwilioClient) -> None:
        """initiate_warm_transfer returns call SID."""
        mock_call = MagicMock()
        mock_call.sid = "CA1234567890"
        with patch.object(twilio_client, "_client") as mock_client:
            mock_client.calls.create.return_value = mock_call
            result = await twilio_client.initiate_warm_transfer(
                participant_call_sid="CA0000000000",
                coordinator_phone="+15035559999",
            )
        assert result == "CA1234567890"
