# src/services/ — External Service Clients

Single-responsibility client wrappers for external APIs. Services never import from agents — agents import services.

## Planned Files (Phase 2+)

| File | Role |
|------|------|
| `twilio_client.py` | Twilio voice/SMS client (outbound calls, DNC sync, warm transfer) |
| `elevenlabs_client.py` | ElevenLabs Conversational AI client (server-side tools, DTMF) |
| `calendar_client.py` | Google Calendar slot booking and availability |
| `uber_client.py` | Uber Health ride booking (mock for MVP) |
| `gcs_client.py` | GCS audio storage (upload, signed URL generation) |
| `pubsub_client.py` | App-level Pub/Sub publisher for Postgres → Databricks bridge |

## Architecture Rules

- Each file wraps exactly one external service.
- All external API calls must be mockable for tests (no real API calls in test suite).
- Services are stateless — configuration comes from `src/config/settings.py`.
