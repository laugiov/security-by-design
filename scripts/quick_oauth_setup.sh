#!/bin/bash
# Script rapide pour configurer OAuth après avoir obtenu le code Google
#
# Usage:
#   ./scripts/quick_oauth_setup.sh <authorization_code>
#
# Exemple:
#   ./scripts/quick_oauth_setup.sh "4/0AfJohXm_abc123xyz"

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
VEHICLE_ID="550e8400-e29b-41d4-a716-446655440000"
SERVICE_URL="http://localhost:8003"

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Configuration OAuth Google - SkyLink                 ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier que le code est fourni
if [ -z "$1" ]; then
    echo -e "${RED}❌ Erreur: Code d'autorisation manquant${NC}"
    echo ""
    echo "Usage: $0 <authorization_code>"
    echo ""
    echo "1. Ouvre cette URL dans ton navigateur:"
    echo ""
    source .env 2>/dev/null || true
    echo "https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=http%3A%2F%2Flocalhost%3A8003%2Foauth%2Fcallback&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcontacts.readonly&access_type=offline&prompt=consent"
    echo ""
    echo "2. Autorise l'accès aux contacts"
    echo ""
    echo "3. Copie le code de l'URL de redirection, puis exécute:"
    echo "   $0 \"TON_CODE_ICI\""
    echo ""
    exit 1
fi

AUTH_CODE="$1"

echo -e "${YELLOW}📋 Configuration${NC}"
echo "   Vehicle ID: $VEHICLE_ID"
echo "   Service URL: $SERVICE_URL"
echo "   Code: ${AUTH_CODE:0:20}..."
echo ""

# Vérifier que le service est accessible
echo -e "${YELLOW}🔍 Vérification du service contacts...${NC}"
if ! curl -s -f "$SERVICE_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ Le service contacts n'est pas accessible sur $SERVICE_URL${NC}"
    echo ""
    echo "Démarre-le avec:"
    echo "   DEMO_MODE=false poetry run uvicorn contacts.main:app --host 0.0.0.0 --port 8003"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓${NC} Service contacts accessible"
echo ""

# Appeler l'endpoint de callback
echo -e "${YELLOW}🔑 Configuration du véhicule avec Google OAuth...${NC}"
RESPONSE=$(curl -s -X POST "$SERVICE_URL/oauth/callback?code=$AUTH_CODE&vehicle_id=$VEHICLE_ID")

# Vérifier si la configuration a réussi
if echo "$RESPONSE" | grep -q '"success".*true'; then
    echo -e "${GREEN}✅ Configuration réussie !${NC}"
    echo ""
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""

    # Tester la récupération des contacts
    echo -e "${YELLOW}📞 Test de récupération des contacts...${NC}"
    echo ""

    CONTACTS_RESPONSE=$(curl -s -H "X-Vehicle-Id: $VEHICLE_ID" \
        "$SERVICE_URL/v1/contacts?person_fields=names,emailAddresses,phoneNumbers&size=5")

    if echo "$CONTACTS_RESPONSE" | grep -q '"items"'; then
        echo -e "${GREEN}🎉 Contacts récupérés avec succès !${NC}"
        echo ""
        echo "Premiers contacts:"
        echo "$CONTACTS_RESPONSE" | python3 -m json.tool 2>/dev/null | head -50
        echo ""
        echo -e "${GREEN}✓${NC} OAuth fonctionne correctement !"
    else
        echo -e "${RED}❌ Erreur lors de la récupération des contacts${NC}"
        echo ""
        echo "$CONTACTS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$CONTACTS_RESPONSE"
    fi
else
    echo -e "${RED}❌ Erreur lors de la configuration${NC}"
    echo ""
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    echo ""

    # Analyser l'erreur
    if echo "$RESPONSE" | grep -q "invalid_grant\|Invalid or expired"; then
        echo -e "${YELLOW}💡 Le code d'autorisation est invalide ou expiré${NC}"
        echo "Les codes expirent après ~10 minutes."
        echo "Recommence le processus pour obtenir un nouveau code."
    elif echo "$RESPONSE" | grep -q "INSUFFICIENT_SCOPES"; then
        echo -e "${YELLOW}💡 Scopes insuffisants${NC}"
        echo "Assure-toi d'autoriser l'accès aux contacts lors de l'autorisation Google."
    fi

    exit 1
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Configuration OAuth terminée avec succès !                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Pour récupérer les contacts à tout moment:"
echo ""
echo "  curl -H \"X-Vehicle-Id: $VEHICLE_ID\" \\"
echo "       \"$SERVICE_URL/v1/contacts?person_fields=names,emailAddresses,phoneNumbers\""
echo ""
