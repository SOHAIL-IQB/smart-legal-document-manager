from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
