"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Ask Mary.

    Args loaded from .env file and environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-west2"

    # Cloud SQL
    cloud_sql_instance_connection: str = ""
    cloud_sql_password: str = ""
    cloud_sql_database: str = "ask_mary_dev"
    cloud_sql_user: str = "postgres"
    cloud_sql_host: str = "127.0.0.1"
    cloud_sql_port: int = 5432
    cloud_sql_ssl: str = "disable"

    # Participant ID hashing
    mary_id_pepper: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_messaging_service_sid: str = ""

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_agent_phone_number_id: str = ""

    # GCS Audio
    gcs_audio_bucket: str = "ask-mary-audio"
    gcs_signed_url_ttl_seconds: int = 3600

    # Databricks
    databricks_server_hostname: str = ""
    databricks_http_path: str = ""
    databricks_token: str = ""

    # Google Calendar
    google_calendar_credentials_path: str = ""
    google_calendar_id: str = ""

    # GitHub
    github_token: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Public URL (for Twilio status callbacks)
    public_base_url: str = ""

    # Dashboard / CORS
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://ask-mary-1030626458480.us-west2.run.app",
    ]
    demo_participant_phone: str = ""
    demo_trial_id: str = "diabetes-study-a"

    @property
    def database_url(self) -> str:
        """Build async Postgres connection URL.

        Uses Unix socket when cloud_sql_instance_connection is set
        (Cloud Run). Falls back to TCP host:port for local dev.
        """
        if self.cloud_sql_instance_connection:
            socket_path = f"/cloudsql/{self.cloud_sql_instance_connection}"
            return (
                f"postgresql+asyncpg://{self.cloud_sql_user}"
                f":{self.cloud_sql_password}"
                f"@/{self.cloud_sql_database}"
                f"?host={socket_path}"
            )
        return (
            f"postgresql+asyncpg://{self.cloud_sql_user}"
            f":{self.cloud_sql_password}"
            f"@{self.cloud_sql_host}:{self.cloud_sql_port}"
            f"/{self.cloud_sql_database}"
        )

    @property
    def database_url_sync(self) -> str:
        """Build sync Postgres connection URL (for Alembic migrations)."""
        if self.cloud_sql_instance_connection:
            socket_path = f"/cloudsql/{self.cloud_sql_instance_connection}"
            return (
                f"postgresql://{self.cloud_sql_user}"
                f":{self.cloud_sql_password}"
                f"@/{self.cloud_sql_database}"
                f"?host={socket_path}"
            )
        return (
            f"postgresql://{self.cloud_sql_user}"
            f":{self.cloud_sql_password}"
            f"@{self.cloud_sql_host}:{self.cloud_sql_port}"
            f"/{self.cloud_sql_database}"
        )


def get_settings() -> Settings:
    """Return a cached Settings instance.

    Returns:
        Application settings loaded from env.
    """
    return Settings()
