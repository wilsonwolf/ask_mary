"""Integration tests for Twilio webhook routing."""

from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


class TestTwilioWebhook:
    """Twilio webhook endpoint integration."""

    async def test_elevenlabs_server_tool_route_exists(self) -> None:
        """ElevenLabs server tool webhook endpoint responds."""
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/webhooks/elevenlabs/server-tool")
            assert response.status_code != 404

    async def test_twilio_dtmf_route_exists(self) -> None:
        """Twilio DTMF capture webhook endpoint responds."""
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/webhooks/twilio/dtmf")
            assert response.status_code != 404

    async def test_twilio_dtmf_verify_route_exists(self) -> None:
        """Twilio DTMF verify webhook endpoint responds."""
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/webhooks/twilio/dtmf-verify")
            assert response.status_code != 404
