"""Tests for router modules."""

import pytest
from fastapi.testclient import TestClient

from skylink.main import app

client = TestClient(app)


# ------------- AUTH ROUTER TESTS -------------


def test_auth_token_success():
    """Test auth token endpoint returns 200 (now implemented with RS256)."""
    response = client.post(
        "/auth/token",
        json={"aircraft_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"  # noqa: S105
    assert data["expires_in"] == 900  # 15 minutes


def test_auth_token_with_invalid_uuid():
    """Test auth token endpoint with invalid UUID."""
    response = client.post("/auth/token", json={"aircraft_id": "invalid-uuid"})
    assert response.status_code == 400  # Validation error (handled by our exception handler)


# ------------- WEATHER ROUTER TESTS -------------
# NOTE: Weather stub tests are obsolete after weather service implementation.
# The weather router now proxies to the weather microservice (demo mode with Paris fixtures).
# See test_gateway_weather_routing.py and test_weather_service.py for new tests.


# ------------- CONTACTS ROUTER TESTS -------------
# NOTE: These stub tests are obsolete after MR #6 and #7.
# The contacts router now proxies to the contacts microservice (demo mode with fixtures).
# See test_gateway_contacts_routing.py and test_contacts_service.py for new tests.

# @pytest.mark.skip(reason="Stub endpoints replaced by proxy in MR #7")
# def test_contacts_health():...
# @pytest.mark.skip(reason="Stub endpoints replaced by proxy in MR #7")
# def test_contacts_token_success():...
# ... (all contacts stub tests commented out)


# ------------- TELEMETRY ROUTER TESTS -------------


def test_telemetry_health():
    """Test telemetry health check endpoint."""
    response = client.get("/telemetry/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "telemetry"


def test_telemetry_token_success():
    """Test telemetry token endpoint returns mock token."""
    response = client.post(
        "/telemetry/token",
        json={"aircraft_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "mock_token"  # noqa: S105
    assert data["token_type"] == "Bearer"  # noqa: S105
    assert data["expires_in"] == 3600


def test_telemetry_ingest_requires_auth():
    """Test telemetry ingest endpoint requires JWT authentication."""
    telemetry_data = {
        "event_id": "550e8400-e29b-41d4-a716-446655440001",
        "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
        "ts": "2025-01-15T12:00:00Z",
        "metrics": {
            "speed": 65.5,
            "altitude": 75.0,
            "engine_temp": 90.0,
        },
    }
    response = client.post("/telemetry/ingest", json=telemetry_data)
    assert response.status_code == 401  # Requires JWT authentication


def test_telemetry_ingest_invalid_data_requires_auth():
    """Test telemetry ingest with invalid data still requires auth first."""
    response = client.post("/telemetry/ingest", json={"invalid": "data"})
    assert response.status_code == 401  # Auth checked before validation


def test_telemetry_events_not_implemented():
    """Test telemetry events endpoint returns 501."""
    response = client.get("/telemetry/events/ABC123")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


def test_telemetry_events_with_pagination():
    """Test telemetry events endpoint with pagination parameters."""
    response = client.get("/telemetry/events/ABC123?limit=50&offset=10")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


# ------------- INTEGRATION TESTS -------------


def test_all_health_endpoints():
    """Test all service health endpoints return healthy status."""
    # NOTE: Contacts and Weather routers no longer have /health endpoints (proxy-only routers)
    # Only telemetry still has its own /health endpoint
    services = ["telemetry"]
    for service in services:
        response = client.get(f"/{service}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == service


@pytest.mark.parametrize(
    "endpoint,expected_status",
    [
        ("/auth/token", 200),  # Now implemented (RS256 JWT)
        # NOTE: /weather/token removed (proxy-only router)
        # NOTE: /contacts/token removed in MR #7 (proxy-only router)
        ("/telemetry/token", 200),  # Mock response
    ],
)
def test_all_token_endpoints(endpoint, expected_status):
    """Test all token endpoints return expected status."""
    payload = {"aircraft_id": "550e8400-e29b-41d4-a716-446655440000"}
    response = client.post(endpoint, json=payload)
    assert response.status_code == expected_status


def test_security_headers_on_router_endpoints():
    """Test security headers are present on router endpoints."""
    # Use telemetry health endpoint since weather/contacts no longer have /health
    response = client.get("/telemetry/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "no-store" in response.headers["Cache-Control"]
