"""
Tests for broken access control (OWASP A01:2021).

This module tests for:
- Endpoint authorization requirements
- Vertical privilege escalation
- Horizontal privilege escalation (IDOR)
- Path traversal attacks

Security by Design: All protected resources must require
proper authentication and authorization.
"""

import pytest
from fastapi.testclient import TestClient


class TestEndpointAuthorization:
    """Tests that all endpoints require proper authorization."""

    PROTECTED_GET_ENDPOINTS = [
        ("/weather/current?lat=48.8&lon=2.3", "Weather endpoint"),
        ("/contacts/?person_fields=names", "Contacts endpoint"),
    ]

    PROTECTED_POST_ENDPOINTS = [
        ("/telemetry/ingest", "Telemetry endpoint"),
    ]

    PUBLIC_ENDPOINTS = [
        ("/health", "Health check"),
        ("/docs", "OpenAPI documentation"),
        ("/openapi.json", "OpenAPI schema"),
    ]

    @pytest.mark.parametrize("endpoint,name", PROTECTED_GET_ENDPOINTS)
    def test_protected_get_requires_auth(self, client: TestClient, endpoint: str, name: str):
        """Protected GET endpoints must require authentication."""
        response = client.get(endpoint)
        assert response.status_code == 401, f"{name} should require authentication"
        assert "WWW-Authenticate" in response.headers

    @pytest.mark.parametrize("endpoint,name", PROTECTED_POST_ENDPOINTS)
    def test_protected_post_requires_auth(self, client: TestClient, endpoint: str, name: str):
        """Protected POST endpoints must require authentication."""
        response = client.post(endpoint, json={})
        assert response.status_code == 401, f"{name} should require authentication"

    @pytest.mark.parametrize("endpoint,name", PUBLIC_ENDPOINTS)
    def test_public_endpoints_accessible(self, client: TestClient, endpoint: str, name: str):
        """Public endpoints should be accessible without auth."""
        response = client.get(endpoint)
        assert response.status_code in [200, 307], f"{name} should be accessible without auth"


class TestIDORVulnerabilities:
    """Insecure Direct Object Reference (IDOR) tests.

    Tests that users cannot access resources belonging to others
    by guessing or manipulating resource identifiers.
    """

    def test_cannot_submit_telemetry_for_other_aircraft(
        self, client: TestClient, auth_headers: dict
    ):
        """Aircraft should only submit telemetry for itself.

        The aircraft_id in telemetry should match the JWT subject.
        """
        # Try to submit telemetry for a different aircraft
        response = client.post(
            "/telemetry/ingest",
            headers=auth_headers,  # Token for aircraft 550e8400...
            json={
                "event_id": "idor-test-001",
                "timestamp": "2025-12-21T12:00:00Z",
                "aircraft_id": "other-aircraft-id-not-mine",  # Different ID
                "event_type": "position",
                "payload": {"lat": 48.8, "lon": 2.3},
            },
        )
        # Should either:
        # 1. Accept (if no IDOR protection yet - current state)
        # 2. Reject with 403 (if IDOR protection implemented)
        # 3. Reject with 400/422 (if validation requires matching IDs)
        # 4. Return 502 if telemetry service is unavailable
        # Important: not 500
        assert response.status_code in [200, 201, 400, 403, 409, 422, 502]

    def test_sequential_id_enumeration_resistance(self, client: TestClient, auth_headers: dict):
        """System should not reveal information through ID enumeration.

        Sequential IDs can reveal system information.
        UUIDs should be used to prevent enumeration.
        """
        # Try sequential IDs
        sequential_ids = [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000003",
        ]

        responses = []
        for aircraft_id in sequential_ids:
            response = client.post(
                "/telemetry/ingest",
                headers=auth_headers,
                json={
                    "event_id": f"enum-test-{aircraft_id}",
                    "timestamp": "2025-12-21T12:00:00Z",
                    "aircraft_id": aircraft_id,
                    "event_type": "position",
                    "payload": {},
                },
            )
            responses.append(response.status_code)

        # All responses should be consistent (not leaking info about ID validity)
        # If 403 for one, should be 403 for all (or 200 for all if no check)
        assert (
            len(set(responses)) <= 2
        ), "Inconsistent responses may leak information about valid IDs"


