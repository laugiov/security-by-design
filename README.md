# SkyLink — Security by Design Reference Implementation

> A **microservices** platform demonstrating **Security by Design** principles for connected aviation telemetry systems.

[![CI](https://github.com/laugiov/security-by-design/actions/workflows/ci.yml/badge.svg)](https://github.com/laugiov/security-by-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](#technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.120-009688?logo=fastapi&logoColor=white)](#technology-stack)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)
[![Security](https://img.shields.io/badge/Security-SAST%20|%20SCA%20|%20DAST-blueviolet)](#cicd-security-pipeline)
[![OWASP](https://img.shields.io/badge/OWASP-Headers%20Compliant-orange?logo=owasp&logoColor=white)](#4-owasp-security-headers)
[![Docker](https://img.shields.io/badge/Docker-Rootless-2496ED?logo=docker&logoColor=white)](#quick-start)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Overview

**SkyLink** is a demonstration platform for connected aircraft services, built with security as a foundational principle. This project showcases practical Security by Design implementations:

- **Multi-layer authentication** (JWT RS256 + mTLS)
- **Defense in depth** (rate limiting, payload limits, strict validation)
- **Privacy by Design** (PII minimization, structured logging without sensitive data)
- **Secure CI/CD pipeline** (SAST, SCA, DAST, SBOM, image signing)

### Architecture

```
                              Internet
                                 │
┌────────────────────────────────┴────────────────────────────────┐
│                      API GATEWAY (:8000)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Security     │  │ Rate         │  │ JWT RS256            │   │
│  │ Headers      │  │ Limiting     │  │ Authentication       │   │
│  │ (OWASP)      │  │ (slowapi)    │  │ + mTLS Validation    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Payload      │  │ Structured   │  │ Prometheus           │   │
│  │ Limit (64KB) │  │ JSON Logging │  │ Metrics              │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────┬──────────────┬──────────────┬─────────────────────┘
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ TELEMETRY   │  │ WEATHER     │  │ CONTACTS    │
    │ :8001       │  │ :8002       │  │ :8003       │
    │             │  │             │  │             │
    │ • Idempotent│  │ • Demo mode │  │ • OAuth 2.0 │
    │ • GPS round │  │ • Fixtures  │  │ • PostgreSQL│
    │ • 201/200/  │  │             │  │ • Encrypted │
    │   409       │  │             │  │   tokens    │
    └─────────────┘  └─────────────┘  └──────┬──────┘
                                             │
                                             ▼
                                     ┌─────────────┐
                                     │ PostgreSQL  │
                                     │ :5432       │
                                     └─────────────┘
```

---

## Security by Design Features

### 1. Multi-Layer Authentication

| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| **Transport** | mTLS (Mutual TLS) | X.509 client certificates, CA validation |
| **Application** | JWT RS256 | 2048-bit RSA keys, 15-min expiry, audience validation |
| **Cross-Validation** | CN ↔ JWT sub | Certificate CN must match JWT subject |

**Implementation**: [skylink/auth.py](skylink/auth.py), [skylink/mtls.py](skylink/mtls.py)

### 2. Defense in Depth

| Control | Description | Implementation |
|---------|-------------|----------------|
| **Rate Limiting** | Per-identity throttling | 60 req/min per aircraft_id ([skylink/rate_limit.py](skylink/rate_limit.py)) |
| **Payload Limits** | DoS protection | 64 KB max request size |
| **Input Validation** | Strict schema enforcement | Pydantic `extra="forbid"`, OpenAPI `additionalProperties: false` |
| **Idempotency** | Replay attack mitigation | Unique `(aircraft_id, event_id)` constraint |

**Implementation**: [skylink/middlewares.py](skylink/middlewares.py)

### 3. PII Minimization (Privacy by Design)

| Data | Protection | Details |
|------|------------|---------|
| GPS Coordinates | Rounding | 4 decimals (~11m accuracy) |
| Logs | Sanitization | No PII, only `trace_id` for correlation |
| OAuth Tokens | Encryption | AES-GCM encryption at rest |

### 4. OWASP Security Headers

All responses include security headers (see [skylink/middlewares.py](skylink/middlewares.py)):

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Cache-Control: no-store, no-cache, must-revalidate, max-age=0
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

### 5. Observability

- **Structured JSON Logging** with W3C trace correlation (`X-Trace-Id`)
- **Prometheus Metrics** endpoint (`/metrics`)
- **No sensitive data** in logs (tokens, secrets, PII never logged)

---

## CI/CD Security Pipeline

CI/CD pipeline with security gates at every stage:
- **GitHub Actions**: [.github/workflows/ci.yml](.github/workflows/ci.yml) — See [setup guide](docs/GITHUB_CI_SETUP.md)
- **GitLab CI**: [.gitlab-ci.yml](.gitlab-ci.yml) — See [setup guide](docs/GITLAB_CI_SETUP.md)

```
┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────────────┐   ┌───────┐
│ LINT  │──▶│ TEST  │──▶│ BUILD │──▶│ SCAN  │──▶│ SBOM  │──▶│ SECURITY-SCAN │──▶│ SIGN  │
└───────┘   └───────┘   └───────┘   └───────┘   └───────┘   └───────────────┘   └───────┘
```

### Security Tools

| Tool | Purpose | Stage |
|------|---------|-------|
| **Ruff** | Python linting | lint |
| **Black** | Code formatting | lint |
| **Bandit** | SAST (security linting) | lint |
| **pytest** | Unit tests (305 tests, 81% coverage) | test |
| **Trivy** | Container vulnerability scanning | scan |
| **pip-audit** | Python dependency SCA | scan |
| **Gitleaks** | Secret detection | scan |
| **OpenAPI Generator** | OpenAPI spec validation | scan |
| **CycloneDX** | SBOM generation | sbom |
| **OWASP ZAP** | DAST baseline scan | security-scan |
| **Cosign** | Image signing & SBOM attestation | sign |

### Supply Chain Security

Images are signed using [Sigstore Cosign](https://github.com/sigstore/cosign) with **keyless signing** (OIDC) and SBOM attestation:

```bash
# Verify image signature (keyless)
cosign verify \
  --certificate-identity-regexp="https://github.com/laugiov/security-by-design" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/laugiov/security-by-design:latest

# Verify SBOM attestation
cosign verify-attestation \
  --certificate-identity-regexp="https://github.com/laugiov/security-by-design" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  --type cyclonedx \
  ghcr.io/laugiov/security-by-design:latest
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenSSL (for key generation)
- curl, jq (optional, for testing)

### 1. Clone & Configure

```bash
git clone <repo-url> skylink
cd skylink

# Copy environment template
cp .env.example .env

# Generate RSA keys for JWT signing
openssl genrsa -out /tmp/private.pem 2048
openssl rsa -in /tmp/private.pem -pubout -out /tmp/public.pem

# Add keys to .env
echo "PRIVATE_KEY_PEM=\"$(cat /tmp/private.pem)\"" >> .env
echo "PUBLIC_KEY_PEM=\"$(cat /tmp/public.pem)\"" >> .env
```

### 2. Start the Stack

```bash
make build && make up

# Verify health
make health
```

### 3. Test Authentication

```bash
# Get a JWT token
AIRCRAFT_ID=$(uuidgen)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"aircraft_id\": \"$AIRCRAFT_ID\"}" | jq -r '.access_token')

echo "Token: ${TOKEN:0:50}..."
```

### 4. Send Telemetry (Idempotency Demo)

```bash
EVENT_ID=$(uuidgen)

# First request: 201 Created
curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"aircraft_id\": \"$AIRCRAFT_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"metrics\": {\"speed\": 450.5, \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}}
  }"
# Response: {"status": "created", "event_id": "..."}

# Same request again: 200 OK (idempotent duplicate)
# Same event_id with different data: 409 Conflict
```

---

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/health` | Health check | No |
| `GET` | `/metrics` | Prometheus metrics | No |
| `POST` | `/auth/token` | Obtain JWT token | No |
| `POST` | `/telemetry/ingest` | Ingest telemetry data | JWT |
| `GET` | `/weather/current` | Current weather | JWT |
| `GET` | `/contacts/` | List contacts | JWT |

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success / Idempotent duplicate |
| `201` | Created |
| `400` | Validation error |
| `401` | Unauthorized (missing/invalid JWT) |
| `403` | Forbidden (mTLS CN ≠ JWT sub) |
| `409` | Conflict (idempotency violation) |
| `413` | Payload too large |
| `429` | Rate limit exceeded |

---

## Project Structure

```
skylink/
├── openapi/                 # OpenAPI specifications (Contract-First)
├── skylink/                 # API Gateway (port 8000)
│   ├── main.py              # FastAPI application
│   ├── auth.py              # JWT RS256 authentication
│   ├── mtls.py              # mTLS configuration
│   ├── middlewares.py       # Security headers, logging, payload limit
│   ├── rate_limit.py        # Rate limiting (slowapi)
│   ├── config.py            # Configuration management
│   └── routers/             # API endpoints
├── telemetry/               # Telemetry service (port 8001)
├── weather/                 # Weather service (port 8002)
├── contacts/                # Contacts service (port 8003)
├── scripts/                 # PKI & utility scripts
├── tests/                   # Test suite
├── docs/                    # Documentation
│   ├── DEMO.md              # Demo guide
│   ├── TECHNICAL_DOCUMENTATION.md  # Technical documentation
│   ├── GITHUB_CI_SETUP.md   # GitHub Actions setup guide
│   └── GITLAB_CI_SETUP.md   # GitLab CI/CD setup guide
├── Dockerfile.*             # Multi-stage Dockerfiles (non-root user)
├── docker-compose.yml       # Orchestration
├── .gitlab-ci.yml           # GitLab CI/CD pipeline
└── .github/workflows/ci.yml # GitHub Actions pipeline
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | STRIDE-based threat analysis and risk assessment |
| [docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) | Data flow diagrams, trust boundaries, security controls |
| [docs/DEMO.md](docs/DEMO.md) | Step-by-step demonstration walkthrough |
| [docs/TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md) | Complete technical documentation (architecture, security, RRA) |
| [docs/GITHUB_CI_SETUP.md](docs/GITHUB_CI_SETUP.md) | GitHub Actions CI/CD setup guide (secrets, variables, workflow) |
| [docs/GITLAB_CI_SETUP.md](docs/GITLAB_CI_SETUP.md) | GitLab CI/CD setup guide (variables, registry, pipeline) |

---

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.12 |
| Framework | FastAPI | ^0.120 |
| ASGI Server | Uvicorn | ^0.27 |
| Authentication | PyJWT | ^2.8 |
| Validation | Pydantic | ^2.10 |
| Rate Limiting | slowapi | ^0.1.9 |
| Metrics | prometheus-fastapi-instrumentator | ^7.0 |
| Database | PostgreSQL | 16 |
| ORM | SQLAlchemy | ^2.0 |
| Containers | Docker | 24+ |

---

## Testing

```bash
# Run all tests
make test

# Or with poetry
poetry run pytest
```

**305 tests** with **81% coverage** — covering authentication, rate limiting, input validation, idempotency, security headers, error handling, and service integration.

---

## Security Controls Implemented

- [x] **Threat Modeling** — STRIDE analysis in [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- [x] **Strict Input Validation** — Pydantic `extra="forbid"`, reject unknown fields
- [x] **JWT RS256 Authentication** — Short TTL (15 min), audience validation
- [x] **mTLS Cross-Validation** — Certificate CN must match JWT subject
- [x] **Rate Limiting** — Per-identity throttling with Prometheus counter
- [x] **Security Headers** — OWASP recommended set
- [x] **Structured Logging** — JSON format, no PII, trace_id correlation
- [x] **SAST** — Bandit security linting
- [x] **SCA** — pip-audit dependency scanning
- [x] **Container Scanning** — Trivy (fail on HIGH/CRITICAL)
- [x] **Secret Detection** — Gitleaks
- [x] **DAST** — OWASP ZAP baseline scan
- [x] **SBOM Generation** — CycloneDX format
- [x] **Image Signing** — Cosign with SBOM attestation
- [x] **Non-root Containers** — User `skylink:1000`
- [x] **Secrets Management** — Environment variables, never in code

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Author

**Laurent Giovannoni**

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <em>Built with Security by Design principles</em>
</p>
