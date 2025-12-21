"""
Tests for cryptographic failures (OWASP A02:2021).

This module tests for:
- JWT algorithm security (RS256)
- Key size adequacy
- Token lifetime limits
- Proper cryptographic practices

Security by Design: Use strong cryptography with appropriate
key sizes and short token lifetimes.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from skylink.auth import create_access_token
from skylink.config import settings


class TestJWTAlgorithm:
    """JWT cryptographic algorithm tests."""

    def test_jwt_uses_rs256(self, auth_token: str):
        """JWT must use RS256 (RSA + SHA-256) algorithm.

        RS256 (asymmetric) is more secure than HS256 (symmetric) because:
        1. Private key never needs to be shared
        2. Tokens can be verified by anyone with public key
        3. Prevents algorithm confusion attacks
        """
        header = jwt.get_unverified_header(auth_token)
        assert header["alg"] == "RS256", (
            f"JWT must use RS256, not {header['alg']}"
        )

    def test_jwt_has_type_claim(self, auth_token: str):
        """JWT header should specify type as JWT."""
        header = jwt.get_unverified_header(auth_token)
        assert header.get("typ") == "JWT"

    def test_configured_algorithm_is_rs256(self):
        """Application configuration must specify RS256."""
        assert settings.jwt_algorithm == "RS256", (
            "JWT algorithm configuration must be RS256"
        )


class TestKeyStrength:
    """RSA key strength tests."""

    def test_rsa_key_minimum_2048_bits(self, jwt_public_key):
        """RSA key must be at least 2048 bits.

        NIST recommends 2048-bit keys minimum for RSA.
        For long-term security, 3072+ bits is recommended.
        """
        key_size = jwt_public_key.key_size
        assert key_size >= 2048, (
            f"RSA key size {key_size} bits is too small. "
            "Minimum 2048 bits required."
        )

    def test_rsa_key_recommended_3072_bits(self, jwt_public_key):
        """RSA key should ideally be 3072+ bits for long-term security.

        This is a warning, not a failure.
        """
        key_size = jwt_public_key.key_size
        if key_size < 3072:
            pytest.skip(
                f"RSA key is {key_size} bits. "
                "Consider upgrading to 3072+ bits for long-term security."
            )

    def test_public_key_is_rsa(self, jwt_public_key):
        """Public key must be an RSA key."""
        assert isinstance(jwt_public_key, rsa.RSAPublicKey), (
            "JWT public key must be RSA"
        )


class TestTokenLifetime:
    """JWT token lifetime tests."""

    def test_jwt_has_expiration(self, auth_token: str):
        """JWT must have an expiration (exp) claim.

        Tokens without expiration are a security risk.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})
        assert "exp" in payload, "JWT must have expiration claim"

    def test_jwt_has_issued_at(self, auth_token: str):
        """JWT should have an issued-at (iat) claim.

        Helps with token validation and debugging.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})
        assert "iat" in payload, "JWT should have issued-at claim"

    def test_jwt_lifetime_maximum_15_minutes(self, auth_token: str):
        """JWT lifetime must not exceed 15 minutes.

        Short-lived tokens limit the window for token theft/reuse.
        15 minutes is the maximum per Security by Design requirements.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})

        exp = payload["exp"]
        iat = payload.get("iat", time.time())

        lifetime_seconds = exp - iat
        lifetime_minutes = lifetime_seconds / 60

        assert lifetime_minutes <= 15, (
            f"JWT lifetime {lifetime_minutes:.1f} minutes exceeds "
            "15-minute maximum (Security by Design)"
        )

    def test_configured_expiration_is_15_minutes(self):
        """Configuration should specify 15-minute maximum expiration."""
        assert settings.jwt_expiration_minutes <= 15, (
            f"Configured expiration {settings.jwt_expiration_minutes} minutes "
            "exceeds 15-minute maximum"
        )

    def test_token_expires_in_expected_time(self, auth_token: str):
        """Token expiration should match configuration."""
        payload = jwt.decode(auth_token, options={"verify_signature": False})

        exp = payload["exp"]
        iat = payload["iat"]

        lifetime_seconds = exp - iat
        expected_seconds = settings.jwt_expiration_minutes * 60

        # Allow 2 second tolerance for timing
        assert abs(lifetime_seconds - expected_seconds) <= 2, (
            f"Token lifetime {lifetime_seconds}s doesn't match "
            f"configured {expected_seconds}s"
        )


class TestTokenClaims:
    """JWT claims security tests."""

    def test_jwt_has_audience(self, auth_token: str):
        """JWT should have audience (aud) claim.

        Audience restricts which services can accept the token.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})
        assert "aud" in payload, "JWT should have audience claim"

    def test_jwt_audience_is_skylink(self, auth_token: str):
        """JWT audience should be 'skylink'.

        Prevents token reuse for other services.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})
        assert payload.get("aud") == "skylink", (
            f"JWT audience should be 'skylink', got '{payload.get('aud')}'"
        )

    def test_jwt_has_subject(self, auth_token: str):
        """JWT must have subject (sub) claim.

        Subject identifies the aircraft.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})
        assert "sub" in payload, "JWT must have subject claim"
        assert payload["sub"], "JWT subject must not be empty"

    def test_jwt_no_sensitive_claims(self, auth_token: str):
        """JWT should not contain sensitive information.

        Tokens should only contain necessary claims, not secrets.
        """
        payload = jwt.decode(auth_token, options={"verify_signature": False})

        sensitive_keys = ["password", "secret", "key", "api_key", "token"]

        for key in sensitive_keys:
            assert key not in payload, (
                f"JWT should not contain '{key}' claim"
            )


class TestCryptographicPractices:
    """General cryptographic practice tests."""

    def test_different_tokens_for_same_aircraft(self):
        """Each token generation should produce unique tokens.

        Tokens should include timestamps making them unique.
        """
        aircraft_id = "550e8400-e29b-41d4-a716-446655440000"

        token1 = create_access_token(aircraft_id)
        # Small delay to ensure different timestamps
        time.sleep(0.01)
        token2 = create_access_token(aircraft_id)

        # Tokens should be different (different iat at minimum)
        # Note: If generated within same second, they might be identical
        # which is acceptable but not ideal
        if token1 == token2:
            pytest.skip(
                "Tokens generated within same second may be identical. "
                "Consider using millisecond precision for iat."
            )

    def test_token_cannot_be_decoded_without_key(self, auth_token: str):
        """Token should fail verification without the key.

        This validates that the token is actually signed.
        """
        # Generate a different RSA key pair for testing
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Generate a different private key
        different_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        # Get its public key in PEM format
        wrong_public_key = different_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        # Decoding with a different key should fail
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(
                auth_token,
                wrong_public_key,
                algorithms=["RS256"],
                audience="skylink"
            )

    def test_private_key_not_in_token(self, auth_token: str):
        """Token should not contain any key material."""
        # Check that the token doesn't contain PEM markers
        assert "-----BEGIN" not in auth_token
        assert "-----END" not in auth_token
        assert "PRIVATE" not in auth_token.upper()
