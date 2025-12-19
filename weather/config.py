"""Configuration for Weather Service."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Weather Service settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service settings
    service_name: str = "weather"
    service_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # Server settings
    host: str = "0.0.0.0"  # nosec B104 (binding to all interfaces for Docker)
    port: int = 8002

    # Demo mode settings
    demo_mode: bool = True

    # Weather API configuration (for production mode)
    weather_api_key: str | None = None
    weather_api_url: str = "https://api.weatherapi.com/v1"


settings = Settings()
