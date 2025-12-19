# Technical Documentation

---

## 1. Overview

### 1.1 Context and Objectives

SkyLink is a connected vehicle services platform implemented following **Security by Design** and **Contract-First** principles. The microservices architecture enables horizontal scalability and business domain isolation.

**Key objectives**:
- Collect and process real-time vehicle telemetry data
- Provide contextualized weather services for driving assistance
- Manage emergency contacts with Google OAuth integration
- Ensure data security (PII minimization, encryption, auditability)

### 1.2 Global Architecture

```
                              Internet
                                 |
                    [Reverse Proxy / Load Balancer]
                                 |
                                 v
+-----------------------------------------------------------------------+
|                           API GATEWAY (:8000)                          |
|  +------------------+  +-------------------+  +--------------------+   |
|  | Security Headers |  | Rate Limiting     |  | JWT RS256 Auth     |   |
|  | (OWASP)          |  | (60 req/min/sub)  |  | (sign + verify)    |   |
|  +------------------+  +-------------------+  +--------------------+   |
|  +------------------+  +-------------------+  +--------------------+   |
|  | Payload Limit    |  | JSON Logging      |  | mTLS Extraction    |   |
|  | (64 KB max)      |  | (trace_id W3C)    |  | (CN validation)    |   |
|  +------------------+  +-------------------+  +--------------------+   |
+-----------------------------------------------------------------------+
         |                      |                      |
         v                      v                      v
+----------------+    +------------------+    +------------------+
| TELEMETRY      |    | WEATHER          |    | CONTACTS         |
| Service        |    | Service          |    | Service          |
| :8001          |    | :8002            |    | :8003            |
+----------------+    +------------------+    +------------------+
| - Idempotency  |    | - Demo mode      |    | - Google OAuth   |
| - GPS rounding |    | - Paris fixtures |    | - PostgreSQL     |
| - 201/200/409  |    | - Cache ready    |    | - CRUD contacts  |
+----------------+    +------------------+    +------------------+
                                                    |
                                                    v
                                            +----------------+
                                            | PostgreSQL     |
                                            | :5432          |
                                            +----------------+
```

---

## 2. Components and Responsibilities

### 2.1 API Gateway (Port 8000)

Single entry point of the platform. Centralizes authentication, validation, and routing.

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **Auth JWT RS256** | Token issuance and verification | PyJWT, 2048-bit RSA keys |
| **Rate Limiting** | Abuse protection | slowapi, 60 req/min per vehicle_id |
| **Security Headers** | OWASP protection | X-Content-Type-Options, X-Frame-Options, CSP |
| **Payload Limit** | DoS protection | 64 KB max per request |
| **JSON Logging** | Observability | Structured logs, W3C trace_id |
| **mTLS** | Mutual auth (optional) | Cross-validation CN <-> JWT sub |
| **Prometheus /metrics** | Metrics | prometheus-fastapi-instrumentator |

### 2.2 Telemetry Service (Port 8001)

Collection and storage of vehicle telemetry data with idempotency guarantee.

| Feature | Description | HTTP Code |
|---------|-------------|-----------|
| Event creation | New event_id | 201 Created |
| Exact duplicate | Same (vehicle_id, event_id) | 200 OK |
| Conflict | event_id reused, different data | 409 Conflict |

**PII Minimization**: GPS coordinates rounded to 4 decimals (~11m accuracy).

### 2.3 Weather Service (Port 8002)

Weather service for driving assistance. Demo mode with Paris fixtures.

**Endpoints**:
- `GET /weather/current`: Current conditions

### 2.4 Contacts Service (Port 8003)

Emergency contact management with Google OAuth authentication.

**Features**:
- Google OAuth 2.0 integration
- PostgreSQL storage
- Full CRUD operations for contacts

---

## 3. Security (Security by Design)

### 3.1 Multi-Level Authentication

