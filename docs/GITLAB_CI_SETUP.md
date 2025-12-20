# GitLab CI/CD Setup Guide

This guide explains how to configure GitLab CI/CD to run the complete pipeline for SkyLink.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [CI/CD Variables Configuration](#cicd-variables-configuration)
4. [Pipeline Configuration](#pipeline-configuration)
5. [Cosign Setup (Supply Chain Security)](#cosign-setup-supply-chain-security)
6. [Protected Branches](#protected-branches)
7. [Container Registry Setup](#container-registry-setup)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The CI/CD pipeline includes the following stages:

| Stage | Jobs | Description |
|-------|------|-------------|
| **lint** | ruff, black, bandit | Code quality and security linting |
| **test** | pytest | Unit tests with coverage (min 75%) |
| **build** | kaniko | Build and push Docker images |
| **scan** | trivy, gitleaks, pip-audit, openapi | Security scanning |
| **sbom** | cyclonedx | Software Bill of Materials |
| **security-scan** | ZAP | Dynamic Application Security Testing |
| **sign** | cosign | Image signing and SBOM attestation |

---

## Prerequisites

Before setting up CI/CD, ensure you have:

- [ ] GitLab repository created
- [ ] GitLab Container Registry enabled (Settings → General → Visibility → Container Registry)
- [ ] GitLab Runner available (shared or project-specific)
- [ ] (Optional) Cosign key pair for image signing
- [ ] (Optional) WeatherAPI key for weather service

---

## CI/CD Variables Configuration

Go to: **Settings → CI/CD → Variables**

### Required Variables

| Variable Name | Type | Description | Protected | Masked |
|---------------|------|-------------|-----------|--------|
| `PRIVATE_KEY_PEM` | Variable | RSA private key for JWT signing | Yes | No* |
| `PUBLIC_KEY_PEM` | Variable | RSA public key for JWT verification | Yes | No* |

> *Keys are too large to mask in GitLab (max 4 characters visible)

### Optional Variables (for full functionality)

| Variable Name | Type | Description | Protected | Masked |
|---------------|------|-------------|-----------|--------|
| `COSIGN_PRIVATE_KEY` | File | Cosign private key file | Yes | No |
| `COSIGN_PASSWORD` | Variable | Password for Cosign private key | Yes | Yes |
| `COSIGN_PUBLIC_KEY` | File | Cosign public key file | Yes | No |
| `WEATHER_API_KEY` | Variable | WeatherAPI.com API key | Yes | Yes |
| `GOOGLE_CLIENT_ID` | Variable | Google OAuth client ID | Yes | No |
| `GOOGLE_CLIENT_SECRET` | Variable | Google OAuth client secret | Yes | Yes |
| `ENCRYPTION_KEY` | Variable | 32-byte hex key for token encryption | Yes | Yes |

### Generate RSA Keys

```bash
# Generate RSA key pair
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# Display keys (copy entire content including BEGIN/END lines)
cat private.pem   # → PRIVATE_KEY_PEM
cat public.pem    # → PUBLIC_KEY_PEM
```

### Adding Variables in GitLab

1. Go to **Settings → CI/CD → Variables**
2. Click **Add variable**
3. Configure:
   - **Key**: Variable name (e.g., `PRIVATE_KEY_PEM`)
   - **Value**: Paste the entire key content
   - **Type**: `Variable` (or `File` for Cosign keys)
   - **Environment scope**: `All` (or specific environment)
   - **Protect variable**: ✅ (recommended for secrets)
   - **Mask variable**: ❌ for keys (too large), ✅ for passwords
   - **Expand variable reference**: ❌

**Important**: For multi-line values (like PEM keys), paste the entire content including `-----BEGIN...-----` and `-----END...-----` lines.

---

## Pipeline Configuration

The pipeline is defined in `.gitlab-ci.yml` at the repository root.

### Pipeline Stages

```yaml
stages: [lint, test, build, scan, sbom, security-scan, sign]
```

### Key Jobs

#### Lint Stage
```yaml
lint:
  stage: lint
  script:
    - pip install ruff black bandit
    - ruff check .
    - black --check .
    - bandit -r skylink -q --severity-level high
```

#### Test Stage
```yaml
test:
  stage: test
  script:
    - poetry install --no-interaction --no-ansi
    - ./scripts/generate_test_certs.sh || echo "Certificate generation skipped"
    - poetry run pytest -q --junitxml=report.xml --cov=skylink --cov-report=term-missing --cov-fail-under=75
  artifacts:
    reports:
      junit: report.xml
```

#### Build Stage (Kaniko)
```yaml
build_image:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:debug
    entrypoint: [""]
  script:
    - /kaniko/executor
        --context $CI_PROJECT_DIR
        --dockerfile $CI_PROJECT_DIR/Dockerfile.gateway
        --destination $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
        --destination $CI_REGISTRY_IMAGE:latest
```

#### Security Scans
```yaml
# Container scanning
trivy_image:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - trivy image --severity HIGH,CRITICAL --exit-code 1 $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA

# Secret detection
gitleaks:
  stage: scan
  image: zricethezav/gitleaks:latest
  script:
    - gitleaks detect --config .gitleaks.toml --source . --exit-code 1

# Dependency audit
sca_pip_audit:
  stage: scan
  script:
    - pip-audit -r requirements.txt --strict
```

#### SBOM Generation
```yaml
sbom:
  stage: sbom
  script:
    - pip install cyclonedx-bom
    - poetry export -f requirements.txt --without-hashes -o requirements.txt
    - python -m cyclonedx_py requirements -i requirements.txt -o sbom.json
  artifacts:
    paths:
      - sbom.json
```

#### DAST (ZAP)
```yaml
zap_scan:
  stage: security-scan
  image: ghcr.io/zaproxy/zaproxy:stable
  services:
    - name: $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
      alias: skylink
  script:
    - zap-baseline.py -t "http://skylink:8000" -r zap-report.html
  artifacts:
    paths:
      - zap-report.html
```

#### Image Signing (Cosign)
```yaml
sign_image:
  stage: sign
  image: cgr.dev/chainguard/cosign:latest
  script:
    - cosign sign --key "$COSIGN_PRIVATE_KEY" "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"
  rules:
    - if: $CI_COMMIT_BRANCH == "master"
```

---

## Cosign Setup (Supply Chain Security)

Cosign is used to sign Docker images and attest SBOMs.

### Generate Cosign Key Pair

```bash
# Generate Cosign key pair
cosign generate-key-pair

# This creates:
# - cosign.key (private key - keep secret!)
# - cosign.pub (public key - can be shared)
```

### Add Keys to GitLab

1. Go to **Settings → CI/CD → Variables**
2. Add `COSIGN_PRIVATE_KEY`:
   - **Type**: `File`
   - **Value**: Upload `cosign.key` content
   - **Protected**: ✅
3. Add `COSIGN_PASSWORD`:
   - **Type**: `Variable`
   - **Value**: Password you entered during generation
   - **Protected**: ✅
   - **Masked**: ✅
4. Add `COSIGN_PUBLIC_KEY`:
   - **Type**: `File`
   - **Value**: Upload `cosign.pub` content
   - **Protected**: ✅

### Verify Signed Images

```bash
# Verify image signature
cosign verify --key cosign.pub registry.gitlab.com/YOUR_GROUP/skylink:latest

# Verify SBOM attestation
cosign verify-attestation --key cosign.pub --type cyclonedx registry.gitlab.com/YOUR_GROUP/skylink:latest
```

---

## Protected Branches

Go to: **Settings → Repository → Protected branches**

Configure for `master` (or `main`):

| Setting | Value |
|---------|-------|
| **Branch** | `master` |
| **Allowed to merge** | Maintainers |
| **Allowed to push** | No one |
| **Allowed to force push** | ❌ |
| **Code owner approval** | ✅ (if using CODEOWNERS) |

### Merge Request Settings

Go to: **Settings → Merge requests**

- [x] **Pipelines must succeed**
- [x] **All discussions must be resolved**
- [x] **Require approval from code owners**
- [ ] **Allow squash commits** (optional)
- [x] **Delete source branch by default**

---

## Container Registry Setup

### Enable Container Registry

1. Go to **Settings → General → Visibility, project features, permissions**
2. Enable **Container Registry**
3. Save changes

### Registry URL

Your images will be available at:
```
registry.gitlab.com/YOUR_GROUP/skylink:TAG
```

### Predefined CI Variables

GitLab provides these variables automatically:

| Variable | Description |
|----------|-------------|
| `CI_REGISTRY` | `registry.gitlab.com` |
| `CI_REGISTRY_IMAGE` | `registry.gitlab.com/YOUR_GROUP/skylink` |
| `CI_REGISTRY_USER` | `gitlab-ci-token` |
| `CI_REGISTRY_PASSWORD` | Auto-generated job token |
| `CI_COMMIT_SHORT_SHA` | Short commit SHA (for tagging) |

---

## Troubleshooting

### Common Issues

#### 1. "PRIVATE_KEY_PEM is not set"

**Cause**: Variable not configured or not accessible.

**Solution**:
- Check variable exists in **Settings → CI/CD → Variables**
- Ensure variable is not protected if running on unprotected branch
- Verify variable scope includes the current environment

#### 2. "Coverage below 75%"

**Cause**: Test coverage threshold not met.

**Solution**:
- Add more tests
- Or temporarily lower threshold:
  ```yaml
  script:
    - poetry run pytest --cov-fail-under=70
  ```

#### 3. Kaniko build fails with "unauthorized"

**Cause**: Registry authentication issue.

**Solution**:
```yaml
script:
  - echo "{\"auths\":{\"$CI_REGISTRY\":{\"username\":\"$CI_REGISTRY_USER\",\"password\":\"$CI_REGISTRY_PASSWORD\"}}}" > /kaniko/.docker/config.json
  - /kaniko/executor ...
```

#### 4. Trivy finds vulnerabilities

**Cause**: Base image or dependencies have CVEs.

**Solution**:
- Update base image in Dockerfile
- Update dependencies: `poetry update`
- Or ignore specific CVEs with `.trivyignore`:
  ```
  CVE-2023-XXXXX
  ```

#### 5. ZAP scan fails - "App not reachable"

**Cause**: Service not starting or network issue.

**Solution**:
- Ensure `FF_NETWORK_PER_BUILD: "true"` is set
- Check service health:
  ```yaml
  script:
    - for i in {1..10}; do wget -q --spider "$APP_URL/health" && break || sleep 2; done
  ```

#### 6. Cosign sign fails - "no key found"

**Cause**: COSIGN_PRIVATE_KEY variable is not a file type.

**Solution**:
- Ensure `COSIGN_PRIVATE_KEY` is added as **File** type, not Variable
- The file path is then available as `$COSIGN_PRIVATE_KEY`

### Debugging Tips

1. **Enable debug mode**:
   ```yaml
   variables:
     CI_DEBUG_TRACE: "true"
   ```

2. **Check variable availability**:
   ```yaml
   script:
     - if [ -n "$PRIVATE_KEY_PEM" ]; then echo "Key is set"; else echo "Key is NOT set"; fi
   ```

3. **View job logs**: Click on failed job → expand sections

4. **SSH into runner** (if using self-hosted):
   ```yaml
   script:
     - sleep 3600  # Keep job running for debugging
   ```

---

## Quick Start Checklist

- [ ] Create repository on GitLab
- [ ] Enable Container Registry
- [ ] Generate RSA keys and add to CI/CD Variables
- [ ] Verify `.gitlab-ci.yml` exists in repository root
- [ ] Push code to trigger first pipeline
- [ ] Configure protected branches
- [ ] (Optional) Generate Cosign keys for image signing
- [ ] (Optional) Set up merge request approvals

---

## GitLab-Specific Features

### Auto DevOps

If you want to use GitLab Auto DevOps alongside this custom pipeline, disable it:
- **Settings → CI/CD → Auto DevOps** → Disable

### Security Dashboard

View security findings in:
- **Security & Compliance → Vulnerability Report**

Requires GitLab Ultimate or enabling SAST/DAST templates.

### Dependency Scanning

GitLab provides built-in dependency scanning:
```yaml
include:
  - template: Security/Dependency-Scanning.gitlab-ci.yml
```

### Container Scanning

GitLab provides built-in container scanning:
```yaml
include:
  - template: Security/Container-Scanning.gitlab-ci.yml
```

---

## Security Considerations

1. **Never commit secrets** to the repository
2. **Use protected variables** for production keys
3. **Rotate keys** every 90 days
4. **Review Security Dashboard** regularly
5. **Enable merge request approvals** for protected branches
6. **Use signed commits** (GPG)

---

## Related Documentation

- [DEMO.md](DEMO.md) - Manual testing guide
- [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) - Architecture details
- [GITHUB_CI_SETUP.md](GITHUB_CI_SETUP.md) - GitHub Actions alternative
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines

---

*Last updated: December 2025*
