"""
SkyLink Audit Event Types

Defines all audit event types for security-relevant operations.
Following OWASP Logging Cheat Sheet recommendations.
"""

from enum import Enum


class EventType(str, Enum):
    """Audit event types for security-relevant operations."""

    # Authentication Events
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"

    # mTLS Events
    MTLS_SUCCESS = "MTLS_SUCCESS"
    MTLS_FAILURE = "MTLS_FAILURE"
    MTLS_CN_MISMATCH = "MTLS_CN_MISMATCH"

    # Rate Limiting Events
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Telemetry Events
    TELEMETRY_CREATED = "TELEMETRY_CREATED"
    TELEMETRY_DUPLICATE = "TELEMETRY_DUPLICATE"
    TELEMETRY_CONFLICT = "TELEMETRY_CONFLICT"

    # OAuth Events (Contacts Service)
    OAUTH_INITIATED = "OAUTH_INITIATED"
    OAUTH_COMPLETED = "OAUTH_COMPLETED"
    OAUTH_REVOKED = "OAUTH_REVOKED"
    OAUTH_FAILURE = "OAUTH_FAILURE"

    # Data Access Events
    CONTACTS_ACCESSED = "CONTACTS_ACCESSED"
    WEATHER_ACCESSED = "WEATHER_ACCESSED"

    # Authorization Events (RBAC)
    AUTHZ_SUCCESS = "AUTHZ_SUCCESS"
    AUTHZ_FAILURE = "AUTHZ_FAILURE"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REVOKED = "ROLE_REVOKED"

    # System Events
    SERVICE_STARTED = "SERVICE_STARTED"
    SERVICE_STOPPED = "SERVICE_STOPPED"
    CONFIG_CHANGED = "CONFIG_CHANGED"


class EventCategory(str, Enum):
    """Categories for grouping audit events."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA = "data"
    SECURITY = "security"
    ADMIN = "admin"
    SYSTEM = "system"


class EventSeverity(str, Enum):
    """Severity levels for audit events."""

    INFO = "info"  # Normal operations
    WARNING = "warning"  # Suspicious activity
    ERROR = "error"  # Security issues
    CRITICAL = "critical"  # Immediate attention required


class EventOutcome(str, Enum):
    """Outcome of the audited action."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


class ActorType(str, Enum):
    """Types of actors in audit events."""

    AIRCRAFT = "aircraft"
    USER = "user"
    SERVICE = "service"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ResourceType(str, Enum):
    """Types of resources in audit events."""

    TOKEN = "token"
    TELEMETRY = "telemetry"
    CONTACT = "contact"
    WEATHER = "weather"
    CERTIFICATE = "certificate"
    CONFIG = "config"
    SERVICE = "service"


# Event type to category/severity mapping
EVENT_METADATA = {
    EventType.AUTH_SUCCESS: (EventCategory.AUTHENTICATION, EventSeverity.INFO),
    EventType.AUTH_FAILURE: (EventCategory.AUTHENTICATION, EventSeverity.WARNING),
    EventType.AUTH_TOKEN_EXPIRED: (EventCategory.AUTHENTICATION, EventSeverity.INFO),
    EventType.AUTH_TOKEN_INVALID: (EventCategory.AUTHENTICATION, EventSeverity.WARNING),
    EventType.MTLS_SUCCESS: (EventCategory.AUTHENTICATION, EventSeverity.INFO),
    EventType.MTLS_FAILURE: (EventCategory.AUTHENTICATION, EventSeverity.WARNING),
    EventType.MTLS_CN_MISMATCH: (EventCategory.AUTHENTICATION, EventSeverity.WARNING),
    EventType.RATE_LIMIT_EXCEEDED: (EventCategory.SECURITY, EventSeverity.WARNING),
    EventType.TELEMETRY_CREATED: (EventCategory.DATA, EventSeverity.INFO),
    EventType.TELEMETRY_DUPLICATE: (EventCategory.DATA, EventSeverity.INFO),
    EventType.TELEMETRY_CONFLICT: (EventCategory.DATA, EventSeverity.WARNING),
    EventType.OAUTH_INITIATED: (EventCategory.AUTHENTICATION, EventSeverity.INFO),
    EventType.OAUTH_COMPLETED: (EventCategory.AUTHENTICATION, EventSeverity.INFO),
    EventType.OAUTH_REVOKED: (EventCategory.AUTHENTICATION, EventSeverity.INFO),
    EventType.OAUTH_FAILURE: (EventCategory.AUTHENTICATION, EventSeverity.WARNING),
    EventType.CONTACTS_ACCESSED: (EventCategory.DATA, EventSeverity.INFO),
    EventType.WEATHER_ACCESSED: (EventCategory.DATA, EventSeverity.INFO),
    EventType.AUTHZ_SUCCESS: (EventCategory.AUTHORIZATION, EventSeverity.INFO),
    EventType.AUTHZ_FAILURE: (EventCategory.AUTHORIZATION, EventSeverity.WARNING),
    EventType.ROLE_ASSIGNED: (EventCategory.AUTHORIZATION, EventSeverity.INFO),
    EventType.ROLE_REVOKED: (EventCategory.AUTHORIZATION, EventSeverity.WARNING),
    EventType.SERVICE_STARTED: (EventCategory.SYSTEM, EventSeverity.INFO),
    EventType.SERVICE_STOPPED: (EventCategory.SYSTEM, EventSeverity.INFO),
    EventType.CONFIG_CHANGED: (EventCategory.ADMIN, EventSeverity.WARNING),
}
