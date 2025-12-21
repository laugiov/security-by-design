"""
Tests for the SkyLink Audit Logging system.

These tests verify:
- Audit event structure and format
- All event types are correctly logged
- No PII/secrets in audit logs
- Trace ID propagation
"""

import json
import logging
from io import StringIO
from unittest.mock import patch

import pytest

from skylink.audit import AuditLogger, audit_logger, get_audit_logger
from skylink.audit_events import (
    ActorType,
    EventCategory,
    EventOutcome,
    EventSeverity,
    EventType,
    ResourceType,
    EVENT_METADATA,
)


class TestAuditEventTypes:
    """Test audit event type definitions."""

    def test_event_types_defined(self):
        """All expected event types should be defined."""
        expected_types = [
            "AUTH_SUCCESS",
            "AUTH_FAILURE",
            "AUTH_TOKEN_EXPIRED",
            "AUTH_TOKEN_INVALID",
            "MTLS_SUCCESS",
            "MTLS_FAILURE",
            "MTLS_CN_MISMATCH",
            "RATE_LIMIT_EXCEEDED",
            "TELEMETRY_CREATED",
            "TELEMETRY_DUPLICATE",
            "TELEMETRY_CONFLICT",
            "OAUTH_INITIATED",
            "OAUTH_COMPLETED",
            "OAUTH_REVOKED",
            "OAUTH_FAILURE",
            "CONTACTS_ACCESSED",
            "WEATHER_ACCESSED",
            "SERVICE_STARTED",
            "SERVICE_STOPPED",
            "CONFIG_CHANGED",
        ]
        for event_type in expected_types:
            assert hasattr(EventType, event_type), f"Missing event type: {event_type}"

    def test_event_categories_defined(self):
        """All expected categories should be defined."""
        expected = ["AUTHENTICATION", "AUTHORIZATION", "DATA", "SECURITY", "ADMIN", "SYSTEM"]
        for category in expected:
            assert hasattr(EventCategory, category), f"Missing category: {category}"

    def test_severity_levels_defined(self):
        """All expected severity levels should be defined."""
        expected = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        for severity in expected:
            assert hasattr(EventSeverity, severity), f"Missing severity: {severity}"

    def test_event_metadata_complete(self):
        """All event types should have metadata defined."""
        for event_type in EventType:
            assert event_type in EVENT_METADATA, f"Missing metadata for: {event_type}"
            category, severity = EVENT_METADATA[event_type]
            assert isinstance(category, EventCategory)
            assert isinstance(severity, EventSeverity)


class TestAuditLogger:
    """Test AuditLogger class functionality."""

    @pytest.fixture
    def capture_logs(self):
        """Fixture to capture audit log output."""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("audit")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        yield log_capture

        logger.handlers = []

    def test_audit_logger_initialization(self):
        """AuditLogger should initialize with service name."""
        logger = AuditLogger("test-service")
        assert logger.service == "test-service"

    def test_global_audit_logger_exists(self):
        """Global audit_logger should be available."""
        assert audit_logger is not None
        assert audit_logger.service == "gateway"

    def test_get_audit_logger_returns_existing_for_gateway(self):
        """get_audit_logger should return existing logger for gateway."""
        logger = get_audit_logger("gateway")
        assert logger is audit_logger

    def test_get_audit_logger_creates_new_for_other_services(self):
        """get_audit_logger should create new logger for other services."""
        logger = get_audit_logger("telemetry")
        assert logger is not audit_logger
        assert logger.service == "telemetry"

    def test_log_event_structure(self, capture_logs):
        """Logged events should have correct structure."""
        logger = AuditLogger("test")
        logger.logger = logging.getLogger("audit")

        event_id = logger.log(
            event_type=EventType.AUTH_SUCCESS,
            actor_type=ActorType.AIRCRAFT,
            actor_id="test-aircraft-123",
            action="create",
            outcome=EventOutcome.SUCCESS,
            trace_id="trace-abc123",
            ip_address="192.168.1.100",
        )

        log_output = capture_logs.getvalue()
        assert "AUDIT:" in log_output

        # Parse JSON from log output
        json_str = log_output.split("AUDIT: ")[1].strip()
        event = json.loads(json_str)

        # Verify structure
        assert "timestamp" in event
        assert "event_id" in event
        assert event["event_id"] == event_id
        assert event["event_type"] == "AUTH_SUCCESS"
        assert event["event_category"] == "authentication"
        assert event["severity"] == "info"
        assert event["actor"]["type"] == "aircraft"
        assert event["actor"]["id"] == "test-aircraft-123"
        assert event["actor"]["ip"] == "192.168.1.100"
        assert event["action"] == "create"
        assert event["outcome"] == "success"
        assert event["trace_id"] == "trace-abc123"
        assert event["service"] == "test"

    def test_log_returns_event_id(self, capture_logs):
        """log() should return a unique event_id."""
        logger = AuditLogger("test")
        logger.logger = logging.getLogger("audit")

        event_id1 = logger.log(event_type=EventType.AUTH_SUCCESS)
        event_id2 = logger.log(event_type=EventType.AUTH_SUCCESS)

        assert event_id1.startswith("evt_")
        assert event_id2.startswith("evt_")
        assert event_id1 != event_id2

    def test_timestamp_format(self, capture_logs):
        """Timestamps should be ISO 8601 UTC format."""
        logger = AuditLogger("test")
        logger.logger = logging.getLogger("audit")

        logger.log(event_type=EventType.AUTH_SUCCESS)

        log_output = capture_logs.getvalue()
        json_str = log_output.split("AUDIT: ")[1].strip()
        event = json.loads(json_str)

        # Should end with Z for UTC
        assert event["timestamp"].endswith("Z")
        # Should be ISO format
        assert "T" in event["timestamp"]


