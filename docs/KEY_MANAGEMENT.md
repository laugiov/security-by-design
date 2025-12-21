# SkyLink Key Management Guide

> **Comprehensive cryptographic key management with rotation procedures**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Cryptographic Inventory](#2-cryptographic-inventory)
3. [Key Generation](#3-key-generation)
4. [Key Storage](#4-key-storage)
5. [Key Rotation Procedures](#5-key-rotation-procedures)
6. [Emergency Procedures](#6-emergency-procedures)
7. [Audit & Compliance](#7-audit--compliance)
8. [Appendix: Scripts Reference](#appendix-scripts-reference)

---

## 1. Overview

### Purpose

This document defines the key management policies and procedures for all cryptographic materials used in the SkyLink platform. It ensures:

- **Confidentiality**: Keys are protected from unauthorized access
- **Integrity**: Keys cannot be modified without detection
- **Availability**: Keys are available when needed for operations
- **Accountability**: Key usage is logged and auditable

### Scope

This guide covers:
- JWT signing/verification keys (RS256)
- Data encryption keys (AES-256-GCM)
- mTLS certificates (X.509)
- Cosign image signing keys

### Key Principles

| Principle | Implementation |
|-----------|----------------|
| Least Privilege | Keys accessible only to services that need them |
| Defense in Depth | Multiple layers of key protection |
| Key Separation | Different keys for different purposes |
| Regular Rotation | Scheduled key rotation (90 days recommended) |
| Secure Destruction | Keys securely deleted after rotation |

---

## 2. Cryptographic Inventory

### 2.1 Current Keys

| Key Type | Algorithm | Size | Location | Rotation Period | Criticality |
|----------|-----------|------|----------|-----------------|-------------|
| JWT Signing Key | RS256 | 2048-bit | `PRIVATE_KEY_PEM` env | 90 days | **MAXIMUM** |
| JWT Verification Key | RS256 | 2048-bit | `PUBLIC_KEY_PEM` env | 90 days | HIGH |
| Token Encryption | AES-256-GCM | 256-bit | `ENCRYPTION_KEY` env | 90 days | **MAXIMUM** |
| mTLS CA Certificate | RSA/X.509 | 4096-bit | `certs/ca/ca.crt` | 10 years | **MAXIMUM** |
| mTLS Server Cert | RSA/X.509 | 2048-bit | `certs/server/` | 1 year | HIGH |
| mTLS Client Certs | RSA/X.509 | 2048-bit | `certs/clients/` | 1 year | HIGH |
| Cosign Signing Key | ECDSA P-256 | 256-bit | CI/CD secrets | 1 year | HIGH |

### 2.2 Key Criticality Levels

| Level | Description | Access Control |
|-------|-------------|----------------|
| **MAXIMUM** | Compromise affects all security | Hardware-backed, 2-person rule |
| **HIGH** | Significant impact on security | Encrypted storage, audit logging |
| **MEDIUM** | Limited security impact | Standard secret management |
| **LOW** | Minimal security impact | Environment variables acceptable |

### 2.3 Key Dependencies

```
┌──────────────────────────────────────────────────────────────┐
│                     KEY DEPENDENCY GRAPH                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────┐                                            │
│   │   CA Key    │ ────────┬───────────────────┐              │
│   │  (4096-bit) │         │                   │              │
│   └─────────────┘         ▼                   ▼              │
│                    ┌─────────────┐     ┌─────────────┐       │
│                    │ Server Cert │     │ Client Certs│       │
│                    │  (2048-bit) │     │  (2048-bit) │       │
│                    └─────────────┘     └─────────────┘       │
│                                                              │
│   ┌─────────────┐                                            │
│   │ JWT Private │ ──────────────────────┐                    │
│   │   (RS256)   │                       │                    │
│   └─────────────┘                       ▼                    │
│                                   ┌─────────────┐            │
│                                   │ JWT Tokens  │            │
│                                   │ (15min TTL) │            │
│                                   └─────────────┘            │
│                                                              │
│   ┌─────────────┐                                            │
│   │ Encryption  │ ──────────────────────┐                    │
│   │   Key       │                       │                    │
│   └─────────────┘                       ▼                    │
│                                   ┌─────────────┐            │
│                                   │ OAuth Tokens│            │
│                                   │ (encrypted) │            │
│                                   └─────────────┘            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Key Generation

### 3.1 JWT RS256 Keys

```bash
# Minimum: 2048 bits (NIST recommendation)
# Recommended: 4096 bits for long-term security

# Using the rotation script (recommended)
./scripts/rotate_jwt_keys.sh --key-size 2048

# Manual generation
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

**Security Requirements**:
- Minimum key size: 2048 bits
- Generated on secure system with sufficient entropy
- Private key immediately protected with restrictive permissions (600)

### 3.2 AES-256 Encryption Keys

```bash
# Using the rotation script (recommended)
./scripts/rotate_encryption_key.sh --format hex

# Manual generation
openssl rand -hex 32  # 256 bits = 32 bytes = 64 hex chars
```

**Security Requirements**:
- Must use cryptographically secure random number generator
- Key must be exactly 256 bits (32 bytes)
- Never derive from passwords without proper KDF (PBKDF2, Argon2)

### 3.3 mTLS Certificates

```bash
# Generate CA (first time only)
./scripts/generate_ca.sh

# Generate server certificate
./scripts/generate_server_cert.sh

# Generate client certificate
./scripts/generate_client_cert.sh aircraft-001

# Renew certificates
./scripts/renew_certificates.sh server
./scripts/renew_certificates.sh client aircraft-001
```

**Certificate Requirements**:

| Certificate | Key Size | Validity | Key Usage |
|-------------|----------|----------|-----------|
| CA | 4096-bit | 10 years | Certificate signing |
| Server | 2048-bit | 1 year | Server authentication |
| Client | 2048-bit | 1 year | Client authentication |

---

## 4. Key Storage

### 4.1 Development Environment

**Method**: Environment variables in `.env` file

```bash
# .env (NEVER commit to version control)
PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----\n..."
PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----\n..."
ENCRYPTION_KEY="a1b2c3d4..."
```

**Security Controls**:
- `.env` added to `.gitignore`
- `.env.example` contains only placeholders
- File permissions: `600` (owner read/write only)

### 4.2 CI/CD Environments

#### GitHub Actions

```yaml
# Settings > Secrets and variables > Actions

secrets:
  PRIVATE_KEY_PEM:     # JWT signing key
  PUBLIC_KEY_PEM:      # JWT verification key
  ENCRYPTION_KEY:      # AES-256 encryption key
  COSIGN_PRIVATE_KEY:  # Image signing key
  COSIGN_PASSWORD:     # Cosign key password
```

**See**: [docs/GITHUB_CI_SETUP.md](GITHUB_CI_SETUP.md) for detailed configuration.

#### GitLab CI/CD

```yaml
# Settings > CI/CD > Variables

variables:
  PRIVATE_KEY_PEM:     # Type: Variable, Protected, Masked
  PUBLIC_KEY_PEM:      # Type: Variable, Protected
  ENCRYPTION_KEY:      # Type: Variable, Protected, Masked
  COSIGN_PRIVATE_KEY:  # Type: File, Protected, Masked
  COSIGN_PASSWORD:     # Type: Variable, Protected, Masked
```

**See**: [docs/GITLAB_CI_SETUP.md](GITLAB_CI_SETUP.md) for detailed configuration.

### 4.3 Production Environment

#### Option 1: HashiCorp Vault (Recommended)

```bash
# Store keys in Vault
vault kv put secret/skylink/jwt \
  private_key=@private.pem \
  public_key=@public.pem

vault kv put secret/skylink/encryption \
  key="${ENCRYPTION_KEY}"

# Application retrieves at runtime
export PRIVATE_KEY_PEM=$(vault kv get -field=private_key secret/skylink/jwt)
```

**Benefits**:
- Dynamic secret generation
- Automatic rotation
- Detailed audit logging
- Lease-based access control

#### Option 2: AWS Secrets Manager

```bash
# Store secrets
aws secretsmanager create-secret \
  --name skylink/jwt-private-key \
  --secret-string file://private.pem

# Application retrieves via SDK
import boto3
client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='skylink/jwt-private-key')
```

#### Option 3: Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: skylink-jwt-keys
type: Opaque
data:
  private.pem: <base64-encoded-key>
  public.pem: <base64-encoded-key>
```

**Security**: Enable encryption at rest for etcd.

---

## 5. Key Rotation Procedures

### 5.1 JWT Key Rotation (Zero-Downtime)

**Strategy**: Dual-key verification period

```
Timeline:
────────────────────────────────────────────────────────────────
Day 0:  Generate new key pair (KEY_B)
        Configure: Sign with KEY_A, Verify with KEY_A + KEY_B
────────────────────────────────────────────────────────────────
Hour 1: Switch signing to KEY_B
        All new tokens use KEY_B
        Old tokens (KEY_A) still valid (15 min max TTL)
────────────────────────────────────────────────────────────────
Hour 2: Remove KEY_A from verification
        Only KEY_B active
────────────────────────────────────────────────────────────────
```

**Procedure**:

```bash
# Step 1: Generate new keys
./scripts/rotate_jwt_keys.sh --env-format

# Step 2: Add new public key to verification (deploy first)
# Update PUBLIC_KEY_PEM_NEW in environment

# Step 3: Deploy and restart services
docker compose restart gateway

# Step 4: Wait for old tokens to expire (15 min)
sleep 900

# Step 5: Switch to new private key for signing
# Update PRIVATE_KEY_PEM with new key

# Step 6: Deploy again
docker compose restart gateway

# Step 7: Remove old public key
# Set PUBLIC_KEY_PEM = PUBLIC_KEY_PEM_NEW
# Remove PUBLIC_KEY_PEM_NEW
```

### 5.2 Encryption Key Rotation

**Strategy**: Key versioning with re-encryption

```bash
# Step 1: Generate new key
./scripts/rotate_encryption_key.sh --version 2

# Step 2: Deploy with both keys available
# ENCRYPTION_KEY_V1 = old key
# ENCRYPTION_KEY_V2 = new key

# Step 3: Re-encrypt existing data
# Application decrypts with V1, re-encrypts with V2

# Step 4: Remove old key after all data migrated
```

**Data Format with Versioning**:
```
v1:base64(nonce):base64(ciphertext)  # Old format
v2:base64(nonce):base64(ciphertext)  # New format
```

### 5.3 Certificate Renewal

**Server Certificate**:

```bash
# Step 1: Renew certificate (30 days before expiry)
./scripts/renew_certificates.sh server

# Step 2: Deploy new certificate
docker compose restart gateway

# Step 3: Verify
openssl s_client -connect localhost:8443 -CAfile certs/ca/ca.crt
```

**Client Certificates**:

```bash
# For each client
./scripts/renew_certificates.sh client aircraft-001

# Distribute new certificate to client
# Update client configuration
```

### 5.4 Rotation Schedule

| Key Type | Rotation Period | Alert at | Owner |
|----------|-----------------|----------|-------|
| JWT Keys | 90 days | 14 days before | Security Team |
| Encryption Key | 90 days | 14 days before | Security Team |
| Server Cert | 1 year | 30 days before | DevOps |
| Client Certs | 1 year | 30 days before | DevOps |
| CA Cert | 10 years | 1 year before | Security Team |
| Cosign Key | 1 year | 30 days before | DevOps |

---

## 6. Emergency Procedures

### 6.1 Key Compromise Response

**Severity: CRITICAL**

**Immediate Actions** (within 15 minutes):

1. **Identify Scope**
   - Which key(s) compromised?
   - What data/systems affected?

2. **Revoke Compromised Keys**
   ```bash
   # For JWT keys: All existing tokens become invalid
   ./scripts/rotate_jwt_keys.sh
   # Deploy immediately

   # For certificates: Add to CRL
   # Update CA CRL and distribute
   ```

3. **Generate New Keys**
   ```bash
   ./scripts/rotate_jwt_keys.sh --env-format
   ./scripts/rotate_encryption_key.sh
   ```

4. **Deploy New Keys**
   - Update all secrets in CI/CD
   - Restart all services
   - Force re-authentication of all clients

**Post-Incident Actions** (within 24 hours):

5. **Investigate**
   - How was the key compromised?
   - Review access logs
   - Check for unauthorized usage

6. **Document**
   - Create incident report
   - Update security procedures
   - Notify affected parties (if required)

### 6.2 Emergency Rotation Checklist

```markdown
[ ] Identified compromised key type
[ ] Notified security team
[ ] Generated new keys
[ ] Updated CI/CD secrets
[ ] Deployed to all environments
[ ] Verified new keys working
[ ] Revoked old keys/certificates
[ ] Reviewed audit logs
[ ] Created incident report
[ ] Updated rotation schedule
```

### 6.3 Recovery from Key Loss

If private keys are lost but not compromised:

1. **Generate new key pairs**
2. **Re-encrypt data** (if encryption key lost)
3. **Reissue certificates** (if CA key lost, full PKI rebuild required)
4. **Update all dependent systems**

---

## 7. Audit & Compliance

### 7.1 Key Access Logging

All key operations should be logged:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "event": "key_rotation",
  "key_type": "jwt_signing",
  "key_id": "skylink-jwt-20240115",
  "actor": "ci-pipeline",
  "result": "success",
  "old_key_id": "skylink-jwt-20231015",
  "details": {
    "rotation_reason": "scheduled",
    "algorithm": "RS256",
    "key_size": 2048
  }
}
```

### 7.2 Rotation History

Maintain a rotation log:

| Date | Key Type | Old Key ID | New Key ID | Reason | Performed By |
|------|----------|------------|------------|--------|--------------|
| 2024-01-15 | JWT | skylink-jwt-20231015 | skylink-jwt-20240115 | Scheduled | CI/CD |
| 2024-01-15 | Encryption | v1 | v2 | Scheduled | CI/CD |

### 7.3 Compliance Requirements

| Standard | Requirement | SkyLink Implementation |
|----------|-------------|------------------------|
| **PCI-DSS** | Annual key rotation | 90-day rotation schedule |
| **SOC 2** | Key access controls | Role-based access + audit logs |
| **NIST 800-57** | Key size minimums | RSA 2048+, AES 256 |
| **GDPR** | Encryption of PII | AES-256-GCM for tokens |

### 7.4 Audit Checklist

```markdown
# Quarterly Key Management Audit

## Key Inventory
[ ] All keys documented in inventory
[ ] Key purposes clearly defined
[ ] Key ownership assigned

## Access Control
[ ] Access restricted to authorized personnel
[ ] Access logs reviewed
[ ] No unauthorized access detected

## Rotation
[ ] All keys within rotation period
[ ] Rotation procedures followed
[ ] Old keys securely destroyed

## Storage
[ ] Keys stored in approved locations
[ ] Encryption at rest enabled
[ ] Backup procedures verified

## Documentation
[ ] Key management procedures current
[ ] Emergency procedures documented
[ ] Training records up to date
```

---

## Appendix: Scripts Reference

### A.1 rotate_jwt_keys.sh

Generate new JWT RS256 key pair.

```bash
Usage: ./scripts/rotate_jwt_keys.sh [OPTIONS]

Options:
  --dry-run       Show what would be done
  --output DIR    Output directory (default: ./keys_new)
  --key-size SIZE RSA key size (default: 2048, min: 2048)
  --kid ID        Custom key ID
  --env-format    Output in .env format
  --backup        Backup existing keys
  --help          Show help
```

### A.2 rotate_encryption_key.sh

Generate new AES-256 encryption key.

```bash
Usage: ./scripts/rotate_encryption_key.sh [OPTIONS]

Options:
  --dry-run       Show what would be done
  --output DIR    Output directory
  --format FMT    Output format: hex, base64 (default: hex)
  --version VER   Key version identifier
  --env-format    Output in .env format
  --help          Show help
```

### A.3 renew_certificates.sh

Renew mTLS certificates.

```bash
Usage: ./scripts/renew_certificates.sh [OPTIONS] TYPE [NAME]

Types:
  server          Renew server certificate
  client NAME     Renew client certificate

Options:
  --dry-run       Show what would be done
  --new-key       Generate new private key
  --days DAYS     Validity in days (default: 365)
  --backup        Backup existing certificates
  --help          Show help
```

### A.4 generate_ca.sh

Generate Certificate Authority (first time only).

```bash
Usage: ./scripts/generate_ca.sh

Output:
  certs/ca/ca.crt  - CA certificate (distribute to all)
  certs/ca/ca.key  - CA private key (KEEP SECURE)
```

---

*Document maintained as part of SkyLink Security by Design implementation.*
