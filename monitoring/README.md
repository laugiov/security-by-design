# SkyLink Monitoring Stack

Security monitoring with Prometheus and Grafana for the SkyLink platform.

## Quick Start

```bash
# Start the full stack including monitoring
docker compose --profile monitoring up -d

# Access dashboards
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## Components

| Service | Port | Description |
|---------|------|-------------|
| Prometheus | 9090 | Metrics collection and alerting |
| Grafana | 3000 | Visualization and dashboards |

## Directory Structure

```
monitoring/
├── prometheus/
│   ├── prometheus.yml         # Prometheus configuration
│   └── alerts/
│       └── security.yml       # Security alert rules
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml # Auto-provision Prometheus
│   │   └── dashboards/
│   │       └── dashboards.yml # Dashboard provisioning
│   └── dashboards/
│       └── security.json      # Security dashboard
└── README.md                  # This file
```

## Dashboards

### SkyLink Security Dashboard

Pre-configured dashboard with:

- **Authentication Overview**: Success rate, failures by status, mTLS failures
- **API Security**: Rate limiting, 401/403/429 responses
- **Performance**: Request latency (p50/p95/p99), error rates
- **Service Health**: Service up/down status, request rates by service

## Alert Rules

| Alert | Severity | Condition |
|-------|----------|-----------|
| HighAuthFailureRate | warning | >0.1 auth failures/s for 2min |
| SustainedAuthFailures | critical | >0.05 auth failures/s for 10min |
| mTLSValidationFailures | critical | Any 403 responses |
| RateLimitAbuse | warning | >1 rate limit/s for 5min |
| RateLimitFlood | critical | >10 rate limit/s for 2min |
| HighErrorRate | critical | >5% error rate for 5min |
| ServiceDown | critical | Service unreachable for 1min |

## Metrics Collected

From SkyLink services (`/metrics` endpoint):

- `http_requests_total` - Request count by status/handler
- `http_request_duration_seconds` - Request latency histogram
- `http_requests_inprogress` - In-flight requests

## Configuration

### Grafana

Default credentials: `admin` / `admin` (change via `GRAFANA_PASSWORD` env var)

### Prometheus

Scrape interval: 10s for services, 15s for Prometheus self-monitoring.

## Documentation

See [docs/MONITORING.md](../docs/MONITORING.md) for full documentation.
