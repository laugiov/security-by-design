"""Encryption utilities for OAuth tokens.

Provides AES-256-GCM encryption for refresh tokens at rest.
"""

import os
from base64 import b64decode, b64encode
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptionError(Exception):
    """Base exception for encryption errors."""


class TokenEncryptor:
    """Handles encryption/decryption of OAuth refresh tokens using AES-256-GCM."""

    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize encryptor with encryption key.

        Args:
            encryption_key: Hex-encoded 32-byte key. If None, reads from env ENCRYPTION_KEY.

        Raises:
            EncryptionError: If key is missing or invalid format.
        """
        key_hex = encryption_key or os.getenv("ENCRYPTION_KEY")

        if not key_hex:
            raise EncryptionError(
                "ENCRYPTION_KEY environment variable is required for token encryption"
            )

        try:
            # Convert hex string to bytes (should be 32 bytes = 256 bits)
            key_bytes = bytes.fromhex(key_hex)
            if len(key_bytes) != 32:
                raise EncryptionError(
                    f"Encryption key must be exactly 32 bytes (256 bits), got {len(key_bytes)} bytes"
                )
            self.aesgcm = AESGCM(key_bytes)
        except ValueError as e:
            raise EncryptionError(f"Invalid encryption key format: {e}") from e

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string using AES-256-GCM.

        Args:
            plaintext: The plaintext string to encrypt (e.g., refresh_token)

        Returns:
            Base64-encoded string in format: iv:ciphertext:tag

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty string")

        try:
            # Generate random 96-bit (12 bytes) nonce (IV)
            nonce = os.urandom(12)

            # Encrypt plaintext (returns ciphertext + auth tag appended)
            plaintext_bytes = plaintext.encode("utf-8")
            ciphertext_with_tag = self.aesgcm.encrypt(nonce, plaintext_bytes, None)

            # Format: base64(nonce):base64(ciphertext+tag)
            nonce_b64 = b64encode(nonce).decode("utf-8")
            ciphertext_b64 = b64encode(ciphertext_with_tag).decode("utf-8")

            return f"{nonce_b64}:{ciphertext_b64}"

        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted: str) -> str:
        """Decrypt an encrypted string using AES-256-GCM.

        Args:
            encrypted: Base64-encoded string in format: iv:ciphertext:tag

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails (wrong key, tampered data, etc.)
        """
        if not encrypted:
            raise EncryptionError("Cannot decrypt empty string")

        try:
            # Parse format: nonce_b64:ciphertext_b64
            parts = encrypted.split(":")
            if len(parts) != 2:
                raise EncryptionError(
                    f"Invalid encrypted format, expected 'nonce:ciphertext', got {len(parts)} parts"
                )

            nonce_b64, ciphertext_b64 = parts
            nonce = b64decode(nonce_b64)
            ciphertext_with_tag = b64decode(ciphertext_b64)

            # Decrypt (verifies auth tag automatically)
            plaintext_bytes = self.aesgcm.decrypt(nonce, ciphertext_with_tag, None)

            return plaintext_bytes.decode("utf-8")

        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e


# Global singleton for convenience
_encryptor: Optional[TokenEncryptor] = None


def get_encryptor() -> TokenEncryptor:
    """Get or create global TokenEncryptor instance.

    Returns:
        Shared TokenEncryptor instance

    Raises:
        EncryptionError: If encryption key is not configured
    """
    global _encryptor
    if _encryptor is None:
        _encryptor = TokenEncryptor()
    return _encryptor


def encrypt_token(plaintext: str) -> str:
    """Convenience function to encrypt a token.

    Args:
        plaintext: Token to encrypt

    Returns:
        Encrypted token string
    """
    return get_encryptor().encrypt(plaintext)


def decrypt_token(encrypted: str) -> str:
    """Convenience function to decrypt a token.

    Args:
        encrypted: Encrypted token string

    Returns:
        Decrypted plaintext token
    """
    return get_encryptor().decrypt(encrypted)
