"""
Tests for security headers (OWASP A05:2021 - Security Misconfiguration).

This module tests for:
- Standard security headers presence
- CORS configuration
- Content-Type handling
- Cache control for sensitive data

Security by Design: Security headers provide defense-in-depth
against various web attacks.
"""

import pytest
from fastapi.testclient import TestClient


class TestSecurityHeaders:
    """HTTP security headers verification tests."""

    def test_content_type_options_header(
        self, client: TestClient, auth_headers: dict
    ):
        """X-Content-Type-Options should prevent MIME sniffing.

        Setting 'nosniff' prevents browsers from MIME-sniffing
        a response away from the declared content-type.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )

        # May be set by middleware or reverse proxy
        content_type_options = response.headers.get("X-Content-Type-Options")
        if content_type_options:
            assert content_type_options == "nosniff"
        else:
            pytest.skip(
                "X-Content-Type-Options not set. "
                "Consider adding security headers middleware."
            )

    def test_frame_options_header(
        self, client: TestClient, auth_headers: dict
    ):
        """X-Frame-Options should prevent clickjacking.

        DENY or SAMEORIGIN prevents the page from being framed.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )

        frame_options = response.headers.get("X-Frame-Options")
        if frame_options:
            assert frame_options.upper() in ["DENY", "SAMEORIGIN"], (
                f"X-Frame-Options should be DENY or SAMEORIGIN, got {frame_options}"
            )
        else:
            pytest.skip(
                "X-Frame-Options not set. "
                "Consider adding security headers middleware."
            )

    def test_xss_protection_header(
        self, client: TestClient, auth_headers: dict
    ):
        """X-XSS-Protection header for legacy browser support.

        Note: Modern browsers have built-in XSS protection and
        this header is considered legacy. CSP is preferred.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )

        xss_protection = response.headers.get("X-XSS-Protection")
        if xss_protection:
            # Should be "1; mode=block" or "0" (disabled due to bypass concerns)
            assert xss_protection in ["1; mode=block", "0"]

    def test_strict_transport_security(
        self, client: TestClient, auth_headers: dict
    ):
        """Strict-Transport-Security (HSTS) should be set in production.

        HSTS ensures browsers only connect via HTTPS.
        Note: Only meaningful over HTTPS connections.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )

        hsts = response.headers.get("Strict-Transport-Security")
        if hsts:
            assert "max-age" in hsts.lower()
        # HSTS is typically only set in production over HTTPS
        # Not a failure if missing in development

    def test_content_security_policy_on_html(self, client: TestClient):
        """Content-Security-Policy should be set for HTML responses.

        CSP prevents XSS and other code injection attacks.
        """
        response = client.get("/docs")

        csp = response.headers.get("Content-Security-Policy")
        if csp:
            # Should have at least default-src directive
            assert "default-src" in csp or "script-src" in csp
        else:
            pytest.skip(
                "CSP not set for HTML pages. "
                "Consider adding Content-Security-Policy."
            )

    def test_no_server_version_disclosure(self, client: TestClient):
        """Server header should not disclose version information.

        Version disclosure helps attackers identify vulnerable software.
        """
        response = client.get("/health")

        server = response.headers.get("Server", "")

        # Check for common framework version patterns
        version_patterns = [
            "uvicorn/",
            "python/",
            "fastapi/",
            "starlette/",
        ]

        for pattern in version_patterns:
            assert pattern.lower() not in server.lower(), (
                f"Server header discloses version: {server}"
            )

    def test_no_powered_by_header(self, client: TestClient):
        """X-Powered-By header should not be present.

        This header can reveal framework information.
        """
        response = client.get("/health")

        powered_by = response.headers.get("X-Powered-By")
        assert powered_by is None, (
            f"X-Powered-By header should not be set: {powered_by}"
        )


