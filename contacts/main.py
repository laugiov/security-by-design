"""Contacts Service - Main application.

Simplified microservice for MVP demo that returns static contact fixtures.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from contacts import __version__
from contacts.api import router
from contacts.config import settings
from contacts.schemas import HealthCheckResponse

# Create FastAPI app
app = FastAPI(
    title="SkyLink Contacts Service",
    version=__version__,
    description="Contacts microservice with Google People API integration (demo mode)",
)

# Include API router
app.include_router(router, tags=["contacts"])


@app.get("/health", response_model=HealthCheckResponse, tags=["health"])
async def health_check() -> HealthCheckResponse:
    """Health check endpoint.

    Returns:
        HealthCheckResponse with service status
    """
    return HealthCheckResponse(status="healthy", service=settings.service_name)


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint with service info."""
    return JSONResponse(
        {
            "service": settings.service_name,
            "version": __version__,
            "status": "running",
            "mode": "demo" if settings.demo_mode else "production",
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "contacts.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "development",
    )
