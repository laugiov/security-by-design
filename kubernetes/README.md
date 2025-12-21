# SkyLink Kubernetes Deployment

Production-ready Kubernetes deployment for the SkyLink Connected Aircraft Platform.

## Quick Start

### Prerequisites

- Kubernetes 1.25+
- Helm 3.10+
- kubectl configured for your cluster
- Docker images built and pushed to a registry
- (Optional) Prometheus Operator for monitoring

> **Note**: This is a demonstration project. The default image repositories (`ghcr.io/skylink/*`) don't exist. You must build and push the images yourself, or override the image repositories in values.yaml.

### Installation

```bash
# Install with development values (creates namespace automatically)
helm install skylink ./skylink \
  --namespace skylink \
  --create-namespace \
  -f skylink/values-dev.yaml \
  --set secrets.jwtPrivateKey="$(cat /path/to/private.pem)" \
  --set secrets.jwtPublicKey="$(cat /path/to/public.pem)" \
  --set secrets.encryptionKey="$(openssl rand -hex 32)"

# Verify installation
helm test skylink -n skylink
kubectl get pods -n skylink
```

### Environment-Specific Deployments

```bash
# Development (with in-cluster secrets)
helm install skylink ./skylink \
  --namespace skylink \
  --create-namespace \
  -f skylink/values-dev.yaml \
  --set secrets.jwtPrivateKey="$(cat keys/jwt.private)" \
  --set secrets.jwtPublicKey="$(cat keys/jwt.public)" \
  --set secrets.encryptionKey="$(openssl rand -hex 32)"

# Staging (secrets must be pre-created or use external secrets)
helm install skylink ./skylink \
  --namespace skylink \
  --create-namespace \
  -f skylink/values-staging.yaml

# Production (secrets must be pre-created externally)
helm install skylink ./skylink \
  --namespace skylink \
  --create-namespace \
  -f skylink/values-prod.yaml
```

> **Note**: For staging/production, create the secret manually first:
> ```bash
> kubectl create secret generic skylink-secrets -n skylink \
>   --from-file=JWT_PRIVATE_KEY=keys/jwt.private \
>   --from-file=JWT_PUBLIC_KEY=keys/jwt.public \
>   --from-literal=ENCRYPTION_KEY="$(openssl rand -hex 32)"
> ```

## Security Features

| Feature | Implementation |
|---------|----------------|
| **Pod Security Standards** | Restricted profile enforced |
| **Non-root containers** | runAsUser: 1000 |
| **Read-only filesystem** | readOnlyRootFilesystem: true |
| **Dropped capabilities** | drop: [ALL] |
| **Network Policies** | Zero-trust, deny-all default |
| **Service Account** | automountServiceAccountToken: false |
| **Secrets Management** | External Secrets Operator support |
| **mTLS Ingress** | Optional client certificate verification |

## Chart Structure

```
kubernetes/
├── skylink/
│   ├── Chart.yaml              # Chart metadata
│   ├── values.yaml             # Default values
│   ├── values-dev.yaml         # Development overrides
│   ├── values-staging.yaml     # Staging overrides
│   ├── values-prod.yaml        # Production overrides
│   └── templates/
│       ├── _helpers.tpl        # Template helpers
│       ├── namespace.yaml      # Namespace with PSS labels
│       ├── configmap.yaml      # Non-sensitive configuration
│       ├── secrets.yaml        # Secret references
│       ├── deployment-*.yaml   # Service deployments
│       ├── service-*.yaml      # Service definitions
│       ├── ingress.yaml        # Ingress with TLS
│       ├── networkpolicy.yaml  # Network policies
│       ├── rbac.yaml           # Kubernetes RBAC
│       ├── serviceaccount.yaml # Service accounts
│       ├── horizontalpodautoscaler.yaml
│       ├── poddisruptionbudget.yaml
│       ├── servicemonitor.yaml # Prometheus integration
│       └── tests/
│           └── test-connection.yaml
└── README.md
```

## Configuration

### Key Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `gateway.replicaCount` | Gateway replicas | `2` |
| `gateway.autoscaling.enabled` | Enable HPA | `true` |
| `networkPolicy.enabled` | Enable NetworkPolicies | `true` |
| `ingress.enabled` | Enable Ingress | `true` |
| `ingress.mtls.enabled` | Require client certs | `false` |
| `secrets.create` | Create secrets in-cluster | `false` |
| `monitoring.serviceMonitor.enabled` | Create ServiceMonitor | `true` |

See [values.yaml](skylink/values.yaml) for all options.

## Production Checklist

- [ ] Use External Secrets Operator or Vault for secrets
- [ ] Enable NetworkPolicies (`networkPolicy.enabled: true`)
- [ ] Enable mTLS on Ingress (`ingress.mtls.enabled: true`)
- [ ] Set specific image tags (not `latest`)
- [ ] Configure resource limits for all containers
- [ ] Enable PodDisruptionBudget (`podDisruptionBudget.enabled: true`)
- [ ] Use managed PostgreSQL (disable in-cluster deployment)
- [ ] Configure cert-manager for TLS certificates
- [ ] Set up Prometheus monitoring

## Troubleshooting

### Pods not starting

```bash
# Check events
kubectl get events -n skylink --sort-by='.lastTimestamp'

# Check pod logs
kubectl logs -n skylink -l app.kubernetes.io/component=gateway
```

### Network policy issues

```bash
# Temporarily disable for debugging
helm upgrade skylink ./skylink -n skylink --set networkPolicy.enabled=false

# Re-enable after debugging
helm upgrade skylink ./skylink -n skylink --set networkPolicy.enabled=true
```

### Secret issues

```bash
# Verify secret exists
kubectl get secrets -n skylink

# Check secret content (base64 encoded)
kubectl get secret skylink-secrets -n skylink -o yaml
```

## Related Documentation

- [KUBERNETES.md](../docs/KUBERNETES.md) - Detailed deployment guide
- [SECURITY_ARCHITECTURE.md](../docs/SECURITY_ARCHITECTURE.md) - Security controls
- [MONITORING.md](../docs/MONITORING.md) - Prometheus & Grafana setup
