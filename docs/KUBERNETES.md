# SkyLink Kubernetes Deployment Guide

> **Production-ready Kubernetes deployment with security best practices**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start](#3-quick-start)
4. [Architecture](#4-architecture)
5. [Security Configuration](#5-security-configuration)
6. [Environment Configuration](#6-environment-configuration)
7. [Secrets Management](#7-secrets-management)
8. [Network Policies](#8-network-policies)
9. [Monitoring Integration](#9-monitoring-integration)
10. [Operations](#10-operations)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

The SkyLink Helm chart provides a complete Kubernetes deployment with:

- **4 microservices**: Gateway, Telemetry, Weather, Contacts
- **Pod Security Standards**: Restricted profile enforced
- **Network Policies**: Zero-trust networking
- **Horizontal Pod Autoscaler**: Automatic scaling
- **Pod Disruption Budgets**: High availability during updates
- **ServiceMonitor**: Prometheus Operator integration

### Key Security Features

| Feature | Implementation |
|---------|----------------|
| Non-root containers | `runAsUser: 1000` |
| Read-only filesystem | `readOnlyRootFilesystem: true` |
| No privilege escalation | `allowPrivilegeEscalation: false` |
| Dropped capabilities | `drop: [ALL]` |
| Seccomp profile | `RuntimeDefault` |
| No service account token | `automountServiceAccountToken: false` |
| Network segmentation | NetworkPolicies with deny-all default |

---

## 2. Prerequisites

### Required

- **Kubernetes**: 1.25 or later
- **Helm**: 3.10 or later
- **kubectl**: Configured for your cluster

### Optional

- **Prometheus Operator**: For ServiceMonitor support
- **cert-manager**: For automatic TLS certificates
- **External Secrets Operator**: For secret management
- **NGINX Ingress Controller**: For ingress with mTLS

### Verify Prerequisites

```bash
# Check Kubernetes version
kubectl version --short

# Check Helm version
helm version --short

# Check if Prometheus Operator is installed
kubectl get crd servicemonitors.monitoring.coreos.com
```

---

## 3. Quick Start

### 3.1 Local Development (kind/minikube)

```bash
# Create a kind cluster
kind create cluster --name skylink

# Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for ingress controller
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s

# Generate keys
openssl genrsa -out /tmp/private.pem 2048
openssl rsa -in /tmp/private.pem -pubout -out /tmp/public.pem

# Install SkyLink (values-dev.yaml has secrets.create=true)
helm install skylink ./kubernetes/skylink \
  --namespace skylink \
  --create-namespace \
  -f kubernetes/skylink/values-dev.yaml \
  --set secrets.jwtPrivateKey="$(cat /tmp/private.pem)" \
  --set secrets.jwtPublicKey="$(cat /tmp/public.pem)" \
  --set secrets.encryptionKey="$(openssl rand -hex 32)"

# Run Helm tests
helm test skylink -n skylink

# Port forward for testing
kubectl port-forward -n skylink svc/skylink-gateway 8000:8000
```

### 3.2 Production Deployment

```bash
# Create namespace
kubectl create namespace skylink

# Create secrets manually (or use External Secrets Operator)
kubectl create secret generic skylink-secrets -n skylink \
  --from-file=JWT_PRIVATE_KEY=/path/to/private.pem \
  --from-file=JWT_PUBLIC_KEY=/path/to/public.pem \
  --from-literal=ENCRYPTION_KEY="$(openssl rand -hex 32)"

# Install with production values
helm install skylink ./kubernetes/skylink \
  --namespace skylink \
  -f kubernetes/skylink/values-prod.yaml

# Verify deployment
kubectl get pods -n skylink
kubectl get ingress -n skylink
```

---

## 4. Architecture

### 4.1 Component Diagram

```
                              Internet
                                 │
                        ┌────────▼────────┐
                        │  Ingress (mTLS) │
                        │  + Rate Limit   │
                        └────────┬────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                      skylink namespace                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 NetworkPolicy (deny-all)                   │   │
│  │                                                            │   │
│  │    ┌─────────────┐                                        │   │
│  │    │   Gateway   │◄────── Only from Ingress               │   │
│  │    │    :8000    │                                        │   │
│  │    └──────┬──────┘                                        │   │
│  │           │                                                │   │
│  │           ▼                                                │   │
│  │    ┌──────────────────────────────────────────────────┐   │   │
│  │    │              Internal Services                    │   │   │
│  │    │                                                   │   │   │
│  │    │   ┌───────────┐ ┌───────────┐ ┌───────────┐      │   │   │
│  │    │   │ Telemetry │ │  Weather  │ │ Contacts  │      │   │   │
│  │    │   │   :8001   │ │   :8002   │ │   :8003   │      │   │   │
│  │    │   └───────────┘ └───────────┘ └─────┬─────┘      │   │   │
│  │    │                                      │            │   │   │
│  │    └──────────────────────────────────────┼────────────┘   │   │
│  │                                           │                │   │
│  │                                    ┌──────▼──────┐        │   │
│  │                                    │  PostgreSQL │        │   │
│  │                                    │    :5432    │        │   │
│  │                                    └─────────────┘        │   │
│  │                                                            │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Service Communication

| Source | Destination | Port | Protocol |
|--------|-------------|------|----------|
| Ingress | Gateway | 8000 | HTTP |
| Gateway | Telemetry | 8001 | HTTP |
| Gateway | Weather | 8002 | HTTP |
| Gateway | Contacts | 8003 | HTTP |
| Contacts | PostgreSQL | 5432 | TCP |
| Weather | External API | 443 | HTTPS |
| Contacts | Google API | 443 | HTTPS |
| Prometheus | All services | 8000-8003 | HTTP |

---

## 5. Security Configuration

### 5.1 Pod Security Context

All pods run with the restricted security profile:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault

containers:
  - securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
```

### 5.2 Resource Limits

All containers have resource limits to prevent DoS:

```yaml
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### 5.3 Service Account

Service accounts are created with minimal permissions:

```yaml
serviceAccount:
  create: true
  automountServiceAccountToken: false

# RBAC: Empty role (no Kubernetes API access)
rules: []
```

---

## 6. Environment Configuration

### 6.1 Development (`values-dev.yaml`)

- Single replicas
- Network policies disabled
- Demo mode enabled
- Secrets created in-cluster

### 6.2 Staging (`values-staging.yaml`)

- 2 replicas per service
- Network policies enabled
- External secrets manager
- ServiceMonitor enabled

### 6.3 Production (`values-prod.yaml`)

- 3+ replicas per service
- HPA enabled (up to 20 replicas)
- mTLS on ingress
- External secrets required
- PDB minAvailable: 2

### 6.4 Key Configuration Differences

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| `replicaCount` | 1 | 2 | 3 |
| `networkPolicy.enabled` | false | true | true |
| `ingress.mtls.enabled` | false | false | true |
| `secrets.create` | true | false | false |
| `autoscaling.enabled` | false | true | true |
| `podDisruptionBudget.minAvailable` | - | 1 | 2 |

---

## 7. Secrets Management

### 7.1 Development (In-Cluster Secrets)

```bash
helm install skylink ./kubernetes/skylink \
  --set secrets.create=true \
  --set secrets.jwtPrivateKey="$(cat private.pem)" \
  --set secrets.jwtPublicKey="$(cat public.pem)" \
  --set secrets.encryptionKey="$(openssl rand -hex 32)"
```

### 7.2 Production (External Secrets Operator)

```yaml
# values-prod.yaml
secrets:
  create: false
  externalSecrets:
    enabled: true
    secretStoreRef:
      name: vault-backend
      kind: ClusterSecretStore
    refreshInterval: "30m"
```

Required secrets in Vault:

| Path | Description |
|------|-------------|
| `skylink/jwt-private-key` | RSA 2048-bit private key (PEM) |
| `skylink/jwt-public-key` | RSA public key (PEM) |
| `skylink/encryption-key` | AES-256 key (64 hex chars) |
| `skylink/database-url` | PostgreSQL connection string |

### 7.3 Sealed Secrets Alternative

```bash
# Install Sealed Secrets controller
helm install sealed-secrets bitnami/sealed-secrets -n kube-system

# Create sealed secret
kubeseal --format yaml < secret.yaml > sealed-secret.yaml
kubectl apply -f sealed-secret.yaml -n skylink
```

---

## 8. Network Policies

### 8.1 Default Deny

All traffic is denied by default:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: skylink-default-deny
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### 8.2 Allowed Traffic

| Policy | From | To | Ports |
|--------|------|-----|-------|
| gateway-ingress | ingress-nginx | gateway | 8000 |
| gateway-egress | gateway | internal services | 8001-8003 |
| internal-ingress | gateway | telemetry/weather/contacts | 8001-8003 |
| internal-egress | internal services | external APIs | 443 |
| prometheus-scrape | monitoring | all pods | 8000-8003 |

### 8.3 Disable for Debugging

```bash
helm upgrade skylink ./kubernetes/skylink \
  --namespace skylink \
  --set networkPolicy.enabled=false
```

---

## 9. Monitoring Integration

### 9.1 ServiceMonitor

The chart creates a ServiceMonitor for Prometheus Operator:

```yaml
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s
```

### 9.2 Metrics Endpoints

| Service | Path | Port |
|---------|------|------|
| Gateway | /metrics | 8000 |
| Telemetry | /metrics | 8001 |
| Weather | /metrics | 8002 |
| Contacts | /metrics | 8003 |

### 9.3 Grafana Dashboards

Import the SkyLink dashboard from `monitoring/grafana/provisioning/dashboards/`.

---

## 10. Operations

### 10.1 Scaling

```bash
# Manual scaling
kubectl scale deployment skylink-gateway -n skylink --replicas=5

# View HPA status
kubectl get hpa -n skylink
```

### 10.2 Rolling Updates

```bash
# Update image
helm upgrade skylink ./kubernetes/skylink \
  --namespace skylink \
  --set gateway.image.tag=1.0.1

# Check rollout status
kubectl rollout status deployment/skylink-gateway -n skylink
```

### 10.3 Rollback

```bash
# View history
helm history skylink -n skylink

# Rollback to previous
helm rollback skylink 1 -n skylink
```

### 10.4 Backup Secrets

```bash
# Export secrets (for migration)
kubectl get secret skylink-secrets -n skylink -o yaml > secrets-backup.yaml

# Encrypt with kubeseal or remove before committing!
```

---

## 11. Troubleshooting

### 11.1 Pods Not Starting

```bash
# Check events
kubectl get events -n skylink --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod -n skylink -l app.kubernetes.io/component=gateway

# Check logs
kubectl logs -n skylink -l app.kubernetes.io/component=gateway --tail=100
```

### 11.2 Network Policy Issues

```bash
# Check if traffic is being blocked
kubectl logs -n kube-system -l k8s-app=cilium

# Temporarily disable for debugging
helm upgrade skylink ./kubernetes/skylink --set networkPolicy.enabled=false
```

### 11.3 Secret Issues

```bash
# Verify secret exists
kubectl get secret skylink-secrets -n skylink

# Check secret keys
kubectl get secret skylink-secrets -n skylink -o jsonpath='{.data}' | jq

# Check external secrets sync
kubectl get externalsecret -n skylink
```

### 11.4 Ingress Issues

```bash
# Check ingress
kubectl get ingress -n skylink
kubectl describe ingress skylink -n skylink

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
```

### 11.5 Health Check Failures

```bash
# Test health endpoint from inside cluster
kubectl run test --rm -it --image=busybox -- \
  wget -qO- http://skylink-gateway.skylink:8000/health
```

---

## Appendix: Helm Chart Values

### Full Reference

```bash
# View all default values
helm show values ./kubernetes/skylink

# View only changed values
helm get values skylink -n skylink
```

### Commonly Used Overrides

```bash
# Disable autoscaling
--set gateway.autoscaling.enabled=false

# Set specific image tag
--set gateway.image.tag=1.0.0

# Enable mTLS
--set ingress.mtls.enabled=true

# Custom ingress host
--set ingress.host=api.mycompany.com

# Increase replicas
--set gateway.replicaCount=5
```

---

*Document maintained as part of SkyLink Security by Design implementation.*
