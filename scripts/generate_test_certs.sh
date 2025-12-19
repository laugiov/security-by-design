#!/bin/bash
# Generate Test Certificates for SkyLink mTLS Testing
#
# This script generates all certificates needed for local development
# and testing: CA, server, and test client certificates.
#
# Usage: ./scripts/generate_test_certs.sh
#
# Output:
#   certs/ca/           - Certificate Authority
#   certs/server/       - Gateway server certificate
#   certs/clients/      - Test aircraft certificates
#
# This script runs non-interactively (overwrites existing certs)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERTS_DIR="${PROJECT_DIR}/certs"

echo "SkyLink mTLS Test Certificate Generation"
echo "=============================================="
echo ""

# Clean existing certificates
echo "Cleaning existing certificates..."
rm -rf "${CERTS_DIR}/ca" "${CERTS_DIR}/server" "${CERTS_DIR}/clients"
mkdir -p "${CERTS_DIR}/ca" "${CERTS_DIR}/server" "${CERTS_DIR}/clients"

# Generate CA
echo ""
echo "Step 1/3: Generating Certificate Authority..."
echo "------------------------------------------------"

CA_DIR="${CERTS_DIR}/ca"
openssl genrsa -out "${CA_DIR}/ca.key" 4096 2>/dev/null
chmod 600 "${CA_DIR}/ca.key"

openssl req -new -x509 \
    -days 3650 \
    -key "${CA_DIR}/ca.key" \
    -out "${CA_DIR}/ca.crt" \
    -subj "/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=PKI/CN=SkyLink Root CA"

echo "CA generated: ${CA_DIR}/ca.crt"

# Generate Server Certificate
echo ""
echo "Step 2/3: Generating Server Certificate..."
echo "------------------------------------------------"

SERVER_DIR="${CERTS_DIR}/server"
openssl genrsa -out "${SERVER_DIR}/server.key" 2048 2>/dev/null
chmod 600 "${SERVER_DIR}/server.key"

openssl req -new \
    -key "${SERVER_DIR}/server.key" \
    -out "${SERVER_DIR}/server.csr" \
    -subj "/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=Gateway/CN=gateway.skylink.local"

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

openssl x509 -req \
    -in "${SERVER_DIR}/server.csr" \
    -CA "${CA_DIR}/ca.crt" \
    -CAkey "${CA_DIR}/ca.key" \
    -CAcreateserial \
    -out "${SERVER_DIR}/server.crt" \
    -days 365 \
    -extfile "${SERVER_DIR}/server.ext"

rm -f "${SERVER_DIR}/server.csr" "${SERVER_DIR}/server.ext"

echo "Server certificate generated: ${SERVER_DIR}/server.crt"

# Generate Test Client Certificates
echo ""
echo "Step 3/3: Generating Test Aircraft Certificates..."
echo "----------------------------------------------------"

TEST_AIRCRAFTS=("aircraft-test-001" "aircraft-test-002" "550e8400-e29b-41d4-a716-446655440000")

for AIRCRAFT_ID in "${TEST_AIRCRAFTS[@]}"; do
    CLIENT_DIR="${CERTS_DIR}/clients/${AIRCRAFT_ID}"
    mkdir -p "${CLIENT_DIR}"

    openssl genrsa -out "${CLIENT_DIR}/${AIRCRAFT_ID}.key" 2048 2>/dev/null
    chmod 600 "${CLIENT_DIR}/${AIRCRAFT_ID}.key"

    openssl req -new \
        -key "${CLIENT_DIR}/${AIRCRAFT_ID}.key" \
        -out "${CLIENT_DIR}/${AIRCRAFT_ID}.csr" \
        -subj "/C=FR/ST=IDF/L=Paris/O=SkyLink/OU=Aircrafts/CN=${AIRCRAFT_ID}"

    cat > "${CLIENT_DIR}/${AIRCRAFT_ID}.ext" << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature
extendedKeyUsage = clientAuth
EOF

    openssl x509 -req \
        -in "${CLIENT_DIR}/${AIRCRAFT_ID}.csr" \
        -CA "${CA_DIR}/ca.crt" \
        -CAkey "${CA_DIR}/ca.key" \
        -CAcreateserial \
        -out "${CLIENT_DIR}/${AIRCRAFT_ID}.crt" \
        -days 365 \
        -extfile "${CLIENT_DIR}/${AIRCRAFT_ID}.ext"

    rm -f "${CLIENT_DIR}/${AIRCRAFT_ID}.csr" "${CLIENT_DIR}/${AIRCRAFT_ID}.ext"

    echo "Client certificate generated: ${AIRCRAFT_ID}"
done

# Verify all certificates
echo ""
echo "Verifying certificate chain..."
echo "----------------------------------"

openssl verify -CAfile "${CA_DIR}/ca.crt" "${SERVER_DIR}/server.crt"
for AIRCRAFT_ID in "${TEST_AIRCRAFTS[@]}"; do
    openssl verify -CAfile "${CA_DIR}/ca.crt" "${CERTS_DIR}/clients/${AIRCRAFT_ID}/${AIRCRAFT_ID}.crt"
done

# Summary
echo ""
echo "=============================================="
echo "All test certificates generated successfully!"
echo "=============================================="
echo ""
echo "Certificate structure:"
echo "   ${CERTS_DIR}/"
echo "   ├── ca/"
echo "   │   ├── ca.crt         (CA certificate - distribute)"
echo "   │   └── ca.key         (CA private key - KEEP SECURE)"
echo "   ├── server/"
echo "   │   ├── server.crt     (Gateway certificate)"
echo "   │   └── server.key     (Gateway private key)"
echo "   └── clients/"
for AIRCRAFT_ID in "${TEST_AIRCRAFTS[@]}"; do
echo "       ├── ${AIRCRAFT_ID}/"
echo "       │   ├── ${AIRCRAFT_ID}.crt"
echo "       │   └── ${AIRCRAFT_ID}.key"
done
echo ""
echo "Test with curl:"
echo "   curl --cacert ${CA_DIR}/ca.crt \\"
echo "        --cert ${CERTS_DIR}/clients/aircraft-test-001/aircraft-test-001.crt \\"
echo "        --key ${CERTS_DIR}/clients/aircraft-test-001/aircraft-test-001.key \\"
echo "        https://localhost:8000/health"
