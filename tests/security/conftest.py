"""
Security test fixtures for OWASP Top 10 testing.

These fixtures provide:
- Test clients with and without authentication
- Valid and invalid JWT tokens
- Expired tokens for testing token expiration
- Cryptographic key access for validation
"""

import base64
import json
import time
from typing import Generator

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from skylink.auth import create_access_token
from skylink.config import settings
from skylink.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client without authentication.

    Use this fixture for testing unauthenticated endpoints
    and verifying authentication requirements.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_token() -> str:
    """Valid JWT token for the default test aircraft.

    Returns:
        str: Valid RS256-signed JWT token

    Note:
        Token is for aircraft ID: 550e8400-e29b-41d4-a716-446655440000
    """
    return create_access_token("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Authorization headers with valid token.

    Returns:
        dict: Headers dictionary with Authorization Bearer token
    """
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def expired_token() -> str:
    """JWT token that has already expired.

    Creates a token that expired 1 hour ago for testing
    token expiration handling.

    Returns:
        str: Expired RS256-signed JWT token
    """
    private_key = settings.get_private_key()
    now = int(time.time())

    payload = {
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "aud": settings.jwt_audience,
        "iat": now - 7200,  # Issued 2 hours ago
        "exp": now - 3600,  # Expired 1 hour ago
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture
def tampered_token(auth_token: str) -> str:
    """JWT token with tampered payload.

    Takes a valid token and modifies the payload
    to test signature verification.

    Returns:
        str: Token with invalid signature due to tampering
    """
    parts = auth_token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    # Decode payload, modify, re-encode (without proper signature)
    payload_b64 = parts[1]
    # Add padding if needed
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding

    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    payload["sub"] = "attacker-modified-subject"

    new_payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    # Return token with modified payload but original signature
    return f"{parts[0]}.{new_payload_b64}.{parts[2]}"


@pytest.fixture
def none_algorithm_token() -> str:
    """JWT token using 'none' algorithm (attack vector).

    This token attempts the algorithm confusion attack
    where an attacker crafts a token with alg=none.

    Returns:
        str: Unsigned JWT token with alg=none
    """
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "550e8400-e29b-41d4-a716-446655440000",
        "aud": "skylink",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }

    header_b64 = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).rstrip(b"=").decode()

    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()

    # Token with empty signature
    return f"{header_b64}.{payload_b64}."


@pytest.fixture
def jwt_public_key():
    """RSA public key for cryptographic tests.

    Returns:
        RSAPublicKey: The public key object for validation
    """
    public_key_pem = settings.get_public_key()
    return serialization.load_pem_public_key(public_key_pem.encode())


@pytest.fixture
def auth_token_aircraft_a() -> str:
    """Token for Aircraft A (for cross-aircraft tests).

    Returns:
        str: Valid JWT for aircraft A
    """
    return create_access_token("aircraft-a-00000000-0000-0000-0000-000000000001")


@pytest.fixture
def auth_token_aircraft_b() -> str:
    """Token for Aircraft B (for cross-aircraft tests).

    Returns:
        str: Valid JWT for aircraft B
    """
    return create_access_token("aircraft-b-00000000-0000-0000-0000-000000000002")


@pytest.fixture
def standard_uuid() -> str:
    """Standard test aircraft UUID.

    Returns:
        str: A valid UUID string for testing
    """
    return "550e8400-e29b-41d4-a716-446655440000"
