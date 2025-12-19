"""Tests for rate limiting with slowapi."""

import pytest
from fastapi.testclient import TestClient

from skylink.auth import create_access_token
from skylink.main import app
from skylink.rate_limit import limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset rate limit state before each test."""
    limiter.reset()
    yield
    limiter.reset()


def test_rate_limit_health_endpoint_not_limited():
    """Test that health endpoint is not rate limited (no decorator)."""
    for _ in range(20):
        response = client.get("/health")
        assert response.status_code == 200


def test_rate_limit_auth_endpoint_not_limited():
    """Test that auth endpoints are not rate limited (no decorator)."""
    for _ in range(15):
        response = client.post(
            "/auth/token",
            json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
        )
        assert response.status_code == 200


def test_rate_limit_weather_endpoint_limited():
    """Test that weather endpoint has rate limiting configured."""
    token = create_access_token("vehicle-rate-test")
    headers = {"Authorization": f"Bearer {token}"}

    # Make 60 requests (the limit per minute)
    for i in range(60):
        response = client.get("/weather/current?lat=48.8&lon=2.3", headers=headers)
        # May be 502 if weather service unavailable, but not 429 yet
        assert response.status_code != 429, f"Request {i+1} should not be rate limited"

    # 61st request should be rate limited
    response = client.get("/weather/current?lat=48.8&lon=2.3", headers=headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in response.headers


def test_rate_limit_response_format():
    """Test that rate limit response follows error format."""
    token = create_access_token("vehicle-format-test")
    headers = {"Authorization": f"Bearer {token}"}

    # Exceed limit (60 requests + 1)
    for _ in range(61):
        response = client.get("/weather/current?lat=48.8&lon=2.3", headers=headers)

    # Verify response format
    assert response.status_code == 429
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limit_different_vehicles_independent():
    """Test that rate limits are tracked independently per vehicle."""
    vehicle_1 = "vehicle-independent-1"
    vehicle_2 = "vehicle-independent-2"
    token_1 = create_access_token(vehicle_1)
    token_2 = create_access_token(vehicle_2)

    # Exhaust rate limit for vehicle_1 (60 requests)
    for _ in range(60):
        client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {token_1}"},
        )

    # Vehicle 1 should be rate limited
    response = client.get(
        "/weather/current?lat=48.8&lon=2.3",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert response.status_code == 429

    # Vehicle 2 should still work (may get 502 from weather service, but not 429)
    response = client.get(
        "/weather/current?lat=48.8&lon=2.3",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert response.status_code != 429
