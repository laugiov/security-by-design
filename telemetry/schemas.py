"""Pydantic schemas for the telemetry service."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------- Sub-models for metrics ----------


class EngineStatus(BaseModel):
    """Tire pressure in kPa per wheel."""

    model_config = ConfigDict(extra="forbid")

    front_left: float | None = Field(None, description="Front left tire pressure")
    front_right: float | None = Field(None, description="Front right tire pressure")
    rear_left: float | None = Field(None, description="Rear left tire pressure")
    rear_right: float | None = Field(None, description="Rear right tire pressure")


class GpsInfo(BaseModel):
    """GPS information (position + movement)."""

    model_config = ConfigDict(extra="forbid")

    lat: float | None = Field(None, description="Latitude")
    lon: float | None = Field(None, description="Longitude")
    heading: float | None = Field(None, description="Heading in degrees")
    altitude: float | None = Field(None, description="Altitude in meters")
    speed_over_ground: float | None = Field(None, description="Ground speed in km/h")


class FlightControlsInfo(BaseModel):
    """Gearbox information."""

    model_config = ConfigDict(extra="forbid")

    gear: int | None = Field(None, description="Engaged gear")
    mode: str | None = Field(
        None,
        description="Driving mode (eco, normal, sport, manual)",
    )


class LightsStatus(BaseModel):
    """Aircraft lights status."""

    model_config = ConfigDict(extra="forbid")

    headlights: bool | None = Field(None, description="Headlights on")
    brake_lights: bool | None = Field(None, description="Brake lights")
    turn_signal_left: bool | None = Field(None, description="Left turn signal")
    turn_signal_right: bool | None = Field(None, description="Right turn signal")


class ClimateControl(BaseModel):
    """Air conditioning and heating status."""

    model_config = ConfigDict(extra="forbid")

    temperature_setting: float | None = Field(None, description="Set temperature")
    fan_speed: int | None = Field(None, description="Fan speed")
    ac_on: bool | None = Field(None, description="AC enabled")
    recirculation_mode: bool | None = Field(None, description="Air recirculation mode enabled")


class CabinPressure(BaseModel):
    """Seatbelt fastening status by seat."""

    model_config = ConfigDict(extra="forbid")

    driver: bool | None = Field(None, description="Driver seatbelt fastened")
    passenger_front: bool | None = Field(None, description="Front passenger seatbelt")
    rear_left: bool | None = Field(None, description="Rear left seatbelt")
    rear_center: bool | None = Field(None, description="Rear center seatbelt")
    rear_right: bool | None = Field(None, description="Rear right seatbelt")


class Metrics(BaseModel):
    """Complete set of telemetry metrics (metrics field from OpenAPI)."""

    model_config = ConfigDict(extra="forbid")

    speed: float | None = Field(None, description="Speed in km/h")
    altitude: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Altitude in feet",
    )
    engine_temp: float | None = Field(None, description="Engine temperature in °C")
    engine_status: EngineStatus | None = Field(None, description="Tire pressure")
    oil_level: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Oil level in %",
    )
    outside_temp: float | None = Field(None, description="Outside temperature in °C")
    brake_status: str | None = Field(
        None,
        description="Brake system status (ok, worn, malfunction)",
    )
    battery_level: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Battery level in %",
    )
    gps: GpsInfo | None = Field(None, description="GPS navigation information")
    airbag_status: str | None = Field(
        None,
        description="Airbag system status (armed, deployed, fault)",
    )
    flight_controls: FlightControlsInfo | None = Field(
        None, description="Flight controls information"
    )
    lights_status: LightsStatus | None = Field(None, description="Lights status")
    climate_control: ClimateControl | None = Field(None, description="Air conditioning / heating")
    cabin_pressure: CabinPressure | None = Field(None, description="Seatbelt fastening")


# ---------- Main models ----------


class TelemetryEvent(BaseModel):
    """Telemetry event (API contract /telemetry)."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(
        ...,
        description="Unique event identifier (UUID)",
    )
    aircraft_id: UUID = Field(
        ...,
        description="Aircraft identifier (UUID)",
    )
    ts: datetime = Field(
        ...,
        description="Event timestamp (ISO 8601 UTC)",
    )
    metrics: Metrics = Field(
        ...,
        description="Complete set of real-time metrics",
    )


class TelemetryIngestResponse(BaseModel):
    """Response for POST /telemetry (201 and 200)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        ...,
        description="created or duplicate",
        examples=["created", "duplicate"],
    )
    event_id: UUID = Field(
        ...,
        description="Identifier of the concerned event",
    )


class HealthCheckResponse(BaseModel):
    """Response for /health."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")


class Error(BaseModel):
    """Simple error model (aligned with common Error on gateway side)."""

    code: str = Field(..., description="Application error code")
    message: str = Field(..., description="Human-readable error message")
