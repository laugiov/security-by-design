"""Tests for Weather Service."""

from fastapi.testclient import TestClient

from weather.fixtures import get_weather_fixtures
from weather.main import app

client = TestClient(app)


class TestWeatherHealth:
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        """Health check should return 200 with status healthy."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "weather"

    def test_root_returns_service_info(self):
        """Root endpoint should return service information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "weather"
        assert "version" in data
        assert data["status"] == "running"
        assert "mode" in data


class TestWeatherEndpoint:
    """Test weather data endpoint."""

    def test_get_weather_requires_lat_lon(self):
        """GET /v1/weather should require lat and lon parameters."""
        # Missing both parameters
        response = client.get("/v1/weather")
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data

        # Missing lon
        response = client.get("/v1/weather?lat=48.87")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Missing lat
        response = client.get("/v1/weather?lon=2.33")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_get_weather_with_valid_coordinates(self):
        """GET /v1/weather should return weather data with valid coordinates."""
        response = client.get("/v1/weather?lat=48.87&lon=2.33")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "location" in data
        assert "current" in data

        # Check location data
        location = data["location"]
        assert "name" in location
        assert "region" in location
        assert "country" in location
        assert "lat" in location
        assert "lon" in location
        assert "tz_id" in location
        assert "localtime_epoch" in location
        assert "localtime" in location

        # Check current weather data
        current = data["current"]
        assert "temp_c" in current
        assert "temp_f" in current
        assert "condition" in current
        assert "wind_kph" in current
        assert "humidity" in current

    def test_get_weather_always_returns_paris(self):
        """In demo mode, should always return Paris weather data."""
        # Test with Paris coordinates
        response1 = client.get("/v1/weather?lat=48.87&lon=2.33")
        data1 = response1.json()

        # Test with New York coordinates
        response2 = client.get("/v1/weather?lat=40.71&lon=-74.01")
        data2 = response2.json()

        # Both should return Paris
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert data1["location"]["name"] == "Paris"
        assert data2["location"]["name"] == "Paris"

        # Should return identical data
        assert data1 == data2

    def test_get_weather_with_lang_parameter(self):
        """GET /v1/weather should accept optional lang parameter."""
        response = client.get("/v1/weather?lat=48.87&lon=2.33&lang=fr")

        assert response.status_code == 200
        data = response.json()
        assert "location" in data
        assert "current" in data

    def test_get_weather_validates_latitude_range(self):
        """Latitude must be between -90 and 90."""
        # Latitude too high
        response = client.get("/v1/weather?lat=100&lon=2.33")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Latitude too low
        response = client.get("/v1/weather?lat=-100&lon=2.33")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Valid edge cases
        response = client.get("/v1/weather?lat=90&lon=2.33")
        assert response.status_code == 200

        response = client.get("/v1/weather?lat=-90&lon=2.33")
        assert response.status_code == 200

    def test_get_weather_validates_longitude_range(self):
        """Longitude must be between -180 and 180."""
        # Longitude too high
        response = client.get("/v1/weather?lat=48.87&lon=200")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Longitude too low
        response = client.get("/v1/weather?lat=48.87&lon=-200")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Valid edge cases
        response = client.get("/v1/weather?lat=48.87&lon=180")
        assert response.status_code == 200

        response = client.get("/v1/weather?lat=48.87&lon=-180")
        assert response.status_code == 200

    def test_get_weather_validates_lang_format(self):
        """Lang parameter must be 2 characters (ISO 639-1)."""
        # Too short
        response = client.get("/v1/weather?lat=48.87&lon=2.33&lang=f")
        assert response.status_code == 422

        # Too long
        response = client.get("/v1/weather?lat=48.87&lon=2.33&lang=fra")
        assert response.status_code == 422

        # Valid 2-character codes
        response = client.get("/v1/weather?lat=48.87&lon=2.33&lang=fr")
        assert response.status_code == 200

        response = client.get("/v1/weather?lat=48.87&lon=2.33&lang=en")
        assert response.status_code == 200

    def test_get_weather_returns_complete_data_structure(self):
        """Weather response should contain all expected fields."""
        response = client.get("/v1/weather?lat=48.87&lon=2.33")

        assert response.status_code == 200
        data = response.json()

        # Location fields
        location = data["location"]
        assert location["name"] == "Paris"
        assert location["region"] == "Ile-de-France"
        assert location["country"] == "France"
        assert isinstance(location["lat"], (int, float))
        assert isinstance(location["lon"], (int, float))
        assert isinstance(location["tz_id"], str)
        assert isinstance(location["localtime_epoch"], int)
        assert isinstance(location["localtime"], str)

        # Current weather fields
        current = data["current"]
        assert isinstance(current["temp_c"], (int, float))
        assert isinstance(current["temp_f"], (int, float))
        assert isinstance(current["is_day"], int)
        assert "text" in current["condition"]
        assert "icon" in current["condition"]
        assert "code" in current["condition"]
        assert isinstance(current["wind_mph"], (int, float))
        assert isinstance(current["wind_kph"], (int, float))
        assert isinstance(current["humidity"], (int, float))
        assert isinstance(current["cloud"], (int, float))
        assert isinstance(current["uv"], int)

        # Air quality (optional but present in fixtures)
        if "air_quality" in current:
            air_quality = current["air_quality"]
            assert "us-epa-index" in air_quality
            assert "gb-defra-index" in air_quality


class TestWeatherFixtures:
    """Test weather fixtures function."""

    def test_get_weather_fixtures_returns_dict(self):
        """Fixtures function should return a dictionary."""
        data = get_weather_fixtures(48.87, 2.33)

        assert isinstance(data, dict)
        assert "location" in data
        assert "current" in data

    def test_get_weather_fixtures_paris_data(self):
        """Fixtures should contain valid Paris weather data."""
        data = get_weather_fixtures(48.87, 2.33)

        assert data["location"]["name"] == "Paris"
        assert data["location"]["country"] == "France"
        assert data["location"]["tz_id"] == "Europe/Paris"

        # Verify current weather has required fields
        current = data["current"]
        assert "temp_c" in current
        assert "temp_f" in current
        assert "condition" in current
        assert "wind_kph" in current
        assert "humidity" in current

    def test_get_weather_fixtures_ignores_coordinates(self):
        """In demo mode, fixtures should always return Paris regardless of coordinates."""
        paris = get_weather_fixtures(48.87, 2.33)
        newyork = get_weather_fixtures(40.71, -74.01)
        tokyo = get_weather_fixtures(35.69, 139.69)

        # All should return Paris
        assert paris["location"]["name"] == "Paris"
        assert newyork["location"]["name"] == "Paris"
        assert tokyo["location"]["name"] == "Paris"

        # All should be identical
        assert paris == newyork == tokyo
