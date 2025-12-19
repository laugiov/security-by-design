"""Schémas Pydantic pour le service de télémétrie."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------- Sous-modèles pour metrics ----------


class TirePressure(BaseModel):
    """Pression des pneus en kPa par roue."""

    model_config = ConfigDict(extra="forbid")

    front_left: float | None = Field(None, description="Pression pneu avant gauche")
    front_right: float | None = Field(None, description="Pression pneu avant droit")
    rear_left: float | None = Field(None, description="Pression pneu arrière gauche")
    rear_right: float | None = Field(None, description="Pression pneu arrière droit")


class GpsInfo(BaseModel):
    """Informations GPS (position + mouvement)."""

    model_config = ConfigDict(extra="forbid")

    lat: float | None = Field(None, description="Latitude")
    lon: float | None = Field(None, description="Longitude")
    heading: float | None = Field(None, description="Cap en degrés")
    altitude: float | None = Field(None, description="Altitude en mètres")
    speed_over_ground: float | None = Field(None, description="Vitesse sol en km/h")


class TransmissionInfo(BaseModel):
    """Infos de boîte de vitesse."""

    model_config = ConfigDict(extra="forbid")

    gear: int | None = Field(None, description="Rapport engagé")
    mode: str | None = Field(
        None,
        description="Mode de conduite (eco, normal, sport, manual)",
    )


class LightsStatus(BaseModel):
    """État des feux du véhicule."""

    model_config = ConfigDict(extra="forbid")

    headlights: bool | None = Field(None, description="Phares allumés")
    brake_lights: bool | None = Field(None, description="Feux stop")
    turn_signal_left: bool | None = Field(None, description="Clignotant gauche")
    turn_signal_right: bool | None = Field(None, description="Clignotant droit")


class ClimateControl(BaseModel):
    """État de la climatisation et chauffage."""

    model_config = ConfigDict(extra="forbid")

    temperature_setting: float | None = Field(None, description="Température réglée")
    fan_speed: int | None = Field(None, description="Vitesse du ventilateur")
    ac_on: bool | None = Field(None, description="AC activée")
    recirculation_mode: bool | None = Field(None, description="Mode recyclage d'air activé")


class SeatbeltStatus(BaseModel):
    """Bouclage des ceintures par siège."""

    model_config = ConfigDict(extra="forbid")

    driver: bool | None = Field(None, description="Ceinture conducteur bouclée")
    passenger_front: bool | None = Field(None, description="Ceinture passager avant")
    rear_left: bool | None = Field(None, description="Ceinture arrière gauche")
    rear_center: bool | None = Field(None, description="Ceinture arrière centrale")
    rear_right: bool | None = Field(None, description="Ceinture arrière droite")


class Metrics(BaseModel):
    """Ensemble des métriques télémétriques (champ metrics de l'OpenAPI)."""

    model_config = ConfigDict(extra="forbid")

    speed: float | None = Field(None, description="Vitesse en km/h")
    fuel_level: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Niveau de carburant en %",
    )
    engine_temp: float | None = Field(None, description="Température moteur en °C")
    tire_pressure: TirePressure | None = Field(None, description="Pression des pneus")
    oil_level: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Niveau d'huile en %",
    )
    outside_temp: float | None = Field(None, description="Température extérieure en °C")
    brake_status: str | None = Field(
        None,
        description="État du système de freinage (ok, worn, malfunction)",
    )
    battery_level: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Niveau de batterie en %",
    )
    gps: GpsInfo | None = Field(None, description="Informations de navigation GPS")
    airbag_status: str | None = Field(
        None,
        description="État du système d'airbag (armed, deployed, fault)",
    )
    transmission: TransmissionInfo | None = Field(None, description="Informations transmission")
    lights_status: LightsStatus | None = Field(None, description="État des feux")
    climate_control: ClimateControl | None = Field(None, description="Climatisation / chauffage")
    seatbelt_status: SeatbeltStatus | None = Field(None, description="Bouclage des ceintures")


# ---------- Modèles principaux ----------


class TelemetryEvent(BaseModel):
    """Événement de télémétrie (contrat API /telemetry)."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(
        ...,
        description="Identifiant unique de l'événement (UUID)",
    )
    vehicle_id: UUID = Field(
        ...,
        description="Identifiant véhicule (UUID)",
    )
    ts: datetime = Field(
        ...,
        description="Timestamp de l'événement (ISO 8601 UTC)",
    )
    metrics: Metrics = Field(
        ...,
        description="Ensemble des métriques temps réel",
    )


class TelemetryIngestResponse(BaseModel):
    """Réponse pour POST /telemetry (201 et 200)."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(
        ...,
        description="created ou duplicate",
        examples=["created", "duplicate"],
    )
    event_id: UUID = Field(
        ...,
        description="Identifiant de l'événement concerné",
    )


class HealthCheckResponse(BaseModel):
    """Réponse de /health."""

    status: str = Field(..., description="Statut du service")
    service: str = Field(..., description="Nom du service")


class Error(BaseModel):
    """Modèle d'erreur simple (aligné sur Error commun côté gateway)."""

    code: str = Field(..., description="Code d'erreur applicatif")
    message: str = Field(..., description="Message d'erreur lisible")
