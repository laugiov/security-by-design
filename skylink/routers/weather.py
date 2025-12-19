"""Weather router - Gateway proxy to Weather microservice."""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from skylink.auth import verify_jwt
from skylink.models.weather.weather_data import WeatherData
from skylink.rate_limit import RATE_LIMIT_PER_AIRCRAFT, limiter

router = APIRouter(
    prefix="/weather",
    tags=["weather"],
)

# Weather service URL (from config or env)
WEATHER_SERVICE_URL = "http://weather:8002"
PROXY_TIMEOUT = 2.0  # 2 seconds timeout


@router.get("/current", response_model=WeatherData)
@limiter.limit(RATE_LIMIT_PER_AIRCRAFT)
async def get_current_weather(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude coordinate"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude coordinate"),
    lang: Optional[str] = Query(
        None, min_length=2, max_length=2, description="ISO 639-1 language code"
    ),
    token: dict = Depends(verify_jwt),
):
    """Get current weather data for a location (requires JWT authentication).

    This endpoint proxies the request to the internal Weather microservice.
    In MVP demo mode, it returns static Paris weather fixtures.

    Args:
        lat: Latitude coordinate (-90 to 90)
        lon: Longitude coordinate (-180 to 180)
        lang: Language code for textual fields (optional)
        token: JWT token payload (injected by verify_jwt dependency)

    Returns:
        Current weather data including location and conditions

    Raises:
        HTTPException: If weather service is unavailable or returns error
    """
    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            params = {"lat": lat, "lon": lon}
            if lang:
                params["lang"] = lang

            response = await client.get(f"{WEATHER_SERVICE_URL}/v1/weather", params=params)

            # Forward status code from weather service
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Weather service error: {response.text}",
                )

            return response.json()

    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Weather service timeout",
        ) from e

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Weather service unavailable: {str(e)}",
        ) from e
