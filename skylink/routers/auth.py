"""Authentication router - Gateway authentication endpoints."""

from fastapi import APIRouter, HTTPException, Request, status

from skylink.audit import audit_logger
from skylink.auth import TokenRequest, TokenResponse, create_access_token
from skylink.config import settings

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


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


@router.post("/token", response_model=TokenResponse, status_code=200)
async def obtain_token(request: Request, body: TokenRequest) -> TokenResponse:
    """Obtain JWT authentication token.

    Authenticate a aircraft and receive a JWT access token.
    Token is valid for 15 minutes maximum (Security by Design).

    Args:
        request: Token request containing aircraft_id (UUID)

    Returns:
        TokenResponse: JWT token with expiration information
            - access_token: RS256-signed JWT token
            - token_type: "Bearer"
            - expires_in: Token lifetime in seconds (900 = 15 min)

    Raises:
        HTTPException: 500 if token generation fails

    Security Notes:
        - Token is signed with RS256 (private key)
        - Aircraft ID becomes the 'sub' claim
        - Short expiration (15 minutes max)
        - Token contains no sensitive data (only aircraft_id)

    Implementation Notes:
        - No database validation in MVP (trusts aircraft_id)
        - Future: Validate aircraft exists in DB
        - Future: Check aircraft status (active/suspended)
        - Future: Rate-limit token issuance per aircraft
    """
    trace_id = _get_trace_id(request)
    client_ip = _get_client_ip(request)
    aircraft_id = str(body.aircraft_id)
    # Use requested role or default to aircraft_standard
    role = body.role if body.role else "aircraft_standard"

    try:
        # Generate JWT token signed with RS256, including role for RBAC
        token = create_access_token(aircraft_id=aircraft_id, role=role)

        # Audit: Log successful token issuance
        audit_logger.log_auth_success(
            actor_id=aircraft_id,
            ip_address=client_ip,
            trace_id=trace_id,
        )

        return TokenResponse(
            access_token=token,
            token_type="Bearer",  # noqa: S106 # nosec B106 (OAuth2 token type, not a password)
            expires_in=settings.jwt_expiration_minutes * 60,  # Convert to seconds
        )

    except RuntimeError as e:
        # Key loading or signing failed
        # Audit: Log token generation failure
        audit_logger.log_auth_failure(
            actor_id=aircraft_id,
            ip_address=client_ip,
            trace_id=trace_id,
            reason="token_generation_failed",
        )
        # DO NOT expose internal error details to client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        ) from e

    except Exception as e:
        # Unexpected error
        # Audit: Log unexpected failure
        audit_logger.log_auth_failure(
            actor_id=aircraft_id,
            ip_address=client_ip,
            trace_id=trace_id,
            reason="unexpected_error",
        )
        # DO NOT expose internal error details to client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
