"""Endpoints API du service de télémétrie."""

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

# Repo simple en mémoire (à remplacer par un vrai repo DB)
repo = InMemoryTelemetryRepository()

# Schéma de sécurité HTTP Bearer pour /telemetry
bearer_scheme = HTTPBearer(auto_error=True)


# ---------- Auth ----------


async def verify_bearer_token(authorization: str | None = Header(default=None)) -> dict:
    """Vérifie le token JWT signé par la Gateway avec la clé publique.

    - Attend un header Authorization: Bearer <token>
    - Vérifie algorithme, audience, exp, etc.
    - Retourne les claims si tout est OK.
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
    vehicle_id_from_token = claims.get("sub")
    # Optionnel : vérifier cohérence
    if vehicle_id_from_token and vehicle_id_from_token != str(event.vehicle_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vehicle_id mismatch between token and payload",
        )
    existing = await repo.get(event.vehicle_id, event.event_id)

    if existing is None:
        await repo.insert(event)
        # force le 201 ici
        if response is not None:
            response.status_code = status.HTTP_201_CREATED
        return TelemetryIngestResponse(
            status="created",
            event_id=event.event_id,
        )

    if existing == event:
        # FastAPI renverra 200 par défaut
        return TelemetryIngestResponse(
            status="duplicate",
            event_id=event.event_id,
        )

    # Même event_id mais contenu différent → conflit
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=Error(
            code="TELEMETRY_CONFLICT",
            message="Event with same event_id but different payload already exists.",
        ).model_dump(),
    )
