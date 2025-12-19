"""Telemetry service configuration."""

import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Telemetry Service settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "telemetry"
    service_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8001

    # JWT RS256 - verification only
    public_key_pem: Optional[str] = None
    _public_key_cache: Optional[str] = None

    jwt_algorithm: str = "RS256"
    jwt_audience: str = "skylink"  # aligned with Gateway

    def get_public_key(self) -> str:
        """Returns the public PEM key, with cache."""
        if self._public_key_cache:
            return self._public_key_cache

        key = os.getenv("PUBLIC_KEY_PEM") or self.public_key_pem
        if not key:
            raise RuntimeError(
                "PUBLIC_KEY_PEM not found. Configure it in .env or as an environment variable."
            )
        self._public_key_cache = key
        return key

    # DB (future PostgreSQL implementation)
    database_url: str = "postgresql+psycopg://user:password@db/telemetry"


# Global configuration instance
settings = Settings()
