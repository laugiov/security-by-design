# GitHub CI/CD Setup Guide

This guide explains how to configure GitHub Actions to run the complete CI/CD pipeline for SkyLink.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Repository Secrets Configuration](#repository-secrets-configuration)
4. [Repository Variables Configuration](#repository-variables-configuration)
5. [GitHub Actions Workflow](#github-actions-workflow)
6. [Cosign Setup (Supply Chain Security)](#cosign-setup-supply-chain-security)
7. [Branch Protection Rules](#branch-protection-rules)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The CI/CD pipeline includes the following stages:

| Stage | Jobs | Description |
|-------|------|-------------|
| **Lint** | ruff, black, bandit | Code quality and security linting |
| **Test** | pytest | Unit tests with coverage (min 75%) |
| **Build** | docker build | Build and push Docker images |
| **Scan** | trivy, gitleaks, pip-audit | Security scanning |
| **SBOM** | cyclonedx | Software Bill of Materials |
| **DAST** | ZAP | Dynamic Application Security Testing |
| **Sign** | cosign | Image signing and SBOM attestation |

---

## Prerequisites

Before setting up CI/CD, ensure you have:

- [ ] GitHub repository created
- [ ] Docker Hub account OR GitHub Container Registry enabled
- [ ] (Optional) Cosign key pair for image signing
- [ ] (Optional) WeatherAPI key for weather service

---

## Repository Secrets Configuration

Go to: **Settings → Secrets and variables → Actions → Secrets**

### Required Secrets

| Secret Name | Description | How to Generate |
|-------------|-------------|-----------------|
| `PRIVATE_KEY_PEM` | RSA private key for JWT signing | See [Generate RSA Keys](#generate-rsa-keys) |
| `PUBLIC_KEY_PEM` | RSA public key for JWT verification | See [Generate RSA Keys](#generate-rsa-keys) |

### Optional Secrets (for full functionality)

| Secret Name | Description | How to Generate |
|-------------|-------------|-----------------|
| `DOCKERHUB_USERNAME` | Docker Hub username | Your Docker Hub account |
| `DOCKERHUB_TOKEN` | Docker Hub access token | Docker Hub → Account Settings → Security |
| `COSIGN_PRIVATE_KEY` | Cosign private key (base64) | See [Cosign Setup](#cosign-setup-supply-chain-security) |
| `COSIGN_PASSWORD` | Password for Cosign private key | Your chosen password |
| `COSIGN_PUBLIC_KEY` | Cosign public key (base64) | See [Cosign Setup](#cosign-setup-supply-chain-security) |
| `WEATHER_API_KEY` | WeatherAPI.com API key | https://www.weatherapi.com/ |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Google Cloud Console |
| `ENCRYPTION_KEY` | 32-byte hex key for token encryption | `openssl rand -hex 32` |

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

## Repository Variables Configuration

Go to: **Settings → Secrets and variables → Actions → Variables**

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `REGISTRY` | `ghcr.io` | Container registry (or `docker.io`) |
| `IMAGE_NAME` | `${{ github.repository }}` | Image name |
| `PYTHON_VERSION` | `3.12` | Python version |

---

## GitHub Actions Workflow

Create the file `.github/workflows/ci.yml`:

```yaml
name: SkyLink CI/CD

on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master]
  release:
    types: [published]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  PYTHON_VERSION: "3.12"

jobs:
  # ============================================
  # LINT
  # ============================================
  lint:
    name: Lint & Security Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install linters
        run: pip install ruff black bandit

      - name: Run Ruff
        run: ruff check .

      - name: Run Black
        run: black --check .

      - name: Run Bandit
        run: bandit -r skylink -q --severity-level high

  # ============================================
  # TEST
  # ============================================
  test:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          virtualenvs-create: true
          virtualenvs-in-project: true

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}

      - name: Install dependencies
        run: poetry install --no-interaction

      - name: Generate test certificates
        run: |
          chmod +x scripts/generate_test_certs.sh
          ./scripts/generate_test_certs.sh || echo "Certificate generation skipped"

      - name: Run tests
        env:
          PRIVATE_KEY_PEM: ${{ secrets.PRIVATE_KEY_PEM }}
          PUBLIC_KEY_PEM: ${{ secrets.PUBLIC_KEY_PEM }}
        run: |
          poetry run pytest -q \
            --junitxml=report.xml \
            --cov=skylink \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=75

      - name: Upload coverage report
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          fail_ci_if_error: false

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results
          path: report.xml

  # ============================================
  # SECRET SCANNING (Gitleaks)
  # ============================================
  gitleaks:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  # ============================================
  # SCA (Dependency Audit)
  # ============================================
  sca:
    name: Dependency Audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry and pip-audit
        run: |
          pip install poetry pip-audit poetry-plugin-export
          poetry self add poetry-plugin-export || true

      - name: Export requirements
        run: poetry export -f requirements.txt --only main --without-hashes -o requirements.txt

      - name: Run pip-audit
        run: pip-audit -r requirements.txt --strict

  # ============================================
  # BUILD & PUSH
  # ============================================
  build:
    name: Build & Push Image
    runs-on: ubuntu-latest
    needs: [lint, test, gitleaks, sca]
    permissions:
      contents: read
      packages: write
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
      image_digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile.gateway
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ============================================
  # TRIVY SCAN
  # ============================================
  trivy:
    name: Container Scan (Trivy)
    runs-on: ubuntu-latest
    needs: [build]
    permissions:
      contents: read
      packages: read
      security-events: write
    steps:
      - uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'HIGH,CRITICAL'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

  # ============================================
  # SBOM
  # ============================================
  sbom:
    name: Generate SBOM
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install tools
        run: |
          pip install poetry cyclonedx-bom poetry-plugin-export
          poetry self add poetry-plugin-export || true

      - name: Export requirements
        run: poetry export -f requirements.txt --without-hashes -o requirements.txt

      - name: Generate SBOM
        run: python -m cyclonedx_py requirements -i requirements.txt -o sbom.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json

  # ============================================
  # DAST (ZAP Scan)
  # ============================================
  zap:
    name: DAST (ZAP Scan)
    runs-on: ubuntu-latest
    needs: [build]
    permissions:
      contents: read
      packages: read
    steps:
      - uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Start application
        run: |
          docker run -d --name skylink -p 8000:8000 \
            -e PRIVATE_KEY_PEM="${{ secrets.PRIVATE_KEY_PEM }}" \
            -e PUBLIC_KEY_PEM="${{ secrets.PUBLIC_KEY_PEM }}" \
            -e DEMO_MODE=true \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

          # Wait for app to be ready
          for i in {1..30}; do
            if curl -s http://localhost:8000/health > /dev/null; then
              echo "Application is ready"
              break
            fi
            echo "Waiting for application... ($i/30)"
            sleep 2
          done

      - name: Run ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.12.0
        with:
          target: 'http://localhost:8000'
          rules_file_name: '.zap/rules.tsv'
          allow_issue_writing: false

      - name: Stop application
        if: always()
        run: docker stop skylink || true

  # ============================================
  # SIGN IMAGE (Cosign)
  # ============================================
  sign:
    name: Sign Image
    runs-on: ubuntu-latest
    needs: [build, trivy]
    if: github.event_name != 'pull_request'
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4

      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Sign image with Cosign
        if: ${{ secrets.COSIGN_PRIVATE_KEY != '' }}
        env:
          COSIGN_PRIVATE_KEY: ${{ secrets.COSIGN_PRIVATE_KEY }}
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          cosign sign --yes --key env://COSIGN_PRIVATE_KEY \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Sign image with keyless signing (Sigstore)
        if: ${{ secrets.COSIGN_PRIVATE_KEY == '' }}
        run: |
          cosign sign --yes \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

  # ============================================
  # ATTEST SBOM
  # ============================================
  attest:
    name: Attest SBOM
    runs-on: ubuntu-latest
    needs: [sign, sbom]
    if: github.event_name != 'pull_request'
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4

      - name: Install Cosign
        uses: sigstore/cosign-installer@v3

      - name: Download SBOM
        uses: actions/download-artifact@v4
        with:
          name: sbom

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Attest SBOM with Cosign
        if: ${{ secrets.COSIGN_PRIVATE_KEY != '' }}
        env:
          COSIGN_PRIVATE_KEY: ${{ secrets.COSIGN_PRIVATE_KEY }}
          COSIGN_PASSWORD: ${{ secrets.COSIGN_PASSWORD }}
        run: |
          cosign attest --yes --key env://COSIGN_PRIVATE_KEY \
            --predicate sbom.json --type cyclonedx \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

      - name: Attest SBOM with keyless signing
        if: ${{ secrets.COSIGN_PRIVATE_KEY == '' }}
        run: |
          cosign attest --yes \
            --predicate sbom.json --type cyclonedx \
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
```

---

## Cosign Setup (Supply Chain Security)

Cosign is used to sign Docker images and attest SBOMs. You have two options:

### Option A: Keyless Signing (Recommended for Open Source)

No setup required! GitHub Actions will use Sigstore's keyless signing with OIDC.

The workflow already supports this - just don't set `COSIGN_PRIVATE_KEY`.

### Option B: Key-based Signing

```bash
# Generate Cosign key pair
cosign generate-key-pair

# This creates:
# - cosign.key (private key - keep secret!)
# - cosign.pub (public key - can be shared)

# Add to GitHub Secrets:
# COSIGN_PRIVATE_KEY = content of cosign.key
# COSIGN_PASSWORD = password you entered during generation
# COSIGN_PUBLIC_KEY = content of cosign.pub (optional, for verification)
```

### Verify Signed Images

```bash
# Keyless verification (Sigstore)
cosign verify \
  --certificate-identity-regexp="https://github.com/YOUR_ORG/skylink" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/YOUR_ORG/skylink:latest

# Key-based verification
cosign verify --key cosign.pub ghcr.io/YOUR_ORG/skylink:latest
```

---

## Branch Protection Rules

Go to: **Settings → Branches → Add rule**

Configure for `main` (or `master`):

- [x] **Require a pull request before merging**
  - [x] Require approvals: 1
  - [x] Dismiss stale pull request approvals when new commits are pushed

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Required checks:
    - `lint`
    - `test`
    - `gitleaks`
    - `sca`

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

#### 4. Trivy finds vulnerabilities

**Cause**: Base image or dependencies have CVEs.

**Solution**:
- Update base image in Dockerfile
- Update dependencies: `poetry update`
- Or add to `.trivyignore`:
  ```
  CVE-2023-XXXXX
  ```

#### 5. ZAP scan fails

**Cause**: Application not starting or port conflict.

**Solution**:
- Check application logs: `docker logs skylink`
- Ensure `DEMO_MODE=true` for testing without external dependencies
- Increase wait time in workflow

### Debugging Tips

1. **Enable debug logging**:
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
   ```

2. **SSH into runner** (for debugging):
   ```yaml
   - name: Debug with tmate
     uses: mxschmitt/action-tmate@v3
   ```

3. **Check secrets availability**:
   ```yaml
   - name: Check secrets
     run: |
       if [ -n "${{ secrets.PRIVATE_KEY_PEM }}" ]; then
         echo "PRIVATE_KEY_PEM is set"
       else
         echo "PRIVATE_KEY_PEM is NOT set"
       fi
   ```

---

## Quick Start Checklist

- [ ] Create repository on GitHub
- [ ] Generate RSA keys and add to Secrets
- [ ] Copy `.github/workflows/ci.yml` to your repository
- [ ] Push code to trigger first pipeline
- [ ] Configure branch protection rules
- [ ] (Optional) Set up Codecov for coverage reports
- [ ] (Optional) Generate Cosign keys for image signing

---

## Security Considerations

1. **Never commit secrets** to the repository
2. **Use protected secrets** for production keys
3. **Rotate keys** every 90 days
4. **Review Dependabot alerts** regularly
5. **Enable GitHub Advanced Security** if available
6. **Use signed commits** (GPG or SSH)

---

## Related Documentation

- [DEMO.md](DEMO.md) - Manual testing guide
- [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) - Architecture details
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines

---

*Last updated: December 2025*
