"""Token storage management for OAuth tokens."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contacts.encryption import decrypt_token, encrypt_token
from contacts.models import OAuthToken


class TokenStorageError(Exception):
    """Base exception for token storage errors."""


class TokenStorage:
    """Manages OAuth token storage with automatic encryption/decryption."""

    def __init__(self, db: Session):
        """Initialize token storage with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def get(self, aircraft_id: UUID) -> Optional[dict]:
        """Get tokens for a aircraft.

        Args:
            aircraft_id: Aircraft UUID

        Returns:
            Dictionary with token data, or None if not found.
            The refresh_token is automatically decrypted.

        Raises:
            TokenStorageError: If database or decryption fails
        """
        try:
            token_record = (
                self.db.query(OAuthToken).filter(OAuthToken.aircraft_id == aircraft_id).first()
            )

            if token_record is None:
                return None

            # Decrypt refresh_token before returning
            decrypted_refresh_token = decrypt_token(token_record.refresh_token)

            return {
                "aircraft_id": str(token_record.aircraft_id),
                "provider": token_record.provider,
                "access_token": token_record.access_token,
                "refresh_token": decrypted_refresh_token,  # Decrypted
                "expires_at": token_record.expires_at,
                "scopes": token_record.scopes,
                "created_at": token_record.created_at,
                "updated_at": token_record.updated_at,
            }

        except SQLAlchemyError as e:
            raise TokenStorageError(f"Database error while fetching tokens: {e}") from e
        except Exception as e:
            raise TokenStorageError(f"Error fetching tokens: {e}") from e

    async def save(self, aircraft_id: UUID, tokens: dict) -> None:
        """Save or update tokens for a aircraft.

        Args:
            aircraft_id: Aircraft UUID
            tokens: Dictionary containing token data:
                - access_token (str): Access token
                - refresh_token (str): Refresh token (will be encrypted)
                - expires_at (datetime or str): Expiration timestamp
                - scopes (list[str]): OAuth scopes
                - provider (str, optional): Provider name (default: 'google')

        Raises:
            TokenStorageError: If save fails
        """
        try:
            # Encrypt refresh_token before saving
            encrypted_refresh_token = encrypt_token(tokens["refresh_token"])

            # Parse expires_at if it's a string
            expires_at = tokens["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

            # Check if token already exists
            existing = self.db.query(OAuthToken).filter(OAuthToken.aircraft_id == aircraft_id).first()

            if existing:
                # Update existing record
                existing.access_token = tokens["access_token"]
                existing.refresh_token = encrypted_refresh_token
                existing.expires_at = expires_at
                existing.scopes = tokens.get("scopes", [])
                existing.provider = tokens.get("provider", "google")
                existing.updated_at = (
                    datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.utcnow()
                )
            else:
                # Create new record
                new_token = OAuthToken(
                    aircraft_id=aircraft_id,
                    provider=tokens.get("provider", "google"),
                    access_token=tokens["access_token"],
                    refresh_token=encrypted_refresh_token,
                    expires_at=expires_at,
                    scopes=tokens.get("scopes", []),
                )
                self.db.add(new_token)

            self.db.commit()

        except SQLAlchemyError as e:
            self.db.rollback()
            raise TokenStorageError(f"Database error while saving tokens: {e}") from e
        except Exception as e:
            self.db.rollback()
            raise TokenStorageError(f"Error saving tokens: {e}") from e

    async def delete(self, aircraft_id: UUID) -> bool:
        """Delete tokens for a aircraft.

        Args:
            aircraft_id: Aircraft UUID

        Returns:
            True if tokens were deleted, False if not found

        Raises:
            TokenStorageError: If delete fails
        """
        try:
            token_record = (
                self.db.query(OAuthToken).filter(OAuthToken.aircraft_id == aircraft_id).first()
            )

            if token_record is None:
                return False

            self.db.delete(token_record)
            self.db.commit()
            return True

        except SQLAlchemyError as e:
            self.db.rollback()
            raise TokenStorageError(f"Database error while deleting tokens: {e}") from e
        except Exception as e:
            self.db.rollback()
            raise TokenStorageError(f"Error deleting tokens: {e}") from e

    async def is_expired(self, aircraft_id: UUID) -> Optional[bool]:
        """Check if access token is expired.

        Args:
            aircraft_id: Aircraft UUID

        Returns:
            True if expired, False if valid, None if not found

        Raises:
            TokenStorageError: If check fails
        """
        try:
            token_record = (
                self.db.query(OAuthToken).filter(OAuthToken.aircraft_id == aircraft_id).first()
            )

            if token_record is None:
                return None

            # Check if expired (with 1 minute buffer for clock skew)
            now = datetime.now(datetime.UTC) if hasattr(datetime, "UTC") else datetime.utcnow()
            return token_record.expires_at <= now

        except SQLAlchemyError as e:
            raise TokenStorageError(f"Database error while checking expiration: {e}") from e
