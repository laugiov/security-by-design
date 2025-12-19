#!/bin/bash
# Generate Client Certificate for SkyLink Aircrafts
#
# This script creates a client certificate signed by the CA.
# The certificate is used by aircrafts to authenticate to the Gateway.
#
# Usage: ./scripts/generate_client_cert.sh <aircraft_id>
#
# Example:
#   ./scripts/generate_client_cert.sh aircraft-001
#   ./scripts/generate_client_cert.sh 550e8400-e29b-41d4-a716-446655440000
#
# Prerequisites:
#   - CA certificate must exist (run generate_ca.sh first)
#
# Output:
#   certs/clients/<aircraft_id>/<aircraft_id>.crt  - Client certificate
#   certs/clients/<aircraft_id>/<aircraft_id>.key  - Client private key
#
# Security Notes:
#   - The aircraft_id is stored in the CN (Common Name) field
#   - This CN should match the aircraft_id in JWT tokens (cross-validation)
#   - In production, certificates would be provisioned during aircraft manufacturing

set -euo pipefail

# Check arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <aircraft_id>"
    echo ""
    echo "Examples:"
    echo "  $0 aircraft-001"
    echo "  $0 550e8400-e29b-41d4-a716-446655440000"
    exit 1
fi

AIRCRAFT_ID="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="${PROJECT_DIR}/certs"
CA_DIR="${CERTS_DIR}/ca"
CLIENT_DIR="${CERTS_DIR}/clients/${AIRCRAFT_ID}"

# Client Certificate Configuration
CLIENT_DAYS=365  # 1 year validity
CLIENT_KEY_SIZE=2048
CLIENT_SUBJECT="/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=Aircrafts/CN=${AIRCRAFT_ID}"

echo "Generating Client Certificate for: ${AIRCRAFT_ID}"

# Check if CA exists
if [[ ! -f "${CA_DIR}/ca.crt" || ! -f "${CA_DIR}/ca.key" ]]; then
    echo "ERROR: CA certificate not found. Run generate_ca.sh first."
    exit 1
fi

# Create directories
mkdir -p "${CLIENT_DIR}"

# Check if client cert already exists
if [[ -f "${CLIENT_DIR}/${AIRCRAFT_ID}.crt" && -f "${CLIENT_DIR}/${AIRCRAFT_ID}.key" ]]; then
    echo "WARNING: Client certificate for ${AIRCRAFT_ID} already exists."
    read -p "Do you want to overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Generate client private key
echo "Generating client private key (${CLIENT_KEY_SIZE} bits)..."
openssl genrsa -out "${CLIENT_DIR}/${AIRCRAFT_ID}.key" ${CLIENT_KEY_SIZE} 2>/dev/null

# Protect client private key
chmod 600 "${CLIENT_DIR}/${AIRCRAFT_ID}.key"

# Create CSR (Certificate Signing Request)
echo "Creating Certificate Signing Request..."
openssl req -new \
    -key "${CLIENT_DIR}/${AIRCRAFT_ID}.key" \
    -out "${CLIENT_DIR}/${AIRCRAFT_ID}.csr" \
    -subj "${CLIENT_SUBJECT}"

# Create extensions file for client auth
cat > "${CLIENT_DIR}/${AIRCRAFT_ID}.ext" << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature
extendedKeyUsage = clientAuth
EOF

# Sign client certificate with CA
echo "Signing client certificate with CA..."
openssl x509 -req \
    -in "${CLIENT_DIR}/${AIRCRAFT_ID}.csr" \
    -CA "${CA_DIR}/ca.crt" \
    -CAkey "${CA_DIR}/ca.key" \
    -CAcreateserial \
    -out "${CLIENT_DIR}/${AIRCRAFT_ID}.crt" \
    -days ${CLIENT_DAYS} \
    -extfile "${CLIENT_DIR}/${AIRCRAFT_ID}.ext"

# Clean up temporary files
rm -f "${CLIENT_DIR}/${AIRCRAFT_ID}.csr" "${CLIENT_DIR}/${AIRCRAFT_ID}.ext"

# Verify certificate
echo ""
echo "Client certificate generated successfully!"
echo ""
echo "Client Certificate Details:"
openssl x509 -in "${CLIENT_DIR}/${AIRCRAFT_ID}.crt" -noout -subject -dates -issuer
echo ""
echo "Verifying certificate chain..."
openssl verify -CAfile "${CA_DIR}/ca.crt" "${CLIENT_DIR}/${AIRCRAFT_ID}.crt"
echo ""
echo "Files created:"
echo "   ${CLIENT_DIR}/${AIRCRAFT_ID}.crt  (client certificate)"
echo "   ${CLIENT_DIR}/${AIRCRAFT_ID}.key  (client private key)"
echo ""
echo "To provision this certificate on a aircraft:"
echo "   1. Copy ${AIRCRAFT_ID}.crt and ${AIRCRAFT_ID}.key to the aircraft"
echo "   2. Copy ca.crt (for server verification)"
echo "   3. Configure the aircraft's TLS client with these files"
