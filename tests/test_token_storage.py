"""Tests for token storage module."""

import os
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest

from contacts.database import get_test_db, reset_test_db
from contacts.encryption import decrypt_token
from contacts.tokens import TokenStorage


@pytest.fixture
def test_encryption_key():
    """Provide a test encryption key."""
    return "0123456789abcdef" * 4  # 64 hex chars = 32 bytes


@pytest.fixture
def token_storage(test_encryption_key):
    """Create TokenStorage with test database."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": test_encryption_key}):
        reset_test_db()  # Ensure clean state
        db = get_test_db()
        yield TokenStorage(db)
        db.close()


@pytest.fixture
def sample_aircraft_id():
    """Provide a sample aircraft UUID."""
    return UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def sample_tokens():
    """Provide sample token data."""
    return {
        "access_token": "ya29.a0AfB_byC...",
        "refresh_token": "1//0gHdtzPnWxCB4CgYIARAAGBASNwF-L9Ir...",
        "expires_at": datetime.utcnow() + timedelta(hours=1),
        "scopes": ["https://www.googleapis.com/auth/contacts.readonly"],
        "provider": "google",
    }


class TestTokenStorageGet:
    """Test TokenStorage.get() method."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_aircraft_returns_none(self, token_storage, sample_aircraft_id):
        """Get should return None if aircraft has no tokens."""
        result = await token_storage.get(sample_aircraft_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_existing_aircraft_returns_decrypted_tokens(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """Get should return tokens with decrypted refresh_token."""
        # Save tokens first
        await token_storage.save(sample_aircraft_id, sample_tokens)

        # Retrieve tokens
        result = await token_storage.get(sample_aircraft_id)

        assert result is not None
        assert result["access_token"] == sample_tokens["access_token"]
        assert result["refresh_token"] == sample_tokens["refresh_token"]  # Decrypted
        assert result["scopes"] == sample_tokens["scopes"]
        assert result["provider"] == sample_tokens["provider"]


class TestTokenStorageSave:
    """Test TokenStorage.save() method."""

    @pytest.mark.asyncio
    async def test_save_new_aircraft_creates_record(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """Save should create a new record for new aircraft."""
        await token_storage.save(sample_aircraft_id, sample_tokens)

        # Verify record exists
        result = await token_storage.get(sample_aircraft_id)
        assert result is not None
        assert str(result["aircraft_id"]) == str(sample_aircraft_id)

    @pytest.mark.asyncio
    async def test_save_encrypts_refresh_token(
        self, token_storage, sample_aircraft_id, sample_tokens, test_encryption_key
    ):
        """Save should encrypt refresh_token before storing."""
        await token_storage.save(sample_aircraft_id, sample_tokens)

        # Get raw database record
        from contacts.models import OAuthToken

        db_record = (
            token_storage.db.query(OAuthToken)
            .filter(OAuthToken.aircraft_id == sample_aircraft_id)
            .first()
        )

        # refresh_token in DB should be encrypted (different from plaintext)
        assert db_record.refresh_token != sample_tokens["refresh_token"]
        assert ":" in db_record.refresh_token  # Contains nonce:ciphertext format

        # But should decrypt correctly
        with patch.dict(os.environ, {"ENCRYPTION_KEY": test_encryption_key}):
            decrypted = decrypt_token(db_record.refresh_token)
            assert decrypted == sample_tokens["refresh_token"]

    @pytest.mark.asyncio
    async def test_save_updates_existing_aircraft(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """Save should update existing record if aircraft already has tokens."""
        # Save initial tokens
        await token_storage.save(sample_aircraft_id, sample_tokens)

        # Update with new tokens
        new_tokens = {
            **sample_tokens,
            "access_token": "ya29.NEW_TOKEN",
            "expires_at": datetime.utcnow() + timedelta(hours=2),
        }
        await token_storage.save(sample_aircraft_id, new_tokens)

        # Verify updated
        result = await token_storage.get(sample_aircraft_id)
        assert result["access_token"] == "ya29.NEW_TOKEN"

    @pytest.mark.asyncio
    async def test_save_accepts_string_expires_at(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """Save should handle expires_at as ISO string."""
        tokens_with_string_expiry = {
            **sample_tokens,
            "expires_at": "2025-12-31T23:59:59+00:00",
        }

        await token_storage.save(sample_aircraft_id, tokens_with_string_expiry)

        result = await token_storage.get(sample_aircraft_id)
        assert result is not None
        assert isinstance(result["expires_at"], datetime)


class TestTokenStorageDelete:
    """Test TokenStorage.delete() method."""

    @pytest.mark.asyncio
    async def test_delete_existing_aircraft_returns_true(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """Delete should return True and remove tokens for existing aircraft."""
        # Save tokens first
        await token_storage.save(sample_aircraft_id, sample_tokens)

        # Delete
        result = await token_storage.delete(sample_aircraft_id)
        assert result is True

        # Verify deleted
        tokens = await token_storage.get(sample_aircraft_id)
        assert tokens is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_aircraft_returns_false(self, token_storage, sample_aircraft_id):
        """Delete should return False if aircraft has no tokens."""
        result = await token_storage.delete(sample_aircraft_id)
        assert result is False


class TestTokenStorageIsExpired:
    """Test TokenStorage.is_expired() method."""

    @pytest.mark.asyncio
    async def test_is_expired_returns_none_for_nonexistent_aircraft(
        self, token_storage, sample_aircraft_id
    ):
        """is_expired should return None if aircraft has no tokens."""
        result = await token_storage.is_expired(sample_aircraft_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_is_expired_returns_false_for_valid_token(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """is_expired should return False if access_token is valid."""
        # Token expires in 1 hour (future)
        tokens = {
            **sample_tokens,
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        await token_storage.save(sample_aircraft_id, tokens)

        result = await token_storage.is_expired(sample_aircraft_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_expired_returns_true_for_expired_token(
        self, token_storage, sample_aircraft_id, sample_tokens
    ):
        """is_expired should return True if access_token is expired."""
        # Token expired 1 hour ago (past)
        tokens = {
            **sample_tokens,
            "expires_at": datetime.utcnow() - timedelta(hours=1),
        }
        await token_storage.save(sample_aircraft_id, tokens)

        result = await token_storage.is_expired(sample_aircraft_id)
        assert result is True
