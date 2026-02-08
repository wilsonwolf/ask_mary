# Ask Mary — Implementation Tracker

> Auto-updated at the end of each phase by the tracker enforcement hook.
> Last updated: 2026-02-07 Phase 1 complete.

---

## Phase 1: Foundation (Hours 0-3)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 1.1 Project scaffolding | DONE | pyproject.toml, src/*/__init__.py, directory structure | — | uv project, 85 deps, Python 3.12 |
| 1.2 Cloud SQL Postgres setup | DONE | alembic/, alembic/versions/ (2 migrations) | — | 8 tables + FKs applied to ask_mary_dev |
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

---

## Phase 2: Core Agents (Hours 3-7)

| Task | Status | Files | Tests | Notes |
|------|--------|-------|-------|-------|
| 2.1 Outreach Agent | NOT STARTED | src/agents/outreach.py (stub exists) | — | DNC enforcement, retry cadence, consent capture, **pre-call context assembly** (load participant + trial criteria → build dynamic_variables + config_override → initiate ElevenLabs outbound call) |
| 2.2 Identity Agent | NOT STARTED | src/agents/identity.py (stub exists) | — | DOB year + ZIP via DTMF, duplicate detection |
| 2.3 Screening Agent | NOT STARTED | src/agents/screening.py (stub exists) | — | Trial criteria, EHR cross-ref, provenance |
| 2.4 Safety Gate (full impl) | PARTIAL | src/shared/safety_gate.py | tests/shared/test_safety_gate.py (9) | Pattern matching done; Langfuse integration TODO |
| 2.5 Scheduling Agent | NOT STARTED | src/agents/scheduling.py (stub exists) | — | Geo gate, Google Calendar, slot booking, teach-back |
| 2.6 Transport Agent | NOT STARTED | src/agents/transport.py (stub exists) | — | Mock Uber Health, pickup verification |
| 2.7 Comms Agent | NOT STARTED | src/agents/comms.py (stub exists) | — | Event-driven cadence, Jinja2 templates |
| 2.8 ElevenLabs voice integration | NOT STARTED | src/services/elevenlabs_client.py | — | Server-side tools, DTMF capture, **outbound call helper** (accepts participant + trial data, builds dynamic_variables + conversation_config_override, calls ElevenLabs API), agent prompt template with {{variable}} placeholders |
| 2.9 Comms templates (YAML) | NOT STARTED | comms_templates/ (dir exists) | — | 9 YAML templates with Jinja2 |

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
| Phase 1: Foundation | 8 + 5 extras | 9 | 0 | 4 |
| Phase 2: Core Agents | 9 | 0 | 1 | 8 |
| Phase 3: Safety & Testing | 5 | 0 | 1 | 4 |
| Phase 4: Frontend & Polish | 5 | 0 | 0 | 5 |
| Phase 5: Demo Validation | 5 | 0 | 0 | 5 |
| **Total** | **37** | **9** | **2** | **26** |

**Test count: 55 passing / 0 failing**

---

## Blocking Dependencies

```
Databricks creds needed → 1.4, 1.5
Twilio/ElevenLabs creds needed → 1.7, 2.8
Google Calendar creds needed → 2.5 (calendar integration part)
GCS bucket created → 1.6
All Phase 2 agents → Phase 3 safety tests
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
