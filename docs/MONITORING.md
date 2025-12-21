# SkyLink Security Monitoring Guide

> **Comprehensive monitoring with Prometheus alerting and Grafana dashboards**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Quick Start](#2-quick-start)
3. [Architecture](#3-architecture)
4. [Prometheus Configuration](#4-prometheus-configuration)
5. [Alert Rules](#5-alert-rules)
6. [Grafana Dashboards](#6-grafana-dashboards)
7. [Metrics Reference](#7-metrics-reference)
8. [Operational Procedures](#8-operational-procedures)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Overview

SkyLink includes a production-ready monitoring stack designed for security observability:

| Component | Purpose | Port |
|-----------|---------|------|
| **Prometheus** | Metrics collection, alerting rules | 9090 |
| **Grafana** | Visualization, dashboards | 3000 |

### Key Features

- Pre-configured security alerts for authentication failures, rate limiting, and errors
- Auto-provisioned Grafana dashboards (no manual setup required)
- Declarative configuration (infrastructure as code)
- Docker Compose profile for optional deployment

---

## 2. Quick Start

### Start Monitoring Stack

```bash
# Start all services including monitoring
docker compose --profile monitoring up -d

# Or start monitoring separately
docker compose --profile monitoring up -d prometheus grafana
```

### Access Dashboards

| Dashboard | URL | Credentials |
|-----------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | (no auth) |

### Verify Setup

```bash
# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'

# Check Grafana health
curl -s http://localhost:3000/api/health
```

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MONITORING STACK                                 │
│                                                                          │
│  ┌─────────────────┐         ┌─────────────────┐                        │
│  │     GRAFANA     │◄────────│   PROMETHEUS    │                        │
│  │     :3000       │  Query  │     :9090       │                        │
│  │                 │         │                 │                        │
│  │  ┌───────────┐  │         │  ┌───────────┐  │                        │
│  │  │ Dashboard │  │         │  │  Alerts   │  │                        │
│  │  │ Security  │  │         │  │ security  │  │                        │
│  │  └───────────┘  │         │  │ .yml      │  │                        │
│  └─────────────────┘         └────────┬────────┘                        │
│                                       │                                  │
│                              Scrape /metrics                            │
│                                       │                                  │
│         ┌─────────────────────────────┼─────────────────────────────┐   │
│         │                             │                             │   │
│         ▼                             ▼                             ▼   │
│  ┌─────────────┐              ┌─────────────┐              ┌───────────┐│
│  │   Gateway   │              │  Telemetry  │              │  Weather  ││
│  │    :8000    │              │    :8001    │              │   :8002   ││
│  │  /metrics   │              │  /metrics   │              │ /metrics  ││
│  └─────────────┘              └─────────────┘              └───────────┘│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Services** expose metrics at `/metrics` endpoint (Prometheus format)
2. **Prometheus** scrapes metrics every 10-15 seconds
3. **Alert rules** evaluate metrics and fire alerts when conditions are met
4. **Grafana** queries Prometheus for visualization

---

## 4. Prometheus Configuration

### Configuration File

Location: `monitoring/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alerts/*.yml

scrape_configs:
  - job_name: 'skylink-gateway'
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: /metrics
    scrape_interval: 10s
```

### Scrape Targets

| Job | Target | Interval |
|-----|--------|----------|
| skylink-gateway | gateway:8000 | 10s |
| skylink-telemetry | telemetry:8001 | 10s |
| skylink-weather | weather:8002 | 10s |
| skylink-contacts | contacts:8003 | 10s |
| prometheus | localhost:9090 | 15s |

### Verify Targets

```bash
# List all targets and their health
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

---

## 5. Alert Rules

### Security Alerts

Location: `monitoring/prometheus/alerts/security.yml`

| Alert | Severity | Condition | Description |
|-------|----------|-----------|-------------|
| **HighAuthFailureRate** | warning | >0.1 401/s for 2min | Potential brute force |
| **SustainedAuthFailures** | critical | >0.05 401/s for 10min | Sustained attack |
| **mTLSValidationFailures** | critical | Any 403 for 1min | mTLS bypass attempt |
| **RateLimitAbuse** | warning | >1 429/s for 5min | Rate limit abuse |
| **RateLimitFlood** | critical | >10 429/s for 2min | DDoS/flood attack |
| **HighErrorRate** | critical | >5% 5xx for 5min | Service degradation |
| **ServiceDown** | critical | up == 0 for 1min | Service unavailable |

### View Active Alerts

```bash
# Check firing alerts
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

# Check all alert rules
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | {name: .name, state: .state}'
```

### Alert Rule Example

```yaml
- alert: HighAuthFailureRate
  expr: sum(rate(http_requests_total{status="401"}[5m])) > 0.1
  for: 2m
  labels:
    severity: warning
    category: authentication
  annotations:
    summary: "High authentication failure rate detected"
    description: "Auth failures: {{ $value | printf \"%.2f\" }}/s"
```

---

## 6. Grafana Dashboards

### Pre-configured Dashboard

**SkyLink Security Dashboard** (UID: `skylink-security`)

Access: http://localhost:3000/d/skylink-security

### Dashboard Panels

#### Row 1: Authentication & Authorization
| Panel | Type | Metric |
|-------|------|--------|
| Auth Success Rate | Gauge | % of non-401 responses |
| Client Errors by Status | Pie | Distribution of 4xx |
| Authentication Failures | Time Series | 401/403 rate |
| mTLS Failures (1h) | Stat | Total 403 count |

#### Row 2: API Security
| Panel | Type | Metric |
|-------|------|--------|
| Rate Limited Requests | Time Series | 429 rate |
| Security Responses | Stacked Area | 401/403/429 |

#### Row 3: Performance & Latency
| Panel | Type | Metric |
|-------|------|--------|
| Request Latency | Time Series | p50/p95/p99 |
| Error Rate (5xx) | Gauge | Server error % |
| Request Rate | Time Series | Total RPS |

#### Row 4: Service Health
| Panel | Type | Metric |
|-------|------|--------|
| Service Status | Stat | UP/DOWN per service |
| Request Rate by Service | Bar | RPS per job |

### Dashboard Provisioning

Dashboards are auto-provisioned from:
- `monitoring/grafana/dashboards/security.json`

Configuration in:
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`

---

## 7. Metrics Reference

### HTTP Metrics (from prometheus-fastapi-instrumentator)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, status, handler | Total requests |
| `http_request_duration_seconds` | Histogram | method, handler | Request latency |
| `http_requests_inprogress` | Gauge | method, handler | In-flight requests |

### Security-Relevant Queries

```promql
# Authentication failure rate
sum(rate(http_requests_total{status="401"}[5m]))

# mTLS validation failures
sum(rate(http_requests_total{status="403"}[5m]))

# Rate limit hits
sum(rate(http_requests_total{status="429"}[5m]))

# Error rate percentage
100 * sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# p99 latency
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Request rate by service
sum by (job) (rate(http_requests_total[5m]))
```

---

## 8. Operational Procedures

### Starting Monitoring

```bash
# Start with the application
docker compose --profile monitoring up -d

# Start monitoring only (if app is already running)
docker compose --profile monitoring up -d prometheus grafana
```

### Stopping Monitoring

```bash
# Stop monitoring only
docker compose --profile monitoring down

# Stop everything
docker compose --profile monitoring down -v
```

### Updating Alert Rules

1. Edit `monitoring/prometheus/alerts/security.yml`
2. Reload Prometheus configuration:
   ```bash
   curl -X POST http://localhost:9090/-/reload
   ```
3. Verify rules loaded:
   ```bash
   curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules | length'
   ```

### Adding New Dashboards

1. Create dashboard JSON in `monitoring/grafana/dashboards/`
2. Dashboard will be auto-provisioned within 30 seconds
3. Or restart Grafana: `docker compose restart grafana`

### Backup and Restore

```bash
# Backup Prometheus data
docker run --rm -v prometheus_data:/data -v $(pwd):/backup alpine tar czf /backup/prometheus-backup.tar.gz /data

# Backup Grafana data
docker run --rm -v grafana_data:/data -v $(pwd):/backup alpine tar czf /backup/grafana-backup.tar.gz /data
```

---

## 9. Troubleshooting

### Prometheus Not Scraping

```bash
# Check target health
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'

# Common issues:
# - Service not running: check docker compose ps
# - Network issue: ensure services are on skylink-net
# - /metrics not exposed: check service configuration
```

### Grafana Dashboard Not Loading

```bash
# Check Grafana logs
docker compose logs grafana | tail -50

# Verify datasource
curl -s http://localhost:3000/api/datasources | jq '.[].name'

# Common issues:
# - Prometheus not reachable: check prometheus container
# - Dashboard JSON invalid: validate with jq
# - Datasource UID mismatch: see below
```

### Dashboard Shows "No data"

**Expected behavior for security panels:**

Some panels may show "No data" when there are no security events. This is **normal**:

| Panel | Shows "No data" when... |
|-------|------------------------|
| Authentication Failures | No 401 errors (good!) |
| mTLS Failures | No 403 errors (good!) |
| Rate Limited Requests | No 429 errors (good!) |
| Client Errors by Status | No 4xx errors (good!) |
| Security Responses | No 401/403/429 errors |

**Panels that should always show data:**
- Auth Success Rate: Shows 100% when no 401 errors
- Error Rate (5xx): Shows 0% when no 5xx errors
- Request Latency: Shows latency if any traffic exists
- Request Rate: Shows RPS if any traffic exists
- Service Status: Shows UP/DOWN for all services

**Datasource UID Mismatch:**

If ALL panels show "No data", check the datasource UID:

```bash
# Check datasource UID in Grafana
curl -s http://localhost:3000/api/datasources | jq '.[0].uid'

# Should return: "prometheus"
# If different, the dashboard won't find the datasource
```

The datasource provisioning file must include explicit UID:

```yaml
# monitoring/grafana/provisioning/datasources/prometheus.yml
datasources:
  - name: Prometheus
    uid: prometheus  # <-- Must match dashboard references
    type: prometheus
    ...
```

**To generate test security events:**

```bash
# Generate 401 errors (invalid token)
curl -s http://localhost:8000/telemetry/health -H "Authorization: Bearer invalid"

# Generate 429 errors (exceed rate limit)
for i in $(seq 1 70); do
  curl -s "http://localhost:8000/weather/current?lat=48&lon=2" \
    -H "Authorization: Bearer $TOKEN" > /dev/null
done
```

### Alerts Not Firing

```bash
# Check alert rule status
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | {name: .name, health: .health, lastError: .lastError}'

# Check if metrics exist
curl -s 'http://localhost:9090/api/v1/query?query=http_requests_total' | jq '.data.result | length'

# Common issues:
# - No traffic: alerts need traffic to evaluate
# - Wrong expression: test in Prometheus UI
```

### High Memory Usage

```bash
# Check Prometheus memory
docker stats prometheus

# Reduce retention (default 15d)
# Add to prometheus command: --storage.tsdb.retention.time=7d
```

---

## Appendix A: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAFANA_PASSWORD` | admin | Grafana admin password |

## Appendix B: Ports Reference

| Service | Internal | External | Protocol |
|---------|----------|----------|----------|
| Gateway | 8000 | 8000 | HTTP |
| Telemetry | 8001 | - | HTTP |
| Weather | 8002 | - | HTTP |
| Contacts | 8003 | - | HTTP |
| Prometheus | 9090 | 9090 | HTTP |
| Grafana | 3000 | 3000 | HTTP |

---

*Document maintained as part of SkyLink Security by Design implementation.*
