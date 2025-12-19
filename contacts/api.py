"""API routes for Contacts Service."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from contacts.config import settings
from contacts.database import get_db
from contacts.fixtures import get_contacts_fixtures
from contacts.google_people import (
    GooglePeopleClient,
    PeopleAPIError,
    PeopleAPITimeoutError,
    PeopleAPIUnavailableError,
    QuotaExceededError,
    UnauthorizedError,
)
from contacts.oauth import GoogleOAuthClient, InvalidCodeError, RefreshTokenRevokedError
from contacts.schemas import ContactsListResponse, PaginationInfo
from contacts.tokens import TokenStorage

router = APIRouter()


@router.get("/v1/contacts", response_model=ContactsListResponse)
async def list_contacts(
    person_fields: str = Query(
        ...,
        description="Google People field mask (required)",
        examples=["names,emailAddresses,phoneNumbers"],
    ),
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    size: int = Query(10, ge=1, le=100, description="Items per page (1-100)"),
    x_aircraft_id: Optional[UUID] = Header(
        None, alias="X-Aircraft-Id", description="Aircraft ID from JWT"
    ),
) -> ContactsListResponse:
    """List contacts from Google People API with OAuth2 authentication.

    **Demo Mode**: If DEMO_MODE=true, returns static fixtures (no OAuth required).

    **Production Mode**: Uses OAuth2 flow to fetch real Google contacts:
    1. Check if aircraft has configured OAuth tokens
    2. Auto-refresh access_token if expired
    3. Call Google People API
    4. Handle errors appropriately

    Args:
        person_fields: Google People field mask (e.g., "names,emailAddresses")
        page: Page number (1-indexed, for pagination)
        size: Items per page (1-100)
        x_aircraft_id: Aircraft UUID from X-Aircraft-Id header (injected by gateway, optional in DEMO_MODE)

    Returns:
        ContactsListResponse with contacts and pagination info

    Raises:
        404: Aircraft not configured (no OAuth tokens)
        401: OAuth tokens expired/revoked (user must re-authorize)
        429: Google API quota exceeded (retry later)
        503: Google API temporarily unavailable
        504: Google API timeout
        502: Other Google API errors
    """
    # ==================== DEMO MODE ====================
    if settings.demo_mode:
        # Return fixtures for demo/testing (no OAuth)
        all_contacts = get_contacts_fixtures()
        total = len(all_contacts)

        # Calculate pagination
        start = (page - 1) * size
        end = start + size
        contacts_page = all_contacts[start:end]

        # Determine if there's a next page
        has_next = end < total
        next_page_token = f"page_{page + 1}" if has_next else None

        return ContactsListResponse(
            items=contacts_page,
            pagination=PaginationInfo(
                page=page,
                size=size,
                total=total,
                next_page_token=next_page_token,
            ),
            next_sync_token=None,
        )

    # ==================== PRODUCTION MODE (OAuth) ====================

    # Check that X-Aircraft-Id is provided in production mode
    if x_aircraft_id is None:
        raise HTTPException(
            status_code=400,
            detail="X-Aircraft-Id header is required in production mode",
        )

    # 1. Get tokens from database
    db = next(get_db())
    token_storage = TokenStorage(db)

    try:
        tokens = await token_storage.get(x_aircraft_id)

        if tokens is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "AIRCRAFT_NOT_CONFIGURED",
                    "message": "Please configure your Google account in the mobile app",
                    "action": "configure_google_account",
                },
            )

        # 2. Check if access_token is expired and refresh if needed
        is_expired = await token_storage.is_expired(x_aircraft_id)

        if is_expired:
            # Auto-refresh access_token
            oauth_client = GoogleOAuthClient()

            try:
                refreshed_tokens = await oauth_client.refresh_access_token(tokens["refresh_token"])

                # Update tokens in database with new access_token
                updated_tokens = {
                    **tokens,
                    "access_token": refreshed_tokens["access_token"],
                    "expires_at": datetime.now(timezone.utc)
                    + timedelta(seconds=refreshed_tokens["expires_in"]),
                }
                await token_storage.save(x_aircraft_id, updated_tokens)

                tokens = updated_tokens

            except RefreshTokenRevokedError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "REFRESH_TOKEN_REVOKED",
                        "message": "Your Google authorization has been revoked. Please reconnect your account",
                        "action": "reauthorize_google_account",
                    },
                )

        # 3. Call Google People API with valid access_token
        people_client = GooglePeopleClient(access_token=tokens["access_token"], timeout=5.0)

        try:
            google_response = await people_client.list_contacts(
                person_fields=person_fields,
                page_size=size,
                # Note: Google uses pageToken, we use page number for simplicity in MVP
            )

            # 4. Format response
            contacts = google_response.get("connections", [])
            total_people = google_response.get("totalPeople", 0)
            next_page_token = google_response.get("nextPageToken")

            return ContactsListResponse(
                items=contacts,
                pagination=PaginationInfo(
                    page=page,
                    size=size,
                    total=total_people,
                    next_page_token=next_page_token,
                ),
                next_sync_token=google_response.get("nextSyncToken"),
            )

        except UnauthorizedError:
            # Access token is invalid even after refresh (shouldn't happen)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "INVALID_ACCESS_TOKEN",
                    "message": "Your Google access token is invalid. Please reconnect your account",
                    "action": "reauthorize_google_account",
                },
            )

        except QuotaExceededError as e:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "QUOTA_EXCEEDED",
                    "message": "Google API quota exceeded. Please try again later",
                    "retry_after": e.retry_after,
                },
                headers={"Retry-After": str(e.retry_after)},
            )

        except PeopleAPIUnavailableError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "GOOGLE_API_UNAVAILABLE",
                    "message": "Google People API is temporarily unavailable. Please try again later",
                },
            )

        except PeopleAPITimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "code": "GOOGLE_API_TIMEOUT",
                    "message": "Google People API request timed out. Please try again",
                },
            )

        except PeopleAPIError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "GOOGLE_API_ERROR",
                    "message": f"Error fetching contacts from Google: {str(e)}",
                },
            )

    finally:
        db.close()


@router.post("/oauth/callback", status_code=status.HTTP_200_OK)
async def oauth_callback(
    code: str = Query(..., description="OAuth authorization code from Google"),
    aircraft_id: UUID = Query(..., description="Aircraft ID to associate tokens with"),
):
    """OAuth callback endpoint for initial Google account configuration.

    This endpoint is called by the mobile app after user authorizes Google access.

    Flow:
    1. Mobile app redirects user to Google OAuth consent screen
    2. User authorizes access
    3. Google redirects back with authorization code
    4. Mobile app calls this endpoint with code + aircraft_id
    5. We exchange code for access/refresh tokens
    6. We save tokens in database (refresh_token encrypted)

    Args:
        code: Authorization code from Google OAuth
        aircraft_id: Aircraft UUID to associate with these tokens

    Returns:
        Success message

    Raises:
        400: Invalid or expired authorization code
        500: Error saving tokens to database
    """
    oauth_client = GoogleOAuthClient()
    db = next(get_db())
    token_storage = TokenStorage(db)

    try:
        # 1. Exchange authorization code for tokens
        try:
            tokens_response = await oauth_client.exchange_code_for_tokens(code)
        except InvalidCodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_AUTHORIZATION_CODE",
                    "message": "The authorization code is invalid or expired",
                    "error": str(e),
                },
            )

        # 2. Validate scopes
        granted_scopes = tokens_response.get("scope", "")
        if not oauth_client.validate_scopes(granted_scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_SCOPES",
                    "message": "Required permissions were not granted. Please authorize with contacts.readonly scope",
                },
            )

        # 3. Prepare tokens for storage
        tokens_to_save = {
            "access_token": tokens_response["access_token"],
            "refresh_token": tokens_response["refresh_token"],
            "expires_at": datetime.now(timezone.utc)
            + timedelta(seconds=tokens_response.get("expires_in", 3600)),
            "scopes": oauth_client.parse_scopes(granted_scopes),
            "provider": "google",
        }

        # 4. Save tokens in database (refresh_token will be encrypted automatically)
        await token_storage.save(aircraft_id, tokens_to_save)

        return {
            "success": True,
            "message": "Google account configured successfully",
            "aircraft_id": str(aircraft_id),
        }

    finally:
        db.close()
