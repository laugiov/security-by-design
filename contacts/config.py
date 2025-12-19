"""Configuration for Contacts Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Contacts Service settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service settings
    service_name: str = "contacts"
    service_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Server settings
    host: str = "0.0.0.0"  # nosec B104 (binding to all interfaces for Docker)
    port: int = 8003

    # Demo mode settings
    demo_mode: bool = True
    demo_contacts_count: int = 5

    # Google OAuth2 settings (required for production mode)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8003/oauth/callback"

    # Database settings
    database_url: str = "postgresql://skylink:password@localhost:5432/skylink"

    # Encryption key for refresh tokens (AES-256, 32 bytes hex)
    encryption_key: str | None = None


settings = Settings()
