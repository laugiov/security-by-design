"""
Integration tests for Role-Based Access Control (RBAC).

This module tests:
- Endpoint access based on role
- Permission-based authorization
- Role in JWT tokens
- Authorization failure responses

Security by Design: Verify that RBAC is properly enforced at the API level.
"""

import pytest
from fastapi.testclient import TestClient

from skylink.auth import create_access_token
from skylink.main import app


@pytest.fixture
def client():
    """Test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def token_standard():
    """Token with aircraft_standard role (default)."""
    return create_access_token(
        "550e8400-e29b-41d4-a716-446655440000",
        role="aircraft_standard",
    )


@pytest.fixture
def token_premium():
    """Token with aircraft_premium role."""
    return create_access_token(
        "550e8400-e29b-41d4-a716-446655440001",
        role="aircraft_premium",
    )


@pytest.fixture
def token_ground_control():
    """Token with ground_control role."""
    return create_access_token(
        "550e8400-e29b-41d4-a716-446655440002",
        role="ground_control",
    )


@pytest.fixture
def token_maintenance():
    """Token with maintenance role."""
    return create_access_token(
        "550e8400-e29b-41d4-a716-446655440003",
        role="maintenance",
    )


@pytest.fixture
def token_admin():
    """Token with admin role."""
    return create_access_token(
        "550e8400-e29b-41d4-a716-446655440004",
        role="admin",
    )


class TestTokenWithRole:
    """Test that tokens include role claim."""

    def test_token_request_with_role(self, client):
        """Token request should accept role parameter."""
        response = client.post(
            "/auth/token",
            json={
                "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "aircraft_premium",
            },
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_token_request_default_role(self, client):
        """Token without role should use default."""
        response = client.post(
            "/auth/token",
            json={"aircraft_id": "550e8400-e29b-41d4-a716-446655440000"},
        )
        assert response.status_code == 200
        # Token should be valid with default role
        token = response.json()["access_token"]

        # Use token to access weather (allowed for all roles)
        weather_response = client.get(
            "/weather/current?lat=48.8566&lon=2.3522",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should work (200) or service unavailable (502/504)
        assert weather_response.status_code in [200, 502, 504]


class TestWeatherEndpointRBAC:
    """Test weather endpoint RBAC (requires WEATHER_READ)."""

    def test_weather_allowed_for_standard(self, client, token_standard):
        """aircraft_standard should access weather."""
        response = client.get(
            "/weather/current?lat=48.8566&lon=2.3522",
            headers={"Authorization": f"Bearer {token_standard}"},
        )
        # Should work or service unavailable
        assert response.status_code in [200, 502, 504]

    def test_weather_allowed_for_premium(self, client, token_premium):
        """aircraft_premium should access weather."""
        response = client.get(
            "/weather/current?lat=48.8566&lon=2.3522",
            headers={"Authorization": f"Bearer {token_premium}"},
        )
        assert response.status_code in [200, 502, 504]

    def test_weather_allowed_for_all_roles(
        self,
        client,
        token_standard,
        token_premium,
        token_ground_control,
        token_maintenance,
        token_admin,
    ):
        """All roles should have weather access."""
        tokens = [
            token_standard,
            token_premium,
            token_ground_control,
            token_maintenance,
            token_admin,
        ]

        for token in tokens:
            response = client.get(
                "/weather/current?lat=48.8566&lon=2.3522",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code in [200, 502, 504]


class TestContactsEndpointRBAC:
    """Test contacts endpoint RBAC (requires CONTACTS_READ)."""

    def test_contacts_denied_for_standard(self, client, token_standard):
        """aircraft_standard should NOT access contacts."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_standard}"},
        )
        assert response.status_code == 403
        assert "Permission denied" in response.json().get("detail", "")

    def test_contacts_allowed_for_premium(self, client, token_premium):
        """aircraft_premium should access contacts."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_premium}"},
        )
        # Should work or service unavailable (not 403)
        assert response.status_code in [200, 502, 504]

    def test_contacts_allowed_for_ground_control(self, client, token_ground_control):
        """ground_control should access contacts."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_ground_control}"},
        )
        assert response.status_code in [200, 502, 504]

    def test_contacts_denied_for_maintenance(self, client, token_maintenance):
        """maintenance should NOT access contacts."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_maintenance}"},
        )
        assert response.status_code == 403

    def test_contacts_allowed_for_admin(self, client, token_admin):
        """admin should access contacts."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert response.status_code in [200, 502, 504]


