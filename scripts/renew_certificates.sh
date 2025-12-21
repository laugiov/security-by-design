#!/bin/bash
# mTLS Certificate Renewal Script for SkyLink
#
# This script renews mTLS certificates (server or client) signed by the
# existing CA. Supports renewal with same or new private key.
#
# Usage:
#   ./scripts/renew_certificates.sh [OPTIONS] TYPE [NAME]
#
# Types:
#   server          Renew server certificate
#   client NAME     Renew client certificate (NAME required)
#
# Options:
#   --dry-run       Show what would be done without generating certificates
#   --new-key       Generate new private key (default: reuse existing)
#   --days DAYS     Certificate validity in days (default: 365)
#   --backup        Backup current certificates before renewal
#   --help          Show this help message
#
# Security Notes:
#   - CA private key (ca.key) is required and must remain secure
#   - Private keys should NEVER be committed to version control
#   - Consider certificate transparency logging in production
#   - Renew certificates at least 30 days before expiration
#
# CA Rotation:
#   CA rotation is complex and requires fleet-wide coordination.
#   Use generate_ca.sh for new CA setup, but plan carefully for transition.

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
CERTS_DIR="${PROJECT_DIR}/certs"
CA_DIR="${CERTS_DIR}/ca"
SERVER_DIR="${CERTS_DIR}/server"
CLIENTS_DIR="${CERTS_DIR}/clients"

CERT_DAYS=365
KEY_SIZE=2048
DRY_RUN=false
NEW_KEY=false
BACKUP=false
CERT_TYPE=""
CLIENT_NAME=""

