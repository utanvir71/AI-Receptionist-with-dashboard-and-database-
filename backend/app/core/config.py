"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for local development and production."""

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_timezone: str = "Asia/Seoul"
    public_base_url: str = ""

    vapi_tool_secret: str = ""
    vapi_manager_transfer_number: str = ""

    google_calendar_id: str = ""
    google_service_account_json: str = ""
    google_application_credentials: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    manager_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    log_level: str = "INFO"
    sentry_dsn: str = ""
    ngrok_domain: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached runtime settings."""
    return Settings()


settings = get_settings()
