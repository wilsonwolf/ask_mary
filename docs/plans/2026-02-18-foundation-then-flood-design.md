# Foundation Then Flood — Parallel Bug-Fix Strategy

> **Date**: 2026-02-18
> **Goal**: Get Ask Mary to near-production structural correctness via 7+ parallel agents
> **Approach**: Define type contracts first (Phase 0), then fan out to 7 parallel agents (Phase 1)
> **Simplifications**: No Databricks, no Firebase, Google Calendar deferred
> **Orchestration decision**: Migrate to ElevenLabs Workflows (subagent nodes per gate)

---

## Problem Statement

The codebase has 339 passing tests and 60/69 planned tasks complete, but is **semantically disconnected**:

1. **16 enums defined, zero used** — `src/shared/types.py` has `IdentityStatus`, `PipelineStatus`, `AppointmentStatus`, etc. None are imported by agents, DB models, or services
2. **34 agent functions return `-> dict`** — No Pydantic response models, no type safety at boundaries
3. **DB models use magic strings** — `default="unverified"` instead of `IdentityStatus.UNVERIFIED`
4. **Pipeline state never tracked** — `participant_trials.pipeline_status` is never updated during calls (KI-10)
5. **Safety gates depend on ElevenLabs prompt** — DNC/consent checks not enforced at backend level
6. **No CI/CD** — No GitHub Actions, no Makefile
7. **Architecture hooks broken** — KI-2/KI-7 block valid `agents/ → services/` and `agents/ → db/` imports

The core risk: running 7+ agents in parallel on disconnected code will **amplify** type mismatches, not fix them — unless contracts are defined first.

---

## Gap Inventory

| # | Gap | Severity | Key Files |
|---|-----|----------|-----------|
| 1 | 16 enums defined, zero used | HIGH | `src/shared/types.py`, all agents, `src/db/models.py` |
| 2 | 34 agent functions return `-> dict` | HIGH | `src/agents/*.py` (8 files) |
| 3 | DB models use magic string defaults | HIGH | `src/db/models.py`, `src/db/postgres.py` |
| 4 | Pipeline state never tracked (KI-10) | HIGH | `src/api/webhooks.py` |
| 5 | Agent reasoning table never written | MEDIUM | `src/api/webhooks.py` |
| 6 | DNC/consent gates not enforced at backend | HIGH | `src/api/webhooks.py`, `src/shared/validators.py` |
| 7 | Architecture hooks block valid imports (KI-2/7) | MEDIUM | PreToolUse hook config |
| 8 | Validator DB stub never wired (KI-8) | MEDIUM | `src/shared/validators.py`, `src/api/app.py` |
| 9 | 22 ruff lint warnings (KI-9) | LOW | `src/shared/types.py`, `src/api/webhooks.py` |
| 10 | No GitHub Actions CI/CD | MEDIUM | `.github/workflows/` (missing) |
| 11 | No Makefile / task runner | LOW | project root |
| 12 | Safety triggers hardcoded (no triggers.py) | LOW | `src/shared/safety_gate.py` |
| 13 | ElevenLabs Workflows migration | HIGH | `src/services/elevenlabs_client.py`, new files |
| 14 | Post-call supervisor audit unreliable | MEDIUM | `src/api/webhooks.py` |
| 15 | Tests use magic strings matching old dict returns | MEDIUM | `tests/**` |

---

## Phase 0: Type Foundation (Sequential — Must Complete Before Phase 1)

### Agent 0A: Type Contract Author

**Purpose**: Create the executable contracts that all Phase 1 agents implement against.

**Deliverables**:

1. **StrEnum migration** (`src/shared/types.py`)
   - Change all 16 enums from `(str, enum.Enum)` to `enum.StrEnum`
   - Fixes KI-9 UP042 warnings

