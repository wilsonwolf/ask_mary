# Ask Mary — Project Overview

## Purpose
AI clinical trial scheduling agent that automates participant recruitment via voice and text. Handles outreach (DNC enforcement), consent capture, identity verification, eligibility screening, appointment scheduling (geo gates, confirmation windows), transportation, event-driven communications, and structured coordinator handoffs.

## Tech Stack
- **Language**: Python 3.12, managed by `uv`
- **Agent SDK**: OpenAI Agents SDK (`from agents import Agent` — third-party package `openai-agents`)
- **Voice**: ElevenLabs Conversational AI 2.0 + Twilio
- **Web Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0 (async, asyncpg driver)
- **Migrations**: Alembic (sync, psycopg2-binary driver)
- **OLTP Database**: Cloud SQL Postgres (via Cloud SQL Auth Proxy on localhost:5432)
- **OLAP Database**: Databricks Delta Lake (trials, EHR, analytics)
- **Config**: Pydantic Settings from `.env`
- **Deployment**: GCP Cloud Run (Docker)
- **Observability**: Langfuse + Databricks MLflow

## Project Structure
```
src/
  agents/       # One file per agent (9 agents + pipeline.py assembly)
  api/          # FastAPI routes (app factory + health endpoint)
  config/       # Pydantic Settings
  db/           # SQLAlchemy models, session, CRUD, event logging
  safety/       # Reserved (safety gate currently in shared/)
  services/     # External service clients (planned)
  shared/       # Cross-cutting: types, identity, safety_gate
  workers/      # Background task handlers (planned)
tests/          # Mirrors src/ structure
comms_templates/ # YAML templates with Jinja2
local_docs/     # Plan docs, tracker, demo script
alembic/        # Database migrations
```

## Architecture Rules
- Agents NEVER import from other agents (communicate via orchestrator handoffs)
- Services NEVER import from agents
- Dependency direction: api → agents → services → db → shared
- `pipeline.py` is the assembly module that wires orchestrator handoffs to all agents
- No circular imports

## Key Terminology
- Use "participant" not "patient" throughout
- `mary_id` = HMAC-SHA256(canonicalize(first|last|dob|phone), pepper)

## Plan Documents
- `local_docs/ask_mary_plan.md` — Master plan (PRD, architecture, data model, impl plan)
- `local_docs/agent_dev_workflow_plan.md` — Dev workflow infrastructure
- `local_docs/implementation_tracker.md` — Phase-by-phase task tracker
