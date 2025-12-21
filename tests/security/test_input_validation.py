"""
Tests for input validation (Defense in Depth).

This module tests for:
- Boundary condition validation
- Type validation
- Size limits
- Format validation
- Malformed input handling

Security by Design: All input must be validated before processing.
Never trust user input.
"""

from fastapi.testclient import TestClient


class TestCoordinateBoundaries:
    """Coordinate input boundary tests for weather endpoint."""

    def test_latitude_must_be_within_range(self, client: TestClient, auth_headers: dict):
        """Latitude must be between -90 and 90 degrees."""
        invalid_latitudes = [
            (-91, "Below minimum"),
            (91, "Above maximum"),
            (-180, "Far below minimum"),
            (180, "Far above maximum"),
            (-1000, "Extreme negative"),
            (1000, "Extreme positive"),
        ]

        for lat, description in invalid_latitudes:
            response = client.get(
                f"/weather/current?lat={lat}&lon=2.3",
                headers=auth_headers,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [
                400,
                422,
            ], f"Latitude {lat} ({description}) should be rejected"

    def test_latitude_edge_cases(self, client: TestClient, auth_headers: dict):
        """Latitude edge cases at exactly -90 and 90 should be valid."""
        valid_latitudes = [-90, 90, 0, -45, 45]

        for lat in valid_latitudes:
            response = client.get(
                f"/weather/current?lat={lat}&lon=2.3",
                headers=auth_headers,
            )
            # Should be accepted (200), timeout (504), or service unavailable (502)
            assert response.status_code in [200, 502, 504], f"Latitude {lat} should be valid"

    def test_longitude_must_be_within_range(self, client: TestClient, auth_headers: dict):
        """Longitude must be between -180 and 180 degrees."""
        invalid_longitudes = [
            (-181, "Below minimum"),
            (181, "Above maximum"),
            (-360, "Far below minimum"),
            (360, "Far above maximum"),
        ]

        for lon, description in invalid_longitudes:
            response = client.get(
                f"/weather/current?lat=48.8&lon={lon}",
                headers=auth_headers,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [
                400,
                422,
            ], f"Longitude {lon} ({description}) should be rejected"

    def test_longitude_edge_cases(self, client: TestClient, auth_headers: dict):
        """Longitude edge cases at exactly -180 and 180 should be valid."""
        valid_longitudes = [-180, 180, 0, -90, 90]

        for lon in valid_longitudes:
            response = client.get(
                f"/weather/current?lat=48.8&lon={lon}",
                headers=auth_headers,
            )
            # Should be accepted (200), timeout (504), or service unavailable (502)
            assert response.status_code in [200, 502, 504], f"Longitude {lon} should be valid"


class TestPaginationLimits:
    """Pagination parameter validation tests."""

    def test_page_must_be_positive(self, client: TestClient, auth_headers: dict):
        """Page number must be positive (>= 1)."""
        invalid_pages = [0, -1, -100]

        for page in invalid_pages:
            response = client.get(
                f"/contacts/?person_fields=names&page={page}&size=10",
                headers=auth_headers,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [400, 422], f"Page {page} should be rejected"

    def test_size_has_maximum_limit(self, client: TestClient, auth_headers: dict):
        """Page size should have a reasonable maximum limit."""
        # Try excessively large page sizes
        large_sizes = [101, 1000, 10000, 1000000]

        for size in large_sizes:
            response = client.get(
                f"/contacts/?person_fields=names&page=1&size={size}",
                headers=auth_headers,
            )
            # Should either reject (400/422) or clamp to maximum
            if response.status_code == 200:
                # If accepted, verify returned items are limited
                data = response.json()
                items = data.get("items", [])
                assert len(items) <= 100, f"Size {size} returned too many items"
            else:
                assert response.status_code in [400, 422, 502, 504]

    def test_size_must_be_positive(self, client: TestClient, auth_headers: dict):
        """Page size must be positive (>= 1)."""
        invalid_sizes = [0, -1, -100]

        for size in invalid_sizes:
            response = client.get(
                f"/contacts/?person_fields=names&page=1&size={size}",
                headers=auth_headers,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [400, 422], f"Size {size} should be rejected"


class TestTypeValidation:
    """Input type validation tests."""

    def test_coordinates_must_be_numeric(self, client: TestClient, auth_headers: dict):
        """Coordinates must be valid numbers."""
        non_numeric = ["abc", "null", "undefined", "NaN", "Infinity", ""]

        for value in non_numeric:
            response = client.get(
                f"/weather/current?lat={value}&lon=2.3",
                headers=auth_headers,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [
                400,
                422,
            ], f"Non-numeric lat '{value}' should be rejected"

            response = client.get(
                f"/weather/current?lat=48.8&lon={value}",
                headers=auth_headers,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [
                400,
                422,
            ], f"Non-numeric lon '{value}' should be rejected"

    def test_aircraft_id_must_be_uuid(self, client: TestClient):
        """Aircraft ID must be a valid UUID format."""
        invalid_uuids = [
            "not-a-uuid",
            "12345",
            "",
            "550e8400-e29b-41d4-a716-44665544000",  # One char short
            "550e8400-e29b-41d4-a716-4466554400000",  # One char long
            "gggggggg-gggg-gggg-gggg-gggggggggggg",  # Invalid hex
        ]

        for invalid_id in invalid_uuids:
            response = client.post("/auth/token", json={"aircraft_id": invalid_id})
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [
                400,
                422,
            ], f"Invalid UUID '{invalid_id}' should be rejected"

    def test_valid_uuid_formats(self, client: TestClient):
        """Valid UUID formats should be accepted."""
        valid_uuids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA",  # Uppercase
        ]

        for valid_id in valid_uuids:
            response = client.post("/auth/token", json={"aircraft_id": valid_id})
            # Should be accepted (200) not validation error
            assert response.status_code == 200, f"Valid UUID '{valid_id}' should be accepted"


class TestMalformedInput:
    """Malformed input handling tests."""

    def test_invalid_json_rejected(self, client: TestClient, auth_headers: dict):
        """Invalid JSON should return 400 or 422, not 500."""
        invalid_json_payloads = [
            b"not json at all",
            b"{invalid json}",
            b"{'single': 'quotes'}",
            b"{missing: quotes}",
            b"",
            b"null",
            b"true",
            b"123",
        ]

        for payload in invalid_json_payloads:
            response = client.post(
                "/telemetry/ingest",
                headers={
                    **auth_headers,
                    "Content-Type": "application/json",
                },
                content=payload,
            )
            # API returns 400 for validation errors (custom handler)
            assert response.status_code in [
                400,
                422,
            ], f"Invalid JSON should return 400/422: {payload[:30]}"

    def test_extra_fields_rejected(self, client: TestClient, auth_headers: dict):
        """Extra/unknown fields should be rejected (strict validation).

        SkyLink uses 'extra = forbid' on models.
        """
        response = client.post(
            "/auth/token",
            json={
                "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                "extra_field": "should_be_rejected",
            },
        )
        # Should reject the extra field
        # API returns 400 for validation errors (custom handler)
        assert response.status_code in [400, 422]

    def test_missing_required_fields(self, client: TestClient):
        """Missing required fields should return clear error."""
        response = client.post("/auth/token", json={})  # Missing aircraft_id
        # API returns 400 for validation errors (custom handler)
        assert response.status_code in [400, 422]

        # Verify error response has useful info
        # (custom handler uses "detail" or "error" field)
        error = response.json()
        assert "detail" in error or "error" in error

    def test_null_values_handled(self, client: TestClient, auth_headers: dict):
        """Null values in required fields should be rejected."""
        response = client.post("/auth/token", json={"aircraft_id": None})
        # API returns 400 for validation errors (custom handler)
        assert response.status_code in [400, 422]

    def test_very_long_strings_handled(self, client: TestClient, auth_headers: dict):
        """Very long string inputs should be handled gracefully."""
        # Use a reasonable length that won't exceed URL limits
        long_string = "A" * 5000  # 5KB string (within URL limits)

        response = client.get(
            f"/contacts/?person_fields={long_string}",
            headers=auth_headers,
        )
        # Should either reject or handle gracefully - not crash
        assert response.status_code in [400, 414, 422, 502, 504]


class TestPayloadSizeLimits:
    """Request payload size limit tests."""

    def test_oversized_json_payload_rejected(self, client: TestClient, auth_headers: dict):
        """Oversized JSON payloads should be rejected."""
        # Create a large payload (10MB)
        large_payload = {
            "event_id": "size-test-001",
            "timestamp": "2025-12-21T12:00:00Z",
            "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_type": "position",
            "payload": {"data": "X" * (10 * 1024 * 1024)},  # 10MB of data
        }

        response = client.post(
            "/telemetry/ingest",
            headers=auth_headers,
            json=large_payload,
        )
        # Should be rejected with appropriate status
        # 413 (Payload Too Large) or 400/422 (Unprocessable Entity)
        assert response.status_code in [400, 413, 422]

    def test_deeply_nested_json_handled(self, client: TestClient, auth_headers: dict):
        """Deeply nested JSON should be handled (potential DoS vector)."""
        # Create deeply nested structure
        nested = {"level": 0}
        current = nested
        for i in range(100):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        response = client.post(
            "/telemetry/ingest",
            headers=auth_headers,
            json={
                "event_id": "nest-test-001",
                "timestamp": "2025-12-21T12:00:00Z",
                "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "position",
                "payload": nested,
            },
        )
        # Should either accept or reject - not crash
        assert response.status_code in [200, 400, 409, 422, 502]


class TestSpecialCharacters:
    """Special character handling tests."""

    def test_unicode_in_strings(self, client: TestClient, auth_headers: dict):
        """Unicode characters should be handled properly."""
        unicode_strings = [
            "Hello World",  # ASCII
            "Bonjour le monde",  # French
            "こんにちは世界",  # Japanese
            "مرحبا بالعالم",  # Arabic
            "🌍🛩️",  # Emoji
        ]

        for text in unicode_strings:
            response = client.post(
                "/telemetry/ingest",
                headers=auth_headers,
                json={
                    "event_id": f"unicode-test-{hash(text)}",
                    "timestamp": "2025-12-21T12:00:00Z",
                    "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "position",
                    "payload": {"message": text},
                },
            )
            # Should handle unicode gracefully
            # 400 if IDOR protection rejects mismatched aircraft_id
            assert response.status_code in [200, 400, 403, 409, 502]

    def test_null_bytes_handled(self, client: TestClient, auth_headers: dict):
        """Null bytes in input should be handled safely."""
        # Null bytes can cause issues in some systems
        response = client.post(
            "/telemetry/ingest",
            headers={
                **auth_headers,
                "Content-Type": "application/json",
            },
            content=b'{"event_id": "null\x00byte"}',
        )
        # Should reject or sanitize - not crash
        assert response.status_code in [200, 400, 409, 422, 502]
