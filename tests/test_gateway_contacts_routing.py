"""Tests for Gateway → Contacts routing (MR #7)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from skylink.auth import create_access_token
from skylink.main import app

client = TestClient(app)

# Valid JWT token for testing
VALID_VEHICLE_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def valid_token():
    """Fixture providing a valid JWT token."""
    return create_access_token(VALID_VEHICLE_ID)


class TestContactsRouting:
    """Test contacts routing from gateway to service."""

    def test_list_contacts_without_auth_returns_401(self):
        """GET /contacts/ without auth should return 401."""
        response = client.get("/contacts/?person_fields=names")
        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    def test_list_contacts_with_invalid_token_returns_401(self):
        """GET /contacts/ with invalid token should return 401."""
        response = client.get(
            "/contacts/?person_fields=names", headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401

    @patch("skylink.routers.contacts.httpx.AsyncClient")
    def test_list_contacts_proxies_successfully(self, mock_async_client, valid_token):
        """GET /contacts/ should proxy to contacts service with valid auth."""
        from unittest.mock import Mock

        # Mock successful response from contacts service
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{"resourceName": "people/c1001", "names": [{"displayName": "Alice"}]}],
            "pagination": {"page": 1, "size": 10, "total": 1, "next_page_token": None},
            "next_sync_token": None,
        }

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        # Make authenticated request
        response = client.get(
            "/contacts/?person_fields=names", headers={"Authorization": f"Bearer {valid_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data

    @patch("skylink.routers.contacts.httpx.AsyncClient")
    def test_list_contacts_forwards_query_params(self, mock_async_client, valid_token):
        """GET /contacts/ should forward query parameters to service."""
        from unittest.mock import Mock

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [],
            "pagination": {"page": 2, "size": 5, "total": 0, "next_page_token": None},
            "next_sync_token": None,
        }

        mock_context = AsyncMock()
        mock_get = AsyncMock(return_value=mock_response)
        mock_context.__aenter__.return_value.get = mock_get
        mock_async_client.return_value = mock_context

        # Request with pagination params
        response = client.get(
            "/contacts/?person_fields=names&page=2&size=5",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

        assert response.status_code == 200
        # Verify params were forwarded
        call_args = mock_get.call_args
        assert call_args[1]["params"]["page"] == 2
        assert call_args[1]["params"]["size"] == 5
        assert call_args[1]["params"]["person_fields"] == "names"

    @patch("skylink.routers.contacts.httpx.AsyncClient")
    def test_list_contacts_handles_timeout(self, mock_async_client, valid_token):
        """GET /contacts/ should return 504 on service timeout."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        mock_async_client.return_value = mock_context

        response = client.get(
            "/contacts/?person_fields=names", headers={"Authorization": f"Bearer {valid_token}"}
        )

        assert response.status_code == 504
        assert "timeout" in response.json()["detail"].lower()

    @patch("skylink.routers.contacts.httpx.AsyncClient")
    def test_list_contacts_handles_service_error(self, mock_async_client, valid_token):
        """GET /contacts/ should return 502 on service error."""
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(side_effect=httpx.HTTPError("Error"))
        mock_async_client.return_value = mock_context

        response = client.get(
            "/contacts/?person_fields=names", headers={"Authorization": f"Bearer {valid_token}"}
        )

        assert response.status_code == 502
        assert "unavailable" in response.json()["detail"].lower()

    @patch("skylink.routers.contacts.httpx.AsyncClient")
    def test_list_contacts_forwards_service_errors(self, mock_async_client, valid_token):
        """GET /contacts/ should forward error status codes from service."""
        from unittest.mock import Mock

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid parameter"

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_async_client.return_value = mock_context

        response = client.get(
            "/contacts/?person_fields=invalid", headers={"Authorization": f"Bearer {valid_token}"}
        )

        assert response.status_code == 400
        assert "Contacts service error" in response.json()["detail"]
