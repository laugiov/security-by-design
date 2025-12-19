# SkyLink Demonstration Guide

> **Estimated time**: 10-15 minutes
> **Prerequisites**: Docker, curl, jq (optional)

---

## Setup

### 1. Clone and Configure

```bash
# Clone the project
git clone <repo-url> skylink
cd skylink

# Copy environment template
cp .env.example .env

# Generate RSA keys (if not already done)
openssl genrsa -out /tmp/private.pem 2048
openssl rsa -in /tmp/private.pem -pubout -out /tmp/public.pem

# Add keys to .env
echo "PRIVATE_KEY_PEM=\"$(cat /tmp/private.pem)\"" >> .env
echo "PUBLIC_KEY_PEM=\"$(cat /tmp/public.pem)\"" >> .env
```

### 2. Start the Stack

```bash
# Build and start (first time)
make build && make up

# Or simply
docker compose up -d

# Verify everything is UP
make status
```

**Expected output**:
```
NAME          STATUS    PORTS
gateway       Up        0.0.0.0:8000->8000/tcp
telemetry     Up        8001/tcp
weather       Up        8002/tcp
contacts      Up        8003/tcp
db            Up        5432/tcp
```

### 3. Verify Health

```bash
make health
```

**Expected output**:
```
Gateway:    healthy
Telemetry:  healthy
Weather:    healthy
Contacts:   healthy
PostgreSQL: UP
```

---

## Demo 1: JWT Authentication

### Step 1.1: Obtain a Token

```bash
# Generate a UUID for the aircraft
AIRCRAFT_ID=$(uuidgen || echo "550e8400-e29b-41d4-a716-446655440000")

# Get a JWT token
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"aircraft_id\": \"$AIRCRAFT_ID\"}" | jq
```

**Expected output**:
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### Step 1.2: Save the Token

```bash
# Extract and save the token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"aircraft_id\": \"$AIRCRAFT_ID\"}" | jq -r '.access_token')

echo "Token obtained: ${TOKEN:0:50}..."
```

### Step 1.3: Decode the Token (Debug)

```bash
# Decode the payload (base64)
echo $TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq
```

**Expected output**:
```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "aud": "skylink",
  "iat": 1734600000,
  "exp": 1734600900
}
```

---

## Demo 2: Telemetry with Idempotency

### Step 2.1: Send an Event (201 Created)

```bash
EVENT_ID=$(uuidgen)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"aircraft_id\": \"$AIRCRAFT_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$TS\",
    \"metrics\": {
      \"speed\": 45.5,
      \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}
    }
  }" -w "\nHTTP Status: %{http_code}\n"
```

**Expected output**:
```json
{
  "status": "created",
  "event_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
HTTP Status: 201
```

### Step 2.2: Resend the Same Event (200 OK - Idempotency)

```bash
# Same request = same result (idempotency)
curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"aircraft_id\": \"$AIRCRAFT_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$TS\",
    \"metrics\": {
      \"speed\": 45.5,
      \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}
    }
  }" -w "\nHTTP Status: %{http_code}\n"
```

**Expected output**:
```json
{
  "status": "duplicate",
  "event_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
HTTP Status: 200
```

### Step 2.3: Idempotency Conflict (409 Conflict)

```bash
# Same event_id but different data = conflict
curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"aircraft_id\": \"$AIRCRAFT_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$TS\",
    \"metrics\": {
      \"speed\": 120.0,
      \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}
    }
  }" -w "\nHTTP Status: %{http_code}\n"
```

**Expected output**:
```json
{
  "detail": {
    "code": "TELEMETRY_CONFLICT",
    "message": "Event with same event_id but different payload already exists."
  }
}
HTTP Status: 409
```

---

## Demo 3: Rate Limiting

> **Note**: Rate limiting is configured on `/weather/current` (60 req/min per aircraft_id).

### Step 3.1: Generate a Burst of Requests

```bash
# Send 70 requests quickly (limit = 60/min)
for i in $(seq 1 70); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/weather/current?lat=48.8566&lon=2.3522" \
    -H "Authorization: Bearer $TOKEN")

  if [ "$STATUS" = "429" ]; then
    echo "Rate limit reached at request $i (HTTP 429)"
    break
  fi

  # Show progress
  if [ $i -le 5 ] || [ $i -ge 58 ]; then
    echo "Request $i: HTTP $STATUS"
  elif [ $i -eq 6 ]; then
    echo "..."
  fi
done
```

