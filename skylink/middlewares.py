"""Middlewares for SkyLink API Gateway.

This module provides middleware functions for:
- Security headers (OWASP best practices)
- JSON structured logging with trace_id (W3C Trace Context)
- Request/response correlation
- mTLS client certificate extraction
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response
from starlette.responses import JSONResponse

from skylink.mtls import extract_client_cn

# Maximum payload size in bytes (64 KB)
MAX_PAYLOAD_SIZE = 64 * 1024

# Security headers to prevent common vulnerabilities
SECURITY_HEADERS = {
    # ZAP 10021 - X-Content-Type-Options Header Missing
    "X-Content-Type-Options": "nosniff",
    # Anti-framing / clickjacking
    "X-Frame-Options": "DENY",
    # ZAP 10049 - Storable and Cacheable Content
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    # ZAP 90004 - Spectre / isolation
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
    # Bonus security best practices
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


async def add_security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses.

    This middleware adds OWASP-recommended security headers to prevent:
    - MIME sniffing attacks
    - Clickjacking
    - Information disclosure through caching
    - Cross-origin attacks

    Args:
        request: The incoming HTTP request
        call_next: The next middleware or route handler

    Returns:
        Response with security headers added
    """
    response: Response = await call_next(request)
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers.setdefault(header_name, header_value)
    return response


async def json_logging_middleware(request: Request, call_next):
    """Log all requests and responses in structured JSON format.

    Implements W3C Trace Context for distributed tracing:
    - Generates or propagates trace_id from X-Trace-Id header
    - Logs request method, path, status, duration
    - Outputs JSON logs to stdout for centralized logging

    Security considerations:
    - No sensitive data (tokens, secrets) are logged
    - No PII (Personally Identifiable Information) is logged
    - Request/response bodies are NOT logged

    Args:
        request: The incoming HTTP request
        call_next: The next middleware or route handler

    Returns:
        Response with X-Trace-Id header added
    """
    # Generate or propagate trace_id (W3C Trace Context)
    trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())

    # Start timer
    start_time = time.time()

    # Process request
    response: Response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Build structured log entry
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "gateway",
        "trace_id": trace_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round(duration_ms, 2),
    }

    # Output JSON log to stdout
    print(json.dumps(log_entry), flush=True)

    # Add trace_id to response headers for correlation
    response.headers["X-Trace-Id"] = trace_id

    return response


async def payload_limit_middleware(request: Request, call_next):
    """Enforce maximum payload size limit for request bodies.

    This middleware rejects requests with Content-Length exceeding 64KB
    to prevent denial-of-service attacks and ensure reasonable request sizes.

    Args:
        request: The incoming HTTP request
        call_next: The next middleware or route handler

    Returns:
        413 Payload Too Large if Content-Length exceeds limit
        Normal response otherwise
    """
    # Check Content-Length header if present
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            length = int(content_length)
            if length > MAX_PAYLOAD_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds maximum size of {MAX_PAYLOAD_SIZE} bytes",
                        }
                    },
                )
        except ValueError:
            # Invalid Content-Length header - let downstream handle it
            pass

    return await call_next(request)


async def mtls_extraction_middleware(request: Request, call_next):
    """Extract client certificate CN from mTLS connection.

    This middleware extracts the Common Name (CN) from the client's
    TLS certificate and stores it in request.state for later use
    in JWT validation (cross-validation of mTLS identity vs JWT subject).

    The CN is expected to contain the aircraft_id, which should match
    the 'sub' claim in the JWT token.

    Args:
        request: The incoming HTTP request
        call_next: The next middleware or route handler

    Returns:
        Response from the next handler

    Note:
        - Only active when mTLS is enabled
        - Sets request.state.mtls_cn if client cert is present
        - Sets request.state.mtls_verified to True if CN was extracted
    """
    # Try to extract client certificate from the connection
    # This works when running behind uvicorn with SSL enabled
    mtls_cn: Optional[str] = None

    # Access the underlying transport to get SSL info
    # FastAPI/Starlette stores SSL socket in scope
    scope = request.scope

    # Check if we have SSL/TLS connection info
    # The peer certificate is available in the transport layer
    if "transport" in scope:
        transport = scope["transport"]
        if hasattr(transport, "get_extra_info"):
            ssl_object = transport.get_extra_info("ssl_object")
            if ssl_object:
                try:
                    peer_cert = ssl_object.getpeercert()
                    mtls_cn = extract_client_cn(peer_cert)
                except Exception:
                    # Certificate extraction failed - continue without mTLS
                    pass

    # Store mTLS info in request state for downstream use
    request.state.mtls_cn = mtls_cn
    request.state.mtls_verified = mtls_cn is not None

    response = await call_next(request)
    return response
