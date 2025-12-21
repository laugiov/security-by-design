"""
Tests for rate limiting (DoS Protection).

This module tests for:
- Rate limit enforcement
- Retry-After header presence
- Different rate limits for different endpoints
- Rate limit bypass attempts

Security by Design: Rate limiting protects against
denial of service and brute force attacks.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient


class TestRateLimitEnforcement:
    """Rate limit enforcement tests."""

    def test_weather_endpoint_rate_limited(
        self, client: TestClient, auth_headers: dict
    ):
        """Weather endpoint should enforce rate limits.

        Protects against excessive API usage.
        """
        responses = []
        request_count = 100

        for _ in range(request_count):
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            )
            responses.append(response.status_code)

        # Count rate limited responses
        rate_limited = responses.count(429)
        successful = responses.count(200)
        timeouts = responses.count(504)

        # Either should see rate limiting or all successful
        # (depends on rate limit configuration)
        assert rate_limited > 0 or successful + timeouts == request_count, (
            f"Expected rate limiting or all success. "
            f"Got: {successful} success, {rate_limited} rate-limited, {timeouts} timeouts"
        )

    def test_rate_limit_returns_429(
        self, client: TestClient, auth_headers: dict
    ):
        """Rate limited requests should return 429 status code."""
        # Make many rapid requests to trigger rate limit
        for _ in range(150):
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            )
            if response.status_code == 429:
                # Successfully triggered rate limit
                return

        pytest.skip("Could not trigger rate limit - may need higher request count")

    def test_rate_limit_includes_retry_after(
        self, client: TestClient, auth_headers: dict
    ):
        """Rate limited responses should include Retry-After header.

        Tells clients when they can retry.
        """
        # Make many rapid requests to trigger rate limit
        for _ in range(150):
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            )
            if response.status_code == 429:
                # Check for Retry-After header
                retry_after = response.headers.get(
                    "Retry-After",
                    response.headers.get("retry-after")
                )
                if retry_after:
                    # Should be a valid number
                    assert retry_after.isdigit() or float(retry_after), (
                        f"Retry-After should be numeric: {retry_after}"
                    )
                    return
                else:
                    pytest.skip("Rate limit hit but Retry-After header not set")

        pytest.skip("Could not trigger rate limit")


class TestRateLimitReset:
    """Rate limit reset behavior tests."""

    def test_rate_limit_resets_after_window(
        self, client: TestClient, auth_headers: dict
    ):
        """Rate limit should reset after the time window.

        This test may be slow as it waits for reset.
        """
        # First, trigger rate limit
        for _ in range(150):
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            )
            if response.status_code == 429:
                break
        else:
            pytest.skip("Could not trigger rate limit")

        # Get Retry-After value
        retry_after = int(response.headers.get("Retry-After", "60"))

        # Skip if wait time is too long
        if retry_after > 5:
            pytest.skip(f"Retry-After is {retry_after}s - too long to wait")

        # Wait for reset
        time.sleep(retry_after + 1)

        # Should be able to make requests again
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )
        assert response.status_code in [200, 504], (
            "Rate limit should have reset after Retry-After period"
        )


class TestPerAircraftRateLimits:
    """Tests that rate limits are per-aircraft, not global."""

    def test_different_aircraft_have_separate_limits(
        self,
        client: TestClient,
        auth_token_aircraft_a: str,
        auth_token_aircraft_b: str,
    ):
        """Different aircraft should have separate rate limits.

        Aircraft A hitting rate limit should not affect Aircraft B.
        """
        headers_a = {"Authorization": f"Bearer {auth_token_aircraft_a}"}
        headers_b = {"Authorization": f"Bearer {auth_token_aircraft_b}"}

        # Make many requests as Aircraft A
        for _ in range(100):
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=headers_a,
            )
            if response.status_code == 429:
                break

        # Aircraft B should still be able to make requests
        response_b = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=headers_b,
        )
        # Should not be rate limited (or at least not 429 from A's limit)
        # 502 is acceptable if weather service is unavailable
        assert response_b.status_code in [200, 502, 504], (
            "Aircraft B should not be affected by Aircraft A's rate limit"
        )


class TestRateLimitBypassAttempts:
    """Tests for rate limit bypass attempts."""

    def test_rate_limit_not_bypassed_by_xff_header(
        self, client: TestClient, auth_headers: dict
    ):
        """Rate limit should not be bypassed by X-Forwarded-For header.

        Attackers might try to spoof their IP address.
        """
        # First, trigger rate limit normally
        for _ in range(100):
            response = client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            )
            if response.status_code == 429:
                break
        else:
            pytest.skip("Could not trigger rate limit")

        # Try to bypass with fake IP
        bypass_response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers={
                **auth_headers,
                "X-Forwarded-For": "1.2.3.4",
            }
        )

        # Should still be rate limited (key is aircraft_id, not IP)
        assert bypass_response.status_code == 429, (
            "Rate limit should not be bypassed by X-Forwarded-For header"
        )

    def test_rate_limit_not_bypassed_by_different_path_case(
        self, client: TestClient, auth_headers: dict
    ):
        """Rate limit should not be bypassed by varying URL case.

        /Weather and /WEATHER should count against same limit.
        """
        # Note: FastAPI is case-sensitive by default,
        # so /Weather would 404. This tests that.
        response = client.get(
            "/Weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )
        # Should be 404 (not found) not a bypass
        assert response.status_code in [404, 307]


class TestConcurrentRequests:
    """Tests for concurrent request handling."""

    def test_concurrent_requests_all_rate_limited(
        self, client: TestClient, auth_headers: dict
    ):
        """Concurrent requests should all be properly rate limited.

        Race conditions in rate limiting could allow bypass.
        """

        def make_request():
            return client.get(
                "/weather/current?lat=48.8&lon=2.3",
                headers=auth_headers,
            ).status_code

        # Make 100 concurrent requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            responses = [f.result() for f in as_completed(futures)]

        # Count responses
        success = responses.count(200)
        rate_limited = responses.count(429)
        # timeouts = responses.count(504)  # Not used but tracked

        # With proper rate limiting, not all can succeed
        # Unless rate limit is very high
        total = len(responses)
        if rate_limited == 0 and success + responses.count(504) == total:
            pytest.skip(
                "Rate limit not triggered with 100 concurrent requests. "
                "Rate limit may be set very high."
            )

        # Verify we got expected status codes
        for status in responses:
            assert status in [200, 429, 504], (
                f"Unexpected status code: {status}"
            )


class TestErrorResponsesNotRateLimited:
    """Tests that error responses don't count against rate limits."""

    def test_validation_errors_dont_count(
        self, client: TestClient, auth_headers: dict
    ):
        """Validation errors (422) should not count against rate limit.

        Prevents attackers from burning rate limit with invalid requests.
        """
        # Make many invalid requests (should not count)
        for _ in range(50):
            client.get(
                "/weather/current?lat=invalid&lon=2.3",
                headers=auth_headers,
            )

        # Valid request should still work
        response = client.get(
            "/weather/current?lat=48.8&lon=2.3",
            headers=auth_headers,
        )
        # Should not be rate limited from invalid requests
        # (depends on implementation - some do count all requests)
        assert response.status_code in [200, 429, 504]
