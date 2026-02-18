# src/api/ — FastAPI Routes

HTTP and WebSocket endpoints for Ask Mary.

## Files

| File | Role |
|------|------|
| `app.py` | Application factory (`create_app()`) and health check endpoint |

## Planned Files (Phase 4)

| File | Role |
|------|------|
| `webhooks.py` | Twilio/ElevenLabs inbound webhooks |
| `dashboard.py` | Dashboard REST API + WebSocket for live events |

## Key Decisions

- **App factory pattern**: `create_app()` returns a configured `FastAPI` instance, enabling test isolation via `TestClient(create_app())`.
- **Health endpoint**: `GET /health` returns `{"status": "ok"}` — used by Cloud Run readiness probes.
