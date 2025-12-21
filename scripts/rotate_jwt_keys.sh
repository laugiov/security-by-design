#!/bin/bash
# JWT RS256 Key Rotation Script for SkyLink
#
# This script generates new RSA key pairs for JWT signing/verification.
# Supports zero-downtime rotation with optional key ID (kid) generation.
#
# Usage:
#   ./scripts/rotate_jwt_keys.sh [OPTIONS]
#
# Options:
#   --dry-run       Show what would be done without generating keys
#   --output DIR    Output directory (default: ./keys_new)
#   --key-size SIZE RSA key size in bits (default: 2048, min: 2048)
#   --kid ID        Custom key ID (default: auto-generated timestamp)
#   --env-format    Output keys in .env format (single line)
#   --backup        Backup current keys before generating new ones
#   --help          Show this help message
#
# Security Notes:
#   - Private keys must NEVER be committed to version control
#   - Use CI/CD secrets or a secrets manager in production
#   - Minimum key size is 2048 bits (NIST recommendation)
#   - Rotate keys every 90 days (recommended)
#
# Zero-Downtime Rotation Strategy:
#   1. Generate new key pair (this script)
#   2. Deploy new public key to verification (add to JWKS)
#   3. Wait for old tokens to expire (15 min TTL)
#   4. Switch signing to new private key
#   5. Remove old public key from verification

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${PROJECT_DIR}/keys_new"
KEY_SIZE=2048
MIN_KEY_SIZE=2048
KID=""
DRY_RUN=false
ENV_FORMAT=false
BACKUP=false

# Function to display usage
usage() {
    echo "JWT RS256 Key Rotation Script for SkyLink"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dry-run       Show what would be done without generating keys"
    echo "  --output DIR    Output directory (default: ./keys_new)"
    echo "  --key-size SIZE RSA key size in bits (default: 2048, min: 2048)"
    echo "  --kid ID        Custom key ID (default: auto-generated)"
    echo "  --env-format    Output keys in .env format (single line)"
    echo "  --backup        Backup current keys if they exist"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Generate new keys in ./keys_new"
    echo "  $0 --env-format             # Output in .env format"
    echo "  $0 --key-size 4096          # Use 4096-bit keys"
    echo "  $0 --dry-run                # Preview without generating"
    exit 0
}

# Function to log messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --key-size)
            KEY_SIZE="$2"
            shift 2
            ;;
        --kid)
            KID="$2"
            shift 2
            ;;
        --env-format)
            ENV_FORMAT=true
            shift
            ;;
        --backup)
            BACKUP=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate key size
if [[ $KEY_SIZE -lt $MIN_KEY_SIZE ]]; then
    log_error "Key size must be at least ${MIN_KEY_SIZE} bits (NIST recommendation)"
    exit 1
fi

# Generate key ID if not provided
if [[ -z "$KID" ]]; then
    KID="skylink-jwt-$(date +%Y%m%d%H%M%S)"
fi

# Display configuration
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           SkyLink JWT Key Rotation Script                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_info "Configuration:"
echo "  Output Directory: ${OUTPUT_DIR}"
echo "  Key Size:         ${KEY_SIZE} bits"
echo "  Key ID (kid):     ${KID}"
echo "  Dry Run:          ${DRY_RUN}"
echo "  Env Format:       ${ENV_FORMAT}"
echo "  Backup:           ${BACKUP}"
echo ""

# Dry run mode
if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - No keys will be generated"
    echo ""
    echo "Would perform the following actions:"
    echo "  1. Create directory: ${OUTPUT_DIR}"
    echo "  2. Generate RSA private key (${KEY_SIZE} bits)"
    echo "  3. Extract public key from private key"
    echo "  4. Create key ID file: ${KID}"
    if [[ "$ENV_FORMAT" == "true" ]]; then
        echo "  5. Output keys in .env format"
    fi
    echo ""
    exit 0
fi

# Check for OpenSSL
if ! command -v openssl &> /dev/null; then
    log_error "OpenSSL is required but not installed"
    exit 1
fi

# Backup existing keys if requested
if [[ "$BACKUP" == "true" && -d "$OUTPUT_DIR" ]]; then
    BACKUP_DIR="${OUTPUT_DIR}_backup_$(date +%Y%m%d%H%M%S)"
    log_info "Backing up existing keys to: ${BACKUP_DIR}"
    mv "$OUTPUT_DIR" "$BACKUP_DIR"
    log_success "Backup created"
fi

# Create output directory
log_info "Creating output directory: ${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

