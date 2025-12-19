"""Google People API client for fetching contacts."""

from typing import Optional

import httpx


class PeopleAPIError(Exception):
    """Base exception for People API errors."""


class UnauthorizedError(PeopleAPIError):
    """Access token is invalid or expired."""


class QuotaExceededError(PeopleAPIError):
    """Google API quota exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        """Initialize with optional retry_after value."""
        super().__init__(message)
        self.retry_after = retry_after or 60  # Default 60 seconds


class PeopleAPIUnavailableError(PeopleAPIError):
    """Google People API is temporarily unavailable."""


class PeopleAPITimeoutError(PeopleAPIError):
    """Request to Google People API timed out."""


class GooglePeopleClient:
    """Client for Google People API to fetch user contacts.

    Handles:
    - Listing contacts with field mask filtering
    - Pagination with pageToken
    - Error handling (401, 429, 503, timeout)
    """

    # Google People API endpoints
    BASE_URL = "https://people.googleapis.com"
    CONNECTIONS_ENDPOINT = "/v1/people/me/connections"

    # Default field mask (names, emails, phones)
    DEFAULT_PERSON_FIELDS = "names,emailAddresses,phoneNumbers"

    # Default pagination
    DEFAULT_PAGE_SIZE = 100  # Max is 2000, but 100 is reasonable default

    def __init__(self, access_token: str, timeout: float = 10.0):
        """Initialize People API client with access token.

        Args:
            access_token: Valid Google OAuth access token
            timeout: Request timeout in seconds (default: 10.0)
        """
        self.access_token = access_token
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def list_contacts(
        self,
        person_fields: Optional[str] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        page_token: Optional[str] = None,
        sync_token: Optional[str] = None,
    ) -> dict:
        """List user contacts from Google People API.

        Args:
            person_fields: Comma-separated field mask (e.g., "names,emailAddresses")
                          If None, uses DEFAULT_PERSON_FIELDS
            page_size: Number of contacts per page (1-2000, default: 100)
            page_token: Token for next page (pagination)
            sync_token: Token for incremental sync (not implemented in MVP)

        Returns:
            Dictionary containing:
                - connections (list): List of contact objects
                - nextPageToken (str, optional): Token for next page
                - totalPeople (int): Total number of contacts
                - totalItems (int): Number of items in this response

        Raises:
            UnauthorizedError: If access token is invalid (401)
            QuotaExceededError: If quota exceeded (429)
            PeopleAPIUnavailableError: If API is unavailable (503)
            PeopleAPITimeoutError: If request times out
            PeopleAPIError: For other API errors
        """
        # Build query parameters
        params = {
            "personFields": person_fields or self.DEFAULT_PERSON_FIELDS,
            "pageSize": min(page_size, 2000),  # Cap at Google's max
        }

        if page_token:
            params["pageToken"] = page_token

        if sync_token:
            params["syncToken"] = sync_token

        # Full URL
        url = f"{self.BASE_URL}{self.CONNECTIONS_ENDPOINT}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, params=params)

                # Handle specific error codes
                if response.status_code == 401:
                    raise UnauthorizedError(
                        "Access token is invalid or expired. Please refresh token."
                    )

                if response.status_code == 429:
                    # Extract retry-after header if present
                    retry_after = response.headers.get("Retry-After")
                    retry_seconds = int(retry_after) if retry_after else 60

                    raise QuotaExceededError(
                        "Google People API quota exceeded. Please retry later.",
                        retry_after=retry_seconds,
                    )

                if response.status_code == 503:
                    raise PeopleAPIUnavailableError(
                        "Google People API is temporarily unavailable. Please retry later."
                    )

                if response.status_code >= 500:
                    raise PeopleAPIError(f"Google People API server error: {response.status_code}")

                # Raise for other HTTP errors
                response.raise_for_status()

                # Return JSON response
                return response.json()

        except httpx.TimeoutException as e:
            raise PeopleAPITimeoutError(
                f"Request to Google People API timed out after {self.timeout}s"
            ) from e

        except httpx.HTTPError as e:
            # Catch other httpx errors not handled above
            if isinstance(e, (UnauthorizedError, QuotaExceededError, PeopleAPIUnavailableError)):
                raise

            raise PeopleAPIError(f"HTTP error while fetching contacts: {e}") from e

        except Exception as e:
            # Catch unexpected errors
            if isinstance(
                e,
                (
                    UnauthorizedError,
                    QuotaExceededError,
                    PeopleAPIUnavailableError,
                    PeopleAPITimeoutError,
                    PeopleAPIError,
                ),
            ):
                raise

            raise PeopleAPIError(f"Unexpected error while fetching contacts: {e}") from e

    def format_contact(self, contact: dict) -> dict:
        """Format a raw Google People API contact into simplified format.

        Args:
            contact: Raw contact object from Google API

        Returns:
            Simplified contact dictionary

        Note:
            This method is optional - clients can use raw contacts directly.
            Provided for convenience if simpler format is needed.
        """
        # Extract primary name
        names = contact.get("names", [])
        primary_name = next((n for n in names if n.get("metadata", {}).get("primary")), {})

        # Extract primary email
        emails = contact.get("emailAddresses", [])
        primary_email = next((e for e in emails if e.get("metadata", {}).get("primary")), {})

        # Extract primary phone
        phones = contact.get("phoneNumbers", [])
        primary_phone = next((p for p in phones if p.get("metadata", {}).get("primary")), {})

        return {
            "id": contact.get("resourceName", ""),
            "display_name": primary_name.get("displayName", ""),
            "given_name": primary_name.get("givenName", ""),
            "family_name": primary_name.get("familyName", ""),
            "email": primary_email.get("value", ""),
            "phone": primary_phone.get("value", ""),
        }