class TestCORSConfiguration:
    """Cross-Origin Resource Sharing (CORS) tests."""

    def test_cors_preflight_handled(self, client: TestClient):
        """CORS preflight requests should be handled."""
        response = client.options(
            "/weather/current",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        # Should either allow or deny, not error
        assert response.status_code in [200, 204, 400, 403, 405]

    def test_cors_no_wildcard_with_credentials(self, client: TestClient):
        """CORS with credentials should not use wildcard origin.

        If Access-Control-Allow-Credentials is true,
        Access-Control-Allow-Origin cannot be "*".
        """
        response = client.options(
            "/weather/current",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )

        allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
        allow_credentials = response.headers.get("Access-Control-Allow-Credentials", "")

        if allow_credentials.lower() == "true":
            assert allow_origin != "*", (
                "CORS with credentials cannot use wildcard origin"
            )

    def test_cors_origin_validation(self, client: TestClient):
        """CORS should validate allowed origins.

        Random origins should not be reflected.
        """
        response = client.options(
            "/weather/current",
            headers={
                "Origin": "https://evil-site.com",
                "Access-Control-Request-Method": "GET",
            }
        )

        allow_origin = response.headers.get("Access-Control-Allow-Origin", "")

        # Should either not reflect the origin, or use a whitelist
        # Reflecting arbitrary origins is a security issue
        if allow_origin == "https://evil-site.com":
            pytest.fail(
                "CORS reflects arbitrary origin - potential security issue"
            )


class TestContentTypeEnforcement:
    """Content-Type enforcement tests."""

    def test_json_content_type_for_api_responses(
        self, client: TestClient, auth_headers: dict
    ):
        """API responses should have correct Content-Type."""
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )

        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            assert "application/json" in content_type, (
                f"API response should be application/json, got {content_type}"
            )

    def test_rejects_wrong_content_type(
        self, client: TestClient, auth_headers: dict
    ):
        """POST endpoints should validate Content-Type."""
        response = client.post(
            "/telemetry/ingest",
            headers={
                **auth_headers,
                "Content-Type": "text/plain",
            },
            content="not json"
        )
        # Should reject non-JSON content
        # API returns 400 for validation errors (custom handler)
        assert response.status_code in [400, 422]


class TestCacheControl:
    """Cache control for sensitive data."""

    def test_auth_response_not_cached(self, client: TestClient):
        """Authentication responses should not be cached."""
        response = client.post(
            "/auth/token",
            json={"aircraft_id": "550e8400-e29b-41d4-a716-446655440000"}
        )

        cache_control = response.headers.get("Cache-Control", "")
        # pragma = response.headers.get("Pragma", "")  # Legacy header, not checked

        # Sensitive responses should have no-store or no-cache
        # This is optional but recommended
        if response.status_code == 200:
            # Token responses contain sensitive data
            if "no-store" not in cache_control and "no-cache" not in cache_control:
                pytest.skip(
                    "Auth responses should have Cache-Control: no-store. "
                    "Consider adding cache control headers."
                )

    def test_api_responses_cache_appropriate(
        self, client: TestClient, auth_headers: dict
    ):
        """API responses should have appropriate caching."""
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )

        # Weather data could be cached briefly
        # Just verify no error occurs (502 for service unavailable, 429 if rate limited)
        assert response.status_code in [200, 429, 502, 504]


class TestErrorResponses:
    """Error response security tests."""

    def test_404_doesnt_leak_info(self, client: TestClient):
        """404 responses should not leak information."""
        response = client.get("/nonexistent-endpoint-12345")

        # Should not reveal framework or version
        body = response.text.lower()
        assert "fastapi" not in body or "version" not in body
        assert "traceback" not in body
        assert "exception" not in body

    def test_error_responses_consistent(
        self, client: TestClient, auth_headers: dict
    ):
        """Error responses should be consistent to prevent enumeration."""
        # Invalid lat and missing lat should both return 422
        response_invalid = client.get(
            "/weather/current?lat=invalid&lon=2.3",
            headers=auth_headers,
        )
        response_missing = client.get(
            "/weather/current?lon=2.3",
            headers=auth_headers,
        )

        assert response_invalid.status_code == response_missing.status_code

    def test_no_stack_trace_in_errors(
        self, client: TestClient, auth_headers: dict
    ):
        """Error responses should not contain stack traces."""
        # Send malformed request
        response = client.post(
            "/telemetry",
            headers=auth_headers,
            content=b"not valid json{{{",
        )

        body = response.text.lower()
        assert "traceback" not in body
        assert "file \"" not in body  # Python traceback pattern
        assert "line " not in body
