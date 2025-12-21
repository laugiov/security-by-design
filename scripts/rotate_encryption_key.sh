#!/bin/bash
# AES-256 Encryption Key Rotation Script for SkyLink
#
# This script generates new AES-256 encryption keys used for
# encrypting sensitive data at rest (e.g., OAuth tokens).
#
# Usage:
#   ./scripts/rotate_encryption_key.sh [OPTIONS]
#
# Options:
#   --dry-run       Show what would be done without generating keys
#   --output DIR    Output directory (default: ./keys_new)
#   --format FMT    Output format: hex, base64 (default: hex)
#   --version VER   Key version identifier (default: auto-generated)
#   --env-format    Output key in .env format
#   --help          Show this help message
#
# Security Notes:
#   - Encryption keys must NEVER be committed to version control
#   - Use CI/CD secrets or a secrets manager in production
#   - Consider key versioning for gradual migration
#   - Rotate keys every 90 days (recommended)
#
# Key Versioning Format:
#   Encrypted data format: v{VERSION}:{NONCE}:{CIPHERTEXT}
#   This allows decryption with the correct key version during rotation.

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
KEY_FORMAT="hex"
KEY_VERSION=""
DRY_RUN=false
ENV_FORMAT=false

# AES-256 key size
KEY_BYTES=32  # 256 bits = 32 bytes

# Function to display usage
usage() {
    echo "AES-256 Encryption Key Rotation Script for SkyLink"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dry-run       Show what would be done without generating keys"
    echo "  --output DIR    Output directory (default: ./keys_new)"
    echo "  --format FMT    Output format: hex, base64 (default: hex)"
    echo "  --version VER   Key version identifier (default: auto-generated)"
    echo "  --env-format    Output key in .env format"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Generate new key in hex format"
    echo "  $0 --format base64          # Generate in base64 format"
    echo "  $0 --env-format             # Output in .env format"
    echo "  $0 --version 2              # Use specific version number"
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
        --format)
            KEY_FORMAT="$2"
            if [[ "$KEY_FORMAT" != "hex" && "$KEY_FORMAT" != "base64" ]]; then
                log_error "Invalid format: $KEY_FORMAT (use 'hex' or 'base64')"
                exit 1
            fi
            shift 2
            ;;
        --version)
            KEY_VERSION="$2"
            shift 2
            ;;
        --env-format)
            ENV_FORMAT=true
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

# Generate version if not provided
if [[ -z "$KEY_VERSION" ]]; then
    KEY_VERSION="$(date +%Y%m%d%H%M%S)"
fi

# Display configuration
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       SkyLink AES-256 Encryption Key Rotation Script          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_info "Configuration:"
echo "  Output Directory: ${OUTPUT_DIR}"
echo "  Key Size:         ${KEY_BYTES} bytes (256 bits)"
echo "  Output Format:    ${KEY_FORMAT}"
echo "  Key Version:      ${KEY_VERSION}"
echo "  Dry Run:          ${DRY_RUN}"
echo "  Env Format:       ${ENV_FORMAT}"
echo ""

# Dry run mode
if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - No keys will be generated"
    echo ""
    echo "Would perform the following actions:"
    echo "  1. Create directory: ${OUTPUT_DIR}"
    echo "  2. Generate ${KEY_BYTES}-byte cryptographically secure random key"
    echo "  3. Output in ${KEY_FORMAT} format"
    echo "  4. Save version file with: ${KEY_VERSION}"
    if [[ "$ENV_FORMAT" == "true" ]]; then
        echo "  5. Display key in .env format"
    fi
    echo ""
    exit 0
fi

# Check for OpenSSL
if ! command -v openssl &> /dev/null; then
    log_error "OpenSSL is required but not installed"
    exit 1
fi

# Create output directory
log_info "Creating output directory: ${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

# Generate encryption key
log_info "Generating AES-256 encryption key (${KEY_BYTES} bytes)..."

