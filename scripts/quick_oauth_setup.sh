#!/bin/bash
# Quick script to configure OAuth after obtaining Google authorization code
#
# Usage:
#   ./scripts/quick_oauth_setup.sh <authorization_code>
#
# Example:
#   ./scripts/quick_oauth_setup.sh "4/0AfJohXm_abc123xyz"

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
AIRCRAFT_ID="550e8400-e29b-41d4-a716-446655440000"
SERVICE_URL="http://localhost:8003"

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Google OAuth Configuration - SkyLink                 ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check that the code is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: Authorization code missing${NC}"
    echo ""
    echo "Usage: $0 <authorization_code>"
    echo ""
    echo "1. Open this URL in your browser:"
    echo ""
    source .env 2>/dev/null || true
    echo "https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=http%3A%2F%2Flocalhost%3A8003%2Foauth%2Fcallback&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcontacts.readonly&access_type=offline&prompt=consent"
    echo ""
    echo "2. Authorize access to contacts"
    echo ""
    echo "3. Copy the code from the redirect URL, then execute:"
    echo "   $0 \"YOUR_CODE_HERE\""
    echo ""
    exit 1
fi

AUTH_CODE="$1"

echo -e "${YELLOW}📋 Configuration${NC}"
echo "   Aircraft ID: $AIRCRAFT_ID"
echo "   Service URL: $SERVICE_URL"
echo "   Code: ${AUTH_CODE:0:20}..."
echo ""

# Check that the service is accessible
echo -e "${YELLOW}🔍 Checking contacts service...${NC}"
if ! curl -s -f "$SERVICE_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ Contacts service is not accessible at $SERVICE_URL${NC}"
    echo ""
    echo "Start it with:"
    echo "   DEMO_MODE=false poetry run uvicorn contacts.main:app --host 0.0.0.0 --port 8003"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓${NC} Contacts service accessible"
echo ""

# Call the callback endpoint
echo -e "${YELLOW}🔑 Configuring aircraft with Google OAuth...${NC}"
RESPONSE=$(curl -s -X POST "$SERVICE_URL/oauth/callback?code=$AUTH_CODE&aircraft_id=$AIRCRAFT_ID")

# Check if configuration succeeded
if echo "$RESPONSE" | grep -q '"success".*true'; then
    echo -e "${GREEN}✅ Configuration successful!${NC}"
    echo ""
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""

    # Test contacts retrieval
    echo -e "${YELLOW}📞 Testing contacts retrieval...${NC}"
    echo ""

    CONTACTS_RESPONSE=$(curl -s -H "X-Aircraft-Id: $AIRCRAFT_ID" \
        "$SERVICE_URL/v1/contacts?person_fields=names,emailAddresses,phoneNumbers&size=5")

    if echo "$CONTACTS_RESPONSE" | grep -q '"items"'; then
        echo -e "${GREEN}🎉 Contacts retrieved successfully!${NC}"
        echo ""
        echo "First contacts:"
        echo "$CONTACTS_RESPONSE" | python3 -m json.tool 2>/dev/null | head -50
        echo ""
        echo -e "${GREEN}✓${NC} OAuth is working correctly!"
    else
        echo -e "${RED}❌ Error retrieving contacts${NC}"
        echo ""
        echo "$CONTACTS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CONTACTS_RESPONSE"
    fi
else
    echo -e "${RED}❌ Error during configuration${NC}"
    echo ""
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""

    # Analyze the error
    if echo "$RESPONSE" | grep -q "invalid_grant\|Invalid or expired"; then
        echo -e "${YELLOW}💡 Authorization code is invalid or expired${NC}"
        echo "Codes expire after ~10 minutes."
        echo "Restart the process to get a new code."
    elif echo "$RESPONSE" | grep -q "INSUFFICIENT_SCOPES"; then
        echo -e "${YELLOW}💡 Insufficient scopes${NC}"
        echo "Make sure to authorize contacts access during Google authorization."
    fi

    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ OAuth configuration completed successfully!               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "To retrieve contacts at any time:"
echo ""
echo "  curl -H \"X-Aircraft-Id: $AIRCRAFT_ID\" \\"
echo "       \"$SERVICE_URL/v1/contacts?person_fields=names,emailAddresses,phoneNumbers\""
echo ""