```
Level 1: Transport (mTLS)
+---------------------------+
| X.509 client certificate  |
| Signed by SkyLink CA      |
| CN = vehicle_id           |
+---------------------------+
            |
            v
Level 2: Application (JWT RS256)
+---------------------------+
| RS256 signed JWT token    |
| sub = vehicle_id          |
| exp = 15 minutes max      |
| aud = "skylink"           |
+---------------------------+
            |
            v
Level 3: Cross-Validation
+---------------------------+
| Certificate CN == JWT sub |
| Automatic verification    |
+---------------------------+
```

### 3.2 Data Protection (PII)

| Measure | Implementation | Justification |
|---------|----------------|---------------|
| GPS Rounding | 4 decimals (~11m) | Position anonymization |
| Payload Limit | 64 KB max | DoS protection |
| PII-free Logs | trace_id only | GDPR compliance |
| Strict Schemas | `additionalProperties: false` | Injection prevention |
| Strict Pydantic | `extra: "forbid"` | Unknown field rejection |

### 3.3 Rate Limiting

```
slowapi Configuration:
- Per vehicle_id: 60 requests/minute
- Global: 10 requests/second
- Response: 429 Too Many Requests
- Prometheus Counter: rate_limit_exceeded_total
```

### 3.4 Security Headers (OWASP)

| Header | Value | Protection |
|--------|-------|------------|
| X-Content-Type-Options | nosniff | MIME sniffing |
| X-Frame-Options | DENY | Clickjacking |
| Cache-Control | no-store, no-cache | Cache poisoning |
| Cross-Origin-Opener-Policy | same-origin | Spectre/Meltdown |
| Cross-Origin-Embedder-Policy | require-corp | Isolation |
| Referrer-Policy | no-referrer | Referrer leakage |
| Permissions-Policy | geolocation=(), camera=() | API restrictions |

---

## 4. Infrastructure and Deployment

### 4.1 Docker Stack

```yaml
# docker-compose.yml (summary)
services:
  gateway:      # python:3.12-slim, port 8000
  telemetry:    # python:3.12-slim, port 8001
  weather:      # python:3.12-slim, port 8002
  contacts:     # python:3.12-slim, port 8003
  db:           # postgres:16-alpine, port 5432
```

**Dockerfile Features**:
- Multi-stage build (builder + runtime)
- Base image: `python:3.12-slim`
- Non-root user: `skylink:1000`
- Integrated health checks
- Secured environment variables

### 4.2 Makefile

| Command | Description |
|---------|-------------|
| `make build` | Build all images |
| `make up` | Start the stack |
| `make down` | Stop the stack |
| `make logs` | Display logs (follow) |
| `make health` | Check service health |
| `make test` | Run tests |
| `make clean` | Remove containers/images |

### 4.3 Docker Network

```
skylink-net (bridge)
+-----------------------------------------------+
|                                               |
|  gateway:8000  <----> telemetry:8001          |
|       |        <----> weather:8002            |
|       |        <----> contacts:8003 --> db    |
|       |                                       |
+-----------------------------------------------+
        |
        | Exposed port: 8000
        v
    Internet
```

---

## 5. CI/CD Pipeline

### 5.1 GitLab CI Stages

```
lint ──> test ──> build ──> scan ──> sbom ──> security-scan ──> sign
```

| Stage | Tools | Objective |
|-------|-------|----------|
| **lint** | ruff, black, bandit | Code quality, static security |
| **test** | pytest, coverage | Unit tests (323 tests, 82% coverage) |
| **build** | kaniko | Image building (rootless) |
| **scan** | trivy, pip-audit, gitleaks | Image vulnerabilities, SCA, secrets |
| **sbom** | cyclonedx-bom | Component inventory (CycloneDX) |
| **security-scan** | ZAP baseline | Dynamic security tests (DAST) |
| **sign** | cosign | Image signing + SBOM attestation |

### 5.2 Supply Chain Security (cosign)

Image signing ensures integrity and provenance of deployed code.

```
Signing Pipeline:

build_image ──> trivy_image ──> sign_image ──> attest_sbom ──> verify_signature
     │                              │              │                │
     v                              v              v                v
  Docker Image              cosign Signature   SBOM attached    Verification
  registry:tag              .sig in registry   in-toto pred.    public key
```

