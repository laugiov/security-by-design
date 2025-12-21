"""
SkyLink Audit Logging

Structured audit logging for security-relevant events.
Separate from operational logs, following OWASP recommendations.

Usage:
    from skylink.audit import audit_logger

    audit_logger.log_auth_success(
        actor_id="aircraft-uuid",
        ip_address="192.168.1.1",
        trace_id="abc123"
    )
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from skylink.audit_events import (
    ActorType,
    EventCategory,
    EventOutcome,
    EventSeverity,
    EventType,
    ResourceType,
    EVENT_METADATA,
)


class AuditLogger:
    """
    Structured audit logger for security events.

    Outputs JSON-formatted audit events to a dedicated logger.
    Each event includes: timestamp, event_id, event_type, actor, resource, outcome.

    Security considerations:
    - Never logs tokens, secrets, or credentials
    - Never logs PII (only IDs, not names/emails)
    - Includes trace_id for correlation with request logs
    """

    def __init__(self, service_name: str = "gateway"):
        """Initialize audit logger with service name."""
        self.service = service_name
        self.logger = self._configure_logger()

    def _configure_logger(self) -> logging.Logger:
        """Configure dedicated audit logger with JSON output."""
        logger = logging.getLogger("audit")
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to root logger

        # Only add handler if not already configured
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)

        return logger

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        return f"evt_{uuid.uuid4().hex[:12]}"

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def log(
        self,
        event_type: EventType,
        actor_type: ActorType = ActorType.UNKNOWN,
        actor_id: Optional[str] = None,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None,
        action: str = "access",
        outcome: EventOutcome = EventOutcome.SUCCESS,
        details: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        category_override: Optional[EventCategory] = None,
        severity_override: Optional[EventSeverity] = None,
    ) -> str:
        """
        Log an audit event.

        Args:
            event_type: Type of event (from EventType enum)
            actor_type: Type of actor (aircraft, user, service, system)
            actor_id: Unique identifier of the actor (no PII)
            resource_type: Type of resource being accessed
            resource_id: Unique identifier of the resource
            action: Action performed (create, read, update, delete, access)
            outcome: Result of the action
            details: Additional context (no secrets/PII)
            trace_id: Request trace ID for correlation
            ip_address: Client IP address
            category_override: Override default category
            severity_override: Override default severity

        Returns:
            Generated event_id for correlation
        """
        # Get default category and severity from metadata
        default_category, default_severity = EVENT_METADATA.get(
            event_type, (EventCategory.SYSTEM, EventSeverity.INFO)
        )

        event_id = self._generate_event_id()

        event = {
            "timestamp": self._get_timestamp(),
            "event_id": event_id,
            "event_type": event_type.value,
            "event_category": (category_override or default_category).value,
            "severity": (severity_override or default_severity).value,
            "actor": {
                "type": actor_type.value,
                "id": actor_id,
                "ip": ip_address,
            },
            "resource": {
                "type": resource_type.value if resource_type else None,
                "id": resource_id,
            },
            "action": action,
            "outcome": outcome.value,
            "details": details or {},
            "trace_id": trace_id,
            "service": self.service,
        }

        # Output as single-line JSON with AUDIT prefix for log routing
        self.logger.info(f"AUDIT: {json.dumps(event, separators=(',', ':'))}")

        return event_id

    # Convenience methods for common events

    def log_auth_success(
        self,
        actor_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        method: str = "jwt_rs256",
    ) -> str:
        """Log successful authentication."""
        return self.log(
            event_type=EventType.AUTH_SUCCESS,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.TOKEN,
            action="create",
            outcome=EventOutcome.SUCCESS,
            details={"method": method},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_auth_failure(
        self,
        actor_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        reason: str = "invalid_credentials",
    ) -> str:
        """Log failed authentication attempt."""
        return self.log(
            event_type=EventType.AUTH_FAILURE,
            actor_type=ActorType.AIRCRAFT if actor_id else ActorType.UNKNOWN,
            actor_id=actor_id,
            resource_type=ResourceType.TOKEN,
            action="create",
            outcome=EventOutcome.FAILURE,
            details={"reason": reason},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_token_expired(
        self,
        actor_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log token expiration event."""
        return self.log(
            event_type=EventType.AUTH_TOKEN_EXPIRED,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.TOKEN,
            action="validate",
            outcome=EventOutcome.DENIED,
            details={"reason": "token_expired"},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_token_invalid(
        self,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        reason: str = "invalid_signature",
    ) -> str:
        """Log invalid token event."""
        return self.log(
            event_type=EventType.AUTH_TOKEN_INVALID,
            actor_type=ActorType.UNKNOWN,
            actor_id=None,
            resource_type=ResourceType.TOKEN,
            action="validate",
            outcome=EventOutcome.DENIED,
            details={"reason": reason},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_mtls_success(
        self,
        actor_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        cn: Optional[str] = None,
    ) -> str:
        """Log successful mTLS validation."""
        return self.log(
            event_type=EventType.MTLS_SUCCESS,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.CERTIFICATE,
            action="validate",
            outcome=EventOutcome.SUCCESS,
            details={"cn": cn} if cn else {},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_mtls_failure(
        self,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        reason: str = "certificate_invalid",
    ) -> str:
        """Log mTLS validation failure."""
        return self.log(
            event_type=EventType.MTLS_FAILURE,
            actor_type=ActorType.UNKNOWN,
            actor_id=None,
            resource_type=ResourceType.CERTIFICATE,
            action="validate",
            outcome=EventOutcome.FAILURE,
            details={"reason": reason},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_mtls_cn_mismatch(
        self,
        jwt_sub: str,
        cert_cn: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log mTLS CN vs JWT subject mismatch."""
        return self.log(
            event_type=EventType.MTLS_CN_MISMATCH,
            actor_type=ActorType.UNKNOWN,
            actor_id=None,
            resource_type=ResourceType.CERTIFICATE,
            action="validate",
            outcome=EventOutcome.DENIED,
            details={"jwt_sub": jwt_sub, "cert_cn": cert_cn},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_rate_limit_exceeded(
        self,
        actor_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        limit: Optional[str] = None,
    ) -> str:
        """Log rate limit exceeded event."""
        return self.log(
            event_type=EventType.RATE_LIMIT_EXCEEDED,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            action="access",
            outcome=EventOutcome.DENIED,
            details={"endpoint": endpoint, "limit": limit},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_telemetry_created(
        self,
        actor_id: str,
        event_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log telemetry event creation."""
        return self.log(
            event_type=EventType.TELEMETRY_CREATED,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.TELEMETRY,
            resource_id=event_id,
            action="create",
            outcome=EventOutcome.SUCCESS,
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_telemetry_duplicate(
        self,
        actor_id: str,
        event_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log duplicate telemetry event (idempotent)."""
        return self.log(
            event_type=EventType.TELEMETRY_DUPLICATE,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.TELEMETRY,
            resource_id=event_id,
            action="create",
            outcome=EventOutcome.SUCCESS,
            details={"idempotent": True},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_telemetry_conflict(
        self,
        actor_id: str,
        event_id: str,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log telemetry idempotency conflict."""
        return self.log(
            event_type=EventType.TELEMETRY_CONFLICT,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.TELEMETRY,
            resource_id=event_id,
            action="create",
            outcome=EventOutcome.DENIED,
            details={"reason": "payload_mismatch"},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_contacts_accessed(
        self,
        actor_id: str,
        count: int,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log contacts data access."""
        return self.log(
            event_type=EventType.CONTACTS_ACCESSED,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.CONTACT,
            action="read",
            outcome=EventOutcome.SUCCESS,
            details={"count": count},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_weather_accessed(
        self,
        actor_id: str,
        lat: float,
        lon: float,
        ip_address: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log weather data access."""
        return self.log(
            event_type=EventType.WEATHER_ACCESSED,
            actor_type=ActorType.AIRCRAFT,
            actor_id=actor_id,
            resource_type=ResourceType.WEATHER,
            action="read",
            outcome=EventOutcome.SUCCESS,
            # Round coordinates to 2 decimals for privacy
            details={"lat": round(lat, 2), "lon": round(lon, 2)},
            trace_id=trace_id,
            ip_address=ip_address,
        )

    def log_service_started(self, version: Optional[str] = None) -> str:
        """Log service startup."""
        return self.log(
            event_type=EventType.SERVICE_STARTED,
            actor_type=ActorType.SYSTEM,
            resource_type=ResourceType.SERVICE,
            resource_id=self.service,
            action="start",
            outcome=EventOutcome.SUCCESS,
            details={"version": version} if version else {},
        )

    def log_service_stopped(self, reason: str = "shutdown") -> str:
        """Log service shutdown."""
        return self.log(
            event_type=EventType.SERVICE_STOPPED,
            actor_type=ActorType.SYSTEM,
            resource_type=ResourceType.SERVICE,
            resource_id=self.service,
            action="stop",
            outcome=EventOutcome.SUCCESS,
            details={"reason": reason},
        )


# Global audit logger instance for gateway service
audit_logger = AuditLogger("gateway")


def get_audit_logger(service_name: str = "gateway") -> AuditLogger:
    """Get or create an audit logger for a service."""
    if service_name == "gateway":
        return audit_logger
    return AuditLogger(service_name)