# Function to display usage
usage() {
    echo "mTLS Certificate Renewal Script for SkyLink"
    echo ""
    echo "Usage: $0 [OPTIONS] TYPE [NAME]"
    echo ""
    echo "Types:"
    echo "  server          Renew server certificate"
    echo "  client NAME     Renew client certificate (NAME required)"
    echo ""
    echo "Options:"
    echo "  --dry-run       Show what would be done without generating certificates"
    echo "  --new-key       Generate new private key (default: reuse existing)"
    echo "  --days DAYS     Certificate validity in days (default: 365)"
    echo "  --backup        Backup current certificates before renewal"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 server                    # Renew server certificate"
    echo "  $0 client aircraft-001       # Renew client 'aircraft-001'"
    echo "  $0 --new-key server          # Renew with new private key"
    echo "  $0 --days 730 server         # 2-year validity"
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
        --new-key)
            NEW_KEY=true
            shift
            ;;
        --days)
            CERT_DAYS="$2"
            shift 2
            ;;
        --backup)
            BACKUP=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        server)
            CERT_TYPE="server"
            shift
            ;;
        client)
            CERT_TYPE="client"
            if [[ $# -lt 2 ]]; then
                log_error "Client name is required"
                exit 1
            fi
            CLIENT_NAME="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option or type: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate certificate type
if [[ -z "$CERT_TYPE" ]]; then
    log_error "Certificate type is required (server or client)"
    echo "Use --help for usage information"
    exit 1
fi

# Display configuration
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        SkyLink Certificate Renewal Script                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_info "Configuration:"
echo "  Certificate Type: ${CERT_TYPE}"
if [[ "$CERT_TYPE" == "client" ]]; then
    echo "  Client Name:      ${CLIENT_NAME}"
fi
echo "  Validity:         ${CERT_DAYS} days"
echo "  New Key:          ${NEW_KEY}"
echo "  Dry Run:          ${DRY_RUN}"
echo "  Backup:           ${BACKUP}"
echo ""

# Check CA exists
if [[ ! -f "${CA_DIR}/ca.crt" || ! -f "${CA_DIR}/ca.key" ]]; then
    log_error "CA not found at ${CA_DIR}"
    echo "Run ./scripts/generate_ca.sh first"
    exit 1
fi
log_success "CA found: ${CA_DIR}/ca.crt"

# Set paths based on certificate type
if [[ "$CERT_TYPE" == "server" ]]; then
    CERT_DIR="${SERVER_DIR}"
    CERT_NAME="server"
    CN="skylink-gateway"
    SUBJECT="/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=Gateway/CN=${CN}"
    SAN="DNS:localhost,DNS:gateway,DNS:skylink-gateway,IP:127.0.0.1"
else
    CERT_DIR="${CLIENTS_DIR}/${CLIENT_NAME}"
    CERT_NAME="${CLIENT_NAME}"
    CN="${CLIENT_NAME}"
    SUBJECT="/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=Aircraft/CN=${CN}"
    SAN=""
fi

KEY_FILE="${CERT_DIR}/${CERT_NAME}.key"
CSR_FILE="${CERT_DIR}/${CERT_NAME}.csr"
CERT_FILE="${CERT_DIR}/${CERT_NAME}.crt"

# Dry run mode
if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - No certificates will be generated"
    echo ""
    echo "Would perform the following actions:"
    echo "  1. Directory: ${CERT_DIR}"
    if [[ "$NEW_KEY" == "true" || ! -f "$KEY_FILE" ]]; then
        echo "  2. Generate new RSA private key (${KEY_SIZE} bits)"
    else
        echo "  2. Reuse existing private key: ${KEY_FILE}"
    fi
    echo "  3. Create CSR with CN=${CN}"
    if [[ -n "$SAN" ]]; then
        echo "     SAN: ${SAN}"
    fi
    echo "  4. Sign certificate with CA (valid ${CERT_DAYS} days)"
    echo "  5. Output: ${CERT_FILE}"
    echo ""
    exit 0
fi

# Check for OpenSSL
if ! command -v openssl &> /dev/null; then
    log_error "OpenSSL is required but not installed"
    exit 1
fi

# Backup existing certificates if requested
if [[ "$BACKUP" == "true" && -d "$CERT_DIR" ]]; then
    BACKUP_DIR="${CERT_DIR}_backup_$(date +%Y%m%d%H%M%S)"
    log_info "Backing up existing certificates to: ${BACKUP_DIR}"
    cp -r "$CERT_DIR" "$BACKUP_DIR"
    log_success "Backup created"
fi

# Create directory
log_info "Creating certificate directory: ${CERT_DIR}"
mkdir -p "${CERT_DIR}"

# Generate or reuse private key
if [[ "$NEW_KEY" == "true" || ! -f "$KEY_FILE" ]]; then
    log_info "Generating new RSA private key (${KEY_SIZE} bits)..."
    openssl genrsa -out "${KEY_FILE}" ${KEY_SIZE} 2>/dev/null
    chmod 600 "${KEY_FILE}"
    log_success "Private key generated: ${KEY_FILE}"
else
    log_info "Reusing existing private key: ${KEY_FILE}"
fi

# Create CSR
log_info "Creating Certificate Signing Request..."
if [[ -n "$SAN" ]]; then
    # Server certificate with SAN
    openssl req -new \
        -key "${KEY_FILE}" \
        -out "${CSR_FILE}" \
        -subj "${SUBJECT}" \
        -addext "subjectAltName=${SAN}"
else
    # Client certificate without SAN
    openssl req -new \
        -key "${KEY_FILE}" \
        -out "${CSR_FILE}" \
        -subj "${SUBJECT}"
fi
log_success "CSR created: ${CSR_FILE}"

# Create extensions file for signing
EXT_FILE=$(mktemp)
if [[ "$CERT_TYPE" == "server" ]]; then
    cat > "${EXT_FILE}" << EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=${SAN}
EOF
else
    cat > "${EXT_FILE}" << EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature
extendedKeyUsage=clientAuth
EOF
fi

# Sign certificate with CA
log_info "Signing certificate with CA (valid ${CERT_DAYS} days)..."
openssl x509 -req \
    -in "${CSR_FILE}" \
    -CA "${CA_DIR}/ca.crt" \
    -CAkey "${CA_DIR}/ca.key" \
    -CAcreateserial \
    -out "${CERT_FILE}" \
    -days ${CERT_DAYS} \
    -sha256 \
    -extfile "${EXT_FILE}"

rm -f "${EXT_FILE}"
log_success "Certificate signed: ${CERT_FILE}"

# Verify certificate
log_info "Verifying certificate..."
if openssl verify -CAfile "${CA_DIR}/ca.crt" "${CERT_FILE}" >/dev/null 2>&1; then
    log_success "Certificate verification: OK"
else
    log_error "Certificate verification failed"
    exit 1
fi

# Display certificate info
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  Certificate Details                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
openssl x509 -in "${CERT_FILE}" -noout -subject -issuer -dates -serial
echo ""

# Check expiration
EXPIRY_DATE=$(openssl x509 -in "${CERT_FILE}" -noout -enddate | cut -d= -f2)
log_info "Certificate expires: ${EXPIRY_DATE}"

# Summary and next steps
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                Certificate Renewal Complete                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Generated files:"
echo "  Private Key:   ${KEY_FILE}"
echo "  CSR:           ${CSR_FILE}"
echo "  Certificate:   ${CERT_FILE}"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                     NEXT STEPS"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [[ "$CERT_TYPE" == "server" ]]; then
    echo "1. DEPLOY SERVER CERTIFICATE:"
    echo "   a. Copy certificate and key to server"
    echo "   b. Update docker-compose.yml volume mounts (if changed)"
    echo "   c. Restart gateway service: docker compose restart gateway"
    echo ""
    echo "2. VERIFY DEPLOYMENT:"
    echo "   openssl s_client -connect localhost:8443 -CAfile ${CA_DIR}/ca.crt"
    echo ""
else
    echo "1. DISTRIBUTE CLIENT CERTIFICATE:"
    echo "   a. Securely transfer to client device: ${CLIENT_NAME}"
    echo "   b. Include CA certificate for verification: ${CA_DIR}/ca.crt"
    echo ""
    echo "2. CLIENT CONFIGURATION:"
    echo "   Certificate: ${CERT_FILE}"
    echo "   Private Key: ${KEY_FILE}"
    echo "   CA Bundle:   ${CA_DIR}/ca.crt"
    echo ""
fi

echo "3. SECURITY REMINDERS:"
echo "   - Private keys must NEVER be committed to version control"
echo "   - Delete CSR files after certificate is issued"
echo "   - Document renewal in your security log"
echo "   - Schedule next renewal ${CERT_DAYS} days from now"
echo ""

# Calculate next renewal date
if command -v date &> /dev/null; then
    RENEWAL_DATE=$(date -d "+$((CERT_DAYS - 30)) days" +%Y-%m-%d 2>/dev/null || echo "N/A")
    if [[ "$RENEWAL_DATE" != "N/A" ]]; then
        log_info "Recommended renewal date: ${RENEWAL_DATE} (30 days before expiry)"
    fi
fi
