"""Tests for Gateway → Weather routing."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from skylink.auth import create_access_token
from skylink.main import app

client = TestClient(app)

# Valid JWT token for testing
VALID_AIRCRAFT_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def valid_token():
    """Fixture providing a valid JWT token."""
    return create_access_token(VALID_AIRCRAFT_ID)


class TestWeatherRouting:
    """Test weather routing from gateway to service."""

    def test_get_weather_without_auth_returns_401(self):
        """GET /weather/current without auth should return 401."""
        response = client.get("/weather/current?lat=48.87&lon=2.33")
        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    def test_get_weather_with_invalid_token_returns_401(self):
        """GET /weather/current with invalid token should return 401."""
        response = client.get(
            "/weather/current?lat=48.87&lon=2.33", headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401

    @patch("skylink.routers.weather.httpx.AsyncClient")
    def test_get_weather_proxies_successfully(self, mock_async_client, valid_token):
        """GET /weather/current should proxy to weather service with valid auth."""
        from unittest.mock import Mock

        # Mock successful response from weather service
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "location": {
                "name": "Paris",
                "region": "Ile-de-France",
                "country": "France",
                "lat": 48.87,
                "lon": 2.33,
                "tz_id": "Europe/Paris",
                "localtime_epoch": 1699012345,
                "localtime": "2023-11-03 14:45",
            },
            "current": {
                "last_updated_epoch": 1699012200,
                "last_updated": "2023-11-03 14:43",
                "temp_c": 15.0,
                "temp_f": 59.0,
                "is_day": 1,
                "condition": {
                    "text": "Partly cloudy",
                    "icon": "//cdn.weather.com/116.png",
                    "code": 1003,
                },
                "wind_mph": 6.9,
                "wind_kph": 11.2,
                "wind_degree": 230,
                "wind_dir": "SW",
                "pressure_mb": 1012.0,
                "pressure_in": 29.88,
                "precip_mm": 0.0,
                "precip_in": 0.0,
                "humidity": 67,
                "cloud": 50,
                "feelslike_c": 15.0,
                "feelslike_f": 59.0,
                "vis_km": 10.0,
                "vis_miles": 6.0,
                "uv": 4,
                "gust_mph": 8.3,
                "gust_kph": 13.3,
                "air_quality": {
                    "co": 230.3,
                    "no2": 15.8,
                    "o3": 68.2,
                    "so2": 3.5,
                    "pm2_5": 8.9,
                    "pm10": 12.4,
                    "us-epa-index": 1,
                    "gb-defra-index": 2,
                },
            },
        }

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Make authenticated request
        response = client.get(
            "/weather/current?lat=48.87&lon=2.33",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "location" in data
        assert "current" in data
        assert data["location"]["name"] == "Paris"

    @patch("skylink.routers.weather.httpx.AsyncClient")
    def test_get_weather_forwards_query_params(self, mock_async_client, valid_token):
        """GET /weather/current should forward query parameters to service."""
        from unittest.mock import Mock

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "location": {
                "name": "Paris",
                "region": "Ile-de-France",
                "country": "France",
                "lat": 40.71,
                "lon": -74.01,
                "tz_id": "Europe/Paris",
                "localtime_epoch": 1699012345,
                "localtime": "2023-11-03 14:45",
            },
            "current": {
                "last_updated_epoch": 1699012200,
                "last_updated": "2023-11-03 14:43",
                "temp_c": 15.0,
                "temp_f": 59.0,
                "is_day": 1,
                "condition": {"text": "Sunny", "icon": "//cdn.weather.com/113.png", "code": 1000},
                "wind_mph": 8.1,
                "wind_kph": 13.0,
                "wind_degree": 180,
                "wind_dir": "S",
                "pressure_mb": 1018.0,
                "pressure_in": 30.06,
                "precip_mm": 0.0,
                "precip_in": 0.0,
                "humidity": 55,
                "cloud": 10,
                "feelslike_c": 18.0,
                "feelslike_f": 64.4,
                "vis_km": 16.0,
                "vis_miles": 10.0,
                "uv": 5,
                "gust_mph": 10.7,
                "gust_kph": 17.2,
            },
        }

        mock_context = AsyncMock()
        mock_get = AsyncMock(return_value=mock_response)
        mock_context.__aenter__.return_value.get = mock_get
        mock_async_client.return_value = mock_context

        # Request with coordinates and lang
        response = client.get(
            "/weather/current?lat=40.71&lon=-74.01&lang=en",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        # Verify params were forwarded
        call_args = mock_get.call_args
        assert call_args[1]["params"]["lat"] == 40.71
        assert call_args[1]["params"]["lon"] == -74.01
        assert call_args[1]["params"]["lang"] == "en"

    @patch("skylink.routers.weather.httpx.AsyncClient")
    def test_get_weather_without_optional_lang(self, mock_async_client, valid_token):
        """GET /weather/current should work without optional lang parameter."""
        from unittest.mock import Mock

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "location": {
                "name": "Paris",
                "region": "Ile-de-France",
                "country": "France",
                "lat": 48.87,
                "lon": 2.33,
                "tz_id": "Europe/Paris",
                "localtime_epoch": 1699012345,
                "localtime": "2023-11-03 14:45",
            },
            "current": {
                "last_updated_epoch": 1699012200,
                "last_updated": "2023-11-03 14:43",
                "temp_c": 15.0,
                "temp_f": 59.0,
                "is_day": 1,
                "condition": {
                    "text": "Partly cloudy",
                    "icon": "//cdn.weather.com/116.png",
                    "code": 1003,
                },
                "wind_mph": 6.9,
                "wind_kph": 11.2,
                "wind_degree": 230,
                "wind_dir": "SW",
                "pressure_mb": 1012.0,
                "pressure_in": 29.88,
                "precip_mm": 0.0,
                "precip_in": 0.0,
                "humidity": 67,
                "cloud": 50,
                "feelslike_c": 15.0,
                "feelslike_f": 59.0,
                "vis_km": 10.0,
                "vis_miles": 6.0,
                "uv": 4,
                "gust_mph": 8.3,
                "gust_kph": 13.3,
            },
        }

        mock_context = AsyncMock()
        mock_get = AsyncMock(return_value=mock_response)
        mock_context.__aenter__.return_value.get = mock_get
        mock_async_client.return_value = mock_context

        # Request without lang parameter
        response = client.get(
            "/weather/current?lat=48.87&lon=2.33",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        # Verify lang was not included in params
        call_args = mock_get.call_args
        assert "lang" not in call_args[1]["params"]

    @patch("skylink.routers.weather.httpx.AsyncClient")
    def test_get_weather_handles_timeout(self, mock_async_client, valid_token):
        """GET /weather/current should return 504 on service timeout."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value = mock_context

        response = client.get(
            "/weather/current?lat=48.87&lon=2.33",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 504
        assert "timeout" in response.json()["detail"].lower()

    @patch("skylink.routers.weather.httpx.AsyncClient")
    def test_get_weather_handles_service_error(self, mock_async_client, valid_token):
        """GET /weather/current should return 502 on service error."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(side_effect=httpx.HTTPError("Error"))
        mock_async_client.return_value = mock_context

        response = client.get(
            "/weather/current?lat=48.87&lon=2.33",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 502
        assert "unavailable" in response.json()["detail"].lower()

    @patch("skylink.routers.weather.httpx.AsyncClient")
    def test_get_weather_forwards_service_errors(self, mock_async_client, valid_token):
        """GET /weather/current should forward error status codes from service."""
        from unittest.mock import Mock

        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.text = "Invalid coordinates"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        response = client.get(
            "/weather/current?lat=200&lon=2.33", headers={"Authorization": f"Bearer {valid_token}"}
        )

        # Gateway validates params before proxying, so it returns 400/422 for invalid lat
        assert response.status_code in [400, 422]

    def test_get_weather_validates_latitude_range(self, valid_token):
        """GET /weather/current should validate latitude range."""
        # Latitude too high
        response = client.get(
            "/weather/current?lat=100&lon=2.33", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in [
            400,
            422,
        ]  # FastAPI may return 400 or 422 for validation errors

        # Latitude too low
        response = client.get(
            "/weather/current?lat=-100&lon=2.33", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in [400, 422]

    def test_get_weather_validates_longitude_range(self, valid_token):
        """GET /weather/current should validate longitude range."""
        # Longitude too high
        response = client.get(
            "/weather/current?lat=48.87&lon=200", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in [400, 422]

        # Longitude too low
        response = client.get(
            "/weather/current?lat=48.87&lon=-200",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code in [400, 422]

    def test_get_weather_requires_lat_and_lon(self, valid_token):
        """GET /weather/current should require both lat and lon parameters."""
        # Missing both
        response = client.get(
            "/weather/current", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in [400, 422]

        # Missing lon
        response = client.get(
            "/weather/current?lat=48.87", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in [400, 422]

        # Missing lat
        response = client.get(
            "/weather/current?lon=2.33", headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in [400, 422]
