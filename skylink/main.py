"""SkyLink - Main application module.

This is the API Gateway for the SkyLink connected car platform.
It provides:
- JWT RS256 authentication
- mTLS mutual authentication (optional)
- Request routing to microservices
- Security headers and structured logging
- Prometheus metrics (/metrics endpoint)
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded

from skylink.config import settings
from skylink.middlewares import (
    add_security_headers_middleware,
    json_logging_middleware,
    mtls_extraction_middleware,
    payload_limit_middleware,
)
from skylink.models.errors import create_error_response
from skylink.rate_limit import limiter, rate_limit_exceeded_handler
from skylink.routers import auth, contacts, telemetry, weather

app = FastAPI(
    title="SkyLink API Gateway",
    version="0.1.0",
    description="Connected Car Platform - API Gateway for Microservices",
)

# Prometheus metrics instrumentation
# Configured here, exposed after routes are added
instrumentator = Instrumentator(
    should_group_status_codes=False,  # Keep individual status codes (200, 201, 400, etc.)
    should_ignore_untemplated=True,  # Ignore requests without route template
    should_respect_env_var=False,  # Always enable metrics (no env var check)
    should_instrument_requests_inprogress=True,  # Track in-progress requests
    excluded_handlers=["/metrics"],  # Don't instrument the metrics endpoint itself
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)


# Exception handlers for standardized error responses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with standard error format."""
    # Extract field-level errors from Pydantic
    field_errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        field_errors.append(
            {
                "field": field_path or "unknown",
                "issue": error["type"],
                "message": error["msg"],
            }
        )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=create_error_response(
            code="VALIDATION_ERROR",
            message="Invalid input data",
            details={"fields": field_errors} if field_errors else None,
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with standard error format."""
    # Log the exception (but not in production logs to avoid info disclosure)
    # In production, this should go to a secure error tracking system
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
        ),
    )


# Configure rate limiting with slowapi
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Apply middlewares (order matters: last added = first executed)
# 1. JSON logging (first to execute, measures total time)
app.middleware("http")(json_logging_middleware)
# 2. Security headers (applied to all responses)
app.middleware("http")(add_security_headers_middleware)
# 3. Payload size limit (reject large requests early)
app.middleware("http")(payload_limit_middleware)
# 4. mTLS client certificate extraction (when mTLS is enabled)
if settings.mtls_enabled:
    app.middleware("http")(mtls_extraction_middleware)


# Include routers
app.include_router(auth.router)
app.include_router(weather.router)
app.include_router(contacts.router)
app.include_router(telemetry.router)

# Expose /metrics endpoint (after all routes are registered)
instrumentator.instrument(app).expose(app, include_in_schema=False)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint - API entry point."""
    return {"status": "ok", "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "skylink"}


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots():
    """Robots.txt for web crawlers."""
    return "User-agent: *\nDisallow:"


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    """Minimal sitemap.xml for SEO."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""
    return Response(content=xml, media_type="application/xml")


def add(a: int, b: int) -> int:
    """Add two numbers (example function for testing)."""
    return a + b


# Entry point for running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    # Get mTLS configuration
    mtls_config = settings.get_mtls_config()

    # Build uvicorn kwargs
    uvicorn_kwargs = {
        "app": "skylink.main:app",
        "host": "0.0.0.0",  # nosec B104 - binding to all interfaces for Docker
        "port": 8000,
        "log_level": settings.log_level.lower(),
    }

    # Add SSL configuration if mTLS is enabled
    if mtls_config.enabled:
        uvicorn_kwargs["ssl_keyfile"] = str(mtls_config.key_file)
        uvicorn_kwargs["ssl_certfile"] = str(mtls_config.cert_file)
        uvicorn_kwargs["ssl_ca_certs"] = str(mtls_config.ca_cert_file)
        # ssl_cert_reqs: 0=CERT_NONE, 1=CERT_OPTIONAL, 2=CERT_REQUIRED
        ssl_cert_reqs_map = {"CERT_NONE": 0, "CERT_OPTIONAL": 1, "CERT_REQUIRED": 2}
        uvicorn_kwargs["ssl_cert_reqs"] = ssl_cert_reqs_map.get(mtls_config.verify_mode, 2)
        print(f"🔐 Starting with mTLS enabled (verify_mode={mtls_config.verify_mode})")
    else:
        print("🔓 Starting without mTLS (HTTP mode)")

    uvicorn.run(**uvicorn_kwargs)
