"""Standard error models for SkyLink API Gateway.

This module provides standardized error responses conforming to OpenAPI specs.
All errors follow the common Error schema defined in openapi/common.yaml.

Error codes:
- VALIDATION_ERROR: Invalid input data
- UNAUTHORIZED: Invalid or expired JWT token
- FORBIDDEN: Insufficient permissions
- RATE_LIMIT_EXCEEDED: Too many requests
- PROVIDER_UNAVAILABLE: External service unavailable
- INTERNAL_ERROR: Unexpected server error
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ErrorFieldDetail(BaseModel):
    """Detailed validation error for a specific field."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field": "lat",
                "issue": "range",
                "message": "lat must be between -90 and 90",
            }
        }
    )

    field: str = Field(..., description="Name of the field that failed validation")
    issue: str = Field(..., description="Type of validation issue")
    message: str = Field(..., description="Human-readable error message")


class ErrorDetails(BaseModel):
    """Optional structured details for validation errors."""

    fields: Optional[list[ErrorFieldDetail]] = Field(
        None, description="Per-field validation issues"
    )


class ErrorObject(BaseModel):
    """Inner error object containing code, message, and optional details."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input data",
            }
        }
    )

    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["VALIDATION_ERROR", "UNAUTHORIZED", "RATE_LIMIT_EXCEEDED"],
    )
    message: str = Field(..., description="Human-readable error message")
    details: Optional[ErrorDetails] = Field(None, description="Optional structured details")


class ErrorResponse(BaseModel):
    """Standard error envelope used across all services.

    This matches the Error schema in openapi/common.yaml.
    All API errors should use this format for consistency.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input data",
                }
            }
        }
    )

    error: ErrorObject = Field(..., description="Error details")


def create_error_response(
    code: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create a standard error response dict.

    Args:
        code: Machine-readable error code
        message: Human-readable error message
        details: Optional structured details

    Returns:
        dict: Error response conforming to ErrorResponse schema
    """
    error_obj: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }

    if details:
        error_obj["error"]["details"] = details

    return error_obj