**Signing Jobs**:

| Job | Description | Trigger |
|-----|-------------|---------|
| `sign_image` | Sign image with cosign private key | master, tags |
| `attest_sbom` | Attach CycloneDX SBOM as attestation | master, tags |
| `verify_signature` | Verify signature and attestation | master, tags |

**Manual Verification**:

```bash
# Verify image signature
cosign verify --key cosign.pub registry.gitlab.com/skylink:latest

# Verify SBOM attestation
cosign verify-attestation --key cosign.pub --type cyclonedx registry.gitlab.com/skylink:latest
```

### 5.3 Secured CI Variables

| Variable | Type | Protected | Usage |
|----------|------|-----------|-------|
| PRIVATE_KEY_PEM | Variable | Yes | JWT signing |
| PUBLIC_KEY_PEM | Variable | Yes | JWT verification |
| COSIGN_PRIVATE_KEY | **File** | Yes + Masked | Docker image signing |
| COSIGN_PASSWORD | Variable | Yes + Masked | Cosign key password |
| COSIGN_PUBLIC_KEY | **File** | Yes | Signature verification |

> **Important Note**: Variables `COSIGN_PRIVATE_KEY` and `COSIGN_PUBLIC_KEY` must be of type **File** (not Variable) for cosign to read the PEM file correctly.

---

## 6. Observability

### 6.1 Prometheus Metrics

Endpoint: `GET /metrics`

| Metric | Type | Description |
|--------|------|-------------|
| http_requests_total | Counter | Requests by handler/method/status |
| http_request_duration_seconds | Histogram | Latencies (buckets) |
| http_requests_inprogress | Gauge | In-progress requests |
| rate_limit_exceeded_total | Counter | Rate limits triggered (429) |

### 6.2 Structured Logging

```json
{
  "timestamp": "2025-12-19T10:00:00.000Z",
  "service": "gateway",
  "trace_id": "abc-123-def",
  "method": "POST",
  "path": "/telemetry",
  "status": 201,
  "duration_ms": 12.5
}
```

**Features**:
- JSON format on stdout
- W3C traceability (trace_id)
- No PII in logs
- ELK/CloudWatch compatible

---

## 7. RRA Compliance (Rapid Risk Assessment)

This section details the project's compliance with recommendations from the **SkyLink-RRA.pdf** document (Fast Car Connect Risk Assessment).

### 7.1 RRA Recommendations and Implementation

| Impact | RRA Recommendation | Status | Implementation |
|--------|-------------------|--------|----------------|
| **MAXIMUM** | Use mTLS for vehicle-service identification | ✅ Done | Module `skylink/mtls.py`, PKI scripts in `scripts/`, cross-validation CN <-> JWT |
| **MAXIMUM** | Use OAuth with least privileges | ✅ Done | Contacts Service with Google OAuth 2.0, `read-only` scope for contacts |
| **MAXIMUM** | Manage secrets with KMS/Vault | ✅ MVP | Protected CI variables + local `.env` (see note 7.6) |
| **HIGH** | Data minimization (Geohash location) | ✅ Done | GPS rounded to 4 decimals (~11m), no contact persistence by default |
| **HIGH** | API security (JWT + rate limiting) | ✅ Done | JWT RS256 (15min exp), slowapi 60 req/min per vehicle_id |
| **HIGH** | PII-free logs, tracing, metrics | ✅ Done | JSON logging with trace_id, `/metrics` Prometheus, PII-free logs |
| **HIGH** | CI/CD supply chain (SBOM, SCA, SAST/DAST) | ✅ Done | GitLab pipeline: bandit, trivy, cyclonedx-bom, ZAP DAST |

### 7.2 Threat Scenarios and Controls

