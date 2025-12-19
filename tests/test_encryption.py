"""Tests for encryption module."""

import os
from unittest.mock import patch

import pytest

from contacts.encryption import (
    EncryptionError,
    TokenEncryptor,
    decrypt_token,
    encrypt_token,
)


class TestTokenEncryptor:
    """Test TokenEncryptor class."""

    def test_init_with_valid_key(self):
        """TokenEncryptor should initialize with valid 32-byte hex key."""
        # Generate a valid 32-byte (256-bit) key
        valid_key = "0123456789abcdef" * 4  # 64 hex chars = 32 bytes

        encryptor = TokenEncryptor(encryption_key=valid_key)
        assert encryptor.aesgcm is not None

    def test_init_without_key_raises_error(self):
        """TokenEncryptor should raise error if no key provided and env not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EncryptionError, match="ENCRYPTION_KEY.*required"):
                TokenEncryptor()

    def test_init_with_invalid_key_length_raises_error(self):
        """TokenEncryptor should raise error if key is not 32 bytes."""
        # Only 16 bytes (128 bits) - too short
        invalid_key = "0123456789abcdef" * 2

        with pytest.raises(EncryptionError, match="must be exactly 32 bytes"):
            TokenEncryptor(encryption_key=invalid_key)

    def test_init_with_invalid_hex_format_raises_error(self):
        """TokenEncryptor should raise error if key is not valid hex."""
        invalid_key = "not-a-hex-string-but-64-chars-long" * 2

        with pytest.raises(EncryptionError, match="Invalid encryption key format"):
            TokenEncryptor(encryption_key=invalid_key)

    def test_encrypt_returns_non_empty_string(self):
        """Encrypt should return a non-empty encrypted string."""
        key = "0123456789abcdef" * 4
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "my_secret_refresh_token"
        encrypted = encryptor.encrypt(plaintext)

        assert encrypted
        assert isinstance(encrypted, str)
        assert ":" in encrypted  # Should contain nonce:ciphertext format
        assert encrypted != plaintext  # Should be different from plaintext

    def test_encrypt_empty_string_raises_error(self):
        """Encrypt should raise error for empty string."""
        key = "0123456789abcdef" * 4
        encryptor = TokenEncryptor(encryption_key=key)

        with pytest.raises(EncryptionError, match="Cannot encrypt empty string"):
            encryptor.encrypt("")

    def test_decrypt_returns_original_plaintext(self):
        """Decrypt should return the original plaintext."""
        key = "0123456789abcdef" * 4
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "1//0gHdtzPnWxCB4CgYIARAAGBASNwF-L9Ir..."
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == plaintext

    def test_decrypt_with_wrong_key_raises_error(self):
        """Decrypt should fail with wrong decryption key."""
        key1 = "0123456789abcdef" * 4
        key2 = "fedcba9876543210" * 4

        encryptor1 = TokenEncryptor(encryption_key=key1)
        encryptor2 = TokenEncryptor(encryption_key=key2)

        plaintext = "secret_token"
        encrypted = encryptor1.encrypt(plaintext)

        with pytest.raises(EncryptionError, match="Decryption failed"):
            encryptor2.decrypt(encrypted)

    def test_decrypt_invalid_format_raises_error(self):
        """Decrypt should raise error for invalid encrypted format."""
        key = "0123456789abcdef" * 4
        encryptor = TokenEncryptor(encryption_key=key)

        # Invalid format (not nonce:ciphertext)
        with pytest.raises(EncryptionError, match="Invalid encrypted format"):
            encryptor.decrypt("invalid_encrypted_string")

    def test_decrypt_empty_string_raises_error(self):
        """Decrypt should raise error for empty string."""
        key = "0123456789abcdef" * 4
        encryptor = TokenEncryptor(encryption_key=key)

        with pytest.raises(EncryptionError, match="Cannot decrypt empty string"):
            encryptor.decrypt("")

    def test_encrypt_produces_different_ciphertext_each_time(self):
        """Encrypt should produce different ciphertext each time (random nonce)."""
        key = "0123456789abcdef" * 4
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "same_plaintext"
        encrypted1 = encryptor.encrypt(plaintext)
        encrypted2 = encryptor.encrypt(plaintext)

        # Different nonces should produce different ciphertexts
        assert encrypted1 != encrypted2

        # But both should decrypt to the same plaintext
        assert encryptor.decrypt(encrypted1) == plaintext
        assert encryptor.decrypt(encrypted2) == plaintext


class TestConvenienceFunctions:
    """Test convenience functions encrypt_token and decrypt_token."""

    def test_encrypt_decrypt_token_functions(self):
        """encrypt_token and decrypt_token should work with env key."""
        test_key = "0123456789abcdef" * 4

        with patch.dict(os.environ, {"ENCRYPTION_KEY": test_key}):
            plaintext = "my_token_123"
            encrypted = encrypt_token(plaintext)
            decrypted = decrypt_token(encrypted)

            assert decrypted == plaintext

    def test_encrypt_token_without_env_raises_error(self):
        """encrypt_token should raise error if ENCRYPTION_KEY not in env."""
        # Reset the singleton encryptor
        import contacts.encryption

        contacts.encryption._encryptor = None

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EncryptionError, match="ENCRYPTION_KEY.*required"):
                encrypt_token("some_token")