**Expected output**:
```
Request 1: HTTP 200
Request 2: HTTP 200
...
Request 58: HTTP 200
Request 59: HTTP 200
Request 60: HTTP 200
Rate limit reached at request 61 (HTTP 429)
```

### Step 3.2: Verify the 429 Response

```bash
# The next request should be rate limited
curl -s "http://localhost:8000/weather/current?lat=48.8566&lon=2.3522" \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP Status: %{http_code}\n"
```

**Expected output**:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded: 60 per 1 minute"
  }
}
HTTP Status: 429
```

---

## Demo 4: Prometheus Metrics

### Step 4.1: Access Metrics

```bash
curl -s http://localhost:8000/metrics | grep -E "^(http_|rate_)" | head -20
```

**Expected output**:
```
# HELP http_requests_total Total number of requests by method, status and handler.
# TYPE http_requests_total counter
http_requests_total{handler="/health",method="GET",status="200"} 5.0
http_requests_total{handler="/auth/token",method="POST",status="200"} 2.0
http_requests_total{handler="/weather/current",method="GET",status="200"} 60.0

# HELP rate_limit_exceeded_total Total number of rate limit exceeded responses (429)
# TYPE rate_limit_exceeded_total counter
rate_limit_exceeded_total 10.0
```

### Step 4.2: Filter Metrics

```bash
# Request counter by status
curl -s http://localhost:8000/metrics | grep "http_requests_total"

# Rate-limit counter
curl -s http://localhost:8000/metrics | grep "rate_limit_exceeded"

# Latencies
curl -s http://localhost:8000/metrics | grep "http_request_duration_seconds"
```

---

## Demo 5: Security Headers

### Step 5.1: Verify Headers

```bash
# Use -D - to display headers (GET request)
curl -s -D - http://localhost:8000/health -o /dev/null
```

**Expected output**:
```
HTTP/1.1 200 OK
content-type: application/json
x-trace-id: f6b40f74-bdd5-4865-9568-9cd2567eecf9
x-content-type-options: nosniff
x-frame-options: DENY
cache-control: no-store, no-cache, must-revalidate, max-age=0
pragma: no-cache
cross-origin-opener-policy: same-origin
cross-origin-embedder-policy: require-corp
referrer-policy: no-referrer
permissions-policy: geolocation=(), microphone=(), camera=()
```

### Step 5.2: Verify Traceability

```bash
# Send a custom trace_id
curl -s -D - http://localhost:8000/health \
  -H "X-Trace-Id: my-custom-trace-123" -o /dev/null | grep -i trace
```

**Expected output**:
```
x-trace-id: my-custom-trace-123
```

---

## Demo 6: Strict Validation

### Step 6.1: Unknown Field Rejected

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "aircraft_id": "550e8400-e29b-41d4-a716-446655440000",
    "unknown_field": "malicious"
  }' | jq
```

**Expected output**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "fields": [
        {
          "field": "unknown_field",
          "issue": "extra_forbidden",
          "message": "Extra inputs are not permitted"
        }
      ]
    }
  }
}
```

### Step 6.2: Invalid UUID Rejected

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"aircraft_id": "not-a-valid-uuid"}' | jq
```

**Expected output**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "fields": [
        {
          "field": "aircraft_id",
          "issue": "uuid_parsing",
          "message": "Input should be a valid UUID"
        }
      ]
    }
  }
}
```

---

## Demo 7: Weather Service

```bash
# Get weather (requires lat/lon query params)
curl -s "http://localhost:8000/weather/current?lat=48.8566&lon=2.3522" \
  -H "Authorization: Bearer $TOKEN" | jq '.location.name, .current.temp_c, .current.condition.text'
```

**Expected output** (demo mode with Paris fixtures):
```json
"Paris"
15
"Partly cloudy"
```

> **Note**: The full response includes `location` (city details) and `current` (temperature, conditions, wind, humidity, air quality).

---

## Demo 8: Contacts Service

```bash
# List contacts (Google People API format)
curl -s "http://localhost:8000/contacts/?person_fields=names,emailAddresses" \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length, .items[0].names[0].displayName'
```

**Expected output** (demo mode with fixtures):
```json
5
"Alice Dupont"
```

> **Note**: Contacts use the Google People API format. In demo mode, 5 fictional contacts are available.

---

## Demo 9: Supply Chain Security (cosign)

> **Prerequisites**: This demo works after the CI pipeline has signed the image.
> Locally, you can simulate verification with a signed image.

### Step 9.1: Install cosign (if needed)

```bash
# macOS
brew install cosign