| Scenario (RRA) | Impact | Implemented Control | Evidence |
|----------------|--------|---------------------|----------|
| **Data leaks** (OAuth tokens, GPS, verbose logs) | MAXIMUM | PII-free logs, strict schemas, protected CI variables | Validation tests, .gitignore |
| **Driving system alteration** | MAXIMUM | Mandatory mTLS, RS256 signed JWT, strict validation | Auth tests, mTLS tests |
| **Vehicle spoofing** (missing mTLS) | HIGH | mTLS with cross-validation CN == JWT sub | Tests `test_mtls_auth_integration.py` |
| **Replay attacks** (missing nonce) | MEDIUM | Idempotency `(vehicle_id, event_id)` unique | Tests 201/200/409 |
| **Supply-chain** (compromised image/dependency) | MAXIMUM | CycloneDX SBOM, Trivy scan, Bandit SAST | CI pipeline artifacts |
| **DDoS/API flood** | HIGH | slowapi rate-limit, 429 response | Rate-limit tests, `rate_limit_exceeded_total` metric |
| **Vendor quota/outage** | MEDIUM | Demo mode fixtures (Weather), targeted circuit-breaker | Weather Service demo mode |
| **CI/CD incidents** | MAXIMUM | Multi-stage pipeline, automated tests, health checks | 323 tests, 82% coverage |

### 7.3 Data Dictionary and Protection

| Data (RRA) | Classification | Implemented Control |
|------------|----------------|---------------------|
| Vehicle UUID | Internal | Strict UUID validation (Pydantic) |
| Telemetry (speed, fuel, etc.) | Confidential | `additionalProperties: false` schemas, data-free logs |
| GPS Position | Confidential (PII) | **Rounded to 4 decimals** (~11m accuracy) |
| Google Contacts | Confidential (PII) | Read-only OAuth, no persistence by default |
| Google auth tokens | Restricted | Protected CI variables, secured PostgreSQL storage |
| Logs (requests, metrics) | Restricted | **PII-free JSON logs**, trace_id only |
| Network metadata | Internal | Not logged (no IP/user-agent in logs) |

### 7.4 Risk Matrix and Evidence

| Risk (RRA) | Control | File/Test | Status |
|------------|---------|-----------|--------|
| API Flood / DDoS | slowapi rate-limit (429) | `tests/test_rate_limit.py` | ✅ |
| Replay / duplicates | Idempotency (vehicle_id, event_id) | `tests/test_telemetry.py` (201/200/409) | ✅ |
| PII exposure | Strict schemas + PII-free logs | `tests/test_middlewares.py` | ✅ |
| Vulnerable dependencies | SCA/SAST + SBOM | `.gitlab-ci.yml` (trivy, bandit, sbom) | ✅ |
| Plaintext secrets | Protected/masked CI vars | GitLab Settings CI/CD | ✅ |
| Vehicle impersonation | mTLS + cross-validation CN<->JWT | `tests/test_mtls*.py` | ✅ |
| Injection / XSS | Strict schemas + Pydantic | `tests/test_error_handlers.py` | ✅ |

### 7.5 Targeted Elements (Non-MVP)

| RRA Element | MVP Status | Production Target |
|-------------|------------|-------------------|
| HSM for vehicle keys | Not implemented | Hardware HSM + automated PKI |
| Centralized SIEM | stdout logs | ELK Stack / Splunk |
| SLSA attestation >= L3 | SBOM generated | cosign + provenance attestation |
| Vendor circuit-breaker | Demo mode | Resilience4j / Hystrix pattern |

### 7.6 Note on Secrets Management (MVP)

**RRA Context**: The recommendation "Manage secrets with KMS/Vault" aims to protect cryptographic secrets (RSA keys, OAuth tokens) against leaks and unauthorized access.

**MVP Implementation**:

| Environment | Mechanism | Security |
|-------------|-----------|----------|
| **Local development** | `.env` file | `.env` in `.gitignore`, never committed |
| **GitLab CI/CD** | Protected variables | Protected + protected branch scope |
| **Docker Compose** | Environment variables | Injected at runtime, not in images |

**Controls in place**:

1. **No hardcoded secrets**: No secrets in source code
   ```python
   # skylink/config.py
   private_key_pem: Optional[str] = None  # Loaded from env
   ```

2. **Strict `.gitignore`**:
   ```
   .env
   *.pem
   certs/
   ```

