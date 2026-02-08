# src/db/ — Database Layer

SQLAlchemy ORM models, async session management, CRUD operations, and event logging for Cloud SQL Postgres.

## Files

| File | Role |
|------|------|
| `models.py` | 8 SQLAlchemy ORM models (Participant, ParticipantTrial, Appointment, Conversation, Event, HandoffQueue, Ride, AgentReasoning) |
| `session.py` | Async engine factory and `get_session()` generator |
| `events.py` | `log_event()` — append-only event logging with idempotency key dedup |
| `postgres.py` | CRUD functions (create_participant, enroll_in_trial, create_appointment, etc.) |

## Key Decisions

- **Async engine**: `asyncpg` driver with `pool_size=5, max_overflow=10` via Cloud SQL Auth Proxy.
- **Idempotency dedup**: `log_event()` checks for existing `idempotency_key` before insert; returns `None` on duplicate. Prevents duplicate outbound actions from retries or Cloud Tasks redelivery.
- **mary_id generation**: `create_participant()` auto-generates the HMAC-SHA256 `mary_id` using inputs + pepper.
- **pipeline_status on ParticipantTrial**: Per-trial progression (not per-participant), supporting multi-trial enrollment.
- **agent_reasoning separated from conversations**: Internal prompts and reasoning traces are never commingled with conversation data.
- **audio_gcs_path**: Stores GCS object path only; signed URLs generated on demand.

## Migrations

Managed by Alembic in `/alembic/`. Uses the sync `psycopg2` driver since Alembic doesn't support async natively.
