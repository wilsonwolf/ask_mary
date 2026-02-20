# src/config/ -- Configuration

Application settings loaded from environment variables and `.env`.

## Files

| File | Role |
|------|------|
| `settings.py` | `Settings` class (Pydantic Settings) with all config vars; `get_settings()` factory |

## Config Groups

| Group | Variables |
|-------|-----------|
| GCP | `gcp_project_id`, `gcp_region` |
| Cloud SQL | `cloud_sql_instance_connection`, `cloud_sql_password`, `cloud_sql_database`, `cloud_sql_user`, `cloud_sql_host`, `cloud_sql_port`, `cloud_sql_ssl` |
| Participant ID | `mary_id_pepper` |
| OpenAI | `openai_api_key` |
| Twilio | `twilio_account_sid`, `twilio_auth_token`, `twilio_phone_number`, `twilio_messaging_service_sid` |
| ElevenLabs | `elevenlabs_api_key`, `elevenlabs_agent_id`, `elevenlabs_agent_phone_number_id` |
| GCS Audio | `gcs_audio_bucket`, `gcs_signed_url_ttl_seconds` |
| Databricks | `databricks_server_hostname`, `databricks_http_path`, `databricks_token` |
| Google Calendar | `google_calendar_credentials_path`, `google_calendar_id` |
| GitHub | `github_token` |
| Anthropic | `anthropic_api_key` |
| Public URL | `public_base_url` (Twilio status callbacks) |
| Dashboard / CORS | `cors_allowed_origins` (list, defaults to localhost:5173, localhost:3000, and Cloud Run URL) |
| Demo | `demo_participant_phone`, `demo_trial_id` |

## Key Decisions

- **Pydantic Settings**: Single `Settings` class loads from `.env` file with `case_sensitive=False`.
- **Two DB URLs**: `database_url` (async, `asyncpg`) and `database_url_sync` (sync, `psycopg2`) computed properties. Auto-detects Cloud Run Unix sockets vs local TCP via `cloud_sql_instance_connection`.
- **Empty defaults**: All API keys default to `""` so the app can start in test mode without every credential configured.
- **No caching**: `get_settings()` creates a new instance each call -- add `@lru_cache` if needed for production.
- **SSL control**: `cloud_sql_ssl` defaults to `"disable"` for local dev; override for production.
