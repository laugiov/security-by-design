"""Configuration module for SkyLink Gateway.

Loads configuration from environment variables with fallback to local files
for development. This allows developers to use the keys in local/ directory
while CI/CD uses GitLab variables.

Security by Design:
- Keys are NEVER logged
- Keys are loaded lazily on first use (solves pytest_configure timing issue)
- Keys are cached in memory after first load
- No key material in error messages
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    # JWT RS256 keys
    # CRITICAL: DO NOT set these fields - they must remain None
    # GitLab CI creates .tmp/PRIVATE_KEY_PEM files that would be loaded as paths
    # We use lazy loading via get_private_key() to read from os.environ
    private_key_pem: Optional[str] = None
    public_key_pem: Optional[str] = None

    # Private cache for lazy-loaded keys
    _private_key_cache: Optional[str] = None
    _public_key_cache: Optional[str] = None

    # Weather API
    weather_api_key: Optional[str] = None
    weather_api_url: str = "https://api.weatherapi.com/v1"

    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_global_per_second: int = 10

    # JWT settings
    jwt_algorithm: str = "RS256"
    jwt_audience: str = "skylink"
    jwt_expiration_minutes: int = 15  # Max 15 minutes per Security by Design

    # mTLS settings
    mtls_enabled: bool = False
    mtls_cert_file: Path = Path("certs/server/server.crt")
    mtls_key_file: Path = Path("certs/server/server.key")
    mtls_ca_cert_file: Path = Path("certs/ca/ca.crt")
    mtls_verify_mode: str = "CERT_REQUIRED"  # CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED

    def get_private_key(self) -> str:
        """Load RSA private key with lazy loading and caching.

        Lazy loading ensures that:
        1. In tests: pytest_configure() can set env vars before first access
        2. In CI/CD: Protected variables are loaded when available
        3. Keys are cached after first successful load

        Returns:
            str: PEM-encoded RSA private key

        Raises:
            RuntimeError: If key is not set in environment

        Security Notes:
            - Key is NEVER logged
            - Errors do not contain key material
            - Key MUST be in .env file or environment variable
            - .env file MUST be in .gitignore

        Usage:
            Development: Set PRIVATE_KEY_PEM in .env file
            CI/CD: Set PRIVATE_KEY_PEM as GitLab CI/CD variable (or pytest_configure fallback)
            Production: Use secrets manager or environment variable
        """
        # Return cached key if already loaded
        if self._private_key_cache:
            return self._private_key_cache

        # Read from os.environ
        # GitLab CI with "File" type variables puts the FILE PATH in the env var
        # So we need to detect if the value is a path and read the file content
        key = os.getenv("PRIVATE_KEY_PEM")

        if not key:
            raise RuntimeError(
                "PRIVATE_KEY_PEM not found in environment. "
                "Please set it in .env file (copy .env.example to .env and add your key). "
                "See AUTH_JWT_IMPLEMENTATION.md for instructions."
            )

        # GitLab CI "File" variables: env var contains path, not content
        # Detect if key is a file path and read the actual content
        if not key.startswith("-----BEGIN") and os.path.isfile(key):
            with open(key, "r") as f:
                key = f.read()

        if not key.startswith("-----BEGIN"):
            raise RuntimeError(
                "PRIVATE_KEY_PEM is not a valid PEM key. "
                "Expected key starting with '-----BEGIN', got a path or invalid value."
            )

        # Cache the key for future calls
        self._private_key_cache = key
        return key

    def get_public_key(self) -> str:
        """Load RSA public key with lazy loading and caching.

        Lazy loading ensures that:
        1. In tests: pytest_configure() can set env vars before first access
        2. In CI/CD: Protected variables are loaded when available
        3. Keys are cached after first successful load

        Returns:
            str: PEM-encoded RSA public key

        Raises:
            RuntimeError: If key is not set in environment

        Security Notes:
            - Key is NEVER logged
            - Errors do not contain key material
            - Key MUST be in .env file or environment variable
            - .env file MUST be in .gitignore

        Usage:
            Development: Set PUBLIC_KEY_PEM in .env file
            CI/CD: Set PUBLIC_KEY_PEM as GitLab CI/CD variable (or pytest_configure fallback)
            Production: Use secrets manager or environment variable
        """
        # Return cached key if already loaded
        if self._public_key_cache:
            return self._public_key_cache

        # Read from os.environ
        # GitLab CI with "File" type variables puts the FILE PATH in the env var
        # So we need to detect if the value is a path and read the file content
        key = os.getenv("PUBLIC_KEY_PEM")

        if not key:
            raise RuntimeError(
                "PUBLIC_KEY_PEM not found in environment. "
                "Please set it in .env file (copy .env.example to .env and add your key). "
                "See AUTH_JWT_IMPLEMENTATION.md for instructions."
            )

        # GitLab CI "File" variables: env var contains path, not content
        # Detect if key is a file path and read the actual content
        if not key.startswith("-----BEGIN") and os.path.isfile(key):
            with open(key, "r") as f:
                key = f.read()

        if not key.startswith("-----BEGIN"):
            raise RuntimeError(
                "PUBLIC_KEY_PEM is not a valid PEM key. "
                "Expected key starting with '-----BEGIN', got a path or invalid value."
            )

        # Cache the key for future calls
        self._public_key_cache = key
        return key

    def get_mtls_config(self):
        """Get mTLS configuration object.

        Returns:
            MTLSConfig: Configuration object for mTLS setup

        Example:
            >>> config = settings.get_mtls_config()
            >>> ssl_context = create_ssl_context(config)
        """
        from skylink.mtls import MTLSConfig

        return MTLSConfig(
            enabled=self.mtls_enabled,
            cert_file=self.mtls_cert_file,
            key_file=self.mtls_key_file,
            ca_cert_file=self.mtls_ca_cert_file,
            verify_mode=self.mtls_verify_mode,
        )


# Global settings instance (singleton pattern)
settings = Settings()
