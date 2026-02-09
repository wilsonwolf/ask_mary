# Task Completion Checklist

Run these steps after completing any implementation task:

## 1. Format & Lint
```bash
uv run ruff format src/ tests/
uv run ruff check --fix src/ tests/
uv run mypy src/ --strict
```

## 2. Run Tests
```bash
uv run pytest
```
- All tests must pass
- Coverage target: 80% minimum
- TDD workflow: RED (failing test) → GREEN (minimal impl) → REFACTOR

## 3. Docstring Coverage
```bash
uv run interrogate src/ -v
```
- Must be ≥ 90%

## 4. README Check
- Every directory under `src/` must have a `README.md`
- If you added a new directory, create its README

## 5. Implementation Tracker
- Update `local_docs/implementation_tracker.md` with current progress
- Mark completed tasks as DONE with file paths and test counts

## 6. Git
- Never develop on main/dev directly
- Use feature branches via worktrees
- Commit pattern for TDD:
  - `test: add failing test for [feature]` (RED)
  - `feat: implement [feature]` (GREEN)
  - `refactor: clean up [feature]` (REFACTOR)

## 7. Immutable Tests
- NEVER modify files in `tests/safety/`
- If a safety test fails, fix the implementation, not the test
