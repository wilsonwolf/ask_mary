# Suggested Commands

## Package Management (uv)
- `uv sync` — Install/sync all dependencies
- `uv add <package>` — Add a dependency
- `uv add --dev <package>` — Add a dev dependency
- `uv run <command>` — Run a command in the project venv

## Testing
- `uv run pytest` — Run all tests
- `uv run pytest tests/path/test_file.py` — Run specific test file
- `uv run pytest -x` — Stop on first failure
- `uv run pytest --cov=src --cov-report=term-missing` — With coverage

## Linting & Formatting
- `uv run ruff format src/ tests/` — Format code
- `uv run ruff check src/ tests/` — Lint check
- `uv run ruff check --fix src/ tests/` — Lint with auto-fix
- `uv run mypy src/ --strict` — Type checking (strict mode)
- `uv run interrogate src/ -v` — Docstring coverage (90% minimum)

## Database
- `uv run alembic upgrade head` — Apply all migrations
- `uv run alembic revision --autogenerate -m "description"` — Generate migration
- `uv run alembic downgrade -1` — Rollback last migration

## Cloud SQL Auth Proxy
- `cloud-sql-proxy ask-mary-486802:us-west2:ask-mary-db` — Start proxy (must be running for DB access)

## Running the App
- `uv run uvicorn src.api.app:app --reload` — Start FastAPI dev server

## Git
- `git worktree add ../ask-mary-{feature} -b feature/{feature}` — Create feature worktree
- `git worktree remove ../ask-mary-{feature}` — Clean up worktree

## System (macOS/Darwin)
- `stat -f %m <file>` — Get file modification time (epoch)
- `gcloud auth application-default login` — Refresh GCP credentials
