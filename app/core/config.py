from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-only-insecure-secret-key-change-me"  # noqa: S105 (placeholder, rejected in prod)


class Settings(BaseSettings):
    """Application settings, read from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Legal Document Manager"
    app_version: str = "0.2.0"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"

    # Default matches docker-compose, which publishes Postgres on host port 5434.
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5434/smart_legal_document_manager"
    )

    # Explicit origins only: the API uses cookies, and browsers reject "*" with credentials.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Auth. The default key is for local development only; production refuses to start with it.
    secret_key: str = DEV_SECRET_KEY
    access_token_minutes: int = Field(default=12 * 60, ge=5, le=7 * 24 * 60)
    auth_cookie_name: str = "sldm_session"
    # Tokens name who issued them and who they are for; decode rejects anything else.
    jwt_issuer: str = "smart-legal-document-manager"
    jwt_audience: str = "smart-legal-document-manager-web"
    login_max_failures: int = 10
    login_window_seconds: int = 15 * 60

    # Uploads (PDF / DOCX / TXT). Also set the same limit on any reverse proxy in front of the API.
    max_upload_bytes: int = 10 * 1024 * 1024
    # Every other request body. Must fit the largest allowed content: 2,000,000 characters of
    # up-to-4-byte UTF-8 plus JSON framing (review finding R1, LOG 009).
    max_json_bytes: int = 9 * 1024 * 1024

    # Read by uvicorn itself (same variable). Listed here so production can refuse "*": with it,
    # uvicorn takes the left-most X-Forwarded-For entry, which any client can forge (R4).
    forwarded_allow_ips: str = "127.0.0.1,::1"

    @model_validator(mode="after")
    def refuse_trusting_every_proxy_in_production(self) -> "Settings":
        if self.environment == "production" and self.forwarded_allow_ips.strip() == "*":
            raise ValueError(
                "FORWARDED_ALLOW_IPS='*' lets any client forge its IP. Set it to the proxy's "
                "address or network instead."
            )
        return self

    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (
            self.secret_key == DEV_SECRET_KEY or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY must be set to a random value of 32+ characters.")
        return self

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origin(cls, origins: list[str]) -> list[str]:
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' because the API allows credentials. "
                'List origins explicitly, e.g. ["http://localhost:5173"].'
            )
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
