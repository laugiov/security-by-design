"""Authentication module for SkyLink API Gateway.

This module provides JWT RS256 authentication:
- Token issuance (sign with private key)
- Token verification (verify with public key)
- mTLS cross-validation (CN must match JWT subject)
- Security by Design principles applied

Security by Design:
- RS256 algorithm only (asymmetric crypto)
- Short token lifetime (max 15 minutes)
- Tokens are NEVER logged
- Only validated claims are exposed
- No sensitive data in error messages
- mTLS CN validated against JWT subject when enabled
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Dict, Optional
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from skylink.config import settings


class TokenRequest(BaseModel):
    """Request body for POST /auth/token."""

    model_config = {"extra": "forbid"}  # Reject unknown fields (Security by Design)

    aircraft_id: UUID = Field(
        ...,
        description="Unique identifier of the aircraft",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class TokenResponse(BaseModel):
    """Response body for POST /auth/token."""

    access_token: str = Field(
        ...,
        description="JWT access token (RS256 signed)",
        examples=["eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type (always Bearer)",
    )
    expires_in: int = Field(
        ...,
        description="Token lifetime in seconds",
        examples=[900],
    )


def create_access_token(aircraft_id: str) -> str:
    """Create a new JWT access token signed with RS256.

    Args:
        aircraft_id: The aircraft's UUID (becomes 'sub' claim)

    Returns:
        str: Signed JWT token

    Raises:
        RuntimeError: If private key cannot be loaded

    Security Notes:
        - Token is NEVER logged
        - Short expiration (15 minutes max)
        - RS256 ensures only gateway can sign tokens
        - Claims follow JWT best practices (sub, aud, iat, exp)
    """
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=settings.jwt_expiration_minutes)

    payload = {
        "sub": aircraft_id,  # Subject: aircraft ID
        "aud": settings.jwt_audience,  # Audience: skylink
        "iat": int(now.timestamp()),  # Issued at
        "exp": int(expiration.timestamp()),  # Expiration
    }

    try:
        private_key = settings.get_private_key()
        token = jwt.encode(payload, private_key, algorithm=settings.jwt_algorithm)
        return token
    except Exception as e:
        # DO NOT log the exception details (might contain key info)
        raise RuntimeError(f"Failed to create JWT token: {type(e).__name__}") from e


async def verify_jwt(
    authorization: str | None = Header(None, description="Bearer JWT token")
) -> Dict[str, any]:
    """Verify JWT token signature and extract claims (RS256).

    This is the real implementation using public key verification.
    Replaces the stub version used for testing.

    Args:
        authorization: Authorization header value (format: "Bearer <token>")

    Returns:
        dict: Validated JWT claims with:
            - sub: Subject (aircraft_id as UUID string)
            - aud: Audience (should be "skylink")
            - iat: Issued at timestamp
            - exp: Expiration timestamp

    Raises:
        HTTPException: 401 if token is invalid, expired, or has wrong signature

    Security Notes:
        - Token is NEVER logged
        - Signature is verified with public key (RS256)
        - Expiration is enforced
        - Audience is validated
        - No sensitive data in error messages
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify format: "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format (expected: Bearer <token>)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Verify signature and decode claims
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
        # Catch all other JWT errors (invalid signature, malformed token, etc.)
        # DO NOT expose internal error details
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    except Exception:
        # Catch unexpected errors (key loading issues, etc.)
        # DO NOT expose internal error details
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


# Type alias for dependency injection
JWTClaims = Annotated[Dict[str, any], Depends(verify_jwt)]


async def verify_jwt_with_mtls(
    request: Request,
    authorization: str | None = Header(None, description="Bearer JWT token"),
) -> Dict[str, any]:
    """Verify JWT token and cross-validate with mTLS client certificate.

    This function performs standard JWT verification and additionally
    validates that the JWT subject matches the mTLS client certificate CN
    when mTLS is enabled.

    This provides defense in depth:
    1. mTLS ensures the client has a valid certificate
    2. JWT ensures the client has a valid token
    3. Cross-validation ensures both identities match

    Args:
        request: FastAPI request (contains mTLS info from middleware)
        authorization: Authorization header value (format: "Bearer <token>")

    Returns:
        dict: Validated JWT claims (same as verify_jwt)

    Raises:
        HTTPException: 401 if JWT is invalid
        HTTPException: 403 if JWT subject doesn't match mTLS CN

    Security Notes:
        - Only active when mTLS is enabled AND client cert is present
        - Prevents token theft/reuse from different client
        - CN comparison is case-sensitive
    """
    # First, perform standard JWT verification
    claims = await verify_jwt(authorization)

    # If mTLS is enabled and we have a client CN, cross-validate
    if settings.mtls_enabled:
        mtls_cn: Optional[str] = getattr(request.state, "mtls_cn", None)

        if mtls_cn is not None:
            jwt_subject = claims.get("sub")

            if jwt_subject and mtls_cn != jwt_subject:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Certificate CN does not match token subject",
                )

    return claims


# Type alias for mTLS-validated JWT claims
JWTClaimsWithMTLS = Annotated[Dict[str, any], Depends(verify_jwt_with_mtls)]
