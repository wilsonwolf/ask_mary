# src/safety/ -- Safety Trigger Definitions

Configurable trigger registry for the safety gate. The gate evaluation logic lives in `src/shared/safety_gate.py`; this package provides the trigger definitions and data structures it consumes.

## Files

| File | Role |
|------|------|
| `__init__.py` | Package marker with docstring (no re-exports) |
| `triggers.py` | `SafetyTrigger` dataclass and `DEFAULT_TRIGGERS` registry -- 7 triggers covering medical advice, severe symptoms, consent withdrawal, anger/threats, adverse events, repeated misunderstanding (context-based), and language mismatch (context-based); `load_triggers()` returns the active list |

## Key Concepts

- **SafetyTrigger**: Frozen dataclass with `reason` (HandoffReason), `severity` (HandoffSeverity), `patterns` (keyword list for text matching), and optional `context_check` (callable inspecting conversation context).
- **Evaluation order**: Triggers are evaluated in list order; first match wins.
- **Text-based vs context-based**: Five triggers match keyword patterns against lowercased response text. Two triggers (repeated misunderstanding, language mismatch) inspect the conversation context dict instead.
- **Consumed by**: `src/shared/safety_gate.py` imports `SafetyTrigger` and `load_triggers()` from this module.

## Immutable Tests

Tests in `tests/safety/` are locked by project policy. If a safety test fails, fix the implementation, not the test. See CLAUDE.md guideline 6.
