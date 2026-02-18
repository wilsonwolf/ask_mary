# Code Style & Conventions

## Formatting & Linting
- **Formatter**: `ruff format` (line length 88)
- **Linter**: `ruff check`
- **Type checker**: `mypy --strict` — type hints required on ALL function signatures
- **Docstring coverage**: `interrogate` (90% minimum)

## Naming Conventions
- Functions: descriptive verb-noun (`verify_identity`, `log_event`), no abbreviations
- Variables: full words (`participant` not `pt`, `appointment` not `appt`)
- Booleans: `is_`/`has_`/`can_`/`should_` prefix
- Constants: `UPPER_SNAKE_CASE`
- Classes: `PascalCase` nouns (`ScreeningAgent`, `HandoffQueue`)
- Enums: `(str, enum.Enum)` for JSON/DB compatibility

## Function Rules
- Max 20 lines per function
- Single responsibility
- Max 3 parameters (use keyword-only `*` for more)
- No nested conditionals deeper than 2 levels — use early returns
- No commented-out code — delete it
- No magic numbers — use named constants or enums

## Docstrings
- Google-style with Args, Returns, Raises sections
- Required on all public functions
- Optional but encouraged on private functions (`_` prefixed)

## Architecture Patterns
- Agents use OpenAI Agents SDK: `from agents import Agent` (NOT local imports)
- Agent cross-communication only via orchestrator handoffs in `pipeline.py`
- All external API calls must be mockable
- Idempotency keys on all outbound actions
- Provenance tracking: `patient_stated|ehr|coordinator|system`
- Annotate-don't-overwrite pattern for data updates

## Imports
- Standard library → third-party → local (`src.`)
- No circular imports
- No wildcard imports
