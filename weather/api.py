"""API routes for Weather Service."""

from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from weather.config import settings
from weather.fixtures import get_weather_fixtures
from weather.schemas import WeatherData

router = APIRouter()


async def _fetch_weather_from_api(lat: float, lon: float, lang: Optional[str] = None) -> dict:
    """Fetch weather data from WeatherAPI.com.

    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate
        lang: Language code (optional)

    Returns:
        Weather data dictionary

    Raises:
        HTTPException: If API key is missing or API request fails
    """
    if not settings.weather_api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "WEATHER_API_KEY not configured. "
                "Set it in environment variables or enable demo_mode."
            ),
        )

    # Build query coordinates
    query = f"{lat},{lon}"

    # Build request parameters
    params = {
        "key": settings.weather_api_key,
        "q": query,
        "aqi": "yes",  # Include air quality data
    }

    if lang:
        params["lang"] = lang

    # Call WeatherAPI.com
    url = f"{settings.weather_api_url}/current.json"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Weather API error: {e.response.text}",
            ) from e
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, detail=f"Failed to connect to weather API: {str(e)}"
            ) from e


@router.get("/v1/weather", response_model=WeatherData)
async def get_weather(
    lat: float = Query(
        ...,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees (rounded to 4 decimals for privacy)",
        examples=[48.87, 40.71],
    ),
    lon: float = Query(
        ...,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees (rounded to 4 decimals for privacy)",
        examples=[2.33, -74.01],
    ),
    lang: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="ISO 639-1 language code (2 letters). Examples: 'en', 'fr', 'es'",
        examples=["fr", "en"],
    ),
) -> WeatherData:
    """Get current weather data for a location.

    In demo mode: Returns static fixtures for Paris.
    In production mode: Calls WeatherAPI.com with WEATHER_API_KEY.

    Args:
        lat: Latitude coordinate (-90 to 90)
        lon: Longitude coordinate (-180 to 180)
        lang: Language code for textual fields (optional)

    Returns:
        WeatherData with current weather conditions

    Raises:
        HTTPException: If production mode is enabled but API key is missing,
                       or if the external API call fails
    """
    if settings.demo_mode:
        # Demo mode: return static fixtures
        weather_data = get_weather_fixtures(lat, lon)
    else:
        # Production mode: call real weather API
        weather_data = await _fetch_weather_from_api(lat, lon, lang)

    return WeatherData(**weather_data)
