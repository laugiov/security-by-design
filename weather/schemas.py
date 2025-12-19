"""Pydantic schemas for Weather Service (simplified for MVP demo mode)."""

from typing import Optional, Union

from pydantic import BaseModel, Field


class WeatherDataCurrentCondition(BaseModel):
    """Weather condition description."""

    text: str = Field(..., description="Weather condition text (e.g., 'Partly cloudy')")
    icon: str = Field(..., description="Weather condition icon URL")
    code: int = Field(..., description="Weather condition code")


class WeatherDataCurrentAirQuality(BaseModel):
    """Air quality metrics (may be absent if provider disabled)."""

    co: Optional[Union[float, int]] = Field(None, description="Carbon Monoxide (μg/m3)")
    no2: Optional[Union[float, int]] = Field(None, description="Nitrogen dioxide (μg/m3)")
    o3: Optional[Union[float, int]] = Field(None, description="Ozone (μg/m3)")
    so2: Optional[Union[float, int]] = Field(None, description="Sulphur dioxide (μg/m3)")
    pm2_5: Optional[Union[float, int]] = Field(None, description="PM2.5 (μg/m3)")
    pm10: Optional[Union[float, int]] = Field(None, description="PM10 (μg/m3)")
    us_epa_index: Optional[int] = Field(None, alias="us-epa-index", description="US EPA Index")
    gb_defra_index: Optional[int] = Field(
        None, alias="gb-defra-index", description="UK Defra Index"
    )

    model_config = {"populate_by_name": True}


class WeatherDataCurrent(BaseModel):
    """Snapshot of current weather conditions."""

    last_updated_epoch: int = Field(..., description="Last updated time in unix epoch")
    last_updated: str = Field(..., description="Last updated time as string")
    temp_c: Union[float, int] = Field(..., description="Temperature in celsius")
    temp_f: Union[float, int] = Field(..., description="Temperature in fahrenheit")
    is_day: int = Field(..., description="1 = Yes, 0 = No (whether it's day or night)")
    condition: WeatherDataCurrentCondition
    wind_mph: Union[float, int] = Field(..., description="Wind speed in miles per hour")
    wind_kph: Union[float, int] = Field(..., description="Wind speed in kilometers per hour")
    wind_degree: Union[float, int] = Field(..., description="Wind direction in degrees")
    wind_dir: str = Field(..., description="Wind direction as 16 point compass (e.g., NSW)")
    pressure_mb: Union[float, int] = Field(..., description="Pressure in millibars")
    pressure_in: Union[float, int] = Field(..., description="Pressure in inches")
    precip_mm: Union[float, int] = Field(..., description="Precipitation amount in millimeters")
    precip_in: Union[float, int] = Field(..., description="Precipitation amount in inches")
    humidity: Union[float, int] = Field(..., description="Humidity as percentage")
    cloud: Union[float, int] = Field(..., description="Cloud cover as percentage")
    feelslike_c: Union[float, int] = Field(..., description="Feels like temperature in celsius")
    feelslike_f: Union[float, int] = Field(..., description="Feels like temperature in fahrenheit")
    vis_km: Union[float, int] = Field(..., description="Visibility in kilometers")
    vis_miles: Union[float, int] = Field(..., description="Visibility in miles")
    uv: int = Field(..., description="UV Index")
    gust_mph: Union[float, int] = Field(..., description="Wind gust in miles per hour")
    gust_kph: Union[float, int] = Field(..., description="Wind gust in kilometers per hour")
    air_quality: Optional[WeatherDataCurrentAirQuality] = None


class WeatherDataLocation(BaseModel):
    """Location metadata for the requested coordinates."""

    name: str = Field(..., description="Location name")
    region: str = Field(..., description="Region or state")
    country: str = Field(..., description="Country name")
    lat: Union[float, int] = Field(..., description="Latitude in decimal degree")
    lon: Union[float, int] = Field(..., description="Longitude in decimal degree")
    tz_id: str = Field(..., description="Time zone name")
    localtime_epoch: int = Field(..., description="Local time in unix epoch")
    localtime: str = Field(..., description="Local date and time")


class WeatherData(BaseModel):
    """Current weather response.

    Main response model for weather data including location
    and current conditions.
    """

    location: WeatherDataLocation
    current: WeatherDataCurrent

    model_config = {
        "json_schema_extra": {
            "example": {
                "location": {
                    "name": "Paris",
                    "region": "Ile-de-France",
                    "country": "France",
                    "lat": 48.87,
                    "lon": 2.33,
                    "tz_id": "Europe/Paris",
                    "localtime_epoch": 1699012345,
                    "localtime": "2023-11-03 12:45",
                },
                "current": {
                    "last_updated_epoch": 1699012200,
                    "last_updated": "2023-11-03 12:43",
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
        }
    }


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., json_schema_extra={"example": "healthy"})
    service: str = Field(..., json_schema_extra={"example": "weather"})
