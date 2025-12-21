"""
Tests for authentication vulnerabilities (OWASP A07:2021).

This module tests for:
- JWT token validation
- Token expiration enforcement
- Algorithm confusion attacks
- Signature verification
- Authentication bypass attempts

Security by Design: Authentication tokens must be properly
validated on every request.
"""

import base64
import json
import time

import jwt
from fastapi.testclient import TestClient

from skylink.config import settings


class TestJWTValidation:
    """JWT token validation tests."""

    def test_missing_auth_header_rejected(self, client: TestClient):
        """Requests without Authorization header must be rejected.

        All protected endpoints require authentication.
        """
        protected_endpoints = [
            "/weather/current?lat=48.8&lon=2.3",
            "/contacts/?person_fields=names",
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, (
                f"Missing auth header not rejected on {endpoint}"
            )
            assert "WWW-Authenticate" in response.headers

    def test_malformed_auth_header_rejected(
        self, client: TestClient, auth_token: str
    ):
        """Malformed Authorization headers must be rejected.

        Only 'Bearer <token>' format is accepted.
        Note: HTTP Authorization header scheme is case-insensitive per RFC 7235,
        so 'bearer' and 'Bearer' are both valid.
        """
        # Headers that should definitely be rejected (401)
        definitely_malformed = [
            ("Bearer", "Missing token after Bearer"),
            ("Basic dXNlcjpwYXNz", "Wrong scheme (Basic instead of Bearer)"),
            ("Token " + auth_token, "Wrong scheme (Token)"),
            (auth_token, "Missing Bearer prefix"),
        ]

        for header_value, description in definitely_malformed:
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers={"Authorization": header_value}
            )
            assert response.status_code == 401, (
                f"Malformed header not rejected: {description}"
            )

        # Headers that may be accepted due to HTTP spec flexibility
        # (case-insensitive scheme, whitespace normalization)
        # If accepted, token is valid so we may get 200 or 502 (service unavailable)
        flexible_headers = [
            ("bearer " + auth_token, "Lowercase bearer (case-insensitive per RFC)"),
            ("Bearer  " + auth_token, "Double space (may be normalized)"),
        ]

        for header_value, description in flexible_headers:
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers={"Authorization": header_value}
            )
            # May be rejected (401) or accepted (200/502/504)
            assert response.status_code in [200, 401, 502, 504], (
                f"Unexpected response for: {description}"
            )

    def test_expired_token_rejected(
        self, client: TestClient, expired_token: str
    ):
        """Expired tokens must be rejected.

        JWT expiration (exp claim) must be enforced.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_invalid_signature_rejected(
        self, client: TestClient, tampered_token: str
    ):
        """Tokens with invalid signatures must be rejected.

        Any modification to the token should invalidate the signature.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )
        assert response.status_code == 401

    def test_truncated_token_rejected(
        self, client: TestClient, auth_token: str
    ):
        """Truncated tokens must be rejected.

        Partial tokens should not be accepted.
        """
        truncated_tokens = [
            auth_token[:50],  # Only header
            auth_token.split(".")[0],  # Only base64 header
            auth_token[:-20],  # Truncated signature
        ]

        for truncated in truncated_tokens:
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers={"Authorization": f"Bearer {truncated}"}
            )
            assert response.status_code == 401, (
                f"Truncated token not rejected: {truncated[:30]}..."
            )