# Linux (via Go)
go install github.com/sigstore/cosign/v2/cmd/cosign@latest

# Or via Docker
alias cosign='docker run --rm gcr.io/projectsigstore/cosign:latest'
```

### Step 9.2: Verify the Image Signature

```bash
# Replace with your GitLab registry
REGISTRY="registry.gitlab.com/your-group/skylink"
IMAGE_TAG="latest"

# Verify with the public key
cosign verify --key cosign.pub "$REGISTRY:$IMAGE_TAG"
```

**Expected output**:
```
Verification for registry.gitlab.com/your-group/skylink:latest --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key

[{"critical":{"identity":{"docker-reference":"registry.gitlab.com/..."},...}]
```

### Step 9.3: Verify the SBOM Attestation

```bash
# Verify that the CycloneDX SBOM is attached
cosign verify-attestation \
  --key cosign.pub \
  --type cyclonedx \
  "$REGISTRY:$IMAGE_TAG"
```

**Expected output**:
```
Verification for registry.gitlab.com/your-group/skylink:latest --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key

{"payloadType":"application/vnd.in-toto+json","payload":"..."}
```

### Step 9.4: Extract the SBOM from the Attestation

```bash
# Download and decode the SBOM attestation
cosign verify-attestation \
  --key cosign.pub \
  --type cyclonedx \
  "$REGISTRY:$IMAGE_TAG" 2>/dev/null \
  | jq -r '.payload' \
  | base64 -d \
  | jq '.predicate'
```

**Expected output** (excerpt):
```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "version": 1,
  "components": [
    {"name": "fastapi", "version": "0.109.0", "type": "library"},
    {"name": "pydantic", "version": "2.5.0", "type": "library"},
    ...
  ]
}
```

### Step 9.5: Verification in CI Mode (without key file)

```bash
# In the GitLab pipeline, the public key is a CI variable
# Verification is automatic after attest_sbom

# To simulate locally with the CI variable:
echo "$COSIGN_PUBLIC_KEY" > /tmp/cosign.pub
cosign verify --key /tmp/cosign.pub "$REGISTRY:$IMAGE_TAG"
rm /tmp/cosign.pub
```

---

## Cleanup

```bash
# Stop services
make down

# Remove everything (containers, volumes, images)
make clean
```

---

## CI/CD Pipeline Overview

### GitLab Pipeline

```
Stages: lint -> test -> build -> scan -> sbom -> security-scan -> sign

Jobs:
- lint:ruff            : OK (0 errors)
- lint:black           : OK (formatted)
- lint:bandit          : OK (0 HIGH)
- test:pytest          : OK (323 tests, 82% coverage)
- build:docker         : OK (4 images)
- scan:trivy           : OK (0 CRITICAL)
- scan:gitleaks        : OK (0 secrets)
- scan:pip-audit       : OK (0 vulns)
- sbom:cyclonedx       : OK (artifact generated)
- dast:zap             : OK (baseline)
- sign:sign_image      : OK (image signed with cosign)
- sign:attest_sbom     : OK (SBOM attached)
- sign:verify_signature: OK (signature verified)
```

### CI Artifacts

| Artifact | Description |
|----------|-------------|
| `sbom.json` | Software Bill of Materials (CycloneDX) |
| `trivy-report.json` | Container vulnerability scan |
| `zap-report.html` | DAST ZAP report |
| `coverage.xml` | pytest coverage report |

---

## HTTP Status Code Summary

| Code | Demo | Meaning |
|------|------|---------|
| 200 | Token, Duplicate | Success |
| 201 | Telemetry | Resource created |
| 400 | Validation | Invalid field |
| 401 | Expired token | Unauthenticated |
| 409 | Conflict | Idempotency violated |
| 429 | Rate limit | Too many requests |

---

## Demo Checklist

- [ ] Stack started (`make up`)
- [ ] Health check OK (`make health`)
- [ ] JWT token obtained
- [ ] Telemetry 201 Created
- [ ] Idempotency 200 OK (duplicate)
- [ ] Conflict 409 (different data)
- [ ] Rate limit 429
- [ ] Metrics /metrics
- [ ] Security headers present
- [ ] Strict validation (extra fields rejected)
- [ ] Image signature verified (cosign verify)
- [ ] SBOM attestation verified (cosign verify-attestation)

---

**SkyLink Demonstration Guide** (with Supply Chain Security)
