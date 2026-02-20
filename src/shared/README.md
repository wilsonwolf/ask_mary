# src/shared/ -- Cross-Cutting Shared Utilities

Modules importable by any layer (agents, services, db, api). Nothing in shared/ imports from shared/.

## Files

| File | Role |
|------|------|
| `types.py` | 18 `StrEnum` classes defining all application state machines (PipelineStatus, AppointmentStatus, HandoffSeverity, CallOutcome, AdversarialCheckStatus, Provenance, etc.) |
| `response_models.py` | 26 Pydantic response models (1 `AgentResult` base class + 25 concrete results) -- typed contracts for all agent helper return types with dict-compatible access (`result["key"]`, `"key" in result`, `{**result}`) |
| `validators.py` | Input validation (`validate_phone`, `validate_zip_code`, `validate_dob_year`, `is_dnc_blocked`, `validate_channel`) plus gate checks (`check_identity_gate`, `check_disclosure_gate`, `_enforce_pre_checks`); patchable `get_participant_by_id` stub for unit testing |
| `safety_gate.py` | Blocking pre-check on every agent response -- `evaluate_safety()` with 7 trigger types loaded from `src/safety/triggers.py`, timing instrumentation (`elapsed_ms`), and async `on_trigger` callback for handoff_queue writes |
| `comms.py` | Jinja2 template rendering -- `load_template()`, `render_template()`, `list_templates()` loading YAML from `comms_templates/` |
| `identity.py` | `generate_mary_id()` -- HMAC-SHA256 with canonicalization (lowercase+strip names, ISO dates, digits-only phones) and secret pepper; raises `ValueError` on empty pepper |

## Key Decisions

- **StrEnum (not str+Enum)**: All enums use `enum.StrEnum` (Python 3.11+) for native JSON serialization and DB storage compatibility.
- **HMAC-SHA256 with pepper**: `mary_id = HMAC(pepper, canonicalize(first|last|dob|phone))`. Empty pepper raises `ValueError`.
- **AgentResult dict-compatible pattern**: All response models inherit from `AgentResult`, which implements `__getitem__`, `__contains__`, `get()`, `keys()`, and `__iter__` so existing code using dict access works without changes.
- **Safety gate timing**: Every `evaluate_safety()` call records `elapsed_ms` for observability. Hard ceiling constant at 1000ms (logged, not enforced).
- **Patchable DB stub in validators.py**: `get_participant_by_id()` raises `NotImplementedError` by default; production wiring or test patches inject the real lookup.
- **auth.py not yet implemented**: Auth helpers are deferred.
