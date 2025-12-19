"""Authentication router - Gateway authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from skylink.auth import TokenRequest, TokenResponse, create_access_token
from skylink.config import settings

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/token", response_model=TokenResponse, status_code=200)
async def obtain_token(request: TokenRequest) -> TokenResponse:
    """Obtain JWT authentication token.

    Authenticate a vehicle and receive a JWT access token.
    Token is valid for 15 minutes maximum (Security by Design).

    Args:
        request: Token request containing vehicle_id (UUID)

    Returns:
        TokenResponse: JWT token with expiration information
            - access_token: RS256-signed JWT token
            - token_type: "Bearer"
            - expires_in: Token lifetime in seconds (900 = 15 min)

    Raises:
        HTTPException: 500 if token generation fails

    Security Notes:
        - Token is signed with RS256 (private key)
        - Vehicle ID becomes the 'sub' claim
        - Short expiration (15 minutes max)
        - Token contains no sensitive data (only vehicle_id)

    Implementation Notes:
        - No database validation in MVP (trusts vehicle_id)
        - Future: Validate vehicle exists in DB
        - Future: Check vehicle status (active/suspended)
        - Future: Rate-limit token issuance per vehicle
    """
    try:
        # Generate JWT token signed with RS256
        token = create_access_token(vehicle_id=str(request.vehicle_id))

        return TokenResponse(
            access_token=token,
            token_type="Bearer",  # noqa: S106 # nosec B106 (OAuth2 token type, not a password)
            expires_in=settings.jwt_expiration_minutes * 60,  # Convert to seconds
        )

    except RuntimeError as e:
        # Key loading or signing failed
        # DO NOT expose internal error details to client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token generation failed",
        ) from e

    except Exception as e:
        # Unexpected error
        # DO NOT expose internal error details to client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e
