# Ask Mary

**AI Clinical Trial Scheduling Agent** — recruits, screens, schedules, and reminds trial participants via voice and SMS in under 60 seconds.

Ask Mary is an autonomous voice agent that calls potential clinical trial participants, verifies their identity, screens for eligibility, books appointments, arranges transportation, and schedules follow-up communications — all in a single phone call with a real-time coordinator dashboard.

---

> **COST WARNING**: Cloud SQL costs **~$7-12/day** while running, even idle.
> After any demo or development session, **pause infrastructure immediately**.
> See [Runbook: Pause Everything](local_docs/runbook.md#after-the-demo-pause-everything).

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- GCP project with Cloud SQL, Cloud Run, Secret Manager
- ElevenLabs Conversational AI account
- Twilio account with phone number

### Local Development

```bash
# Clone and install
git clone https://github.com/wilsonwolf/ask_mary.git
cd ask_mary

# Backend dependencies
pip install uv
uv sync

# Frontend dependencies
cd frontend && npm ci && cd ..

# Configure environment
cp .env.example .env  # Edit with your credentials

# Run database migrations
uv run alembic upgrade head

# Seed demo data
uv run python scripts/seed_demo.py

# Register ElevenLabs server tools
set -a && source .env && set +a
python scripts/register_elevenlabs_tools.py --clean

# Start backend (port 8000)
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8000

# Start frontend dev server (port 5173)
cd frontend && npm run dev
```

### Deploy to GCP

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)
```

See the full [Operations Runbook](local_docs/runbook.md) for start/stop/teardown commands.

---

## Architecture

Ask Mary is built on three runtime systems:

| Layer | Technology | Role |
|-------|-----------|------|
| **Voice Agent** | ElevenLabs Conversational AI 2.0 + Twilio | Real-time voice conversations, DTMF capture |
| **Backend API** | FastAPI on Cloud Run | Tool execution, database, event logging, WebSocket |
| **Coordinator Dashboard** | React + TypeScript + Vite | Real-time monitoring, handoff management |

For detailed architecture with diagrams, see [ARCHITECTURE.md](ARCHITECTURE.md).

### Key Design Decisions

- **ElevenLabs is the runtime orchestrator** during voice calls — it decides tool call order based on the system prompt. No OpenAI/LLM calls in the real-time path.
- **OpenAI Agents SDK** is used only for background post-call analysis (supervisor audit, adversarial checks).
- **Tool gating removed** (disclosure/consent pre-checks on every tool) to eliminate latency. Safety is enforced via the system prompt conversation flow and reactive safety_check tool.
- **Safety gate is reactive** — `safety_check` is called only when the participant says something medically concerning, not on every response.
- **Append-only event log** with provenance tracking and idempotency keys for auditability.

---

## Project Structure

```
ask_mary/
├── src/
│   ├── agents/             # 9 agent modules (identity, screening, scheduling, etc.)
│   ├── api/                # FastAPI routes, webhooks, WebSocket, dashboard
│   ├── services/           # External clients (ElevenLabs, Twilio, GCS, etc.)
│   ├── db/                 # SQLAlchemy models, CRUD, event logging
│   ├── shared/             # Types (18 enums), validators, response models
│   ├── safety/             # Safety trigger definitions (7 triggers)
│   ├── workers/            # Cloud Tasks callback handlers
│   └── config/             # Pydantic Settings (env vars)
├── tests/                  # 530+ tests mirroring src/ structure
│   └── safety/             # Immutable safety tests (locked)
├── frontend/               # React + TypeScript + Tailwind dashboard
│   └── src/components/     # 12 dashboard components
├── comms_templates/        # 13 YAML message templates (Jinja2)
├── scripts/                # Tool registration, demo seeding
├── local_docs/             # Design docs, runbook, demo script
├── alembic/                # Database migrations
├── Dockerfile              # Multi-stage (Node frontend + Python backend)
├── cloudbuild.yaml         # GCP Cloud Build → Cloud Run
├── Makefile                # lint, format, typecheck, test, ci
└── CLAUDE.md               # Development guidelines (7 mandatory standards)
```

### Dependency Direction

```
api/ → agents/ → services/ → db/ → shared/
```

Agents never import other agents. Services never import agents. No circular imports.

---

## Conversation Flow (S0-S9 Pipeline)

```
S1: Outreach → S2: Identity → S3: Screening → S4: Scheduling → S7: Transport → S8: Comms
      │              │              │               │               │            │
   Disclosure   DOB + ZIP    Eligibility     Calendar query    Uber Health   Reminders
   + Consent    verification  determination   + booking        booking       T-48h/24h/2h