2. **Pydantic response models** (new file: `src/shared/response_models.py`)
   - One model per agent helper function return value
   - Derived from actual dict shapes returned by current implementations
   - Models include:

   ```python
   class IdentityVerificationResult(BaseModel):
       verified: bool
       error: str | None = None
       reason: str | None = None
       handoff_required: bool = False
       attempts: int = 0

   class DuplicateDetectionResult(BaseModel):
       is_duplicate: bool
       duplicate_ids: list[str] = []
       error: str | None = None

   class ScreeningCriteriaResult(BaseModel):
       inclusion: dict[str, Any] = {}
       exclusion: dict[str, Any] = {}
       trial_name: str = ""
       error: str | None = None

   class HardExcludeResult(BaseModel):
       excluded: bool
       reason: str = ""
       error: str | None = None

   class EligibilityResult(BaseModel):
       eligible: bool
       status: EligibilityStatus
       reason: str
       handoff_required: bool = False

   class ScreeningResponseResult(BaseModel):
       recorded: bool
       error: str | None = None

   class GeoEligibilityResult(BaseModel):
       eligible: bool
       distance_miles: float | None = None
       error: str | None = None

   class SlotAvailabilityResult(BaseModel):
       available: bool
       slots: list[dict[str, Any]] = []
       error: str | None = None

   class SlotHoldResult(BaseModel):
       held: bool
       appointment_id: str | None = None
       error: str | None = None

   class AppointmentBookingResult(BaseModel):
       booked: bool
       appointment_id: str | None = None
       confirmation_due_at: str | None = None
       reason: str | None = None

   class TeachBackResult(BaseModel):
       verified: bool
       handoff_required: bool = False
       error: str | None = None

   class TransportBookingResult(BaseModel):
       booked: bool
       ride_id: str | None = None
       pickup_address: str = ""
       dropoff_address: str = ""
       scheduled_pickup_at: str | None = None
       error: str | None = None

   class CommunicationResult(BaseModel):
       sent: bool
       channel: Channel | None = None
       error: str | None = None

   class ReminderResult(BaseModel):
       scheduled: bool
       task_id: str | None = None
       error: str | None = None

   class SafetyGateResult(BaseModel):
       triggered: bool
       trigger_type: HandoffReason | None = None
       severity: HandoffSeverity | None = None
       elapsed_ms: float = 0.0

   class SupervisorAuditResult(BaseModel):
       compliant: bool
       violations: list[str] = []
       phi_detected: bool = False

   class DeceptionResult(BaseModel):
       deception_detected: bool
       discrepancies: list[dict[str, Any]] = []
       recheck_scheduled: bool = False

   class OutreachCallResult(BaseModel):
       initiated: bool
       conversation_id: str | None = None
       error: str | None = None

   class DncCheckResult(BaseModel):
       is_dnc: bool
       source: str | None = None
       error: str | None = None

   class CallContextResult(BaseModel):
       context: dict[str, Any] = {}
       error: str | None = None
   ```

3. **DB model default updates** (`src/db/models.py`)
   - Replace `default="unverified"` with `default=IdentityStatus.UNVERIFIED`
   - Replace `default="new"` with `default=PipelineStatus.NEW`
   - Replace all other magic string defaults with enum values
   - Add `from src.shared.types import ...` imports

4. **Test stubs** (new file: `tests/shared/test_response_models.py`)
   - One test per response model verifying construction from representative dict
   - Pattern for each:
     ```python
     def test_identity_verification_result_from_dict():
         data = {"verified": True, "attempts": 1}
         result = IdentityVerificationResult(**data)
         assert result.verified is True
         assert result.attempts == 1
         assert result.error is None
     ```
   - Tests for enum field validation (e.g., passing invalid status string fails)

5. **Agent return type stubs** — For each of the 34 `-> dict` functions, write a comment-only stub showing the expected signature change:
   - Create `docs/plans/agent-signature-contracts.md` listing every function, current signature, target signature
   - This is the "contract sheet" that Phase 1 agents reference

### Agent 0B: CI/CD and Tooling (Parallel with 0A)

**Deliverables**:

1. **Makefile** (project root)
   ```makefile
   lint:     ruff check src/ tests/
   format:   ruff format src/ tests/
   typecheck: mypy --strict src/
   test:     pytest tests/ -x --ignore=tests/db/test_crud.py
   coverage: pytest tests/ --cov=src --cov-report=term-missing --ignore=tests/db/test_crud.py
   ci:       make lint && make typecheck && make test
   ```

2. **GitHub Actions** (`.github/workflows/ci.yml`)
   - Trigger: push and PR to `dev` and `main`
   - Jobs: ruff check, mypy --strict, pytest, coverage report
   - Skip DB integration tests (require live Cloud SQL)

