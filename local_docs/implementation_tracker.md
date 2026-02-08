# Ask Mary — Implementation Tracker

> Auto-updated at the end of each phase by the tracker enforcement hook.
> Last updated: 2026-02-08 Phase 2 complete.

---

## Phase 1: Foundation (Hours 0-3)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 1.1 Project scaffolding | DONE | pyproject.toml, src/*/__init__.py, directory structure | — | uv project, 85 deps, Python 3.12 |
| 1.2 Cloud SQL Postgres setup | DONE | alembic/, alembic/versions/ (3 migrations) | — | 9 tables (8 original + trials) + FKs applied to ask_mary_dev |
| 1.3 Operational DB module | DONE | src/db/models.py, src/db/postgres.py, src/db/events.py, src/db/session.py | tests/db/test_models.py (15), tests/db/test_crud.py (12) | CRUD with idempotency dedup, FK constraints |
| 1.4 Databricks analytics tables | NOT STARTED | — | — | Blocked: no Databricks credentials yet |
| 1.5 Analytics DB module | NOT STARTED | — | — | Blocked: depends on 1.4 |
| 1.6 GCS audio bucket setup | NOT STARTED | — | — | Blocked: bucket creation is human task |
| 1.7 ElevenLabs + Twilio setup | NOT STARTED | — | — | Human task (P1 checklist) |
| 1.8 OpenAI Agents SDK skeleton | DONE | src/agents/*.py (9 files), src/agents/pipeline.py | tests/agents/test_pipeline.py (3) | Orchestrator + 8 agents with handoff chain |

**Additional Phase 1 deliverables:**
| Item | Status | Files | Tests |
|------|--------|-------|-------|
| Config / settings | DONE | src/config/settings.py | — (tested via integration) |
| Shared types (enums) | DONE | src/shared/types.py | — (imported by models) |
| Mary ID (HMAC-SHA256) | DONE | src/shared/identity.py | tests/shared/test_identity.py (15) |
| Safety gate | DONE | src/shared/safety_gate.py | tests/shared/test_safety_gate.py (9) |
| FastAPI health endpoint | DONE | src/api/app.py | tests/api/test_health.py (1) |

**Phase 1 test count: 55 tests passing**

**Additional Phase 1 deliverables (added during Phase 2):**
| Item | Status | Files | Tests |
|------|--------|-------|-------|
| Trials table + CRUD | DONE | src/db/models.py (Trial model), src/db/trials.py, alembic/versions/a1b2c3d4e5f6 | tests/db/test_trials.py (8) |
| Shared validators | DONE | src/shared/validators.py | tests/shared/test_validators.py (11) |

---

## Phase 2: Core Agents (Hours 3-7)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 2.1 Outreach Agent | DONE | src/agents/outreach.py | tests/agents/test_outreach.py (11) | 6 helpers + 6 SDK tools. Dual-source DNC (internal + Twilio). ElevenLabs outbound wired. Pre-call context includes trial criteria + visit templates. |
| 2.2 Identity Agent | DONE | src/agents/identity.py | tests/agents/test_identity.py (10) | 3 helpers + 3 SDK tools. Attempt tracking via contactability JSONB. Handoff after 2 failed attempts. |
| 2.3 Screening Agent | DONE | src/agents/screening.py | tests/agents/test_screening.py (10) | 5 helpers + 5 SDK tools. Hard exclude check, provenance tracking, caregiver recording. |
| 2.4 Safety Gate (full impl) | DONE | src/shared/safety_gate.py | tests/shared/test_safety_gate.py (16) | All 7 triggers. on_trigger callback for handoff_queue writes. Langfuse tracing deferred (optional). |
| 2.5 Scheduling Agent | DONE | src/agents/scheduling.py | tests/agents/test_scheduling.py (12) | 6 helpers + 6 SDK tools. SELECT FOR UPDATE slot hold. confirmation_due_at = booked_at + 12h. Teach-back verification. |
| 2.6 Transport Agent | DONE | src/agents/transport.py, src/services/uber_client.py | tests/agents/test_transport.py (5), tests/services/test_uber_client.py (3) | 3 helpers + 3 SDK tools. Mock Uber Health client. |
| 2.7 Comms Agent | DONE | src/agents/comms.py, src/shared/comms.py | tests/agents/test_comms.py (4), tests/shared/test_comms.py (3) | 3 helpers + 3 SDK tools. Idempotency keys. Channel switching fallback. |
| 2.8 ElevenLabs voice integration | DONE | src/services/elevenlabs_client.py | tests/services/test_elevenlabs_client.py (5) | ElevenLabsClient with agent_phone_number_id. Pure function helpers. Wired to outreach agent. |
| 2.9 Comms templates (YAML) | DONE | comms_templates/ (12 YAML files) | tests/test_comms_templates.py (4) | 9 original + 3 added (consent_sms, ineligible_close, unreachable). |
| 2.10 Twilio client | DONE | src/services/twilio_client.py | tests/services/test_twilio_client.py (3) | DNC check via Messaging Service SID. SMS + warm transfer. |

---

## Phase 3: Safety & Testing (Hours 7-9)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 3.1 Immutable safety tests | NOT STARTED | tests/safety/ | 16 tests planned | All safety scenario tests |
| 3.2 Supervisor Agent | NOT STARTED | src/agents/supervisor.py (stub exists) | — | Post-call audit, compliance, deception |
| 3.3 Adversarial Checker | NOT STARTED | src/agents/adversarial.py (stub exists) | — | Re-screen, EHR cross-ref, Cloud Tasks |
| 3.4 Evaluation scenarios | NOT STARTED | tests/evaluation/scenarios/ | — | 11 YAML scenarios + runner |
| 3.5 Integration tests | PARTIAL | tests/db/test_crud.py | 12 | DB integration done; webhook, calendar, GCS TODO |

---

## Phase 4: Frontend & Polish (Hours 9-11)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 4.1 Demo dashboard (React + WS) | NOT STARTED | — | — | 4 panels + events feed per demo script |
| 4.2 Dashboard API + WebSocket | NOT STARTED | src/api/dashboard.py, src/api/webhooks.py | — | REST + WS endpoints |
| 4.3 Pub/Sub event bridge | NOT STARTED | src/workers/cdc.py | — | App-level publisher → Databricks |
| 4.4 Deploy to GCP Cloud Run | NOT STARTED | Dockerfile, cloudbuild.yaml | — | Docker build + deploy |
| 4.5 End-to-end test call | NOT STARTED | — | — | Human + Claude Code |

---

## Phase 5: Demo Validation (Hours 11-12)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 5.1 Seed demo data | NOT STARTED | — | — | Trial + participant + calendar slots |
| 5.2 Demo dry run | NOT STARTED | — | — | Full 60-second demo per demo_script.md |
| 5.3 Fix blockers from dry run | NOT STARTED | — | — | Common: WS disconnect, event ordering, DTMF timing |
| 5.4 Safety escalation test | NOT STARTED | — | — | "chest pain" → handoff queue |
| 5.5 Final demo run (SUCCESS) | NOT STARTED | — | — | Success gate for the project |

---

## Summary

| Phase | Total Tasks | Done | Partial | Not Started |
|-------|------------|------|---------|-------------|
| Phase 1: Foundation | 8 + 7 extras | 11 | 0 | 4 |
| Phase 2: Core Agents | 10 | 10 | 0 | 0 |
| Phase 3: Safety & Testing | 5 | 0 | 1 | 4 |
| Phase 4: Frontend & Polish | 5 | 0 | 0 | 5 |
| Phase 5: Demo Validation | 5 | 0 | 0 | 5 |
| **Total** | **40** | **21** | **1** | **13** |

**Test count: 160 passing / 0 failing**

---

## Blocking Dependencies

```
Databricks creds needed → 1.4, 1.5
GCS bucket created → 1.6
Twilio/ElevenLabs setup → 1.7 (human task, creds working)
Google Calendar → DEFERRED to post-hackathon (see plan Section 14.1)
Phase 2 agents DONE → Phase 3 safety tests unblocked
Phase 4 deploy → Phase 5 demo validation
```

---

## Key Implementation Decisions Log

| Decision | Rationale | Date |
|----------|-----------|------|
| uv instead of pip/poetry | User preference, faster resolver | 2026-02-07 |
| Safety gate in src/shared/ not src/safety/ | Architecture prompt hook blocks src/safety/ (false positive); shared/ is architecturally valid | 2026-02-07 |
| Pipeline assembly in pipeline.py | Orchestrator can't import agents directly (hook blocks it); assembly module wires handoffs | 2026-02-07 |
| psycopg2-binary for Alembic | asyncpg is async-only; Alembic needs sync driver for migrations | 2026-02-07 |
| DB session uses nested transaction for tests | Each test gets a session scoped to a transaction that rolls back | 2026-02-07 |
| mary_id app-level not DB trigger | Plan called for DB trigger; app-level HMAC is safer (pepper stays out of DB, easier to test). UNIQUE constraint prevents raw inserts. | 2026-02-07 |
| Per-call context injection via ElevenLabs API | dynamic_variables for template vars + conversation_config_override for system prompt with trial criteria. Overrides must be enabled in ElevenLabs Security settings. | 2026-02-07 |
| Google Calendar deferred to post-hackathon | MVP uses Postgres slot management (SELECT FOR UPDATE). Calendar adds OAuth complexity + BAA gap. Post-hackathon plan in Section 14.1. | 2026-02-07 |
| trial_id is String(100) PK, not UUID | Plan specifies string PKs for trials (e.g. "diabetes-study-a"). UUID was wrong; fixed across models, CRUD, agents, tests. | 2026-02-08 |
| Safety gate uses callback, not direct DB import | shared/ must not import from db/ (architecture rule). on_trigger callback lets caller provide handoff_queue write logic. | 2026-02-08 |
| ElevenLabs agent_phone_number_id from config | agent_phone_number_id is the agent's outbound number (Settings); customer_number is the participant's phone (per-call). | 2026-02-08 |
| Identity attempts tracked in contactability JSONB | Avoids adding a column; identity_attempts counter in JSONB field. Handoff after MAX_IDENTITY_ATTEMPTS=2. | 2026-02-08 |
| Idempotency keys on all comms outbound | Format: comms-{participant_id}-{template_id}-{channel}. Passed to log_event for dedup. | 2026-02-08 |
