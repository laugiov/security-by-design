# SkyLink — Security by Design Reference Implementation

> A **microservices** platform demonstrating **Security by Design** principles for connected aviation telemetry systems.

## TL;DR

**What this proves:** End-to-end Security Engineering — from threat model to signed container in production-ready Kubernetes, with full observability and audit trail.

**Evaluate in 15 minutes:**
1. **Threat Model** → [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) (STRIDE, 30+ threats, mitigations)
2. **CI/CD Pipeline** → [.github/workflows/ci.yml](.github/workflows/ci.yml) (SAST → DAST → SBOM → Cosign)
3. **K8s Policies** → [kubernetes/skylink/templates/networkpolicy.yaml](kubernetes/skylink/templates/networkpolicy.yaml) (zero-trust)

**Verify controls work** (after `make up`):
- RBAC denial → `curl -H "Authorization: Bearer $TOKEN" /admin/` → 403 + audit event
- Idempotency → same event twice → 201 then 200
- Rate limit → 61 requests/min → 429 + `rate_limit_exceeded_total` increments

**Hiring relevance:** Security Engineering Lead · Platform Security · DevSecOps Director

---

[![CI](https://github.com/laugiov/security-by-design/actions/workflows/ci.yml/badge.svg)](https://github.com/laugiov/security-by-design/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](#technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.120-009688?logo=fastapi&logoColor=white)](#technology-stack)
[![License](https://img.shields.io/badge/License-MIT-green)](#license)
[![Security](https://img.shields.io/badge/Security-SAST%20|%20SCA%20|%20DAST-blueviolet)](#cicd-security-pipeline)
[![OWASP](https://img.shields.io/badge/OWASP-Headers%20Compliant-orange?logo=owasp&logoColor=white)](#4-owasp-security-headers)
[![Docker](https://img.shields.io/badge/Docker-Rootless-2496ED?logo=docker&logoColor=white)](#quick-start)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Helm%20Ready-326CE5?logo=kubernetes&logoColor=white)](#kubernetes-deployment)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Security Highlights

<table>
<tr>
<td width="50%">

**Authentication & Authorization**
- JWT RS256 + mTLS mutual authentication
- Cross-validation (Certificate CN = JWT subject)
- RBAC with 5 roles, 7 permissions
- Per-identity rate limiting (60 req/min)

</td>
<td width="50%">

**DevSecOps Pipeline**
- SAST (Bandit) + SCA (pip-audit, Trivy)
- DAST (OWASP ZAP baseline)
- SBOM generation (CycloneDX)
- Image signing (Sigstore Cosign)

</td>
</tr>
<tr>
<td>

**Privacy & Data Protection**
- PII minimization (GPS rounding ~11m)
- AES-256-GCM token encryption
- Structured logging without sensitive data
- Audit trail for compliance

</td>
<td>

**Kubernetes Production-Ready**
- Helm chart with Pod Security Restricted
- NetworkPolicies (zero-trust)
- External Secrets Operator support
- HPA, PDB, ServiceMonitor

</td>
</tr>
</table>

---

## Why This Project?

A **production-grade reference implementation** demonstrating how to embed Security by Design into a microservices architecture. Every pattern, control, and pipeline stage is designed for real-world adoption.

**Who is this for?**

| Audience | Value |
|----------|-------|
| **Security Engineers** | Reference architecture for threat modeling and security controls |
| **Architects** | Template for secure microservices design |
| **DevOps/Platform Teams** | Secure CI/CD pipeline with SAST, SCA, DAST, SBOM, and image signing |

**What makes it different?**

- **Production patterns**: Secure defaults, operational readiness, not just documentation
- **Complete lifecycle**: Threat model → code → test → build → deploy → monitor
- **Evidence-based**: Every control has corresponding tests and audit events
- **Runnable**: Full Docker Compose + Kubernetes Helm chart

---

## The SkyLink Scenario

**SkyLink** simulates a **connected aircraft telemetry platform** where:

- **Aircraft** send real-time telemetry data (GPS position, speed, altitude)
- **Crew members** access weather forecasts and contact information
- **Ground systems** receive and process telemetry for flight monitoring

This aviation context justifies strict security requirements:

| Requirement | Justification |
|-------------|---------------|
| **Strong Authentication** | Only authorized aircraft can transmit data |
| **Role-Based Access Control** | 5 roles with least-privilege permissions |
| **Data Integrity** | Telemetry must be tamper-proof (idempotency, checksums) |
| **Privacy Protection** | GPS coordinates rounded, PII minimized in logs |
| **Audit Trail** | All security events logged for compliance |
| **High Availability** | Rate limiting prevents DoS, circuit breakers for resilience |

> **Note**: This is a fictional scenario for educational purposes. The security controls demonstrated are applicable to any API-based microservices architecture.

---

## Overview

**SkyLink** is a demonstration platform for connected aircraft services, built with security as a foundational principle. This project showcases practical Security by Design implementations:

- **Multi-layer authentication** (JWT RS256 + mTLS)
- **Role-Based Access Control** (5 roles, 7 permissions, principle of least privilege)
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

### 1. Multi-Layer Authentication & Authorization

| Layer | Mechanism | Implementation |
|-------|-----------|----------------|
| **Transport** | mTLS (Mutual TLS) | X.509 client certificates, CA validation |
| **Application** | JWT RS256 | 2048-bit RSA keys, 15-min expiry, audience validation |
| **Cross-Validation** | CN ↔ JWT sub | Certificate CN must match JWT subject |
| **Authorization** | RBAC | 5 roles, 7 permissions, principle of least privilege |

**Implementation**: [skylink/auth.py](skylink/auth.py), [skylink/mtls.py](skylink/mtls.py), [skylink/rbac.py](skylink/rbac.py)

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

### 5. Observability & Monitoring

| Feature | Description | Documentation |
|---------|-------------|---------------|
| **Structured JSON Logging** | W3C trace correlation (`X-Trace-Id`) | [middlewares.py](skylink/middlewares.py) |
| **Prometheus Metrics** | Counters, histograms, gauges | `/metrics` endpoint |
| **Grafana Dashboards** | Pre-configured security dashboard | [MONITORING.md](docs/MONITORING.md) |
| **Audit Logging** | Security-relevant event tracking | [AUDIT_LOGGING.md](docs/AUDIT_LOGGING.md) |
| **Alert Rules** | 14 security alerts (auth, rate limit, errors) | [security.yml](monitoring/prometheus/alerts/security.yml) |

```bash
# Start monitoring stack
docker compose --profile monitoring up -d

# Access dashboards
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

### 6. Key Management

Secure cryptographic key management with rotation scripts:

| Key Type | Algorithm | Rotation Script |
|----------|-----------|-----------------|
| JWT Signing | RS256 (2048-bit) | `scripts/rotate_jwt_keys.sh` |
| Token Encryption | AES-256-GCM | `scripts/rotate_encryption_key.sh` |
| mTLS Certificates | X.509 | `scripts/renew_certificates.sh` |

See [KEY_MANAGEMENT.md](docs/KEY_MANAGEMENT.md) for rotation procedures and compliance.

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
| **pytest** | Unit tests (478 tests, 81% coverage) | test |
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

## Kubernetes Deployment

Production-ready Helm chart with security best practices:

```bash
# Deploy to Kubernetes
helm install skylink ./kubernetes/skylink \
  --namespace skylink --create-namespace \
  -f kubernetes/skylink/values-prod.yaml
```

| Security Feature | Implementation |
|------------------|----------------|
| **Pod Security** | Restricted profile (non-root, read-only fs, drop ALL capabilities) |
| **Network Policies** | Zero-trust default deny, explicit allow rules |
| **Secrets** | External Secrets Operator integration |
| **Availability** | HPA (auto-scaling), PDB (disruption budget) |
| **Observability** | ServiceMonitor for Prometheus Operator |

See [docs/KUBERNETES.md](docs/KUBERNETES.md) for complete deployment guide.

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
| `POST` | `/telemetry/ingest` | Ingest telemetry data | JWT + RBAC (telemetry:write) |
| `GET` | `/weather/current` | Current weather | JWT + RBAC (weather:read) |
| `GET` | `/contacts/` | List contacts | JWT + RBAC (contacts:read) |

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success / Idempotent duplicate |
| `201` | Created |
| `400` | Validation error |
| `401` | Unauthorized (missing/invalid JWT) |
| `403` | Forbidden (mTLS CN ≠ JWT sub, or RBAC permission denied) |
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
│   ├── rbac.py              # Role-Based Access Control
│   ├── rbac_roles.py        # Role and permission definitions
│   ├── config.py            # Configuration management
│   └── routers/             # API endpoints
├── telemetry/               # Telemetry service (port 8001)
├── weather/                 # Weather service (port 8002)
├── contacts/                # Contacts service (port 8003)
├── scripts/                 # PKI & utility scripts
├── tests/                   # Test suite
├── kubernetes/              # Kubernetes Helm chart
│   └── skylink/             # Helm chart with security policies
├── docs/                    # Documentation
│   ├── DEMO.md              # Demo guide
│   ├── KUBERNETES.md        # Kubernetes deployment guide
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
| [docs/MONITORING.md](docs/MONITORING.md) | Security monitoring with Prometheus and Grafana |
| [docs/KEY_MANAGEMENT.md](docs/KEY_MANAGEMENT.md) | Cryptographic key management, rotation procedures, compliance |
| [docs/AUDIT_LOGGING.md](docs/AUDIT_LOGGING.md) | Audit event logging, security event tracking, compliance |
| [docs/AUTHORIZATION.md](docs/AUTHORIZATION.md) | Role-Based Access Control (RBAC), permissions, role matrix |
| [docs/KUBERNETES.md](docs/KUBERNETES.md) | Kubernetes deployment with Helm, security policies, operations |
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

**478 tests** with **81% coverage** — covering authentication, RBAC authorization, rate limiting, input validation, idempotency, OWASP Top 10 security tests, security headers, error handling, and service integration.

---

## Security Controls Implemented

- [x] **Threat Modeling** — STRIDE analysis in [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- [x] **Strict Input Validation** — Pydantic `extra="forbid"`, reject unknown fields
- [x] **JWT RS256 Authentication** — Short TTL (15 min), audience validation
- [x] **RBAC Authorization** — 5 roles, 7 permissions, least privilege principle
- [x] **mTLS Cross-Validation** — Certificate CN must match JWT subject
- [x] **Rate Limiting** — Per-identity throttling with Prometheus counter
- [x] **OWASP Top 10 Security Tests** — 97 tests covering injection, XSS, access control, etc.
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
- [x] **Kubernetes Security** — Pod Security Restricted, NetworkPolicies, External Secrets

---

## Security Maturity

| Category | Status | Evidence |
|----------|--------|----------|
| **Threat Modeling** | ✅ | [THREAT_MODEL.md](docs/THREAT_MODEL.md) — STRIDE, 30+ threats |
| **Security Architecture** | ✅ | [SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) — DFD, trust boundaries |
| **Authentication** | ✅ | `test_auth*.py`, `test_mtls*.py` — 45+ tests |
| **Authorization** | ✅ | [AUTHORIZATION.md](docs/AUTHORIZATION.md) — 5 roles, 7 permissions |
| **Monitoring & Alerting** | ✅ | [MONITORING.md](docs/MONITORING.md) — 14 alert rules |
| **Audit Logging** | ✅ | [AUDIT_LOGGING.md](docs/AUDIT_LOGGING.md) — 20 event types |
| **Key Management** | ✅ | [KEY_MANAGEMENT.md](docs/KEY_MANAGEMENT.md) — rotation scripts |
| **Supply Chain Security** | ✅ | CI pipeline — SBOM, Cosign, Trivy |
| **Kubernetes Security** | ✅ | [KUBERNETES.md](docs/KUBERNETES.md) — Pod Security Restricted |

---

## Standards Alignment

| Control | OWASP ASVS | NIST SSDF | SLSA | Zero Trust |
|---------|------------|-----------|------|------------|
| Threat Modeling (STRIDE) | V1.1 | PO.1 | — | — |
| JWT RS256 + mTLS | V3.5, V9.1 | PS.1 | — | Identity verification |
| RBAC (least privilege) | V4.1 | PS.1 | — | Explicit access |
| Input validation | V5.1 | PW.5 | — | Never trust input |
| SAST/DAST/SCA | V14.2 | PW.7, PW.8 | L1 | — |
| SBOM + signing | V14.2 | PS.3 | L2 | — |
| Container hardening | V14.1 | PO.5 | — | Assume breach |
| NetworkPolicies | — | PO.5 | — | Micro-segmentation |
| Audit logging | V7.1 | PW.9 | — | Continuous monitoring |

---

## Portability

While built around an aviation telemetry scenario, all security controls are **directly reusable** for:

| Domain | Applicable Controls |
|--------|---------------------|
| **SaaS B2B / API Platform** | JWT auth, RBAC, rate limiting, audit trail, supply chain security |
| **Fintech / Regulated** | Threat model, key rotation, encryption at rest, compliance logging |
| **IAM / Identity Platform** | mTLS, OAuth integration, RBAC matrix, audit events |
| **Marketplace / Multi-tenant** | Tenant isolation (NetworkPolicies), per-identity rate limiting |
| **Healthcare / HIPAA** | PII minimization, encryption, audit trail, access control |

The architecture patterns, CI/CD gates, and operational practices transfer directly to any API-based microservices environment.

---

## Learning Path

New to this project? Follow this recommended learning path:

```
1. UNDERSTAND THE RISKS
   └── Read docs/THREAT_MODEL.md
       └── STRIDE analysis, threat scenarios

2. EXPLORE THE ARCHITECTURE
   └── Read docs/SECURITY_ARCHITECTURE.md
       └── Data flow diagrams, trust boundaries

3. HANDS-ON DEMO
   └── Follow docs/DEMO.md step by step
       └── JWT auth, rate limiting, idempotency

4. DEEP DIVE INTO CODE
   └── Explore skylink/ source code
       └── Security comments explain each control

5. REVIEW OPERATIONAL SECURITY
   └── docs/MONITORING.md → Prometheus/Grafana
   └── docs/AUDIT_LOGGING.md → Security events
   └── docs/KEY_MANAGEMENT.md → Key rotation
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Author

**Laurent Giovannoni** — 20+ years scaling SaaS platforms as CTO/VP Engineering

This project demonstrates how I approach **Security Engineering at scale**:
- Embedding security gates into CI/CD without blocking velocity
- Designing RBAC and IAM patterns that scale with organizational growth
- Building observable, auditable systems that satisfy compliance requirements
- Making security decisions explicit and traceable (threat model → control → test → evidence)

Beyond code, I bring experience in security design reviews, cross-team influence, and building security culture in engineering organizations.

> **Security issues?** See [SECURITY.md](SECURITY.md) — please use GitHub Security Advisories, not LinkedIn.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <em>Built with Security by Design principles</em>
</p>
