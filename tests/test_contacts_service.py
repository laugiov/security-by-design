"""Tests for Contacts Service (MR #6)."""

from fastapi.testclient import TestClient

from contacts.fixtures import get_contacts_fixtures
from contacts.main import app

client = TestClient(app)


class TestContactsHealth:
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        """Health check should return 200 with status healthy."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "contacts"

    def test_root_returns_service_info(self):
        """Root endpoint should return service information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "contacts"
        assert "version" in data
        assert data["status"] == "running"
        assert "mode" in data


class TestContactsList:
    """Test contacts list endpoint."""

    def test_list_contacts_requires_person_fields(self):
        """GET /v1/contacts should require person_fields parameter."""
        response = client.get("/v1/contacts")

        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data

    def test_list_contacts_default_pagination(self):
        """GET /v1/contacts should return first page with default size."""
        response = client.get("/v1/contacts?person_fields=names,emailAddresses")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)

        # Check pagination metadata
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["size"] == 10
        assert pagination["total"] == 5  # We have 5 fixtures
        assert pagination["next_page_token"] is None  # Only 1 page with size=10

    def test_list_contacts_returns_all_fixtures(self):
        """GET /v1/contacts should return all 5 fixture contacts."""
        response = client.get("/v1/contacts?person_fields=names&page=1&size=10")

        assert response.status_code == 200
        data = response.json()

        # Should return all 5 contacts
        assert len(data["items"]) == 5
        assert data["pagination"]["total"] == 5

        # Verify fixture format
        first_contact = data["items"][0]
        assert "resourceName" in first_contact
        assert "names" in first_contact
        assert "emailAddresses" in first_contact

    def test_list_contacts_pagination_page_1_size_2(self):
        """Test pagination with page=1, size=2."""
        response = client.get("/v1/contacts?person_fields=names&page=1&size=2")

        assert response.status_code == 200
        data = response.json()

        # Should return 2 contacts
        assert len(data["items"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["size"] == 2
        assert data["pagination"]["total"] == 5

        # Should have next page
        assert data["pagination"]["next_page_token"] == "page_2"  # nosec B105 (pagination token)

    def test_list_contacts_pagination_page_2_size_2(self):
        """Test pagination with page=2, size=2."""
        response = client.get("/v1/contacts?person_fields=names&page=2&size=2")

        assert response.status_code == 200
        data = response.json()

        # Should return 2 contacts (contacts 3-4)
        assert len(data["items"]) == 2
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["size"] == 2

        # Should have next page (page 3 has 1 contact)
        assert data["pagination"]["next_page_token"] == "page_3"  # nosec B105 (pagination token)

    def test_list_contacts_pagination_last_page(self):
        """Test last page returns remaining contacts and no next token."""
        response = client.get("/v1/contacts?person_fields=names&page=3&size=2")

        assert response.status_code == 200
        data = response.json()

        # Should return 1 contact (the 5th one)
        assert len(data["items"]) == 1
        assert data["pagination"]["page"] == 3
        assert data["pagination"]["total"] == 5

        # No next page
        assert data["pagination"]["next_page_token"] is None

    def test_list_contacts_pagination_beyond_available(self):
        """Test requesting page beyond available data returns empty."""
        response = client.get("/v1/contacts?person_fields=names&page=10&size=10")

        assert response.status_code == 200
        data = response.json()

        # Should return empty list
        assert len(data["items"]) == 0
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["next_page_token"] is None

    def test_list_contacts_invalid_page_number(self):
        """Test page number validation (must be >= 1)."""
        response = client.get("/v1/contacts?person_fields=names&page=0")

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    def test_list_contacts_invalid_page_size_too_small(self):
        """Test size validation (must be >= 1)."""
        response = client.get("/v1/contacts?person_fields=names&size=0")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_list_contacts_invalid_page_size_too_large(self):
        """Test size validation (must be <= 100)."""
        response = client.get("/v1/contacts?person_fields=names&size=101")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_list_contacts_max_page_size(self):
        """Test maximum allowed page size (100)."""
        response = client.get("/v1/contacts?person_fields=names&size=100")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["size"] == 100

    def test_list_contacts_fixture_data_structure(self):
        """Verify fixtures match expected Google Person format."""
        fixtures = get_contacts_fixtures()

        assert len(fixtures) == 5

        # Check first fixture structure
        contact = fixtures[0]
        assert contact["resourceName"] == "people/c1001"
        assert "etag" in contact
        assert "names" in contact
        assert len(contact["names"]) > 0
        assert "displayName" in contact["names"][0]
        assert "emailAddresses" in contact
        assert len(contact["emailAddresses"]) > 0
        assert "value" in contact["emailAddresses"][0]

    def test_list_contacts_no_sync_token_in_demo_mode(self):
        """Demo mode should not return sync_token."""
        response = client.get("/v1/contacts?person_fields=names")

        assert response.status_code == 200
        data = response.json()

        # Sync token should be None in demo mode
        assert data.get("next_sync_token") is None

    def test_list_contacts_person_fields_accepted_but_not_filtered(self):
        """person_fields parameter is required but doesn't filter in demo mode."""
        # Request with minimal fields
        response1 = client.get("/v1/contacts?person_fields=names")

        # Request with all fields
        response2 = client.get(
            "/v1/contacts?person_fields=names,emailAddresses,phoneNumbers,photos,organizations"
        )

        # Both should return same data (no filtering in demo)
        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Should return same number of contacts with same structure
        assert len(data1["items"]) == len(data2["items"])
        assert data1["items"][0]["resourceName"] == data2["items"][0]["resourceName"]
