"""Tests for /auth/token endpoint (token issuance via HTTP)."""

import jwt
from fastapi.testclient import TestClient

from skylink.config import settings
from skylink.main import app

client = TestClient(app)


def test_obtain_token_success():
    """Test POST /auth/token with valid vehicle_id returns token."""
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "access_token" in data
    assert "token_type" in data
    assert "expires_in" in data

    # Verify values
    assert data["token_type"] == "Bearer"  # noqa: S105 (checking token type, not password)
    assert data["expires_in"] == 900  # 15 minutes = 900 seconds
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 50  # JWT tokens are long


def test_obtain_token_returns_valid_jwt():
    """Test that returned token is a valid RS256 JWT."""
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    # Verify token with public key
    public_key = settings.get_public_key()
    payload = jwt.decode(token, public_key, algorithms=["RS256"], audience="skylink")

    assert payload["sub"] == "550e8400-e29b-41d4-a716-446655440000"
    assert payload["aud"] == "skylink"
    assert "iat" in payload
    assert "exp" in payload


def test_obtain_token_invalid_uuid():
    """Test POST /auth/token with invalid UUID returns 400."""
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "not-a-valid-uuid"},
    )

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_obtain_token_missing_vehicle_id():
    """Test POST /auth/token without vehicle_id returns 400."""
    response = client.post("/auth/token", json={})

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_obtain_token_extra_fields():
    """Test POST /auth/token with extra fields returns 400 (additionalProperties: false)."""
    response = client.post(
        "/auth/token",
        json={
            "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
            "extra_field": "should_not_be_allowed",
        },
    )

    # Should be rejected due to additionalProperties: false
    assert response.status_code == 400


def test_obtain_token_multiple_vehicles():
    """Test that different vehicles get different tokens."""
    vehicle_1 = "550e8400-e29b-41d4-a716-446655440000"
    vehicle_2 = "660e8400-e29b-41d4-a716-446655440111"

    response_1 = client.post("/auth/token", json={"vehicle_id": vehicle_1})
    response_2 = client.post("/auth/token", json={"vehicle_id": vehicle_2})

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    token_1 = response_1.json()["access_token"]
    token_2 = response_2.json()["access_token"]

    # Tokens should be different
    assert token_1 != token_2

    # Each should contain correct vehicle_id
    payload_1 = jwt.decode(token_1, options={"verify_signature": False})
    payload_2 = jwt.decode(token_2, options={"verify_signature": False})

    assert payload_1["sub"] == vehicle_1
    assert payload_2["sub"] == vehicle_2


def test_obtain_token_can_be_used_for_auth():
    """Test that token from /auth/token can be used to access protected endpoints."""
    # Get token
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Use token to access a protected endpoint (health doesn't require auth)
    response = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_obtain_token_security_headers():
    """Test that /auth/token responses include security headers."""
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
    )

    # Even token issuance should have security headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_obtain_token_has_trace_id():
    """Test that /auth/token responses include trace_id for observability."""
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
    )

    # Should have trace_id for correlation
    assert "X-Trace-Id" in response.headers
    assert len(response.headers["X-Trace-Id"]) > 0


def test_obtain_token_repeated_calls():
    """Test that calling /auth/token multiple times works (stateless)."""
    vehicle_id = "550e8400-e29b-41d4-a716-446655440000"

    # Call 3 times
    for _ in range(3):
        response = client.post("/auth/token", json={"vehicle_id": vehicle_id})
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert len(token) > 50