class TestTelemetryEndpointRBAC:
    """Test telemetry ingest endpoint RBAC (requires TELEMETRY_WRITE)."""

    def _make_telemetry_event(self, aircraft_id: str, event_suffix: str = "0001"):
        """Create a test telemetry event with matching aircraft_id.

        Uses the correct TelemetryEvent schema: event_id, aircraft_id, ts, metrics.
        """
        # Create unique event_id based on aircraft_id suffix
        return {
            "event_id": f"{aircraft_id[:-4]}{event_suffix}",
            "aircraft_id": aircraft_id,
            "ts": "2025-01-01T12:00:00Z",
            "metrics": {
                "speed": 65.5,
                "altitude": 75.0,
                "engine_temp": 90.0,
            },
        }

    def test_telemetry_ingest_allowed_for_standard(self, client, token_standard):
        """aircraft_standard should ingest telemetry."""
        # Aircraft ID must match JWT sub (IDOR protection)
        response = client.post(
            "/telemetry/ingest",
            json=self._make_telemetry_event("550e8400-e29b-41d4-a716-446655440000"),
            headers={"Authorization": f"Bearer {token_standard}"},
        )
        # Should work or service unavailable (not 403)
        assert response.status_code in [200, 201, 409, 502, 504]

    def test_telemetry_ingest_denied_for_ground_control(self, client, token_ground_control):
        """ground_control should NOT ingest telemetry (read-only)."""
        response = client.post(
            "/telemetry/ingest",
            json=self._make_telemetry_event("550e8400-e29b-41d4-a716-446655440002"),
            headers={"Authorization": f"Bearer {token_ground_control}"},
        )
        assert response.status_code == 403
        assert "Permission denied" in response.json().get("detail", "")

    def test_telemetry_ingest_allowed_for_maintenance(self, client, token_maintenance):
        """maintenance should ingest telemetry."""
        response = client.post(
            "/telemetry/ingest",
            json=self._make_telemetry_event("550e8400-e29b-41d4-a716-446655440003"),
            headers={"Authorization": f"Bearer {token_maintenance}"},
        )
        assert response.status_code in [200, 201, 409, 502, 504]


class TestAuthorizationErrorResponse:
    """Test authorization error responses."""

    def test_403_response_format(self, client, token_standard):
        """403 response should have standard format."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_standard}"},
        )
        assert response.status_code == 403

        body = response.json()
        assert "detail" in body
        assert "Permission denied" in body["detail"]

    def test_403_does_not_leak_role_info(self, client, token_standard):
        """403 response should not reveal all available roles."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_standard}"},
        )
        body = response.json()

        # Should not list other roles that would work
        assert "aircraft_premium" not in body.get("detail", "")
        assert "admin" not in body.get("detail", "")


class TestAuthenticationVsAuthorization:
    """Test that authentication (401) and authorization (403) are distinct."""

    def test_no_token_returns_401(self, client):
        """Missing token should return 401, not 403."""
        response = client.get("/contacts/?person_fields=names")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """Invalid token should return 401, not 403."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    def test_valid_token_wrong_permission_returns_403(self, client, token_standard):
        """Valid token without permission should return 403."""
        response = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token_standard}"},
        )
        assert response.status_code == 403


class TestRBACWithInvalidRole:
    """Test handling of invalid role values in tokens."""

    def test_invalid_role_falls_back_to_default(self, client):
        """Token with invalid role should use default permissions."""
        # Request token with invalid role
        response = client.post(
            "/auth/token",
            json={
                "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "super_admin_hacker",  # Invalid role
            },
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Should have default (aircraft_standard) permissions
        # Weather allowed
        weather_resp = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert weather_resp.status_code in [200, 502, 504]

        # Contacts denied
        contacts_resp = client.get(
            "/contacts/?person_fields=names",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert contacts_resp.status_code == 403