# Generate private key
PRIVATE_KEY_FILE="${OUTPUT_DIR}/private.pem"
log_info "Generating RSA private key (${KEY_SIZE} bits)..."
openssl genrsa -out "${PRIVATE_KEY_FILE}" ${KEY_SIZE} 2>/dev/null

# Protect private key
chmod 600 "${PRIVATE_KEY_FILE}"
log_success "Private key generated: ${PRIVATE_KEY_FILE}"

# Extract public key
PUBLIC_KEY_FILE="${OUTPUT_DIR}/public.pem"
log_info "Extracting public key..."
openssl rsa -in "${PRIVATE_KEY_FILE}" -pubout -out "${PUBLIC_KEY_FILE}" 2>/dev/null
log_success "Public key generated: ${PUBLIC_KEY_FILE}"

# Save key ID
KID_FILE="${OUTPUT_DIR}/kid.txt"
echo "${KID}" > "${KID_FILE}"
log_success "Key ID saved: ${KID_FILE}"

# Validate generated keys
log_info "Validating generated keys..."

# Verify private key
if openssl rsa -in "${PRIVATE_KEY_FILE}" -check -noout 2>/dev/null; then
    log_success "Private key validation: OK"
else
    log_error "Private key validation failed"
    exit 1
fi

# Verify public key (check it can be read as a public key)
if openssl rsa -in "${PUBLIC_KEY_FILE}" -pubin -noout 2>/dev/null; then
    log_success "Public key validation: OK"
else
    log_error "Public key validation failed"
    exit 1
fi

# Test sign/verify cycle
log_info "Testing sign/verify cycle..."
TEST_DATA="SkyLink JWT rotation test $(date -u +%Y-%m-%dT%H:%M:%SZ)"
TEST_SIG_FILE=$(mktemp)
echo -n "${TEST_DATA}" | openssl dgst -sha256 -sign "${PRIVATE_KEY_FILE}" -out "${TEST_SIG_FILE}"
if echo -n "${TEST_DATA}" | openssl dgst -sha256 -verify "${PUBLIC_KEY_FILE}" -signature "${TEST_SIG_FILE}" >/dev/null 2>&1; then
    log_success "Sign/verify test: PASSED"
else
    log_error "Sign/verify test: FAILED"
    rm -f "${TEST_SIG_FILE}"
    exit 1
fi
rm -f "${TEST_SIG_FILE}"

# Output in .env format if requested
if [[ "$ENV_FORMAT" == "true" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    .env Format Output                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "# JWT RS256 Keys (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))"
    echo "# Key ID: ${KID}"
    echo ""
    echo "PRIVATE_KEY_PEM=\"$(cat "${PRIVATE_KEY_FILE}" | tr '\n' '\\' | sed 's/\\/\\n/g')\""
    echo ""
    echo "PUBLIC_KEY_PEM=\"$(cat "${PUBLIC_KEY_FILE}" | tr '\n' '\\' | sed 's/\\/\\n/g')\""
    echo ""
    echo "JWT_KEY_ID=\"${KID}\""
fi

# Summary and next steps
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Key Generation Complete                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Generated files:"
echo "  Private Key: ${PRIVATE_KEY_FILE}"
echo "  Public Key:  ${PUBLIC_KEY_FILE}"
echo "  Key ID:      ${KID_FILE} (${KID})"
echo ""
echo "Key Details:"
openssl rsa -in "${PRIVATE_KEY_FILE}" -text -noout 2>/dev/null | head -1
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                     NEXT STEPS"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "1. ZERO-DOWNTIME ROTATION:"
echo "   a. Add new public key to verification (JWKS or env var)"
echo "   b. Wait for old tokens to expire (15 min default TTL)"
echo "   c. Switch signing to new private key"
echo "   d. Remove old public key from verification"
echo ""
echo "2. UPDATE SECRETS:"
echo "   - GitHub: Settings > Secrets > PRIVATE_KEY_PEM, PUBLIC_KEY_PEM"
echo "   - GitLab: Settings > CI/CD > Variables"
echo "   - Vault:  vault kv put secret/skylink/jwt @${PRIVATE_KEY_FILE}"
echo ""
echo "3. SECURITY REMINDERS:"
echo "   - NEVER commit private.pem to version control"
echo "   - Delete ${OUTPUT_DIR} after updating secrets"
echo "   - Document rotation in your security log"
echo "   - Schedule next rotation in 90 days"
echo ""
log_warning "Private key in ${PRIVATE_KEY_FILE} - DELETE after use!"