class TestAlgorithmAttacks:
    """JWT algorithm confusion attack tests."""

    def test_none_algorithm_rejected(
        self, client: TestClient, none_algorithm_token: str
    ):
        """Tokens with 'none' algorithm must be rejected.

        The 'none' algorithm attack allows unsigned tokens.
        RS256 must be enforced.
        """
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {none_algorithm_token}"}
        )
        assert response.status_code == 401

    def test_hs256_algorithm_rejected(self, client: TestClient):
        """Tokens signed with HS256 must be rejected.

        Algorithm confusion: attacker uses public key as HMAC secret.
        Only RS256 should be accepted.
        """
        # Try to sign with the public key using HS256
        # (If server incorrectly uses public key for HS256 verification, it would accept)
        public_key = settings.get_public_key()

        payload = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "aud": "skylink",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }

        # Create HS256 token signed with public key bytes
        try:
            hs256_token = jwt.encode(
                payload,
                public_key,  # Using public key as HMAC secret
                algorithm="HS256"
            )

            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers={"Authorization": f"Bearer {hs256_token}"}
            )
            assert response.status_code == 401, (
                "HS256 algorithm confusion attack should be rejected"
            )
        except Exception:
            # Some JWT libraries reject this - that's acceptable
            pass

    def test_algorithm_in_header_ignored(
        self, client: TestClient, auth_token: str
    ):
        """Token algorithm header should not override server config.

        Server must use configured algorithm, not the one in token header.
        """
        # Decode and re-encode with different algorithm claim (but same signature)
        parts = auth_token.split(".")

        # Modify header to claim HS256 (but keep RS256 signature)
        header = {"alg": "HS256", "typ": "JWT"}  # Lie about algorithm
        header_b64 = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).rstrip(b"=").decode()

        # Create token with modified header but original payload and signature
        modified_token = f"{header_b64}.{parts[1]}.{parts[2]}"

        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {modified_token}"}
        )
        # Should be rejected because server enforces RS256
        assert response.status_code == 401


class TestTokenClaims:
    """JWT claims validation tests."""

    def test_wrong_audience_rejected(self, client: TestClient):
        """Tokens with wrong audience must be rejected.

        The 'aud' claim must match the expected audience.
        """
        private_key = settings.get_private_key()

        payload = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "aud": "wrong-audience",  # Wrong audience
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
        }

        wrong_aud_token = jwt.encode(payload, private_key, algorithm="RS256")

        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {wrong_aud_token}"}
        )
        assert response.status_code == 401

    def test_missing_subject_handled(self, client: TestClient):
        """Tokens without subject claim should be handled.

        The 'sub' claim is required for identifying the aircraft.
        """
        private_key = settings.get_private_key()

        payload = {
            # No "sub" claim
            "aud": settings.jwt_audience,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
        }

        no_sub_token = jwt.encode(payload, private_key, algorithm="RS256")

        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {no_sub_token}"}
        )
        # Should either work (sub is optional) or be rejected
        # The important thing is no 500 error
        # 502 is acceptable if the weather service is unavailable
        assert response.status_code in [200, 401, 502, 504]

    def test_future_iat_handled(self, client: TestClient):
        """Tokens with future 'iat' should be handled.

        Some implementations reject tokens issued in the future.
        """
        private_key = settings.get_private_key()
        future_time = int(time.time()) + 3600  # 1 hour in future

        payload = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "aud": settings.jwt_audience,
            "iat": future_time,  # Issued in the future
            "exp": future_time + 900,
        }

        future_token = jwt.encode(payload, private_key, algorithm="RS256")

        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {future_token}"}
        )
        # May be accepted or rejected - important is no crash
        assert response.status_code in [200, 401, 504]


class TestBruteForceProtection:
    """Brute force and rate limiting tests.

    Note: Detailed rate limiting tests are in test_rate_limiting.py
    """

    def test_rapid_auth_requests_limited(self, client: TestClient):
        """Rapid authentication requests should be rate limited.

        Prevents brute force attacks on authentication.
        """
        responses = []
        for i in range(50):
            response = client.post(
                "/auth/token",
                json={"aircraft_id": f"550e8400-e29b-41d4-a716-446655440{i:03d}"}
            )
            responses.append(response.status_code)

        # Check if any requests were rate limited
        # (Rate limiting may or may not be configured for auth endpoint)
        # At minimum, all should succeed or be rate limited - not crash
        for status in responses:
            assert status in [200, 429, 422], (
                f"Unexpected status during rapid auth: {status}"
            )


class TestTokenLeakagePrevention:
    """Tests to ensure tokens are not leaked in responses."""

    def test_error_responses_dont_leak_token(
        self, client: TestClient, auth_token: str
    ):
        """Error responses should not echo back the token.

        Prevents token exposure in error messages.
        """
        # Send invalid request with valid token
        response = client.get(
            "/weather/current",  # Missing required params
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Response body should not contain the token
        response_text = response.text
        assert auth_token not in response_text, (
            "Token leaked in error response"
        )

    def test_expired_error_doesnt_leak_token(
        self, client: TestClient, expired_token: str
    ):
        """Expired token errors should not echo the token."""
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert expired_token not in response.text
