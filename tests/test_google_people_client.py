"""Tests for Google People API client."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from contacts.google_people import (
    GooglePeopleClient,
    PeopleAPITimeoutError,
    PeopleAPIUnavailableError,
    QuotaExceededError,
    UnauthorizedError,
)


@pytest.fixture
def google_fixtures():
    """Load Google API response fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "google_responses.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture
def people_client():
    """Create People API client with test access token."""
    return GooglePeopleClient(access_token="test_access_token_123", timeout=10.0)


class TestGooglePeopleClientInit:
    """Test GooglePeopleClient initialization."""

    def test_init_with_access_token(self):
        """Should initialize with access token."""
        client = GooglePeopleClient(access_token="my_token_123")

        assert client.access_token == "my_token_123"
        assert client.headers["Authorization"] == "Bearer my_token_123"
        assert client.timeout == 10.0  # default

    def test_init_with_custom_timeout(self):
        """Should accept custom timeout."""
        client = GooglePeopleClient(access_token="token", timeout=5.0)

        assert client.timeout == 5.0


class TestListContacts:
    """Test list_contacts method."""

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_success(self, mock_async_client, people_client, google_fixtures):
        """Should successfully fetch contacts."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_fixtures["people_api_success"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Fetch contacts
        result = await people_client.list_contacts(person_fields="names,emailAddresses")

        # Assertions
        assert "connections" in result
        assert len(result["connections"]) == 2
        assert result["connections"][0]["names"][0]["displayName"] == "Alice Dupont"
        assert result["totalPeople"] == 2

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_empty(self, mock_async_client, people_client, google_fixtures):
        """Should handle empty contact list."""
        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_fixtures["people_api_empty"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Fetch contacts
        result = await people_client.list_contacts()

        # Assertions
        assert result["connections"] == []
        assert result["totalPeople"] == 0

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_with_pagination(
        self, mock_async_client, people_client, google_fixtures
    ):
        """Should handle pagination with nextPageToken."""
        # Mock paginated response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_fixtures["people_api_with_pagination"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Fetch contacts
        result = await people_client.list_contacts(page_size=1)

        # Assertions
        assert "nextPageToken" in result
        assert result["nextPageToken"] == "CAoQAhiAgICAqIev5wIyCggBEAIYAiABKAE"
        assert len(result["connections"]) == 1

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_unauthorized(
        self, mock_async_client, people_client, google_fixtures
    ):
        """Should raise UnauthorizedError for invalid access token (401)."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = google_fixtures["people_api_error_unauthorized"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Should raise UnauthorizedError
        with pytest.raises(UnauthorizedError, match="invalid or expired"):
            await people_client.list_contacts()

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_quota_exceeded(
        self, mock_async_client, people_client, google_fixtures
    ):
        """Should raise QuotaExceededError for rate limit (429)."""
        # Mock 429 response with Retry-After header
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "120"}
        mock_response.json.return_value = google_fixtures["people_api_error_quota_exceeded"]

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Should raise QuotaExceededError
        with pytest.raises(QuotaExceededError, match="quota exceeded") as exc_info:
            await people_client.list_contacts()

        # Check retry_after value
        assert exc_info.value.retry_after == 120

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_api_unavailable(
        self, mock_async_client, people_client, google_fixtures
    ):
        """Should raise PeopleAPIUnavailableError for 503."""
        # Mock 503 response
        mock_response = Mock()
        mock_response.status_code = 503

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Should raise PeopleAPIUnavailableError
        with pytest.raises(PeopleAPIUnavailableError, match="temporarily unavailable"):
            await people_client.list_contacts()

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_timeout(self, mock_async_client, people_client):
        """Should raise PeopleAPITimeoutError on timeout."""
        # Mock timeout exception
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value = mock_context

        # Should raise PeopleAPITimeoutError
        with pytest.raises(PeopleAPITimeoutError, match="timed out"):
            await people_client.list_contacts()

    @pytest.mark.asyncio
    @patch("contacts.google_people.httpx.AsyncClient")
    async def test_list_contacts_caps_page_size(
        self, mock_async_client, people_client, google_fixtures
    ):
        """Should cap page_size at Google's maximum (2000)."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = google_fixtures["people_api_empty"]

        mock_get = AsyncMock(return_value=mock_response)
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = mock_get
        mock_async_client.return_value = mock_context

        # Request with page_size > 2000
        await people_client.list_contacts(page_size=5000)

        # Check that pageSize was capped to 2000
        call_args = mock_get.call_args
        params = call_args.kwargs["params"]
        assert params["pageSize"] == 2000


class TestFormatContact:
    """Test format_contact method."""

    def test_format_contact_complete(self, people_client, google_fixtures):
        """Should format contact with all fields."""
        raw_contact = google_fixtures["people_api_success"]["connections"][0]

        formatted = people_client.format_contact(raw_contact)

        assert formatted["id"] == "people/c1234567890"
        assert formatted["display_name"] == "Alice Dupont"
        assert formatted["given_name"] == "Alice"
        assert formatted["family_name"] == "Dupont"
        assert formatted["email"] == "alice.dupont@example.com"
        assert formatted["phone"] == "+33 6 12 34 56 78"

    def test_format_contact_partial(self, people_client, google_fixtures):
        """Should format contact with missing fields."""
        raw_contact = google_fixtures["people_api_success"]["connections"][1]

        formatted = people_client.format_contact(raw_contact)

        assert formatted["id"] == "people/c9876543210"
        assert formatted["display_name"] == "Bob Martin"
        assert formatted["email"] == "bob.martin@example.com"
        assert formatted["phone"] == ""  # No phone in fixture
