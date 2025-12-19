"""Tests for middlewares module."""

import json

from fastapi.testclient import TestClient

from skylink.main import app

client = TestClient(app)


def test_security_headers_middleware():
    """Test that security headers are added to all responses."""
    response = client.get("/health")

    # ZAP 10021 - X-Content-Type-Options
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    # Anti-clickjacking
    assert response.headers["X-Frame-Options"] == "DENY"

    # ZAP 10049 - Cache control
    assert "no-store" in response.headers["Cache-Control"]
    assert "no-cache" in response.headers["Cache-Control"]

    # ZAP 90004 - Spectre isolation
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"

    # Bonus headers
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "geolocation=()" in response.headers["Permissions-Policy"]


def test_json_logging_middleware_generates_trace_id(capsys):
    """Test that JSON logging middleware generates trace_id."""
    response = client.get("/health")

    # Verify trace_id is added to response headers
    assert "X-Trace-Id" in response.headers
    trace_id = response.headers["X-Trace-Id"]
    assert len(trace_id) > 0

    # Verify JSON log output
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split("\n") if line]

    # Find the log line for this request
    log_found = False
    for line in log_lines:
        try:
            log_entry = json.loads(line)
            if log_entry.get("trace_id") == trace_id:
                log_found = True
                assert log_entry["service"] == "gateway"
                assert log_entry["method"] == "GET"
                assert log_entry["path"] == "/health"
                assert log_entry["status"] == 200
                assert "duration_ms" in log_entry
                assert isinstance(log_entry["duration_ms"], (int, float))
                assert "timestamp" in log_entry
                break
        except json.JSONDecodeError:
            continue

    assert log_found, f"Log entry with trace_id {trace_id} not found"


def test_json_logging_middleware_propagates_trace_id(capsys):
    """Test that JSON logging middleware propagates existing trace_id."""
    custom_trace_id = "test-trace-123"

    response = client.get("/health", headers={"X-Trace-Id": custom_trace_id})

    # Verify trace_id is propagated in response
    assert response.headers["X-Trace-Id"] == custom_trace_id

    # Verify JSON log contains the same trace_id
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split("\n") if line]

    log_found = False
    for line in log_lines:
        try:
            log_entry = json.loads(line)
            if log_entry.get("trace_id") == custom_trace_id:
                log_found = True
                break
        except json.JSONDecodeError:
            continue

    assert log_found, f"Log entry with custom trace_id {custom_trace_id} not found"


def test_json_logging_middleware_logs_different_methods(capsys):
    """Test that JSON logging works for different HTTP methods."""
    # Test POST request
    response = client.post(
        "/auth/token",
        json={"vehicle_id": "550e8400-e29b-41d4-a716-446655440000"},
    )

    trace_id = response.headers.get("X-Trace-Id")
    assert trace_id is not None

    # Verify log entry
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split("\n") if line]

    log_found = False
    for line in log_lines:
        try:
            log_entry = json.loads(line)
            if log_entry.get("trace_id") == trace_id:
                log_found = True
                assert log_entry["method"] == "POST"
                assert log_entry["path"] == "/auth/token"
                break
        except json.JSONDecodeError:
            continue

    assert log_found


def test_json_logging_middleware_logs_error_status(capsys):
    """Test that JSON logging captures error status codes."""
    response = client.get("/nonexistent")

    trace_id = response.headers.get("X-Trace-Id")
    assert trace_id is not None

    # Verify log entry captures 404 status
    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split("\n") if line]

    log_found = False
    for line in log_lines:
        try:
            log_entry = json.loads(line)
            if log_entry.get("trace_id") == trace_id:
                log_found = True
                assert log_entry["status"] == 404
                break
        except json.JSONDecodeError:
            continue

    assert log_found


def test_json_log_structure_is_valid(capsys):
    """Test that JSON logs have valid structure."""
    response = client.get("/health")
    trace_id = response.headers["X-Trace-Id"]

    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.strip().split("\n") if line]

    for line in log_lines:
        try:
            log_entry = json.loads(line)
            if log_entry.get("trace_id") == trace_id:
                # Verify required fields
                required_fields = [
                    "timestamp",
                    "service",
                    "trace_id",
                    "method",
                    "path",
                    "status",
                    "duration_ms",
                ]
                for field in required_fields:
                    assert field in log_entry, f"Missing field: {field}"

                # Verify timestamp format (ISO 8601 with Z)
                assert log_entry["timestamp"].endswith("Z")

                # Verify duration_ms is positive
                assert log_entry["duration_ms"] > 0

                break
        except json.JSONDecodeError:
            continue