```

Each step is gated — the ElevenLabs agent follows strict ordering enforced by the system prompt. The dashboard updates in real-time via WebSocket for every event.

### Safety Gates

| Gate | Mechanism | When |
|------|-----------|------|
| DNC enforcement | Database check | Before outreach |
| Disclosure | System prompt step 1 | Call start |
| Consent | `capture_consent` tool | After disclosure |
| Identity | `verify_identity` tool | Before sharing any trial details |
| Safety check | `safety_check` tool (reactive) | On medically concerning input |
| Warm transfer | Tier 1 (emergency) / Tier 2 (stuck) | Real-time during call |

---

## Data Model

9 core tables in Cloud SQL Postgres:

| Table | Purpose |
|-------|---------|
| `participants` | Demographics, consent, identity status, DNC flags |
| `participant_trials` | Multi-trial enrollment, screening responses, eligibility |
| `trials` | Trial metadata, criteria, operating hours |
| `appointments` | Scheduled visits (held → booked → confirmed) |
| `conversations` | Call transcripts, audio paths, call SIDs |
| `events` | Append-only audit log with provenance + idempotency |
| `handoff_queue` | Safety escalations for coordinator action |
| `rides` | Transport bookings |
| `agent_reasoning` | Internal agent decision traces |

See [Database Schema](local_docs/database_schema.md) for full column definitions.

---

## API Endpoints

### Webhooks (ElevenLabs + Twilio)

| Endpoint | Purpose |
|----------|---------|
| `POST /webhooks/elevenlabs/server-tool` | 18 server tool handlers (identity, screening, scheduling, etc.) |
| `POST /webhooks/elevenlabs/call-complete` | Post-call audio fetch, transcript storage, supervisor audit |
| `POST /webhooks/twilio/dtmf` | DTMF digit capture for identity verification |
| `POST /webhooks/twilio/status` | Call SID association |

### Dashboard REST API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/participants` | List participants |
| `GET /api/participants/{id}` | Participant detail with trials, conversations, appointments |
| `GET /api/appointments` | List appointments |
| `GET /api/handoff-queue` | Active handoff tickets |
| `GET /api/conversations` | Recent conversations |
| `GET /api/events` | Paginated event feed |
| `GET /api/analytics/summary` | Aggregate statistics |
| `POST /api/demo/start-call` | Trigger outbound demo call |
| `WS /ws/events` | Real-time event streaming |

---

## Development

### Code Quality

```bash
make lint        # ruff check
make format      # ruff format
make typecheck   # mypy --strict
make test        # pytest (530+ tests)
make coverage    # pytest with coverage report
make ci          # lint + typecheck + test
```

### 7 Mandatory Standards

1. **DRY** — Search existing code before writing; shared utilities in `src/shared/`
2. **Clean Code** — 20-line max functions, descriptive naming, type hints everywhere
3. **TDD** — Red-Green-Refactor; tests before implementation; 80% coverage minimum
4. **Microservices** — Strict dependency direction; no cross-agent imports
5. **Git Worktrees** — Feature branches, never develop on main
6. **Immutable Tests** — `tests/safety/` is locked; fix implementation, not tests
7. **Documentation** — README per directory, Google-style docstrings, 90% docstring coverage

### Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/agents/test_screening.py -v

# Run with coverage
make coverage
```

Tests mock all external services (ElevenLabs, Twilio, GCS, Postgres). No real API calls in tests.

---

## Environment Variables

| Group | Variables |
|-------|-----------|
| GCP | `gcp_project_id`, `gcp_region` |
| Cloud SQL | `cloud_sql_instance_connection`, `cloud_sql_database`, `cloud_sql_user`, `cloud_sql_password` |
| ElevenLabs | `elevenlabs_api_key`, `elevenlabs_agent_id`, `elevenlabs_agent_phone_number_id` |
| Twilio | `twilio_account_sid`, `twilio_auth_token`, `twilio_phone_number` |
| GCS | `gcs_audio_bucket` |
| Public URL | `public_base_url` (Cloud Run URL for Twilio callbacks) |
| CORS | `cors_allowed_origins` (dashboard origins) |
| Demo | `demo_participant_phone`, `demo_trial_id` |

See [Configuration README](src/config/README.md) for the full list.

---

## Live Demo

The 60-second demo proves end-to-end functionality:

1. Click **Start Demo Call** on the dashboard
2. Answer phone — Mary introduces herself and discloses automation
3. Provide consent, DOB year, and ZIP code
4. Answer 2-3 screening questions
5. Mary determines eligibility and offers appointment slots
6. Book appointment, confirm transport
7. Dashboard shows real-time updates for every step

See the full [Demo Script](local_docs/demo_script.md) for the run-of-show.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagrams, data flow, infrastructure |
| [Runbook](local_docs/runbook.md) | Start/stop/teardown commands, cost reference |
| [Demo Script](local_docs/demo_script.md) | 60-second live demo walkthrough |
| [Master Plan](local_docs/ask_mary_plan.md) | PRD, architecture decisions, implementation plan |
| [Database Schema](local_docs/database_schema.md) | Full table definitions |
| [Implementation Tracker](local_docs/implementation_tracker.md) | Phase-by-phase progress |
| [Known Issues](local_docs/known_issues.md) | Current limitations and workarounds |
| [Human Setup Checklist](local_docs/human_setup_checklist.md) | GCP/Twilio/ElevenLabs initial setup |

---

## Infrastructure Cost

> **IMPORTANT: Shut down after every session to avoid unnecessary charges.**

| Service | Running Cost | Idle Cost | How to Stop |
|---------|-------------|-----------|-------------|
| Cloud SQL (Postgres) | **~$7-12/day** | $0 if stopped | `gcloud sql instances patch ask-mary-db --activation-policy=NEVER` |
| Cloud Run | ~$0.50-1.00/day | $0 at min-instances=0 | `gcloud run services update ask-mary --min-instances=0` |
| GCS bucket | ~$0.02/GB/month | Same | Leave running (negligible) |
| Artifact Registry | ~$0.10/GB/month | Same | Leave running (negligible) |

**Quick pause** (drops to ~$0/month):
```bash
gcloud sql instances patch ask-mary-db --activation-policy=NEVER --project=ask-mary-486802
gcloud run services update ask-mary --region=us-west2 --min-instances=0 --project=ask-mary-486802
```

**Quick resume**:
```bash
gcloud sql instances patch ask-mary-db --activation-policy=ALWAYS --project=ask-mary-486802
# Cloud Run auto-scales from 0 on next request
```

See the full [Runbook](local_docs/runbook.md) for all operations commands.

---

## License

Hackathon project. All rights reserved.
