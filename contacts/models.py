"""Database models for OAuth tokens storage."""

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class JSONEncodedList(TypeDecorator):
    """Stores a list as JSON in databases that don't support ARRAY (SQLite)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert list to JSON string before storing."""
        if value is None:
            return None
        # For PostgreSQL, return as-is (will use ARRAY)
        if dialect.name == "postgresql":
            return value
        # For SQLite/others, convert to JSON
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        """Convert JSON string back to list after retrieving."""
        if value is None:
            return None
        # For PostgreSQL, return as-is (already a list)
        if dialect.name == "postgresql":
            return value
        # For SQLite/others, parse JSON
        if isinstance(value, str):
            return json.loads(value)
        return value


class OAuthToken(Base):
    """OAuth tokens table for storing Google OAuth credentials per aircraft.

    Stores access_token and refresh_token for each aircraft_id.
    The refresh_token is encrypted at rest using AES-256-GCM.
    """

    __tablename__ = "oauth_tokens"

    # Primary key: aircraft_id from JWT
    aircraft_id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        comment="Aircraft UUID from JWT token",
    )

    # OAuth provider (always 'google' for now)
    provider = Column(
        String(50),
        nullable=False,
        default="google",
        comment="OAuth provider name",
    )

    # Access token (short-lived, ~1h)
    access_token = Column(
        Text,
        nullable=False,
        comment="Google access token (plaintext, short TTL)",
    )

    # Refresh token (long-lived, ~6 months) - ENCRYPTED
    refresh_token = Column(
        Text,
        nullable=False,
        comment="Google refresh token (AES-256-GCM encrypted)",
    )

    # Expiration timestamp of access_token
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Access token expiration timestamp (UTC)",
    )

    # Scopes granted by user
    scopes = Column(
        JSONEncodedList,
        nullable=False,
        comment="List of OAuth scopes granted",
    )

    # Audit timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.utcnow()
        ),
        comment="Record creation timestamp (UTC)",
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.utcnow()
        ),
        onupdate=lambda: (
            datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.utcnow()
        ),
        comment="Record last update timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """String representation (safe - no tokens exposed)."""
        return (
            f"<OAuthToken(aircraft_id={self.aircraft_id}, "
            f"provider={self.provider}, "
            f"expires_at={self.expires_at})>"
        )

    def to_dict(self, decrypt_refresh_token: bool = False) -> dict:
        """Convert model to dictionary.

        Args:
            decrypt_refresh_token: If True, decrypt refresh_token before returning.
                                   WARNING: Only use when necessary!

        Returns:
            Dictionary representation of the token
        """
        return {
            "aircraft_id": str(self.aircraft_id),
            "provider": self.provider,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,  # Returns encrypted unless specified
            "expires_at": self.expires_at.isoformat(),
            "scopes": self.scopes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
