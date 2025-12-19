"""Integration tests for Contacts Service OAuth2 flow.

Tests the complete end-to-end OAuth flow with mocked external dependencies:
- Demo mode vs Production mode
- OAuth callback endpoint
- Auto-refresh when token expired
- All error scenarios (404, 401, 429, 503, 504, 502)

Note: These tests use mocks - no actual calls to Google APIs.
For E2E tests with real Google APIs, see tests/e2e/test_google_oauth_e2e.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from contacts.database import Base, get_db, get_test_db
from contacts.google_people import (
    PeopleAPIError,
    PeopleAPITimeoutError,
    PeopleAPIUnavailableError,
    QuotaExceededError,
    UnauthorizedError,
)
from contacts.main import app
from contacts.oauth import InvalidCodeError, RefreshTokenRevokedError

# Load fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
with open(FIXTURES_DIR / "google_responses.json") as f:
    GOOGLE_FIXTURES = json.load(f)


@pytest.fixture
def test_vehicle_id() -> UUID:
    """Return a test vehicle UUID."""
    return uuid4()


@pytest.fixture
def test_db_session():
    """Create a test database session."""
    db = get_test_db()
    Base.metadata.create_all(bind=db.bind)
    yield db
    db.close()
    Base.metadata.drop_all(bind=db.bind)


@pytest.fixture
def test_client(test_db_session):
    """Create a test client with overridden database dependency."""

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_valid_tokens(test_vehicle_id) -> dict:
    """Return mock valid OAuth tokens."""
    # Use timezone-aware UTC with Python 3.10 compatibility
    from datetime import timezone

    now = datetime.now(timezone.utc)
    return {
        "vehicle_id": str(test_vehicle_id),
        "access_token": "ya29.mock_access_token_valid",
        "refresh_token": "1//mock_refresh_token_valid",
        "expires_at": now + timedelta(hours=1),  # Valid for 1 hour
        "scopes": ["https://www.googleapis.com/auth/contacts.readonly"],
        "provider": "google",
    }


@pytest.fixture
def mock_expired_tokens(test_vehicle_id) -> dict:
    """Return mock expired OAuth tokens."""
    # Use timezone-aware UTC with Python 3.10 compatibility
    from datetime import timezone

    now = datetime.now(timezone.utc)
    return {
        "vehicle_id": str(test_vehicle_id),
        "access_token": "ya29.mock_access_token_expired",
        "refresh_token": "1//mock_refresh_token_valid",
        "expires_at": now - timedelta(hours=1),  # Expired 1 hour ago
        "scopes": ["https://www.googleapis.com/auth/contacts.readonly"],
        "provider": "google",
    }


class TestContactsIntegrationDemoMode:
    """Test suite for demo mode (no OAuth required)."""

    @patch("contacts.api.settings.demo_mode", True)
    def test_list_contacts_demo_mode_success(self, test_client, test_vehicle_id):
        """Test listing contacts in demo mode returns fixtures."""
        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names,emailAddresses", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) <= 10  # Respects page size

        # Check pagination info
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["size"] == 10
        assert "total" in pagination

    @patch("contacts.api.settings.demo_mode", True)
    def test_list_contacts_demo_mode_pagination(self, test_client, test_vehicle_id):
        """Test pagination works in demo mode."""
        # Page 1
        response1 = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 5},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert len(data1["items"]) == 5
        assert data1["pagination"]["page"] == 1

        # Page 2
        response2 = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 2, "size": 5},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["pagination"]["page"] == 2

        # Items should be different
        if len(data1["items"]) > 0 and len(data2["items"]) > 0:
            assert data1["items"][0] != data2["items"][0]


class TestContactsIntegrationOAuthCallback:
    """Test suite for OAuth callback endpoint."""

    @patch("contacts.api.settings.demo_mode", False)
    @patch.dict(
        "os.environ",
        {
            "GOOGLE_CLIENT_ID": "mock_client_id",
            "GOOGLE_CLIENT_SECRET": "mock_client_secret",
            "ENCRYPTION_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    @patch("contacts.oauth.GoogleOAuthClient.exchange_code_for_tokens")
    @patch("contacts.oauth.GoogleOAuthClient.validate_scopes")
    @patch("contacts.oauth.GoogleOAuthClient.parse_scopes")
    @patch("contacts.api.TokenStorage.save")
    async def test_oauth_callback_success(
        self,
        mock_token_save,
        mock_parse_scopes,
        mock_validate_scopes,
        mock_exchange,
        test_client,
        test_vehicle_id,
    ):
        """Test successful OAuth callback saves tokens to database."""
        # Mock OAuth client responses
        mock_exchange.return_value = GOOGLE_FIXTURES["oauth_token_success"]
        mock_validate_scopes.return_value = True
        mock_parse_scopes.return_value = ["https://www.googleapis.com/auth/contacts.readonly"]

        response = test_client.post(
            "/oauth/callback",
            params={"code": "mock_authorization_code", "vehicle_id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Google account configured successfully"
        assert data["vehicle_id"] == str(test_vehicle_id)

        # Verify OAuth exchange was called
        mock_exchange.assert_called_once_with("mock_authorization_code")

        # Verify token save was called
        mock_token_save.assert_called_once()

    @patch("contacts.api.settings.demo_mode", False)
    @patch.dict(
        "os.environ",
        {
            "GOOGLE_CLIENT_ID": "mock_client_id",
            "GOOGLE_CLIENT_SECRET": "mock_client_secret",
            "ENCRYPTION_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    @patch("contacts.oauth.GoogleOAuthClient.exchange_code_for_tokens")
    async def test_oauth_callback_invalid_code(self, mock_exchange, test_client, test_vehicle_id):
        """Test OAuth callback with invalid authorization code."""
        mock_exchange.side_effect = InvalidCodeError("Invalid authorization code")

        response = test_client.post(
            "/oauth/callback",
            params={"code": "invalid_code", "vehicle_id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["detail"]["code"] == "INVALID_AUTHORIZATION_CODE"

    @patch("contacts.api.settings.demo_mode", False)
    @patch.dict(
        "os.environ",
        {
            "GOOGLE_CLIENT_ID": "mock_client_id",
            "GOOGLE_CLIENT_SECRET": "mock_client_secret",
            "ENCRYPTION_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    @patch("contacts.oauth.GoogleOAuthClient.exchange_code_for_tokens")
    @patch("contacts.oauth.GoogleOAuthClient.validate_scopes")
    async def test_oauth_callback_insufficient_scopes(
        self, mock_validate_scopes, mock_exchange, test_client, test_vehicle_id
    ):
        """Test OAuth callback when user doesn't grant required scopes."""
        mock_exchange.return_value = GOOGLE_FIXTURES["oauth_token_success"]
        mock_validate_scopes.return_value = False  # Scopes not validated

        response = test_client.post(
            "/oauth/callback",
            params={"code": "mock_code", "vehicle_id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert data["detail"]["code"] == "INSUFFICIENT_SCOPES"


class TestContactsIntegrationProductionMode:
    """Test suite for production mode with OAuth."""

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_oauth_valid_token(
        self,
        mock_list_contacts,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_valid_tokens,
    ):
        """Test listing contacts with valid OAuth token (no refresh needed)."""
        # Mock token storage
        mock_token_get.return_value = mock_valid_tokens
        mock_is_expired.return_value = False

        # Mock Google People API
        mock_list_contacts.return_value = GOOGLE_FIXTURES["people_api_success"]

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names,emailAddresses", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "pagination" in data

        # Verify token was retrieved
        mock_token_get.assert_called_once_with(test_vehicle_id)

        # Verify Google API was called
        mock_list_contacts.assert_called_once()

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    async def test_list_contacts_vehicle_not_configured(
        self, mock_token_get, test_client, test_vehicle_id
    ):
        """Test listing contacts when vehicle has no OAuth tokens configured."""
        mock_token_get.return_value = None  # No tokens found

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["detail"]["code"] == "VEHICLE_NOT_CONFIGURED"
        assert "configure your Google account" in data["detail"]["message"]

    @patch("contacts.api.settings.demo_mode", False)
    @patch.dict(
        "os.environ",
        {
            "GOOGLE_CLIENT_ID": "mock_client_id",
            "GOOGLE_CLIENT_SECRET": "mock_client_secret",
            "ENCRYPTION_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.TokenStorage.save")
    @patch("contacts.api.GoogleOAuthClient.refresh_access_token")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_auto_refresh_token(
        self,
        mock_list_contacts,
        mock_refresh_token,
        mock_token_save,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_expired_tokens,
    ):
        """Test auto-refresh when access token is expired."""
        # Mock token storage - expired token
        mock_token_get.return_value = mock_expired_tokens
        mock_is_expired.return_value = True

        # Mock OAuth client refresh
        mock_refresh_token.return_value = {
            "access_token": "ya29.new_access_token",
            "expires_in": 3600,
        }

        # Mock Google People API
        mock_list_contacts.return_value = GOOGLE_FIXTURES["people_api_success"]

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify refresh was called
        mock_refresh_token.assert_called_once_with(mock_expired_tokens["refresh_token"])

        # Verify new token was saved
        mock_token_save.assert_called_once()

        # Verify Google API was called with refreshed token
        mock_list_contacts.assert_called_once()

    @patch("contacts.api.settings.demo_mode", False)
    @patch.dict(
        "os.environ",
        {
            "GOOGLE_CLIENT_ID": "mock_client_id",
            "GOOGLE_CLIENT_SECRET": "mock_client_secret",
            "ENCRYPTION_KEY": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    )
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GoogleOAuthClient.refresh_access_token")
    async def test_list_contacts_refresh_token_revoked(
        self,
        mock_refresh_token,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_expired_tokens,
    ):
        """Test when refresh token has been revoked by user."""
        mock_token_get.return_value = mock_expired_tokens
        mock_is_expired.return_value = True

        # Mock refresh token revoked error
        mock_refresh_token.side_effect = RefreshTokenRevokedError("Refresh token has been revoked")

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"]["code"] == "REFRESH_TOKEN_REVOKED"
        assert "reauthorize" in data["detail"]["action"]


class TestContactsIntegrationErrorHandling:
    """Test suite for error handling scenarios."""

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_unauthorized_error(
        self,
        mock_list_contacts,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_valid_tokens,
    ):
        """Test when Google returns 401 (invalid access token)."""
        mock_token_get.return_value = mock_valid_tokens
        mock_is_expired.return_value = False

        # Mock Google API 401 error
        mock_list_contacts.side_effect = UnauthorizedError("Access token is invalid")

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["detail"]["code"] == "INVALID_ACCESS_TOKEN"

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_quota_exceeded(
        self,
        mock_list_contacts,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_valid_tokens,
    ):
        """Test when Google API quota is exceeded (429)."""
        mock_token_get.return_value = mock_valid_tokens
        mock_is_expired.return_value = False

        # Mock Google API 429 error
        mock_list_contacts.side_effect = QuotaExceededError("Quota exceeded", retry_after=120)

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = response.json()
        assert data["detail"]["code"] == "QUOTA_EXCEEDED"
        assert data["detail"]["retry_after"] == 120
        assert "Retry-After" in response.headers

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_api_unavailable(
        self,
        mock_list_contacts,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_valid_tokens,
    ):
        """Test when Google API is temporarily unavailable (503)."""
        mock_token_get.return_value = mock_valid_tokens
        mock_is_expired.return_value = False

        # Mock Google API 503 error
        mock_list_contacts.side_effect = PeopleAPIUnavailableError("API unavailable")

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["detail"]["code"] == "GOOGLE_API_UNAVAILABLE"

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_timeout(
        self,
        mock_list_contacts,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_valid_tokens,
    ):
        """Test when Google API request times out."""
        mock_token_get.return_value = mock_valid_tokens
        mock_is_expired.return_value = False

        # Mock timeout error
        mock_list_contacts.side_effect = PeopleAPITimeoutError("Request timed out")

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        data = response.json()
        assert data["detail"]["code"] == "GOOGLE_API_TIMEOUT"

    @patch("contacts.api.settings.demo_mode", False)
    @patch("contacts.api.TokenStorage.get")
    @patch("contacts.api.TokenStorage.is_expired")
    @patch("contacts.api.GooglePeopleClient.list_contacts")
    async def test_list_contacts_generic_api_error(
        self,
        mock_list_contacts,
        mock_is_expired,
        mock_token_get,
        test_client,
        test_vehicle_id,
        mock_valid_tokens,
    ):
        """Test when Google API returns other errors (502)."""
        mock_token_get.return_value = mock_valid_tokens
        mock_is_expired.return_value = False

        # Mock generic API error
        mock_list_contacts.side_effect = PeopleAPIError("Unknown error")

        response = test_client.get(
            "/v1/contacts",
            params={"person_fields": "names", "page": 1, "size": 10},
            headers={"X-Vehicle-Id": str(test_vehicle_id)},
        )

        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        data = response.json()
        assert data["detail"]["code"] == "GOOGLE_API_ERROR"
