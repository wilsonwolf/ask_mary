"""Tests for health check endpoint."""

from fastapi.testclient import TestClient

from src.api.app import app


def test_health_returns_ok() -> None:
    """Health endpoint returns 200 with status ok."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
