#!/bin/bash
# Generate Certificate Authority (CA) for SkyLink mTLS
#
# This script creates a self-signed CA certificate used to sign
# server and client certificates.
#
# Usage: ./scripts/generate_ca.sh
#
# Output:
#   certs/ca/ca.crt    - CA certificate (distribute to all parties)
#   certs/ca/ca.key    - CA private key (KEEP SECURE - never distribute)
#
# Security Notes:
#   - ca.key is the most sensitive file - protect it carefully
#   - In production, use an HSM or external CA service
#   - Rotate CA certificate before expiration (10 years default)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="${PROJECT_DIR}/certs"
CA_DIR="${CERTS_DIR}/ca"

# CA Configuration
CA_DAYS=3650  # 10 years validity
CA_KEY_SIZE=4096
CA_SUBJECT="/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=PKI/CN=SkyLink Root CA"

echo "Generating SkyLink Certificate Authority..."
echo "   Output directory: ${CA_DIR}"

# Create directories
mkdir -p "${CA_DIR}"

# Check if CA already exists
if [[ -f "${CA_DIR}/ca.crt" && -f "${CA_DIR}/ca.key" ]]; then
    echo "WARNING: CA already exists. To regenerate, remove:"
    echo "   rm ${CA_DIR}/ca.crt ${CA_DIR}/ca.key"
    echo ""
    read -p "Do you want to overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Generate CA private key (4096 bits for CA)
echo "Generating CA private key (${CA_KEY_SIZE} bits)..."
openssl genrsa -out "${CA_DIR}/ca.key" ${CA_KEY_SIZE} 2>/dev/null

# Protect CA private key
chmod 600 "${CA_DIR}/ca.key"

# Generate self-signed CA certificate
echo "Generating CA certificate (valid ${CA_DAYS} days)..."
openssl req -new -x509 \
    -days ${CA_DAYS} \
    -key "${CA_DIR}/ca.key" \
    -out "${CA_DIR}/ca.crt" \
    -subj "${CA_SUBJECT}"

# Verify CA certificate
echo "CA certificate generated successfully!"
echo ""
echo "CA Certificate Details:"
openssl x509 -in "${CA_DIR}/ca.crt" -noout -subject -dates
echo ""
echo "Files created:"
echo "   ${CA_DIR}/ca.crt  (distribute to clients and servers)"
echo "   ${CA_DIR}/ca.key  (KEEP SECURE - never distribute!)"
echo ""
echo "SECURITY REMINDER:"
echo "   - ca.key must NEVER be committed to version control"
echo "   - ca.key must NEVER be distributed to clients"
echo "   - In production, use an HSM or external PKI service"
