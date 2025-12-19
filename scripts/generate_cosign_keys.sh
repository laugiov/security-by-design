#!/bin/bash
# =============================================================================
# SkyLink - Script de generation des cles cosign
# =============================================================================
# Ce script genere une paire de cles pour signer les images Docker avec cosign.
# Les cles generees doivent etre ajoutees aux variables CI GitLab.
#
# Usage:
#   ./scripts/generate_cosign_keys.sh
#
# Prerequis:
#   - cosign installe (brew install cosign / apt install cosign)
#
# Output:
#   - cosign.key (cle privee - NE PAS COMMITTER)
#   - cosign.pub (cle publique - peut etre committee)
# =============================================================================

set -euo pipefail

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== SkyLink - Generation des cles cosign ===${NC}"
echo ""

# Verifier que cosign est installe
if ! command -v cosign &> /dev/null; then
    echo -e "${RED}Erreur: cosign n'est pas installe.${NC}"
    echo ""
    echo "Installation:"
    echo "  - macOS:  brew install cosign"
    echo "  - Linux:  https://docs.sigstore.dev/cosign/installation/"
    echo "  - Docker: docker run -it cgr.dev/chainguard/cosign:latest version"
    exit 1
fi

echo -e "cosign version: $(cosign version 2>&1 | head -1)"
echo ""

# Repertoire de sortie
OUTPUT_DIR="${1:-./cosign-keys}"
mkdir -p "$OUTPUT_DIR"

# Generer les cles
echo -e "${YELLOW}Generation des cles cosign...${NC}"
echo "Les cles seront stockees dans: $OUTPUT_DIR"
echo ""

# Demander un mot de passe pour la cle privee
echo -e "${YELLOW}Entrez un mot de passe pour proteger la cle privee:${NC}"
echo "(Ce mot de passe sera necessaire pour COSIGN_PASSWORD dans GitLab CI)"
read -s COSIGN_PASSWORD
export COSIGN_PASSWORD

echo ""
echo "Generation en cours..."

# Generer la paire de cles
cd "$OUTPUT_DIR"
cosign generate-key-pair

echo ""
echo -e "${GREEN}=== Cles generees avec succes ===${NC}"
echo ""
echo "Fichiers crees:"
echo "  - $OUTPUT_DIR/cosign.key (cle privee)"
echo "  - $OUTPUT_DIR/cosign.pub (cle publique)"
echo ""

# Afficher les instructions
echo -e "${YELLOW}=== Configuration GitLab CI ===${NC}"
echo ""
echo "Ajoutez ces variables dans GitLab > Settings > CI/CD > Variables:"
echo ""
echo "1. COSIGN_PRIVATE_KEY"
echo "   - Type: Variable"
echo "   - Protected: Oui"
echo "   - Masked: Non (trop long)"
echo "   - Valeur: Contenu de $OUTPUT_DIR/cosign.key"
echo ""
echo "2. COSIGN_PASSWORD"
echo "   - Type: Variable"
echo "   - Protected: Oui"
echo "   - Masked: Oui"
echo "   - Valeur: Le mot de passe que vous venez d'entrer"
echo ""
echo "3. COSIGN_PUBLIC_KEY"
echo "   - Type: Variable"
echo "   - Protected: Oui"
echo "   - Masked: Non"
echo "   - Valeur: Contenu de $OUTPUT_DIR/cosign.pub"
echo ""

# Afficher la cle publique (peut etre partagee)
echo -e "${GREEN}=== Cle publique (peut etre committee) ===${NC}"
echo ""
cat "$OUTPUT_DIR/cosign.pub"
echo ""

# Warning securite
echo -e "${RED}=== ATTENTION SECURITE ===${NC}"
echo ""
echo "- NE JAMAIS committer cosign.key"
echo "- Ajoutez 'cosign-keys/' a .gitignore"
echo "- Stockez la cle privee dans un endroit securise"
echo "- En production, utilisez un KMS (AWS KMS, GCP KMS, etc.)"
echo ""

# Verifier .gitignore
if [ -f "../.gitignore" ]; then
    if ! grep -q "cosign-keys/" "../.gitignore"; then
        echo "cosign-keys/" >> "../.gitignore"
        echo -e "${GREEN}Ajout de 'cosign-keys/' a .gitignore${NC}"
    fi
fi

echo -e "${GREEN}Termine!${NC}"
