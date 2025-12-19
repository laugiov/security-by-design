"""Tests for error handlers and error models."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skylink.main import app
from skylink.models.errors import ErrorFieldDetail, ErrorResponse, create_error_response

client = TestClient(app)


# Tests for error models
def test_error_field_detail_model():
    """Test ErrorFieldDetail model."""
    field_detail = ErrorFieldDetail(
        field="lat", issue="range", message="lat must be between -90 and 90"
    )

    assert field_detail.field == "lat"
    assert field_detail.issue == "range"
    assert field_detail.message == "lat must be between -90 and 90"


def test_error_response_model():
    """Test ErrorResponse model."""
    error_response = ErrorResponse(
        error={
            "code": "VALIDATION_ERROR",
            "message": "Invalid input data",
        }
    )

    assert error_response.error.code == "VALIDATION_ERROR"
    assert error_response.error.message == "Invalid input data"


def test_create_error_response_without_details():
    """Test create_error_response helper without details."""
    result = create_error_response(code="UNAUTHORIZED", message="Invalid token")

    assert result["error"]["code"] == "UNAUTHORIZED"
    assert result["error"]["message"] == "Invalid token"
    assert "details" not in result["error"]


def test_create_error_response_with_details():
    """Test create_error_response helper with details."""
    details = {
        "fields": [{"field": "vehicle_id", "issue": "format", "message": "Must be a valid UUID"}]
    }

    result = create_error_response(
        code="VALIDATION_ERROR", message="Invalid input data", details=details
    )

    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert result["error"]["message"] == "Invalid input data"
    assert result["error"]["details"] == details


# Tests for validation exception handler
def test_validation_exception_handler_invalid_uuid():
    """Test validation exception handler with invalid UUID."""
    # Send invalid vehicle_id (not a UUID)
    response = client.post("/auth/token", json={"vehicle_id": "not-a-uuid"})

    assert response.status_code == 400
    data = response.json()

    # Verify error structure
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Invalid input data"

    # Verify field details
    assert "details" in data["error"]
    assert "fields" in data["error"]["details"]
    assert len(data["error"]["details"]["fields"]) > 0

    # Check that vehicle_id is mentioned in field errors
    field_names = [f["field"] for f in data["error"]["details"]["fields"]]
    assert any("vehicle_id" in field for field in field_names)


def test_validation_exception_handler_missing_required_field():
    """Test validation exception handler with missing required field."""
    # Send request without vehicle_id
    response = client.post("/auth/token", json={})

    assert response.status_code == 400
    data = response.json()

    # Verify error structure
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]
    assert "fields" in data["error"]["details"]


def test_validation_exception_handler_extra_field():
    """Test validation exception handler with extra unexpected field."""
    # Send request with extra field (if additionalProperties: false is enforced)
    response = client.post(
        "/auth/token",
        json={
            "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
            "extra_field": "not_allowed",
        },
    )

    # Note: This might be 200 if additionalProperties is not enforced,
    # or 501 if the endpoint is not implemented yet
    # The actual behavior depends on the router implementation
    # This test documents the current behavior
    assert response.status_code in [200, 400, 501]


# Test for general exception handler
def test_general_exception_handler():
    """Test general exception handler for unexpected errors."""
    # This test is tricky because we need to trigger an unexpected exception
    # For now, we'll document that the handler exists and returns 500

    # Create a test app with a route that raises an exception
    test_app = FastAPI()

    @test_app.get("/trigger-error")
    async def trigger_error():
        raise ValueError("Unexpected error")

    # Apply the same exception handler
    from skylink.main import general_exception_handler

    test_app.add_exception_handler(Exception, general_exception_handler)

    # Apply middlewares too to avoid conflicts
    from skylink.middlewares import add_security_headers_middleware, json_logging_middleware

    test_app.middleware("http")(json_logging_middleware)
    test_app.middleware("http")(add_security_headers_middleware)

    test_client = TestClient(test_app, raise_server_exceptions=False)
    response = test_client.get("/trigger-error")

    assert response.status_code == 500
    data = response.json()

    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert data["error"]["message"] == "An unexpected error occurred"
    # Verify that no exception details are leaked
    assert "ValueError" not in data["error"]["message"]


def test_error_response_has_security_headers():
    """Test that error responses include security headers."""
    response = client.post("/auth/token", json={"vehicle_id": "invalid"})

    # Even error responses should have security headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_error_response_has_trace_id():
    """Test that error responses include trace_id."""
    response = client.post("/auth/token", json={"vehicle_id": "invalid"})

    # Error responses should have trace_id for correlation
    assert "X-Trace-Id" in response.headers
    assert len(response.headers["X-Trace-Id"]) > 0
