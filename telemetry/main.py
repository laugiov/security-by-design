"""Point d'entrée FastAPI pour le Telemetry Service."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from telemetry import __version__
from telemetry.api import router as telemetry_router
from telemetry.config import settings
from telemetry.schemas import HealthCheckResponse

app = FastAPI(
    title="SkyLink Telemetry Service",
    version=__version__,
    description="Internal microservice handling vehicle telemetry ingestion with idempotency.",
)

# Routes principales (auth, telemetry)
app.include_router(telemetry_router)


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["health"],
)
async def health_check() -> HealthCheckResponse:
    """Health check simple aligné avec telemetry.yaml."""
    return HealthCheckResponse(
        status="healthy",
        service=settings.service_name,
    )


@app.get("/", tags=["info"])
async def root() -> JSONResponse:
    """Infos basiques sur le service."""
    return JSONResponse(
        {
            "service": settings.service_name,
            "version": __version__,
            "status": "running",
        }
    )
