"""Google OAuth2 client for authorization code flow and token refresh."""

import os
from typing import Optional
from urllib.parse import urlencode

import httpx


class OAuthError(Exception):
    """Base exception for OAuth errors."""


class InvalidCodeError(OAuthError):
    """OAuth authorization code is invalid or expired."""


class RefreshTokenExpiredError(OAuthError):
    """Refresh token has expired or been revoked."""


class RefreshTokenRevokedError(OAuthError):
    """Refresh token was explicitly revoked by the user."""


class InvalidScopesError(OAuthError):
    """Scopes received don't match required scopes."""


class GoogleOAuthClient:
    """Client for Google OAuth2 authorization code flow and token management.

    Handles:
    - Exchanging authorization code for access/refresh tokens
    - Refreshing access tokens using refresh tokens
    - Validating scopes granted by the user
    """

    # Google OAuth2 endpoints
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"

    # Required scope for Google People API (contacts readonly)
    REQUIRED_SCOPE = "https://www.googleapis.com/auth/contacts.readonly"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        """Initialize OAuth client with Google credentials.

        Args:
            client_id: Google OAuth client ID. If None, reads from env GOOGLE_CLIENT_ID.
            client_secret: Google OAuth client secret. If None, reads from env GOOGLE_CLIENT_SECRET.
            redirect_uri: OAuth redirect URI. If None, reads from env GOOGLE_REDIRECT_URI.

        Raises:
            OAuthError: If credentials are missing
        """
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("GOOGLE_REDIRECT_URI")

        if not self.client_id or not self.client_secret:
            raise OAuthError(
                "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables are required"
            )

    def get_authorization_url(
        self,
        state: Optional[str] = None,
        access_type: str = "offline",
        prompt: str = "consent",
    ) -> str:
        """Generate OAuth authorization URL for user consent.

        Args:
            state: Optional state parameter for CSRF protection
            access_type: 'offline' to get refresh_token, 'online' for access_token only
            prompt: 'consent' to force consent screen, 'none' for silent auth

        Returns:
            Full authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.REQUIRED_SCOPE,
            "access_type": access_type,
            "prompt": prompt,
        }

        if state:
            params["state"] = state

        return f"{self.AUTH_ENDPOINT}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing:
                - access_token (str): Access token
                - refresh_token (str): Refresh token (for offline access)
                - expires_in (int): Token TTL in seconds (~3600)
                - scope (str): Granted scopes
                - token_type (str): Usually "Bearer"

        Raises:
            InvalidCodeError: If code is invalid or expired
            OAuthError: If token exchange fails
        """
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.TOKEN_ENDPOINT, data=data)

                if response.status_code == 400:
                    error_data = response.json()
                    error_type = error_data.get("error", "unknown")

                    if error_type == "invalid_grant":
                        error_desc = error_data.get("error_description", "No description")
                        raise InvalidCodeError(
                            f"Invalid or expired authorization code: {error_desc}"
                        )

                    raise OAuthError(
                        f"OAuth error: {error_type} - {error_data.get('error_description', 'No description')}"
                    )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            raise OAuthError(f"HTTP error during token exchange: {e}") from e
        except Exception as e:
            if isinstance(e, (InvalidCodeError, OAuthError)):
                raise
            raise OAuthError(f"Unexpected error during token exchange: {e}") from e

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token.

        Args:
            refresh_token: The refresh token obtained during authorization

        Returns:
            Dictionary containing:
                - access_token (str): New access token
                - expires_in (int): Token TTL in seconds (~3600)
                - scope (str): Granted scopes
                - token_type (str): Usually "Bearer"

        Raises:
            RefreshTokenExpiredError: If refresh token is expired
            RefreshTokenRevokedError: If refresh token was revoked by user
            OAuthError: If refresh fails for other reasons
        """
        data = {
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.TOKEN_ENDPOINT, data=data)

                if response.status_code == 400:
                    error_data = response.json()
                    error_type = error_data.get("error", "unknown")

                    if error_type == "invalid_grant":
                        # Could be expired or revoked - treat as revoked
                        error_desc = error_data.get("error_description", "No description")
                        raise RefreshTokenRevokedError(
                            f"Refresh token is invalid or revoked: {error_desc}"
                        )

                    raise OAuthError(
                        f"OAuth error: {error_type} - {error_data.get('error_description', 'No description')}"
                    )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            raise OAuthError(f"HTTP error during token refresh: {e}") from e
        except Exception as e:
            if isinstance(e, (RefreshTokenRevokedError, RefreshTokenExpiredError, OAuthError)):
                raise
            raise OAuthError(f"Unexpected error during token refresh: {e}") from e

    def validate_scopes(self, granted_scopes: str) -> bool:
        """Validate that granted scopes include required scope.

        Args:
            granted_scopes: Space-separated string of granted scopes from OAuth response

        Returns:
            True if required scope is present, False otherwise
        """
        scopes_list = granted_scopes.split()
        return self.REQUIRED_SCOPE in scopes_list

    def parse_scopes(self, scope_string: str) -> list[str]:
        """Parse space-separated scope string into list.

        Args:
            scope_string: Space-separated scopes (e.g., "scope1 scope2")

        Returns:
            List of scope strings
        """
        return scope_string.split()