3. **Ruff config fix** (`pyproject.toml`)
   - Add `"B008"` to `ignore` list (standard FastAPI `Depends()` pattern)
   - Fix forward reference issues (F821) in `webhooks.py` and `app.py`

4. **Architecture hook fix** (KI-2/KI-7)
   - Document the required hook config change
   - Update any `.claude/` hook config if accessible

---

## Phase 1: Parallel Flood (7 Agents, All Start After Phase 0 Completes)

### File Ownership Rules

**No two agents touch the same file.** This eliminates merge conflicts entirely.

| Agent | Exclusively Owns |
|-------|-----------------|
| 1 | `src/agents/identity.py`, `src/agents/screening.py`, `src/agents/scheduling.py`, `src/agents/transport.py`, `src/agents/outreach.py`, `src/agents/comms.py`, `src/agents/supervisor.py`, `src/agents/adversarial.py`, `src/agents/orchestrator.py`, `src/agents/pipeline.py` |
| 2 | `src/db/postgres.py`, `src/db/events.py`, `src/db/trials.py`, `src/db/session.py` |
| 3 | `src/api/webhooks.py` |
| 4 | `src/shared/validators.py`, `src/api/app.py` (startup wiring only) |
| 5 | `src/services/elevenlabs_client.py`, new `src/services/elevenlabs_workflows.py` |
| 6 | `src/shared/safety_gate.py`, `src/services/safety_service.py`, new `src/safety/triggers.py` |
| 7 | All files under `tests/` |

### Agent 1: Agent Enum Adoption

**Scope**: All 8 agent files + orchestrator + pipeline

**Tasks**:
- Replace all 34 `-> dict` returns with Pydantic response models from `src/shared/response_models.py`
- Replace all magic strings with enum values (e.g., `"verified"` → `IdentityStatus.VERIFIED`)
- Add missing type hints on function parameters
- Construct response models instead of raw dicts

**Example transform** (`src/agents/identity.py:verify_identity`):
```python
# BEFORE
async def verify_identity(...) -> dict:
    ...
    return {"verified": True, "attempts": attempts}

# AFTER
async def verify_identity(...) -> IdentityVerificationResult:
    ...
    return IdentityVerificationResult(verified=True, attempts=attempts)
```

**Test contract**: Every function return must pass `isinstance(result, ExpectedModel)`

### Agent 2: DB/CRUD Enum Adoption

**Scope**: `src/db/postgres.py`, `src/db/events.py`, `src/db/trials.py`, `src/db/session.py`

**Tasks**:
- Replace magic string comparisons in CRUD functions with enum values
- Add type hints to all CRUD function parameters (e.g., `status: AppointmentStatus` not `status: str`)
- Wire enum values in `log_event()` calls
- Ensure CRUD functions that return model instances have proper return type annotations

### Agent 3: Pipeline State + Agent Reasoning + Post-Call Audit

**Scope**: `src/api/webhooks.py`

**Tasks**:
- After each tool handler succeeds, update `participant_trials.pipeline_status`:
  - `_handle_verify_identity` success → `PipelineStatus.SCREENING`
  - `_handle_determine_eligibility` eligible → `PipelineStatus.SCHEDULING`
  - `_handle_determine_eligibility` ineligible → `PipelineStatus.DNC`
  - `_handle_book_appointment` success → `PipelineStatus.BOOKED`
- Write to `agent_reasoning` table in `_handle_safety_check` and key decision points
- Wire post-call supervisor audit in `handle_call_completion`:
  - Call `audit_transcript()` after transcript is stored
  - Call `check_phi_leak()` on pre-identity conversation entries
  - Log results to events table
- Wire adversarial recheck scheduling post-screening

### Agent 4: Backend DNC/Consent Gates + Validator Wiring

**Scope**: `src/shared/validators.py`, `src/api/app.py` (startup wiring)

**Tasks**:
- Add `_enforce_pre_checks()` function to validators that:
  - Checks DNC status before any tool handler runs
  - Verifies consent and disclosure gates
  - Returns error response if gates fail
- Wire `src.shared.validators.get_participant_by_id = src.db.postgres.get_participant_by_id` at app startup in `create_app()` (fixes KI-8)
- Replace magic strings in validators with enum values

### Agent 5: ElevenLabs Workflows Research + Scaffold