class TestConvenienceMethods:
    """Test audit logger convenience methods."""

    @pytest.fixture
    def logger_with_capture(self):
        """Fixture providing a logger with captured output."""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(logging.Formatter("%(message)s"))

        audit_log = logging.getLogger("audit")
        audit_log.handlers = []
        audit_log.addHandler(handler)
        audit_log.setLevel(logging.INFO)

        logger = AuditLogger("test")
        logger.logger = audit_log

        return logger, log_capture

    def test_log_auth_success(self, logger_with_capture):
        """log_auth_success should log correct event."""
        logger, capture = logger_with_capture

        event_id = logger.log_auth_success(
            actor_id="aircraft-123",
            ip_address="10.0.0.1",
            trace_id="trace-xyz",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "AUTH_SUCCESS"
        assert event["actor"]["id"] == "aircraft-123"
        assert event["outcome"] == "success"
        assert event["details"]["method"] == "jwt_rs256"

    def test_log_auth_failure(self, logger_with_capture):
        """log_auth_failure should log correct event."""
        logger, capture = logger_with_capture

        logger.log_auth_failure(
            actor_id="aircraft-456",
            reason="invalid_signature",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "AUTH_FAILURE"
        assert event["outcome"] == "failure"
        assert event["details"]["reason"] == "invalid_signature"
        assert event["severity"] == "warning"

    def test_log_rate_limit_exceeded(self, logger_with_capture):
        """log_rate_limit_exceeded should log correct event."""
        logger, capture = logger_with_capture

        logger.log_rate_limit_exceeded(
            actor_id="aircraft-789",
            endpoint="/weather/current",
            limit="60/minute",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "RATE_LIMIT_EXCEEDED"
        assert event["event_category"] == "security"
        assert event["outcome"] == "denied"
        assert event["details"]["endpoint"] == "/weather/current"
        assert event["details"]["limit"] == "60/minute"

    def test_log_telemetry_created(self, logger_with_capture):
        """log_telemetry_created should log correct event."""
        logger, capture = logger_with_capture

        logger.log_telemetry_created(
            actor_id="aircraft-abc",
            event_id="evt-123456",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "TELEMETRY_CREATED"
        assert event["event_category"] == "data"
        assert event["resource"]["type"] == "telemetry"
        assert event["resource"]["id"] == "evt-123456"

    def test_log_telemetry_conflict(self, logger_with_capture):
        """log_telemetry_conflict should log correct event with warning severity."""
        logger, capture = logger_with_capture

        logger.log_telemetry_conflict(
            actor_id="aircraft-def",
            event_id="evt-conflict",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "TELEMETRY_CONFLICT"
        assert event["severity"] == "warning"
        assert event["outcome"] == "denied"

    def test_log_contacts_accessed(self, logger_with_capture):
        """log_contacts_accessed should log correct event."""
        logger, capture = logger_with_capture

        logger.log_contacts_accessed(
            actor_id="aircraft-ghi",
            count=5,
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "CONTACTS_ACCESSED"
        assert event["resource"]["type"] == "contact"
        assert event["details"]["count"] == 5

    def test_log_weather_accessed_rounds_coordinates(self, logger_with_capture):
        """log_weather_accessed should round coordinates for privacy."""
        logger, capture = logger_with_capture

        logger.log_weather_accessed(
            actor_id="aircraft-jkl",
            lat=48.856789,
            lon=2.352345,
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "WEATHER_ACCESSED"
        # Coordinates should be rounded to 2 decimals
        assert event["details"]["lat"] == 48.86
        assert event["details"]["lon"] == 2.35

    def test_log_mtls_cn_mismatch(self, logger_with_capture):
        """log_mtls_cn_mismatch should log both identities."""
        logger, capture = logger_with_capture

        logger.log_mtls_cn_mismatch(
            jwt_sub="aircraft-123",
            cert_cn="aircraft-456",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["event_type"] == "MTLS_CN_MISMATCH"
        assert event["details"]["jwt_sub"] == "aircraft-123"
        assert event["details"]["cert_cn"] == "aircraft-456"
        assert event["outcome"] == "denied"


class TestNoPIIInLogs:
    """Test that no PII or secrets appear in audit logs."""

    @pytest.fixture
    def logger_with_capture(self):
        """Fixture providing a logger with captured output."""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(logging.Formatter("%(message)s"))

        audit_log = logging.getLogger("audit")
        audit_log.handlers = []
        audit_log.addHandler(handler)
        audit_log.setLevel(logging.INFO)

        logger = AuditLogger("test")
        logger.logger = audit_log

        return logger, log_capture

    def test_no_token_in_logs(self, logger_with_capture):
        """JWT tokens should never appear in logs."""
        logger, capture = logger_with_capture

        # Log various events
        logger.log_auth_success(actor_id="aircraft-123")
        logger.log_auth_failure(actor_id="aircraft-456", reason="expired")

        log_output = capture.getvalue()

        # Check for common JWT patterns
        assert "eyJ" not in log_output  # JWT header prefix
        assert "Bearer" not in log_output
        assert "access_token" not in log_output

    def test_no_email_in_logs(self, logger_with_capture):
        """Email addresses should never appear in logs."""
        logger, capture = logger_with_capture

        logger.log_contacts_accessed(actor_id="aircraft-123", count=5)

        log_output = capture.getvalue()

        # Check for email patterns
        assert "@" not in log_output or log_output.count("@") == 0

    def test_no_private_key_in_logs(self, logger_with_capture):
        """Private keys should never appear in logs."""
        logger, capture = logger_with_capture

        logger.log_auth_success(actor_id="aircraft-123")

        log_output = capture.getvalue()

        assert "PRIVATE KEY" not in log_output
        assert "RSA" not in log_output

    def test_only_ids_not_names(self, logger_with_capture):
        """Only IDs should be logged, not names or PII."""
        logger, capture = logger_with_capture

        logger.log_contacts_accessed(
            actor_id="550e8400-e29b-41d4-a716-446655440000",
            count=3,
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        # Actor ID should be a UUID-like string
        assert event["actor"]["id"] == "550e8400-e29b-41d4-a716-446655440000"
        # No name field
        assert "name" not in event["actor"]


class TestTraceIdPropagation:
    """Test trace ID propagation through audit logs."""

    @pytest.fixture
    def logger_with_capture(self):
        """Fixture providing a logger with captured output."""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(logging.Formatter("%(message)s"))

        audit_log = logging.getLogger("audit")
        audit_log.handlers = []
        audit_log.addHandler(handler)
        audit_log.setLevel(logging.INFO)

        logger = AuditLogger("test")
        logger.logger = audit_log

        return logger, log_capture

    def test_trace_id_included_when_provided(self, logger_with_capture):
        """trace_id should be included when provided."""
        logger, capture = logger_with_capture

        logger.log_auth_success(
            actor_id="aircraft-123",
            trace_id="trace-abc123def456",
        )

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["trace_id"] == "trace-abc123def456"

    def test_trace_id_null_when_not_provided(self, logger_with_capture):
        """trace_id should be null when not provided."""
        logger, capture = logger_with_capture

        logger.log_auth_success(actor_id="aircraft-123")

        log_output = capture.getvalue()
        event = json.loads(log_output.split("AUDIT: ")[1].strip())

        assert event["trace_id"] is None
