# src/config/ — Configuration

Application settings loaded from environment variables and `.env`.

## Files

| File | Role |
|------|------|
| `settings.py` | `Settings` class (Pydantic Settings) with all config vars |

## Key Decisions

- **Pydantic Settings**: Single `Settings` class loads from `.env` file with `case_sensitive=False`.
- **Two DB URLs**: `database_url` (async, `asyncpg`) for runtime and `database_url_sync` (sync, `psycopg2`) for Alembic migrations.
- **Empty defaults**: All API keys default to `""` so the app can start in test mode without every credential configured.
- **No caching**: `get_settings()` creates a new instance each call — add `@lru_cache` if needed for production.