3. **Protected CI variables**:
   - `PRIVATE_KEY_PEM`: Protected, accessible only on protected branches
   - `PUBLIC_KEY_PEM`: Protected, accessible only on protected branches

4. **Rotation possible**: Keys can be changed without code modification

**MVP Justification**:

This approach complies with **12-Factor App** (Config in Environment) and is sufficient for an MVP because:
- Secrets are never exposed in logs or code
- CI access is restricted to protected branches
- The mechanism is identical to that used with a Vault (environment variables)

**Production Evolution**:

For production, the architecture allows transparent migration to HashiCorp Vault:
- Modify only `skylink/config.py` to read from Vault API
- No changes in the rest of the code (same interface `settings.get_private_key()`)

---

## 8. Technical Specifications

### 8.1 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.12 |
| Framework | FastAPI | ^0.120 |
| ASGI Server | Uvicorn | ^0.27 |
| JWT | PyJWT | ^2.8 |
| Validation | Pydantic | ^2.10 |
| Rate Limiting | slowapi | ^0.1.9 |
| Metrics | prometheus-fastapi-instrumentator | ^7.0 |
| Database | PostgreSQL | 16 |
| Containers | Docker | 24+ |
| CI/CD | GitLab CI | - |

### 8.2 Contract-First (OpenAPI)

Specifications in `openapi/*.yaml`:
- `common.yaml`: Shared schemas (Error, Pagination)
- `gateway.yaml`: API Gateway
- `telemetry.yaml`: Telemetry Service
- `weather.yaml`: Weather Service
- `contacts.yaml`: Contacts Service

**Validation**:
- Schemas with `additionalProperties: false`
- Pydantic with `extra: "forbid"`
- CI OpenAPI lint (openapi-generator-cli)

---

## 9. Appendices

### 9.1 Project Structure

```
SkyLink/
|-- openapi/                 # OpenAPI specifications
|-- skylink/                 # Gateway (port 8000)
|   |-- main.py              # FastAPI application
|   |-- auth.py              # JWT RS256
|   |-- mtls.py              # mTLS configuration
|   |-- middlewares.py       # Security, logging
|   |-- rate_limit.py        # Rate limiting
|   |-- config.py            # Configuration
|   |-- routers/             # Endpoints
|   +-- models/              # Pydantic models
|-- telemetry/               # Telemetry Service (port 8001)
|-- weather/                 # Weather Service (port 8002)
|-- contacts/                # Contacts Service (port 8003)
|-- scripts/                 # PKI scripts
|-- tests/                   # Tests (323 tests)
|-- docs/                    # Documentation
|-- Dockerfile.gateway       # Gateway image
|-- Dockerfile.telemetry     # Telemetry image
|-- Dockerfile.weather       # Weather image
|-- Dockerfile.contacts      # Contacts image
|-- docker-compose.yml       # Orchestration
|-- Makefile                 # Utility commands
|-- pyproject.toml           # Python dependencies
+-- .gitlab-ci.yml           # CI/CD pipeline
```

### 9.2 API Endpoints

| Method | Endpoint | Service | Description |
|--------|----------|---------|-------------|
| GET | / | Gateway | API entrypoint |
| GET | /health | Gateway | Health check |
| GET | /metrics | Gateway | Prometheus metrics |
| POST | /auth/token | Gateway | Obtain JWT |
| POST | /telemetry/ingest | Gateway | Telemetry ingestion (proxy → Telemetry) |
| GET | /telemetry/health | Telemetry | Health check |
| GET | /weather/current | Gateway | Current weather |
| GET | /contacts/ | Gateway | List contacts |
| GET | /contacts/health | Contacts | Health check |

### 9.3 Standard HTTP Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Success, idempotent duplicate |
| 201 | Created | Resource created |
| 400 | Bad Request | Validation failed |
| 401 | Unauthorized | Invalid/expired JWT |
| 403 | Forbidden | mTLS CN != JWT sub |
| 409 | Conflict | Idempotency violated |
| 422 | Unprocessable | Invalid schema |
| 429 | Too Many Requests | Rate limit |
| 500 | Internal Error | Server error |

---
