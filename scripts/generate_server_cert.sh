#!/bin/bash
# Generate Server Certificate for SkyLink Gateway
#
# This script creates a server certificate signed by the CA.
# The certificate is used by the Gateway for TLS connections.
#
# Usage: ./scripts/generate_server_cert.sh
#
# Prerequisites:
#   - CA certificate must exist (run generate_ca.sh first)
#
# Output:
#   certs/server/server.crt  - Server certificate
#   certs/server/server.key  - Server private key
#
# The certificate includes SANs (Subject Alternative Names) for:
#   - localhost
#   - gateway.skylink.local
#   - gateway (Docker service name)
#   - 127.0.0.1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="${PROJECT_DIR}/certs"
CA_DIR="${CERTS_DIR}/ca"
SERVER_DIR="${CERTS_DIR}/server"

# Server Certificate Configuration
SERVER_DAYS=365  # 1 year validity
SERVER_KEY_SIZE=2048
SERVER_SUBJECT="/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=Gateway/CN=gateway.skylink.local"

echo "Generating SkyLink Server Certificate..."

# Check if CA exists
if [[ ! -f "${CA_DIR}/ca.crt" || ! -f "${CA_DIR}/ca.key" ]]; then
    echo "ERROR: CA certificate not found. Run generate_ca.sh first."
    exit 1
fi

# Create directories
mkdir -p "${SERVER_DIR}"

# Check if server cert already exists
if [[ -f "${SERVER_DIR}/server.crt" && -f "${SERVER_DIR}/server.key" ]]; then
    echo "WARNING: Server certificate already exists."
    read -p "Do you want to overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Generate server private key
echo "Generating server private key (${SERVER_KEY_SIZE} bits)..."
openssl genrsa -out "${SERVER_DIR}/server.key" ${SERVER_KEY_SIZE} 2>/dev/null

# Protect server private key
chmod 600 "${SERVER_DIR}/server.key"

# Create CSR (Certificate Signing Request)
echo "Creating Certificate Signing Request..."
openssl req -new \
    -key "${SERVER_DIR}/server.key" \
    -out "${SERVER_DIR}/server.csr" \
    -subj "${SERVER_SUBJECT}"

# Create extensions file for SAN (Subject Alternative Names)
cat > "${SERVER_DIR}/server.ext" << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = gateway.skylink.local
DNS.2 = localhost
DNS.3 = gateway
DNS.4 = skylink-gateway
IP.1 = 127.0.0.1
IP.2 = ::1
EOF

# Sign server certificate with CA
echo "Signing server certificate with CA..."
openssl x509 -req \
    -in "${SERVER_DIR}/server.csr" \
    -CA "${CA_DIR}/ca.crt" \
    -CAkey "${CA_DIR}/ca.key" \
    -CAcreateserial \
    -out "${SERVER_DIR}/server.crt" \
    -days ${SERVER_DAYS} \
    -extfile "${SERVER_DIR}/server.ext"

# Clean up temporary files
rm -f "${SERVER_DIR}/server.csr" "${SERVER_DIR}/server.ext"

# Verify certificate
echo ""
echo "Server certificate generated successfully!"
echo ""
echo "Server Certificate Details:"
openssl x509 -in "${SERVER_DIR}/server.crt" -noout -subject -dates -issuer
echo ""
echo "Subject Alternative Names:"
openssl x509 -in "${SERVER_DIR}/server.crt" -noout -ext subjectAltName 2>/dev/null || echo "   (none)"
echo ""
echo "Verifying certificate chain..."
openssl verify -CAfile "${CA_DIR}/ca.crt" "${SERVER_DIR}/server.crt"
echo ""
echo "Files created:"
echo "   ${SERVER_DIR}/server.crt  (server certificate)"
echo "   ${SERVER_DIR}/server.key  (server private key - keep secure)"