**Scope**: `src/services/elevenlabs_client.py`, new `src/services/elevenlabs_workflows.py`

**Tasks**:
- Research ElevenLabs Workflows API (agent-to-agent transfer, workflow nodes, guardrails)
- Create `elevenlabs_workflows.py` with:
  - Workflow node definitions for each pipeline gate (Disclosure → Consent → Identity → Screening → Scheduling)
  - Per-node system prompts (extracted from monolithic prompt)
  - Guardrail definitions for safety boundaries
  - Workflow creation/update API client methods
- Update `elevenlabs_client.py` with new methods for workflow management
- This is **design + scaffold** — not full migration (that's a separate effort)

### Agent 6: Safety Hardening

**Scope**: `src/shared/safety_gate.py`, `src/services/safety_service.py`, new `src/safety/triggers.py`

**Tasks**:
- Extract 7 trigger definitions from `safety_gate.py` into `src/safety/triggers.py`
- Make triggers configurable (load from config, not hardcoded)
- Replace magic strings with `HandoffReason` and `HandoffSeverity` enums
- Return `SafetyGateResult` Pydantic model from `evaluate_safety()`
- Update `safety_service.py` to use typed results

### Agent 7: Test Modernization

**Scope**: All files under `tests/` (EXCEPT `tests/safety/` which is IMMUTABLE)

**Tasks**:
- Update all test assertions to use enum values instead of magic strings
- Update all mock return values to use Pydantic response models
- Add `isinstance` checks on agent function returns
- Ensure all test files import from `src/shared/response_models.py`
- Fill in the test stubs created by Agent 0A
- Run full test suite, fix any failures caused by the type changes
- Verify safety tests still pass with the new types (read-only — if they fail, flag for Agent 1/2/3 to fix)

---

## Merge Order

```
Phase 0A (types + response models + test stubs) ──┐
                                                    ├─> merge to dev
Phase 0B (CI/CD + Makefile + ruff fix) ────────────┘
                                                    │
                                    ┌───────────────┘
                                    ▼
                    ┌── Agent 2 (DB/CRUD) merges FIRST
                    │
                    ├── Agents 1, 5, 6 merge in parallel (no file overlap)
                    │
                    ├── Agent 4 (validators + app.py startup) merges
                    │
                    ├── Agent 3 (webhooks pipeline state) rebases + merges
                    │
                    └── Agent 7 (tests) rebases against ALL + merges LAST
```

**Why this order**:
- DB layer (Agent 2) first because agents and webhooks consume DB types
- Agent implementations (1, 5, 6) next because they produce the response models
- Validators/startup (4) next because it wires the DNC gates
- Webhooks (3) after agents because it consumes agent return types
- Tests (7) last because it validates everything

---

## Quality Gates

### After Phase 0 merges:
- [ ] `ruff check src/ tests/` — zero warnings
- [ ] `mypy --strict src/shared/types.py src/shared/response_models.py` — passes
- [ ] `pytest tests/shared/test_response_models.py` — all stub tests pass

### After each Phase 1 agent merges:
- [ ] `mypy --strict` on owned files — passes
- [ ] `pytest` on corresponding test files — passes
- [ ] `ruff check` on owned files — zero warnings

### After all agents merged:
- [ ] `make ci` (full lint + typecheck + test suite) — passes
- [ ] All 339+ existing tests still pass
- [ ] All 59 immutable safety tests still pass
- [ ] Zero `-> dict` returns remain in agent files
- [ ] Zero magic string status assignments remain
- [ ] `grep -r "= \"verified\"\\|= \"unverified\"\\|= \"new\"\\|= \"pending\"\\|= \"held\"\\|= \"booked\"" src/` — zero hits

---

## What This Does NOT Cover (Future Work)

1. **ElevenLabs Workflows full migration** — Agent 5 delivers the scaffold only. Actual migration (rewiring live calls through workflow nodes) is a separate effort.
2. **Google Calendar integration** — Deferred to post-hackathon per existing decision.
3. **Real Cloud Tasks client** — KI-4 stays as MVP stub until GCP queue is created.
4. **Databricks / CDC worker** — Removed from scope per user simplification.
5. **Firebase hosting** — Removed from scope per user simplification.
6. **Production deployment** — This plan fixes structural correctness. Deployment is orthogonal.
