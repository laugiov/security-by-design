"""Telemetry service API endpoints."""

import jwt  # PyJWT
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.security import HTTPBearer

from telemetry.config import settings
from telemetry.repository import InMemoryTelemetryRepository
from telemetry.schemas import (
    Error,
    TelemetryEvent,
    TelemetryIngestResponse,
)

router = APIRouter()

# Simple in-memory repository (to be replaced with real DB repo)
repo = InMemoryTelemetryRepository()

# HTTP Bearer security scheme for /telemetry
bearer_scheme = HTTPBearer(auto_error=True)


# ---------- Auth ----------


async def verify_bearer_token(authorization: str | None = Header(default=None)) -> dict:
    """Verify the JWT token signed by the Gateway with the public key.

    - Expects an Authorization: Bearer <token> header
    - Verifies algorithm, audience, exp, etc.
    - Returns claims if everything is OK.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        public_key = settings.get_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


# ---------- Telemetry ----------


@router.post(
    "/telemetry",
    response_model=TelemetryIngestResponse,
    tags=["telemetry"],
    responses={
        409: {"model": Error},
        413: {"model": Error},
    },
)
async def ingest_telemetry(
    event: TelemetryEvent,
    claims: dict = Depends(verify_bearer_token),
    response: Response = None,
):
    aircraft_id_from_token = claims.get("sub")
    # Optional: verify consistency
    if aircraft_id_from_token and aircraft_id_from_token != str(event.aircraft_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="aircraft_id mismatch between token and payload",
        )
    existing = await repo.get(event.aircraft_id, event.event_id)

    if existing is None:
        await repo.insert(event)
        # force 201 here
        if response is not None:
            response.status_code = status.HTTP_201_CREATED
        return TelemetryIngestResponse(
            status="created",
            event_id=event.event_id,
        )

    if existing == event:
        # FastAPI returns 200 by default
        return TelemetryIngestResponse(
            status="duplicate",
            event_id=event.event_id,
        )

    # Same event_id but different content -> conflict
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=Error(
            code="TELEMETRY_CONFLICT",
            message="Event with same event_id but different payload already exists.",
        ).model_dump(),
    )
