"""Pydantic schemas for Contacts Service (simplified for MVP demo mode)."""

from typing import Any

from pydantic import BaseModel, Field


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., ge=1, description="Current page number")
    size: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    next_page_token: str | None = Field(None, description="Token for next page (Google API format)")


class ContactsListResponse(BaseModel):
    """Response for GET /v1/contacts.

    Simplified format matching Google People API structure
    but using static fixtures for MVP demo.
    """

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "resourceName": "people/c1001",
                        "names": [{"displayName": "Alice Dupont"}],
                        "emailAddresses": [{"value": "alice.dupont@example.com"}],
                    }
                ],
                "pagination": {"page": 1, "size": 10, "total": 5, "next_page_token": None},
                "next_sync_token": None,
            }
        }
    }

    items: list[dict[str, Any]] = Field(..., description="List of contacts (GooglePerson format)")
    pagination: PaginationInfo
    next_sync_token: str | None = Field(
        None, description="Sync token for incremental updates (not implemented in demo mode)"
    )


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., json_schema_extra={"example": "healthy"})
    service: str = Field(..., json_schema_extra={"example": "contacts"})
