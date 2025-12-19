"""Tests for OAuth client."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from contacts.oauth import (
    GoogleOAuthClient,
    InvalidCodeError,
    OAuthError,
    RefreshTokenRevokedError,
)


@pytest.fixture
def google_fixtures():
    """Load Google API response fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "google_responses.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture
def oauth_client():
    """Create OAuth client with test credentials."""
    return GoogleOAuthClient(
        client_id="test_client_id_123.apps.googleusercontent.com",
        client_secret="test_client_secret_abc",
        redirect_uri="http://localhost:8003/oauth/callback",
    )


class TestGoogleOAuthClientInit:
    """Test GoogleOAuthClient initialization."""

    def test_init_with_explicit_credentials(self):
        """Should initialize with explicit credentials."""
        client = GoogleOAuthClient(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )

        assert client.client_id == "test_id"
        assert client.client_secret == "test_secret"
        assert client.redirect_uri == "http://localhost/callback"

    def test_init_with_env_credentials(self):
        """Should initialize with credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "GOOGLE_CLIENT_ID": "env_id",
                "GOOGLE_CLIENT_SECRET": "env_secret",
                "GOOGLE_REDIRECT_URI": "http://localhost/callback",
            },
        ):
            client = GoogleOAuthClient()

            assert client.client_id == "env_id"
            assert client.client_secret == "env_secret"

    def test_init_without_credentials_raises_error(self):
        """Should raise error if credentials are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(OAuthError, match="GOOGLE_CLIENT_ID.*required"):
                GoogleOAuthClient()


class TestGetAuthorizationUrl:
    """Test get_authorization_url method."""

    def test_get_authorization_url_basic(self, oauth_client):
        """Should generate valid authorization URL."""
        url = oauth_client.get_authorization_url()

        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "client_id=test_client_id_123" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8003%2Foauth%2Fcallback" in url
        assert "response_type=code" in url
        assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcontacts.readonly" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url

    def test_get_authorization_url_with_state(self, oauth_client):
        """Should include state parameter for CSRF protection."""
        url = oauth_client.get_authorization_url(state="random_state_123")

        assert "state=random_state_123" in url


class TestExchangeCodeForTokens:
    """Test exchange_code_for_tokens method."""

    @pytest.mark.asyncio
    @patch("contacts.oauth.httpx.AsyncClient")
    async def test_exchange_code_success(self, mock_async_client, oauth_client, google_fixtures):
        """Should successfully exchange code for tokens."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_fixtures["oauth_token_success"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Exchange code
        result = await oauth_client.exchange_code_for_tokens("test_auth_code_123")

        # Assertions
        assert result["access_token"] == google_fixtures["oauth_token_success"]["access_token"]
        assert result["refresh_token"] == google_fixtures["oauth_token_success"]["refresh_token"]
        assert result["expires_in"] == 3599
        assert result["token_type"] == "Bearer"

    @pytest.mark.asyncio
    @patch("contacts.oauth.httpx.AsyncClient")
    async def test_exchange_code_invalid_code(
        self, mock_async_client, oauth_client, google_fixtures
    ):
        """Should raise InvalidCodeError for invalid authorization code."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = google_fixtures["oauth_token_error_invalid_grant"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Should raise InvalidCodeError
        with pytest.raises(InvalidCodeError, match="Invalid or expired authorization code"):
            await oauth_client.exchange_code_for_tokens("invalid_code")

    @pytest.mark.asyncio
    @patch("contacts.oauth.httpx.AsyncClient")
    async def test_exchange_code_http_error(self, mock_async_client, oauth_client):
        """Should handle HTTP errors gracefully."""
        # Mock HTTP error
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )
        mock_async_client.return_value = mock_context

        # Should raise OAuthError
        with pytest.raises(OAuthError, match="HTTP error during token exchange"):
            await oauth_client.exchange_code_for_tokens("test_code")


class TestRefreshAccessToken:
    """Test refresh_access_token method."""

    @pytest.mark.asyncio
    @patch("contacts.oauth.httpx.AsyncClient")
    async def test_refresh_token_success(self, mock_async_client, oauth_client, google_fixtures):
        """Should successfully refresh access token."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_fixtures["oauth_refresh_success"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Refresh token
        result = await oauth_client.refresh_access_token("test_refresh_token_123")

        # Assertions
        assert result["access_token"] == google_fixtures["oauth_refresh_success"]["access_token"]
        assert result["expires_in"] == 3599
        assert "refresh_token" not in result  # Refresh endpoint doesn't return new refresh_token

    @pytest.mark.asyncio
    @patch("contacts.oauth.httpx.AsyncClient")
    async def test_refresh_token_revoked(self, mock_async_client, oauth_client, google_fixtures):
        """Should raise RefreshTokenRevokedError for revoked refresh token."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = google_fixtures["oauth_refresh_error_revoked"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Should raise RefreshTokenRevokedError
        with pytest.raises(RefreshTokenRevokedError, match="invalid or revoked"):
            await oauth_client.refresh_access_token("revoked_refresh_token")

    @pytest.mark.asyncio
    @patch("contacts.oauth.httpx.AsyncClient")
    async def test_refresh_token_http_error(self, mock_async_client, oauth_client):
        """Should handle HTTP errors gracefully during refresh."""
        # Mock HTTP error
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value = mock_context

        # Should raise OAuthError
        with pytest.raises(OAuthError, match="HTTP error during token refresh"):
            await oauth_client.refresh_access_token("test_refresh_token")


class TestValidateScopes:
    """Test validate_scopes method."""

    def test_validate_scopes_valid(self, oauth_client):
        """Should return True if required scope is present."""
        scopes = "https://www.googleapis.com/auth/contacts.readonly https://www.googleapis.com/auth/userinfo.email"

        result = oauth_client.validate_scopes(scopes)

        assert result is True

    def test_validate_scopes_missing(self, oauth_client):
        """Should return False if required scope is missing."""
        scopes = "https://www.googleapis.com/auth/userinfo.email"

        result = oauth_client.validate_scopes(scopes)

        assert result is False

    def test_validate_scopes_exact_match(self, oauth_client):
        """Should return True for exact scope match."""
        scopes = "https://www.googleapis.com/auth/contacts.readonly"

        result = oauth_client.validate_scopes(scopes)

        assert result is True


class TestParseScopes:
    """Test parse_scopes method."""

    def test_parse_scopes_multiple(self, oauth_client):
        """Should parse multiple space-separated scopes."""
        scopes = "scope1 scope2 scope3"

        result = oauth_client.parse_scopes(scopes)

        assert result == ["scope1", "scope2", "scope3"]

    def test_parse_scopes_single(self, oauth_client):
        """Should parse single scope."""
        scopes = "single_scope"

        result = oauth_client.parse_scopes(scopes)

        assert result == ["single_scope"]
