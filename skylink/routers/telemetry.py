"""Telemetry router - Gateway proxy to Telemetry microservice."""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from httpx import AsyncClient

from skylink.auth import verify_jwt

# Import telemetry models
from skylink.models.telemetry.telemetry_event import TelemetryEvent
from skylink.models.telemetry.telemetry_health_check200_response import (
    TelemetryHealthCheck200Response,
)
from skylink.models.telemetry.telemetry_obtain_token200_response import (
    TelemetryObtainToken200Response,
)
from skylink.models.telemetry.telemetry_obtain_token_request import TelemetryObtainTokenRequest

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
)

# Telemetry service URL (from config or env)
TELEMETRY_SERVICE_URL = "http://telemetry:8001"
PROXY_TIMEOUT = 5.0  # 5 seconds timeout for telemetry ingestion


@router.get("/health", response_model=TelemetryHealthCheck200Response)
async def telemetry_health_check():
    """
    Health check for Telemetry service.

    Gateway endpoint that proxies to the Telemetry microservice.
    """
    # TODO: Implement proxy call to telemetry microservice
    # For now, return mock response
    return {"status": "healthy", "service": "telemetry", "version": "0.1.0"}


@router.post("/token", response_model=TelemetryObtainToken200Response)
async def obtain_telemetry_token(request: TelemetryObtainTokenRequest):
    """
    Obtain authentication token for Telemetry service.

    Gateway endpoint that proxies to the Telemetry microservice.
    """
    # TODO: Implement proxy call to telemetry microservice
    # For now, return mock response
    return {"access_token": "mock_token", "token_type": "Bearer", "expires_in": 3600}


@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_telemetry(
    event: TelemetryEvent,
    response: Response,
    claims: dict = Depends(verify_jwt),
    authorization: str = Header(..., description="Bearer JWT token"),
):
    """Ingest vehicle telemetry data.

    Gateway endpoint that proxies to the Telemetry microservice.
    Requires JWT authentication.

    Args:
        event: Telemetry event data from vehicle
        response: FastAPI response object to set status code
        claims: JWT claims from verify_jwt dependency
        authorization: Original Authorization header to forward

    Returns:
        Response from Telemetry service (201 created, 200 duplicate, 409 conflict)

    Raises:
        HTTPException: 504 on timeout, 502 on service unavailable
    """
    try:
        async with AsyncClient(timeout=PROXY_TIMEOUT) as client:
            # Forward the original Authorization header to the telemetry service
            upstream_response = await client.post(
                f"{TELEMETRY_SERVICE_URL}/telemetry",
                json=event.model_dump(mode="json"),
                headers={"Authorization": authorization},
            )

            # Propagate the status code from the telemetry service
            response.status_code = upstream_response.status_code
            return upstream_response.json()

    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Telemetry service timeout",
        ) from e

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Telemetry service unavailable: {str(e)}",
        ) from e


@router.get("/events/{vehicle_id}")
async def get_vehicle_telemetry(
    vehicle_id: str, limit: Optional[int] = 100, offset: Optional[int] = 0
):
    """
    Get telemetry events for a specific vehicle.

    Gateway endpoint that proxies to the Telemetry microservice.

    Args:
        vehicle_id: Vehicle identifier
        limit: Maximum number of events to return
        offset: Offset for pagination
    """
    # TODO: Implement proxy call to telemetry microservice
    # For now, return mock response
    raise HTTPException(status_code=501, detail="Telemetry retrieval not yet implemented")
