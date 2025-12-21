# SkyLink Audit Logging Guide

> **Structured audit logging for security-relevant events**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Event Schema](#3-event-schema)
4. [Event Types](#4-event-types)
5. [Integration](#5-integration)
6. [Viewing Audit Logs](#6-viewing-audit-logs)
7. [Compliance](#7-compliance)
8. [Best Practices](#8-best-practices)

---

## 1. Overview

SkyLink implements a dedicated audit logging system separate from operational logs. Audit logs track security-relevant events for:

- **Compliance**: SOC 2, GDPR data access tracking
- **Forensics**: Security incident investigation
- **Monitoring**: Real-time security alerting (via log aggregation)

### Key Principles

| Principle | Implementation |
|-----------|----------------|
| **No PII** | Only IDs logged, never names/emails |
| **No Secrets** | Tokens, keys, passwords never logged |
| **Trace Correlation** | trace_id links to request logs |
| **Structured Format** | JSON for machine parsing |
| **Immutable** | Events cannot be modified after creation |

---

## 2. Quick Start

### Viewing Audit Logs

```bash
# Start the stack
docker compose up -d

# Follow audit logs (filter by AUDIT prefix)
docker compose logs -f gateway | grep "AUDIT:"

# Generate some events
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"aircraft_id": "550e8400-e29b-41d4-a716-446655440000"}'
```

### Example Audit Event

```json
{
  "timestamp": "2025-12-21T15:30:00.123Z",
  "event_id": "evt_a1b2c3d4e5f6",
  "event_type": "AUTH_SUCCESS",
  "event_category": "authentication",
  "severity": "info",
  "actor": {
    "type": "aircraft",
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "ip": "192.168.1.100"
  },
  "resource": {
    "type": "token",
    "id": null
  },
  "action": "create",
  "outcome": "success",
  "details": {
    "method": "jwt_rs256"
  },
  "trace_id": "abc123def456",
  "service": "gateway"
}
```

---

## 3. Event Schema

### Base Structure

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 UTC timestamp |
| `event_id` | string | Unique event identifier (evt_xxxx) |
| `event_type` | string | Event type (see Section 4) |
| `event_category` | string | Category grouping |
| `severity` | string | info, warning, error, critical |
| `actor` | object | Who performed the action |
| `resource` | object | What was accessed/modified |
| `action` | string | create, read, update, delete, access, validate |
| `outcome` | string | success, failure, denied, error |
| `details` | object | Additional context (varies by event) |
| `trace_id` | string | Request correlation ID |
| `service` | string | Service that generated the event |

### Actor Object

```json
{
  "type": "aircraft|user|service|system|unknown",
  "id": "unique-identifier",
  "ip": "192.168.1.100"
}
```

### Resource Object

```json
{
  "type": "token|telemetry|contact|weather|certificate|config|service",
  "id": "resource-identifier"
}
```

---

## 4. Event Types

### Authentication Events

| Event Type | Severity | Description |
|------------|----------|-------------|
| `AUTH_SUCCESS` | info | JWT token issued successfully |
| `AUTH_FAILURE` | warning | Token generation failed |
| `AUTH_TOKEN_EXPIRED` | info | Token validation - expired |
| `AUTH_TOKEN_INVALID` | warning | Token validation - invalid signature |

### mTLS Events

| Event Type | Severity | Description |
|------------|----------|-------------|
| `MTLS_SUCCESS` | info | mTLS certificate validated |
| `MTLS_FAILURE` | warning | mTLS certificate invalid |
| `MTLS_CN_MISMATCH` | warning | Certificate CN != JWT subject |

### Authorization Events (RBAC)

| Event Type | Severity | Description |
|------------|----------|-------------|
| `AUTHZ_SUCCESS` | info | Permission granted |
| `AUTHZ_FAILURE` | warning | Permission denied (403) |

### Security Events

| Event Type | Severity | Description |
|------------|----------|-------------|
| `RATE_LIMIT_EXCEEDED` | warning | Rate limit triggered |

### Data Events

| Event Type | Severity | Description |
|------------|----------|-------------|
| `TELEMETRY_CREATED` | info | New telemetry event ingested |
| `TELEMETRY_DUPLICATE` | info | Duplicate event (idempotent) |
| `TELEMETRY_CONFLICT` | warning | Same ID, different payload |
| `CONTACTS_ACCESSED` | info | Contacts data retrieved |
| `WEATHER_ACCESSED` | info | Weather data retrieved |

### OAuth Events

| Event Type | Severity | Description |
|------------|----------|-------------|
| `OAUTH_INITIATED` | info | OAuth flow started |
| `OAUTH_COMPLETED` | info | OAuth tokens received |
| `OAUTH_REVOKED` | info | OAuth tokens revoked |
| `OAUTH_FAILURE` | warning | OAuth flow failed |

### System Events

| Event Type | Severity | Description |
|------------|----------|-------------|
| `SERVICE_STARTED` | info | Service started |
| `SERVICE_STOPPED` | info | Service stopped |
| `CONFIG_CHANGED` | warning | Configuration modified |

---

## 5. Integration

### Using the Audit Logger

```python
from skylink.audit import audit_logger

# Log authentication success
audit_logger.log_auth_success(
    actor_id="aircraft-uuid",
    ip_address="192.168.1.100",
    trace_id="trace-abc123",
)

# Log rate limit exceeded
audit_logger.log_rate_limit_exceeded(
    actor_id="aircraft-uuid",
    endpoint="/weather/current",
    limit="60/minute",
    trace_id="trace-abc123",
)

# Log data access
audit_logger.log_contacts_accessed(
    actor_id="aircraft-uuid",
    count=5,
    trace_id="trace-abc123",
)
```

### Convenience Methods

| Method | Event Type |
|--------|------------|
| `log_auth_success()` | AUTH_SUCCESS |
| `log_auth_failure()` | AUTH_FAILURE |
| `log_token_expired()` | AUTH_TOKEN_EXPIRED |
| `log_token_invalid()` | AUTH_TOKEN_INVALID |
| `log_mtls_success()` | MTLS_SUCCESS |
| `log_mtls_failure()` | MTLS_FAILURE |
| `log_mtls_cn_mismatch()` | MTLS_CN_MISMATCH |
| `log_authz_success()` | AUTHZ_SUCCESS |
| `log_authz_failure()` | AUTHZ_FAILURE |
| `log_rate_limit_exceeded()` | RATE_LIMIT_EXCEEDED |
| `log_telemetry_created()` | TELEMETRY_CREATED |
| `log_telemetry_duplicate()` | TELEMETRY_DUPLICATE |
| `log_telemetry_conflict()` | TELEMETRY_CONFLICT |
| `log_contacts_accessed()` | CONTACTS_ACCESSED |
| `log_weather_accessed()` | WEATHER_ACCESSED |
| `log_service_started()` | SERVICE_STARTED |
| `log_service_stopped()` | SERVICE_STOPPED |

### Generic Logging

```python
from skylink.audit import audit_logger
from skylink.audit_events import EventType, ActorType, EventOutcome

audit_logger.log(
    event_type=EventType.CONFIG_CHANGED,
    actor_type=ActorType.USER,
    actor_id="admin-123",
    action="update",
    outcome=EventOutcome.SUCCESS,
    details={"setting": "rate_limit", "old": 60, "new": 100},
)
```

---

## 6. Viewing Audit Logs

### Docker Compose

```bash
# Real-time audit logs
docker compose logs -f gateway | grep "AUDIT:"

# Count events by type
docker compose logs gateway 2>/dev/null \
  | grep "AUDIT:" \
  | jq -r '.event_type' \
  | sort | uniq -c
```

### Parse JSON Events

```bash
# Extract and pretty-print audit events
docker compose logs gateway 2>/dev/null \
  | grep "AUDIT:" \
  | sed 's/.*AUDIT: //' \
  | jq '.'
```

### Filter by Severity

```bash
# Show only warnings and errors
docker compose logs gateway 2>/dev/null \
  | grep "AUDIT:" \
  | sed 's/.*AUDIT: //' \
  | jq 'select(.severity == "warning" or .severity == "error")'
```

### Filter by Event Type

```bash
# Show authentication events
docker compose logs gateway 2>/dev/null \
  | grep "AUDIT:" \
  | sed 's/.*AUDIT: //' \
  | jq 'select(.event_category == "authentication")'
```

---

## 7. Compliance

### SOC 2 Type II

Audit logs support SOC 2 requirements:

| Control | Audit Support |
|---------|---------------|
| CC6.1 | Authentication events logged |
| CC6.2 | Authorization failures logged |
| CC7.2 | Security incidents traceable |
| CC8.1 | Changes logged (CONFIG_CHANGED) |

### GDPR

| Requirement | Implementation |
|-------------|----------------|
| Data Access Tracking | CONTACTS_ACCESSED events |
| No PII in Logs | Only IDs, never names/emails |
| Right to Access | trace_id enables request tracing |

### Log Retention

Recommended retention policies:

| Environment | Retention | Rationale |
|-------------|-----------|-----------|
| Development | 7 days | Debugging |
| Staging | 30 days | Testing |
| Production | 90 days | Compliance (SOC 2) |
| Archive | 1 year | Legal/regulatory |

### Log Rotation

Example logrotate configuration:

```
/var/log/skylink/audit.log {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0640 skylink skylink
}
```

---

## 8. Best Practices

### Do

- Always include trace_id for request correlation
- Use convenience methods when available
- Log at appropriate severity levels
- Keep details minimal but useful

### Don't

- Log tokens, passwords, or secrets
- Log PII (names, emails, phone numbers)
- Log request/response bodies
- Log sensitive business data

### Security Considerations

1. **Access Control**: Restrict audit log access to security team
2. **Integrity**: Use append-only storage if possible
3. **Encryption**: Encrypt audit logs at rest
4. **Backup**: Maintain secure backups of audit logs

### Example: Complete Request Flow

```
Request: POST /auth/token
         ↓
Middleware: trace_id = "abc123"
         ↓
Handler: create_access_token()
         ↓
Audit: AUTH_SUCCESS (trace_id="abc123", actor_id="aircraft-xyz")
         ↓
Response: 200 OK
```

Correlating logs:

```bash
# Find all logs for a specific request
docker compose logs gateway | grep "abc123"

# Output:
# gateway | {"trace_id":"abc123", "method":"POST", "path":"/auth/token", ...}
# gateway | AUDIT: {"trace_id":"abc123", "event_type":"AUTH_SUCCESS", ...}
```

---

## Appendix: Event Category Reference

| Category | Event Types |
|----------|-------------|
| authentication | AUTH_*, MTLS_*, OAUTH_* |
| authorization | AUTHZ_SUCCESS, AUTHZ_FAILURE |
| security | RATE_LIMIT_EXCEEDED |
| data | TELEMETRY_*, CONTACTS_*, WEATHER_* |
| admin | CONFIG_CHANGED |
| system | SERVICE_STARTED, SERVICE_STOPPED |

---

*Document maintained as part of SkyLink Security by Design implementation.*