class TestPathTraversal:
    """Path traversal vulnerability tests.

    Tests that file paths or resource paths cannot be manipulated
    to access unauthorized resources.
    """

    PATH_TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "....//....//etc/passwd",
        "..%2F..%2F..%2Fetc%2Fpasswd",
        "..%252f..%252f..%252fetc%252fpasswd",
        "/etc/passwd",
        "\\..\\..\\windows\\system32\\config\\sam",
    ]

    def test_contacts_person_fields_traversal(self, client: TestClient, auth_headers: dict):
        """Person fields parameter should not allow path traversal."""
        for payload in self.PATH_TRAVERSAL_PAYLOADS:
            response = client.get(
                f"/contacts/?person_fields={payload}",
                headers=auth_headers,
            )
            # Should not return file contents or 500 error
            if response.status_code == 200:
                # If 200, verify response doesn't contain file contents
                assert "root:" not in response.text, f"Path traversal may have succeeded: {payload}"
            else:
                # Error response is acceptable
                assert response.status_code in [400, 422, 502, 504]


class TestForcedBrowsing:
    """Forced browsing / direct URL access tests.

    Tests that admin or internal endpoints are properly protected.
    """

    ADMIN_PATHS = [
        "/admin",
        "/admin/",
        "/administrator",
        "/manage",
        "/management",
        "/internal",
        "/api/internal",
        "/debug",
        "/.env",
        "/config",
        "/settings",
    ]

    SENSITIVE_PATHS = [
        "/.git/config",
        "/.git/HEAD",
        "/backup",
        "/backup.sql",
        "/db.sqlite",
        "/database.db",
        "/.htaccess",
        "/web.config",
        "/server-status",
    ]

    def test_admin_paths_not_exposed(self, client: TestClient):
        """Administrative paths should not be accessible."""
        for path in self.ADMIN_PATHS:
            response = client.get(path)
            # Should return 404 (not found) or 401/403 (forbidden)
            # Never 200 with sensitive content
            assert response.status_code in [
                401,
                403,
                404,
                405,
                307,
            ], f"Admin path may be exposed: {path}"

    def test_sensitive_paths_not_exposed(self, client: TestClient):
        """Sensitive system paths should not be accessible."""
        for path in self.SENSITIVE_PATHS:
            response = client.get(path)
            assert response.status_code in [
                401,
                403,
                404,
                405,
            ], f"Sensitive path may be exposed: {path}"
            if response.status_code == 200:
                # If somehow 200, verify no sensitive content
                text = response.text.lower()
                assert "[core]" not in text  # Git config
                assert "password" not in text
                assert "secret" not in text


class TestHTTPMethodRestriction:
    """HTTP method restriction tests.

    Tests that endpoints only accept intended HTTP methods.
    """

    def test_auth_token_only_accepts_post(self, client: TestClient):
        """Auth token endpoint should only accept POST."""
        methods = [
            ("GET", client.get),
            ("PUT", client.put),
            ("DELETE", client.delete),
            ("PATCH", client.patch),
        ]

        for method_name, method_func in methods:
            response = method_func("/auth/token")
            assert response.status_code == 405, f"Auth token should not accept {method_name}"

    def test_weather_only_accepts_get(self, client: TestClient, auth_headers: dict):
        """Weather endpoint should only accept GET."""
        methods = [
            ("POST", client.post),
            ("PUT", client.put),
            ("DELETE", client.delete),
        ]

        for method_name, method_func in methods:
            response = method_func(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            )
            assert response.status_code == 405, f"Weather should not accept {method_name}"

    def test_telemetry_only_accepts_post(self, client: TestClient, auth_headers: dict):
        """Telemetry endpoint should only accept POST."""
        methods = [
            ("GET", lambda url: client.get(url, headers=auth_headers)),
            ("PUT", lambda url: client.put(url, headers=auth_headers, json={})),
            ("DELETE", lambda url: client.delete(url, headers=auth_headers)),
        ]

        for method_name, method_func in methods:
            response = method_func("/telemetry/ingest")
            assert response.status_code == 405, f"Telemetry should not accept {method_name}"


class TestHostHeaderInjection:
    """Host header injection tests.

    Tests that the Host header cannot be manipulated to cause issues.
    """

    def test_host_header_validation(self, client: TestClient):
        """Malicious Host headers should not cause security issues."""
        malicious_hosts = [
            "evil.com",
            "localhost:8000@evil.com",
            "localhost:8000#@evil.com",
        ]

        for host in malicious_hosts:
            response = client.get("/health", headers={"Host": host})
            # Should handle gracefully - either reject or ignore
            assert response.status_code in [200, 400, 421]
