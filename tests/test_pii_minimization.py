"""Tests for PII minimization and data protection features.

Tests cover:
- GPS coordinate validation (bounds: lat -90..90, lon -180..180)
- GPS coordinate rounding to 4 decimals for privacy (~11m precision)
- Strict schema validation (extra fields rejected)
- Payload size limit (64KB max)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from pydantic import ValidationError

from skylink.middlewares import MAX_PAYLOAD_SIZE, payload_limit_middleware
from skylink.models.telemetry.telemetry_event import TelemetryEvent
from skylink.models.telemetry.telemetry_event_metrics import TelemetryEventMetrics
from skylink.models.telemetry.telemetry_event_metrics_gps import (
    TelemetryEventMetricsGps,
)


class TestGPSValidation:
    """Tests for GPS coordinate validation and privacy rounding."""

    def test_valid_gps_coordinates(self):
        """Valid GPS coordinates should be accepted."""
        gps = TelemetryEventMetricsGps(lat=48.8566, lon=2.3522)
        assert gps.lat == 48.8566
        assert gps.lon == 2.3522

    def test_gps_lat_at_bounds(self):
        """GPS latitude at boundary values should be accepted."""
        # Max latitude
        gps_max = TelemetryEventMetricsGps(lat=90.0, lon=0.0)
        assert gps_max.lat == 90.0

        # Min latitude
        gps_min = TelemetryEventMetricsGps(lat=-90.0, lon=0.0)
        assert gps_min.lat == -90.0

    def test_gps_lon_at_bounds(self):
        """GPS longitude at boundary values should be accepted."""
        # Max longitude
        gps_max = TelemetryEventMetricsGps(lat=0.0, lon=180.0)
        assert gps_max.lon == 180.0

        # Min longitude
        gps_min = TelemetryEventMetricsGps(lat=0.0, lon=-180.0)
        assert gps_min.lon == -180.0

    def test_gps_lat_out_of_bounds_positive(self):
        """Latitude > 90 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryEventMetricsGps(lat=90.1, lon=0.0)
        assert "lat must be between -90 and 90" in str(exc_info.value)

    def test_gps_lat_out_of_bounds_negative(self):
        """Latitude < -90 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryEventMetricsGps(lat=-90.1, lon=0.0)
        assert "lat must be between -90 and 90" in str(exc_info.value)

    def test_gps_lon_out_of_bounds_positive(self):
        """Longitude > 180 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryEventMetricsGps(lat=0.0, lon=180.1)
        assert "lon must be between -180 and 180" in str(exc_info.value)

    def test_gps_lon_out_of_bounds_negative(self):
        """Longitude < -180 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryEventMetricsGps(lat=0.0, lon=-180.1)
        assert "lon must be between -180 and 180" in str(exc_info.value)

    def test_gps_rounds_to_4_decimals(self):
        """GPS coordinates should be rounded to 4 decimals for privacy."""
        # 6 decimals in, 4 decimals out
        gps = TelemetryEventMetricsGps(lat=48.856614, lon=2.352222)
        assert gps.lat == 48.8566
        assert gps.lon == 2.3522

    def test_gps_rounds_correctly_up(self):
        """GPS rounding should follow standard rounding rules (up)."""
        gps = TelemetryEventMetricsGps(lat=48.85665, lon=2.35225)
        # 48.85665 rounds to 48.8567 (5 rounds up)
        # 2.35225 rounds to 2.3523 (5 rounds up)
        assert gps.lat == 48.8567
        assert gps.lon == 2.3523

    def test_gps_rounds_correctly_down(self):
        """GPS rounding should follow standard rounding rules (down)."""
        gps = TelemetryEventMetricsGps(lat=48.85664, lon=2.35224)
        assert gps.lat == 48.8566
        assert gps.lon == 2.3522

    def test_gps_none_values_allowed(self):
        """GPS with None values should be allowed."""
        gps = TelemetryEventMetricsGps(lat=None, lon=None)
        assert gps.lat is None
        assert gps.lon is None

    def test_gps_partial_none_allowed(self):
        """GPS with partial None values should be allowed."""
        gps = TelemetryEventMetricsGps(lat=48.8566, lon=None)
        assert gps.lat == 48.8566
        assert gps.lon is None


class TestStrictSchemaValidation:
    """Tests for strict schema validation (extra fields rejected)."""

    def test_gps_rejects_extra_fields(self):
        """GPS model should reject extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryEventMetricsGps(
                lat=48.8566,
                lon=2.3522,
                extra_field="not allowed",
            )
        assert "extra" in str(exc_info.value).lower()

    def test_telemetry_metrics_rejects_extra_fields(self):
        """TelemetryEventMetrics should reject extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryEventMetrics(
                speed=100.0,
                unknown_metric="not allowed",
            )
        assert "extra" in str(exc_info.value).lower()

    def test_telemetry_event_rejects_extra_fields(self):
        """TelemetryEvent should reject extra fields."""
        from datetime import datetime, timezone
        from uuid import uuid4

        with pytest.raises(ValidationError) as exc_info:
            TelemetryEvent(
                event_id=uuid4(),
                aircraft_id=uuid4(),
                ts=datetime.now(timezone.utc),
                metrics=TelemetryEventMetrics(),
                hacker_field="attempt",
            )
        assert "extra" in str(exc_info.value).lower()


class TestPayloadLimitMiddleware:
    """Tests for the 64KB payload limit middleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.headers = {}
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next that returns a success response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        return AsyncMock(return_value=mock_response)

    @pytest.mark.asyncio
    async def test_no_content_length_passes(self, mock_request, mock_call_next):
        """Requests without Content-Length should pass through."""
        mock_request.headers = {}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_small_payload_passes(self, mock_request, mock_call_next):
        """Requests with small payloads should pass through."""
        mock_request.headers = {"content-length": "1024"}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_exact_limit_passes(self, mock_request, mock_call_next):
        """Requests at exactly the limit should pass through."""
        mock_request.headers = {"content-length": str(MAX_PAYLOAD_SIZE)}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_over_limit_rejected(self, mock_request, mock_call_next):
        """Requests exceeding the limit should be rejected with 413."""
        mock_request.headers = {"content-length": str(MAX_PAYLOAD_SIZE + 1)}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        # Should not call next handler
        mock_call_next.assert_not_called()
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_over_limit_error_message(self, mock_request, mock_call_next):
        """Error response should include proper error format."""
        mock_request.headers = {"content-length": str(MAX_PAYLOAD_SIZE + 1)}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        assert response.status_code == 413
        # Check response body structure
        import json

        body = json.loads(response.body)
        assert "error" in body
        assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert "65536" in body["error"]["message"]  # Contains the size limit in bytes

    @pytest.mark.asyncio
    async def test_way_over_limit_rejected(self, mock_request, mock_call_next):
        """Very large payloads should be rejected."""
        # 1 MB payload
        mock_request.headers = {"content-length": str(1024 * 1024)}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        mock_call_next.assert_not_called()
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_invalid_content_length_passes(self, mock_request, mock_call_next):
        """Invalid Content-Length values should pass through."""
        mock_request.headers = {"content-length": "not-a-number"}

        response = await payload_limit_middleware(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response.status_code == 200


class TestMaxPayloadConstant:
    """Tests for the MAX_PAYLOAD_SIZE constant."""

    def test_max_payload_is_64kb(self):
        """MAX_PAYLOAD_SIZE should be exactly 64KB."""
        assert MAX_PAYLOAD_SIZE == 64 * 1024
        assert MAX_PAYLOAD_SIZE == 65536


class TestGPSPrivacyPrecision:
    """Tests for GPS privacy through precision reduction.

    4 decimal places gives ~11.1m precision which is sufficient for:
    - Neighborhood-level location
    - Traffic and weather services
    - General navigation

    But NOT precise enough for:
    - Exact parking spot
    - Individual building identification
    - Tracking within a property
    """

    def test_precision_reduces_accuracy(self):
        """Demonstrate that 4 decimals reduces tracking precision."""
        # Full precision coordinate (could pinpoint a specific location)
        full_lat = 48.85661234
        full_lon = 2.35221234

        gps = TelemetryEventMetricsGps(lat=full_lat, lon=full_lon)

        # After rounding, precision is reduced
        assert gps.lat == 48.8566
        assert gps.lon == 2.3522

        # The difference shows loss of precision
        lat_diff = abs(full_lat - gps.lat)
        lon_diff = abs(full_lon - gps.lon)

        # Differences should be > 0 (precision was lost)
        assert lat_diff > 0
        assert lon_diff > 0

    def test_nearby_coords_become_same(self):
        """Very close coordinates should become identical after rounding."""
        # Two spots ~5m apart
        gps1 = TelemetryEventMetricsGps(lat=48.85661234, lon=2.35221234)
        gps2 = TelemetryEventMetricsGps(lat=48.85662345, lon=2.35222345)

        # After rounding, they are the same
        assert gps1.lat == gps2.lat
        assert gps1.lon == gps2.lon
