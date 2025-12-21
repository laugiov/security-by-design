"""Contacts router - Gateway proxy to Contacts microservice."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from skylink.audit import audit_logger
from skylink.rbac import require_permission
from skylink.rbac_roles import Permission

router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
)

# Contacts service URL (from config or env)
CONTACTS_SERVICE_URL = "http://contacts:8003"
PROXY_TIMEOUT = 2.0  # 2 seconds timeout


def _get_trace_id(request: Request) -> str | None:
    """Extract trace ID from request state or headers."""
    try:
        trace_id = getattr(request.state, "trace_id", None)
        if not trace_id:
            trace_id = request.headers.get("X-Trace-Id")
        return trace_id if isinstance(trace_id, str) else None
    except Exception:
        return None


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP address from request."""
    try:
        if request.client and hasattr(request.client, "host"):
            host = request.client.host
            return host if isinstance(host, str) else None
    except Exception:
        pass
    return None


@router.get("/")
async def list_contacts(
    request: Request,
    person_fields: str = Query(
        ..., description="Google People field mask", examples=["names,emailAddresses,phoneNumbers"]
    ),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    token: dict = Depends(require_permission(Permission.CONTACTS_READ)),
):
    """List contacts from Contacts microservice (requires JWT authentication).

    This endpoint proxies the request to the internal Contacts microservice.
    In MVP demo mode, it returns static fixtures.

    Args:
        request: FastAPI request object
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
    trace_id = _get_trace_id(request)
    client_ip = _get_client_ip(request)

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

            result = response.json()

            # Audit: Log contacts access (PII data access)
            items = result.get("items", [])
            audit_logger.log_contacts_accessed(
                actor_id=aircraft_id,
                count=len(items),
                ip_address=client_ip,
                trace_id=trace_id,
            )

            return result

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
