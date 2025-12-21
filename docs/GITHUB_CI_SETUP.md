# GitHub CI/CD Setup Guide

This guide explains how to configure GitHub Actions to run the complete CI/CD pipeline for SkyLink.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Repository Secrets Configuration](#repository-secrets-configuration)
4. [Pipeline Configuration](#pipeline-configuration)
5. [Cosign Setup (Supply Chain Security)](#cosign-setup-supply-chain-security)
6. [Branch Protection Rules](#branch-protection-rules)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The CI/CD pipeline includes the following stages:

| Stage | Jobs | Description |
|-------|------|-------------|
| **Lint** | ruff, black, bandit | Code quality and security linting |
| **Test** | pytest | Unit tests with coverage (min 75%) |
| **Build** | docker build | Build and push Docker images to GHCR |
| **Scan** | trivy, gitleaks, pip-audit, openapi | Security scanning |
| **SBOM** | cyclonedx | Software Bill of Materials |
| **DAST** | ZAP | Dynamic Application Security Testing |
| **Sign** | cosign | Image signing with Sigstore (keyless) |

---

## Prerequisites

Before setting up CI/CD, ensure you have:

- [x] GitHub repository created
- [x] GitHub Container Registry (GHCR) enabled (automatic with GitHub)
- [ ] RSA keys generated for JWT authentication
- [ ] (Optional) WeatherAPI key for weather service

> **Note**: No Cosign keys are required - the pipeline uses **keyless signing** with Sigstore OIDC.

---

## Repository Secrets Configuration

Go to: **Settings → Secrets and variables → Actions → Secrets**

### Required Secrets

| Secret Name | Description | How to Generate |
|-------------|-------------|-----------------|
| `PRIVATE_KEY_PEM` | RSA private key for JWT signing | See [Generate RSA Keys](#generate-rsa-keys) |
| `PUBLIC_KEY_PEM` | RSA public key for JWT verification | See [Generate RSA Keys](#generate-rsa-keys) |

### Optional Secrets

| Secret Name | Description | How to Generate |
|-------------|-------------|-----------------|
| `WEATHER_API_KEY` | WeatherAPI.com API key | https://www.weatherapi.com/ |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Google Cloud Console |
| `ENCRYPTION_KEY` | 32-byte hex key for token encryption | `openssl rand -hex 32` |

> **Note**: `COSIGN_*` secrets are **NOT required** - the pipeline uses Sigstore keyless signing.

### Generate RSA Keys

```bash
# Generate RSA key pair
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# Display keys (copy entire content including BEGIN/END lines)
cat private.pem   # → PRIVATE_KEY_PEM
cat public.pem    # → PUBLIC_KEY_PEM
```

**Important**: When adding to GitHub Secrets:
- Copy the **entire** content including `-----BEGIN...-----` and `-----END...-----` lines
- Do NOT base64 encode (GitHub handles this automatically)

---

## Pipeline Configuration

The pipeline is defined in `.github/workflows/ci.yml`.

### Key Features

1. **Image tagging**: Uses short SHA (`abc1234`) for consistent tagging across jobs
2. **Keyless signing**: Uses Sigstore OIDC - no keys to manage
3. **Fail-safe scans**: Trivy and ZAP use `continue-on-error: true` to not block the pipeline
4. **GHCR integration**: Uses GitHub Container Registry with automatic authentication

### Pipeline Flow

```
┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐
│ lint  │──▶│ test  │──▶│ build │──▶│ trivy │──▶│ sign  │
└───────┘   └───────┘   └───────┘   └───────┘   └───────┘
    │           │           │           │           │
    │           │           │           │           ▼
    │           │           │           │      ┌─────────┐
    │           │           │           └─────▶│ attest  │
    │           │           │                  └─────────┘
    │           │           │
    │           │           └──────────▶┌───────┐
    │           │                       │  zap  │
    │           │                       └───────┘
    │           │
    │           └──────────────────────▶┌───────┐
    │                                   │ sbom  │
    │                                   └───────┘
    │
    └──────────────────────────────────▶┌─────────┐
                                        │gitleaks │
                                        └─────────┘
```

### Build Job Output

The `build` job exports an `image_tag` output containing the short SHA:

```yaml
outputs:
  image_tag: ${{ steps.short_sha.outputs.sha }}
```

This tag is used by downstream jobs (trivy, zap, sign, attest) to reference the correct image.

### Image Tags Generated

| Tag | Example | Description |
|-----|---------|-------------|
| SHA | `abc1234` | Short commit SHA |
| Branch | `master` | Branch name |
| Latest | `latest` | Only on default branch |
| Version | `1.0.0` | Only on release tags |

---

## Cosign Setup (Supply Chain Security)

The pipeline uses **Sigstore keyless signing** by default - no setup required!

### How Keyless Signing Works

1. GitHub Actions provides an OIDC token
2. Sigstore's Fulcio CA issues a short-lived certificate
3. The image is signed with this certificate
4. Signature is recorded in Rekor transparency log

### Verify Signed Images

```bash
# Verify with keyless (Sigstore)
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

### Optional: Key-based Signing

If you prefer key-based signing, you can modify the workflow:

```bash
# Generate Cosign key pair
cosign generate-key-pair

# Add to GitHub Secrets:
# COSIGN_PRIVATE_KEY = content of cosign.key
# COSIGN_PASSWORD = password you entered
```

Then modify the sign job in `.github/workflows/ci.yml`:

```yaml
- name: Sign image with key
  env:
    COSIGN_PRIVATE_KEY: ${{ secrets.COSIGN_PRIVATE_KEY }}
    COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
  run: |
    cosign sign --yes --key env://COSIGN_PRIVATE_KEY \
      ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.build.outputs.image_tag }}
```

---

## Branch Protection Rules

Go to: **Settings → Branches → Add rule**

Configure for `master` (or `main`):

- [x] **Require a pull request before merging**
  - [x] Require approvals: 1
  - [x] Dismiss stale pull request approvals when new commits are pushed

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Required checks:
    - `Lint & Security Check`
    - `Unit Tests`
    - `Secret Scanning`
    - `Dependency Audit`

- [x] **Require conversation resolution before merging**

- [x] **Do not allow bypassing the above settings**

---

## Troubleshooting

### Common Issues

#### 1. "PRIVATE_KEY_PEM is not set"

**Cause**: Secret not configured or incorrect format.

**Solution**:
```bash
# Verify key format
cat private.pem | head -1
# Should output: -----BEGIN PRIVATE KEY-----

# Add to GitHub Secrets with exact content (no extra spaces/newlines)
```

#### 2. "Coverage below 75%"

**Cause**: Test coverage threshold not met.

**Solution**:
- Add more tests
- Or temporarily lower threshold in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  addopts = "--cov-fail-under=70"
  ```

#### 3. "Permission denied" on Docker push

**Cause**: GitHub token doesn't have package write permission.

**Solution**: Ensure workflow has:
```yaml
permissions:
  packages: write
```

#### 4. Trivy scan fails

**Cause**: Image not found or SARIF file not generated.

**Solution**: The current workflow handles this with:
- `docker pull` before scanning
- `exit-code: '0'` to not fail on vulnerabilities
- `continue-on-error: true` on the job

#### 5. ZAP scan fails - "manifest unknown"

**Cause**: Image tag mismatch between build and scan jobs.

**Solution**: The workflow now uses `needs.build.outputs.image_tag` to ensure consistent tagging. Make sure:
```yaml
# In ZAP job
docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.build.outputs.image_tag }}
```

#### 6. Cosign sign fails

**Cause**: Missing OIDC permissions.

**Solution**: Ensure the sign job has:
```yaml
permissions:
  id-token: write  # Required for keyless signing
  packages: write  # Required to push signature
```

### Debugging Tips

1. **Enable debug logging**:
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
   ```

2. **Check image exists**:
   ```yaml
   - name: List images
     run: |
       docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ needs.build.outputs.image_tag }}
       docker images
   ```

3. **View container logs on failure**:
   ```yaml
   - name: Debug on failure
     if: failure()
     run: docker logs skylink
   ```

---

## Quick Start Checklist

- [ ] Create repository on GitHub
- [ ] Generate RSA keys: `openssl genrsa -out private.pem 2048`
- [ ] Add `PRIVATE_KEY_PEM` secret
- [ ] Add `PUBLIC_KEY_PEM` secret
- [ ] Push code to trigger first pipeline
- [ ] Configure branch protection rules
- [ ] (Optional) Set up Codecov for coverage reports

> **No Cosign setup required** - keyless signing works automatically!

---

## Security Considerations

1. **Never commit secrets** to the repository
2. **Use protected secrets** for production keys
3. **Rotate RSA keys** every 90 days
4. **Review Dependabot alerts** regularly
5. **Enable GitHub Advanced Security** if available
6. **Use signed commits** (GPG or SSH)

---

## Related Documentation

- [DEMO.md](DEMO.md) - Manual testing guide
- [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) - Architecture details
- [GITLAB_CI_SETUP.md](GITLAB_CI_SETUP.md) - GitLab CI alternative
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines

---

*Last updated: December 2025*
