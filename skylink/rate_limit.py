"""Rate limiting module using slowapi.

This module provides rate limiting for the SkyLink API Gateway:
- Per-aircraft rate limit: 60 requests per minute
- Global rate limit: 10 requests per second

Uses slowapi (based on limits library) for robust rate limiting.
Includes Prometheus counter for rate limit exceeded events.
Includes audit logging for security monitoring.
"""

from fastapi import Request
from prometheus_client import Counter
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from skylink.audit import audit_logger

# Prometheus counter for rate limit exceeded events
rate_limit_exceeded_counter = Counter(
    "rate_limit_exceeded_total",
    "Total number of rate limit exceeded responses (429)",
    ["path", "method"],
)

# Rate limit configuration
RATE_LIMIT_PER_AIRCRAFT = "60/minute"
RATE_LIMIT_GLOBAL = "10/second"


def get_aircraft_id_from_request(request: Request) -> str:
    """Extract aircraft_id from JWT token for rate limiting.

    Falls back to remote address if no JWT is present.

    Args:
        request: The incoming HTTP request

    Returns:
        Aircraft ID from JWT 'sub' claim, or remote address as fallback
    """
    authorization = request.headers.get("authorization")

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            try:
                import jwt

                payload = jwt.decode(token, options={"verify_signature": False})
                aircraft_id = payload.get("sub")
                if aircraft_id:
                    return aircraft_id
            except Exception:
                pass

    # Fallback to IP address
    return get_remote_address(request)


# Create limiter instance with aircraft_id as key
limiter = Limiter(key_func=get_aircraft_id_from_request)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors.

    Returns a standardized error response matching the project's error format.
    Also increments the Prometheus counter for monitoring.
    Logs audit event for security monitoring.

    Args:
        request: The incoming HTTP request
        exc: The rate limit exceeded exception

    Returns:
        JSONResponse with 429 status and error details
    """
    # Increment Prometheus counter for rate limit exceeded
    rate_limit_exceeded_counter.labels(
        path=request.url.path,
        method=request.method,
    ).inc()

    # Extract actor ID and trace ID for audit logging
    actor_id = get_aircraft_id_from_request(request)
    trace_id = getattr(request.state, "trace_id", None)
    if not trace_id:
        trace_id = request.headers.get("X-Trace-Id")
    client_ip = request.client.host if request.client else None

    # Audit: Log rate limit exceeded event
    audit_logger.log_rate_limit_exceeded(
        actor_id=actor_id,
        ip_address=client_ip,
        trace_id=trace_id,
        endpoint=request.url.path,
        limit=exc.detail,
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {exc.detail}",
            }
        },
        headers={"Retry-After": "60"},
    )
