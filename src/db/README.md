# src/db/ -- Database Layer

SQLAlchemy ORM models, async session management, CRUD operations, and event logging for Cloud SQL Postgres.

## Files

| File | Role |
|------|------|
| `models.py` | 9 SQLAlchemy ORM models (Participant, ParticipantTrial, Appointment, Conversation, Event, HandoffQueue, Ride, Trial, AgentReasoning) |
| `session.py` | Async engine factory and `get_session()` generator with auto-commit/rollback |
| `events.py` | `log_event()` -- append-only event logging with idempotency key dedup |
| `postgres.py` | Participant, appointment, handoff, ride, conversation, and enrollment CRUD |
| `trials.py` | Trial-specific CRUD: `create_trial`, `get_trial`, `get_trial_criteria`, `list_active_trials`, `seed_diabetes_study_a` |
| `databricks.py` | No-op stub connector (Databricks blocked by OAuth errors; analytics stay in Postgres for MVP) |

### models.py -- ORM Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Participant` | `participants` | Participant record with `mary_id` (HMAC-SHA256), contact info, identity/consent state |
| `ParticipantTrial` | `participant_trials` | Junction table for multi-trial enrollment with per-trial pipeline/eligibility status |
| `Appointment` | `appointments` | Scheduled visit with confirmation window, teach-back tracking, cancellation/no-show fields |
| `Conversation` | `conversations` | Voice or text conversation with transcript, audio GCS path, handoff reason |
| `Event` | `events` | Append-only event log with provenance, idempotency key, and composite index |
| `HandoffQueue` | `handoff_queue` | Structured handoff tickets for human coordinators (HANDOFF_NOW, CALLBACK_TICKET, STOP_CONTACT) |
| `Ride` | `rides` | Transport ride booking linked to appointment and participant |
| `Trial` | `trials` | Clinical trial definition with inclusion/exclusion criteria, visit templates, operating hours |
| `AgentReasoning` | `agent_reasoning` | Agent internal reasoning traces separated from conversations |

### postgres.py -- CRUD Functions

| Function | Description |
|----------|-------------|
| `create_participant` | Create participant with auto-generated HMAC mary_id |
| `get_participant_by_mary_id` | Look up by deterministic identifier |
| `get_participant_by_id` | Look up by UUID |
| `enroll_in_trial` | Create ParticipantTrial junction record |
| `get_participant_trial` | Look up enrollment by participant + trial composite key |
| `create_appointment` | Create appointment with BOOKED status |
| `get_appointment` | Look up appointment by UUID |
| `create_handoff` | Create handoff ticket for coordinators |
| `create_ride` | Create transport ride booking |
| `get_ride` | Look up ride by UUID |
| `create_conversation` | Create conversation record with ACTIVE status |

### trials.py -- Trial CRUD Functions

| Function | Description |
|----------|-------------|
| `create_trial` | Create trial record (auto-generates trial_id if omitted) |
| `get_trial` | Look up trial by string ID |
| `get_trial_criteria` | Get inclusion/exclusion criteria dict for a trial |
| `list_active_trials` | List all trials where `active=True` |
| `seed_diabetes_study_a` | Seed the demo Diabetes Study A trial with sample criteria |

## Key Decisions

- **Async engine**: `asyncpg` driver with `pool_size=5, max_overflow=10` via Cloud SQL Auth Proxy.
- **Session auto-commit**: `get_session()` commits on successful completion and rolls back on exception. This prevents silent data loss from uncommitted sessions.
- **Idempotency dedup**: `log_event()` checks for existing `idempotency_key` before insert; returns `None` on duplicate. Prevents duplicate outbound actions from retries or Cloud Tasks redelivery.
- **mary_id generation**: `create_participant()` auto-generates the HMAC-SHA256 `mary_id` using inputs + pepper.
- **pipeline_status on ParticipantTrial**: Per-trial progression (not per-participant), supporting multi-trial enrollment.
- **agent_reasoning separated from conversations**: Internal prompts and reasoning traces are never commingled with conversation data.
- **audio_gcs_path**: Stores GCS object path only; signed URLs generated on demand.
- **Databricks stubbed**: The `DatabricksConnector` returns empty results and logs warnings. All analytics remain in Postgres for the MVP.

## Migrations

Managed by Alembic in `/alembic/`. Uses the sync `psycopg2` driver since Alembic doesn't support async natively.
