"""Static fixtures for demo mode weather data."""

from typing import Union


def get_weather_fixtures(lat: Union[float, int], lon: Union[float, int]) -> dict:
    """Return static demo weather data for Paris.

    In demo mode, always returns Paris weather data regardless of coordinates.

    Args:
        lat: Latitude coordinate (ignored in demo mode)
        lon: Longitude coordinate (ignored in demo mode)

    Returns:
        Weather data dictionary matching WeatherData schema

    Note:
        In production, this would call a real weather API.
        For demo, we always return Paris weather data.
    """
    return {
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
                "icon": "//cdn.weatherapi.com/weather/64x64/day/116.png",
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
