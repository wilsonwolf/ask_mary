# Ask Mary — Development Guidelines

## Project Context

AI clinical trial scheduling agent for clinical trials. Full architecture in `local_docs/ask_mary_plan.md`.
Dev workflow infrastructure in `local_docs/agent_dev_workflow_plan.md`.

## Plugins Active

- **Superpowers**: TDD, git worktrees, subagent dev, code review, verification
- **Ralph Wiggum**: autonomous iteration loops (invoke with /ralph-loop)
- **Serena MCP**: semantic code intelligence (find_symbol, find_referencing_symbols)

## MANDATORY STANDARDS (enforced by plugins + hooks + CI/CD)

### 1. DRY — Don't Repeat Yourself

- Before writing any new function: search with Serena MCP for existing implementations
- Shared utilities go in src/shared/ (db, validators, comms, auth, types)
- If logic appears in 2+ places, extract to src/shared/ and import
- Database query patterns: use shared CRUD functions in src/shared/db.py
- Validation logic: use shared validators in src/shared/validators.py
- Event logging: use the central log_event() function

### 2. Clean Code (Robert C. Martin)

- Functions: max 20 lines, single responsibility, max 3 params
- Naming: descriptive verb-noun (verify_identity, log_event), no abbreviations
- Variables: participant not pt, appointment not appt
- Booleans: is_/has_/can_/should_ prefix
- Constants: UPPER_SNAKE_CASE
- Classes: PascalCase nouns (ScreeningAgent, HandoffQueue)
- No magic numbers — use named constants or enums
- No nested conditionals deeper than 2 levels — use early returns
- No commented-out code — delete it (git has history)
- Type hints on ALL function signatures (mypy --strict enforced)
- Formatter: ruff format | Linter: ruff check | Types: mypy --strict

### 3. TDD — Test-Driven Development

Enforced by Superpowers test-driven-development skill (auto-activates).

- RED: Write failing test FIRST. Do NOT write implementation before the test.
- GREEN: Minimum code to pass. Commit.
- REFACTOR: Clean up. Tests must still pass. Commit.
- Test file mirrors source: src/agents/screening.py -> tests/agents/test_screening.py
- Test names describe behavior: test_identity_rejects_wrong_dob()
- Use pytest + pytest-asyncio for async code
- Use fixtures in conftest.py for shared test setup
- Mock all external services (Twilio, ElevenLabs, Databricks) — never call real APIs in tests
- Coverage target: 80% (measured by pytest-cov)

Commit pattern:
- "test: add failing test for [feature]"     <- RED
- "feat: implement [feature]"                <- GREEN
- "refactor: clean up [feature]"             <- REFACTOR

### 4. Microservices Architecture

```
src/
  agents/           # Agent implementations (one file per agent)
    orchestrator.py
    outreach.py
    identity.py
    screening.py
    scheduling.py
    transport.py
    comms.py
    supervisor.py
    adversarial.py
  safety/           # Safety gate (inline check, not a full agent)
    gate.py
    triggers.py
  services/         # External service clients (single responsibility)
    twilio_client.py
    elevenlabs_client.py
    calendar_client.py
    uber_client.py   # Mock for MVP
    gcs_client.py
    pubsub_client.py
  db/               # Database layer
    postgres.py     # SQLAlchemy models + CRUD
    databricks.py   # Read-only analytics connector
    events.py       # Append-only event logging
  shared/           # Cross-cutting shared utilities
    types.py        # Pydantic models, enums, constants
    validators.py   # Input validation
    comms.py        # Template rendering
    auth.py         # Auth helpers
  api/              # FastAPI routes
    webhooks.py     # Twilio/ElevenLabs webhooks
    dashboard.py    # Dashboard REST API
    health.py       # Health check endpoint
  workers/          # Background task handlers
    reminders.py    # Cloud Tasks callbacks
    cdc.py          # Pub/Sub -> Databricks bridge
  config/           # Configuration
    settings.py     # Pydantic Settings (env vars)
comms_templates/    # YAML templates (NOT in src/)
tests/              # Mirror of src/ structure
```

Rules:
- Agents NEVER import from other agents. They communicate via orchestrator handoffs.
- Services NEVER import from agents. Agents import services.
- shared/ can be imported by anyone. Nothing imports from shared/ into shared/.
- db/ is accessed through defined interfaces, not raw SQL in agent code.
- No circular imports. Dependency direction: api -> agents -> services -> db -> shared

### 5. Git Worktrees

Enforced by Superpowers using-git-worktrees skill (auto-activates).

- NEVER develop features directly on main or dev
- Create worktree: git worktree add ../ask-mary-{feature} -b feature/{feature}
- One worktree per major feature
- Merge to dev first, then dev -> main
- Clean up after merge: git worktree remove ../ask-mary-{feature}

### 6. Immutable Tests

Files in tests/safety/ are LOCKED. You MUST NOT:
- Edit any file in tests/safety/
- Delete any file in tests/safety/
- Rename any file in tests/safety/
- Change the expected outcomes of any safety test

If a safety test fails, the IMPLEMENTATION is wrong, not the test.
Fix the implementation to make the test pass.

Enforced by PreToolUse hook (blocks writes to tests/safety/).

### 7. Documentation

- Every directory under src/ MUST have a README.md
- All public functions MUST have Google-style docstrings (Args, Returns, Raises)
- Private functions (_prefixed) — docstring optional but encouraged
- Architecture diagrams auto-generated by noodles on PR

## Tools

- Formatter: ruff format
- Linter: ruff check
- Type checker: mypy --strict
- Test runner: pytest
- Coverage: pytest-cov (80% minimum)
- Docstring coverage: interrogate (90% minimum)
- Duplicate detection: jscpd (3% max)
- Architecture diagrams: noodles (unslop run)
- Code intelligence: Serena MCP (find_symbol, find_referencing_symbols)

## Terminology

- Use "participant" not "patient" throughout all code, comments, and documentation
- Internal participant identifier: mary_id = hash(first_name, last_name, dob, phone)

## Handoff Protocol

When implementation is complete:
1. Touch .ralph-complete marker
2. Ralph loop exits -> handoff-to-codex.sh pushes PR
3. Codex reviews PR against 7 guidelines
4. Address comments -> push fixes -> Codex re-reviews
5. All CI/CD checks pass -> merge to dev
