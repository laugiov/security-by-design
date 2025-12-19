"""Contacts router - Gateway proxy to Contacts microservice."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from skylink.auth import verify_jwt

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
)

# Contacts service URL (from config or env)
CONTACTS_SERVICE_URL = "http://contacts:8003"
PROXY_TIMEOUT = 2.0  # 2 seconds timeout


@router.get("/")
async def list_contacts(
    person_fields: str = Query(
        ..., description="Google People field mask", examples=["names,emailAddresses,phoneNumbers"]
    ),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    token: dict = Depends(verify_jwt),
):
    """List contacts from Contacts microservice (requires JWT authentication).

    This endpoint proxies the request to the internal Contacts microservice.
    In MVP demo mode, it returns static fixtures.

    Args:
        person_fields: Google People API field mask (required)
        page: Page number (1-indexed)
        size: Items per page (1-100)
        token: JWT token payload (injected by verify_jwt dependency)

    Returns:
        Paginated list of contacts

    Raises:
        HTTPException: If contacts service is unavailable or returns error
    """
    # Extract aircraft_id from JWT (claim "sub")
    aircraft_id = token.get("sub")

    try:
        async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
            response = await client.get(
                f"{CONTACTS_SERVICE_URL}/v1/contacts",
                headers={"X-Aircraft-Id": aircraft_id},  # Pass aircraft_id to service
                params={"person_fields": person_fields, "page": page, "size": size},
            )

            # Forward status code from contacts service
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Contacts service error: {response.text}",
                )

            return response.json()

    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Contacts service timeout",
        ) from e

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Contacts service unavailable: {str(e)}",
        ) from e