if [[ "$KEY_FORMAT" == "hex" ]]; then
    # Hex format: 64 characters
    ENCRYPTION_KEY=$(openssl rand -hex ${KEY_BYTES})
    KEY_FILE="${OUTPUT_DIR}/encryption_key.hex"
else
    # Base64 format: 44 characters
    ENCRYPTION_KEY=$(openssl rand -base64 ${KEY_BYTES})
    KEY_FILE="${OUTPUT_DIR}/encryption_key.b64"
fi

# Save key to file with restricted permissions
echo "${ENCRYPTION_KEY}" > "${KEY_FILE}"
chmod 600 "${KEY_FILE}"
log_success "Encryption key generated: ${KEY_FILE}"

# Save version
VERSION_FILE="${OUTPUT_DIR}/encryption_key_version.txt"
echo "${KEY_VERSION}" > "${VERSION_FILE}"
log_success "Key version saved: ${VERSION_FILE}"

# Validate key length
KEY_LENGTH=${#ENCRYPTION_KEY}
if [[ "$KEY_FORMAT" == "hex" ]]; then
    EXPECTED_LENGTH=64
else
    EXPECTED_LENGTH=44  # base64 of 32 bytes
fi

if [[ $KEY_LENGTH -ge $EXPECTED_LENGTH ]]; then
    log_success "Key length validation: OK (${KEY_LENGTH} characters)"
else
    log_error "Key length validation failed: expected >= ${EXPECTED_LENGTH}, got ${KEY_LENGTH}"
    exit 1
fi

# Test key entropy (basic check)
log_info "Checking key entropy..."
UNIQUE_CHARS=$(echo -n "${ENCRYPTION_KEY}" | fold -w1 | sort -u | wc -l)
if [[ $UNIQUE_CHARS -lt 10 ]]; then
    log_warning "Low entropy detected: only ${UNIQUE_CHARS} unique characters"
else
    log_success "Key entropy check: OK (${UNIQUE_CHARS} unique characters)"
fi

# Output in .env format if requested
if [[ "$ENV_FORMAT" == "true" ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    .env Format Output                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "# AES-256 Encryption Key (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))"
    echo "# Key Version: ${KEY_VERSION}"
    echo "# Format: ${KEY_FORMAT}"
    echo ""
    echo "ENCRYPTION_KEY=\"${ENCRYPTION_KEY}\""
    echo "ENCRYPTION_KEY_VERSION=\"${KEY_VERSION}\""
fi

# Summary and next steps
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    Key Generation Complete                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Generated files:"
echo "  Encryption Key:  ${KEY_FILE}"
echo "  Key Version:     ${VERSION_FILE} (${KEY_VERSION})"
echo ""
echo "Key Details:"
echo "  Algorithm:  AES-256-GCM"
echo "  Key Size:   256 bits (32 bytes)"
echo "  Format:     ${KEY_FORMAT}"
echo "  Length:     ${KEY_LENGTH} characters"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                     NEXT STEPS"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "1. KEY VERSIONING (recommended):"
echo "   Store encrypted data with version prefix:"
echo "   Format: v${KEY_VERSION}:<nonce>:<ciphertext>"
echo ""
echo "2. DATA RE-ENCRYPTION:"
echo "   If you have existing encrypted data:"
echo "   a. Keep old key temporarily for decryption"
echo "   b. Decrypt existing data with old key"
echo "   c. Re-encrypt with new key"
echo "   d. Update stored ciphertext"
echo "   e. Remove old key"
echo ""
echo "3. UPDATE SECRETS:"
echo "   - GitHub: Settings > Secrets > ENCRYPTION_KEY"
echo "   - GitLab: Settings > CI/CD > Variables"
echo "   - Vault:  vault kv put secret/skylink/encryption key=@${KEY_FILE}"
echo ""
echo "4. SECURITY REMINDERS:"
echo "   - NEVER commit encryption keys to version control"
echo "   - Delete ${OUTPUT_DIR} after updating secrets"
echo "   - Document rotation in your security log"
echo "   - Schedule next rotation in 90 days"
echo ""
log_warning "Encryption key in ${KEY_FILE} - DELETE after use!"
