#!/usr/bin/env python3
"""Script de test pour vérifier la configuration OAuth Google.

Ce script vérifie que :
1. Les variables d'environnement sont définies
2. Le client_id est valide
3. L'URL d'autorisation peut être générée
4. Le service contacts est accessible

Usage:
    python scripts/test_oauth_url.py
"""

import os
import sys
from urllib.parse import urlencode

# Vérifier si httpx est disponible
try:
    import httpx
except ImportError:
    print("⚠️  httpx n'est pas installé")
    print("   Installé avec: poetry add httpx")
    httpx = None


def test_env_vars():
    """Teste que les variables d'environnement sont définies."""
    print("\n" + "=" * 60)
    print("1. Vérification des variables d'environnement")
    print("=" * 60)

    required_vars = {
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
        "ENCRYPTION_KEY": os.getenv("ENCRYPTION_KEY"),
    }

    optional_vars = {
        "GOOGLE_REDIRECT_URI": os.getenv(
            "GOOGLE_REDIRECT_URI", "http://localhost:8003/oauth/callback"
        ),
        "DEMO_MODE": os.getenv("DEMO_MODE", "true"),
    }

    all_ok = True

    # Variables requises
    for var_name, var_value in required_vars.items():
        if var_value:
            # Masquer partiellement les valeurs sensibles
            if var_name == "GOOGLE_CLIENT_SECRET" or var_name == "ENCRYPTION_KEY":
                display_value = (
                    var_value[:10] + "..." + var_value[-10:] if len(var_value) > 20 else "***"
                )
            else:
                display_value = var_value[:30] + "..." if len(var_value) > 30 else var_value
            print(f"✅ {var_name:25} = {display_value}")
        else:
            print(f"❌ {var_name:25} = (non définie)")
            all_ok = False

    # Variables optionnelles
    print("\nVariables optionnelles:")
    for var_name, var_value in optional_vars.items():
        print(f"ℹ️  {var_name:25} = {var_value}")

    if not all_ok:
        print("\n❌ Certaines variables requises sont manquantes!")
        print("\nDéfinissez-les dans votre .env:")
        print('GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"')
        print('GOOGLE_CLIENT_SECRET="GOCSPX-your-secret"')
        print('ENCRYPTION_KEY="$(openssl rand -hex 32)"')
        return False

    print("\n✅ Toutes les variables requises sont définies!")
    return True


def test_client_id_format():
    """Vérifie le format du client ID."""
    print("\n" + "=" * 60)
    print("2. Vérification du format Client ID")
    print("=" * 60)

    client_id = os.getenv("GOOGLE_CLIENT_ID")

    if not client_id:
        print("❌ GOOGLE_CLIENT_ID non définie")
        return False

    # Vérifier le format Google OAuth client ID
    if ".apps.googleusercontent.com" in client_id:
        print(f"✅ Format Client ID valide: {client_id[:30]}...")
        return True
    else:
        print(f"⚠️  Format Client ID inhabituel: {client_id}")
        print("   Format attendu: xxxxx-xxxxx.apps.googleusercontent.com")
        return False


def test_encryption_key_format():
    """Vérifie le format de la clé de chiffrement."""
    print("\n" + "=" * 60)
    print("3. Vérification de la clé de chiffrement")
    print("=" * 60)

    encryption_key = os.getenv("ENCRYPTION_KEY")

    if not encryption_key:
        print("❌ ENCRYPTION_KEY non définie")
        return False

    # Vérifier que c'est un hex de 64 caractères (32 bytes)
    if len(encryption_key) == 64:
        try:
            bytes.fromhex(encryption_key)
            print("✅ Clé de chiffrement valide (32 bytes hex)")
            print(f"   Début: {encryption_key[:10]}...")
            return True
        except ValueError:
            print("❌ Clé de chiffrement invalide (pas du hex)")
            return False
    else:
        print(f"⚠️  Longueur de clé incorrecte: {len(encryption_key)} caractères (attendu: 64)")
        print("   Générez une nouvelle clé avec: openssl rand -hex 32")
        return False


def generate_oauth_url():
    """Génère l'URL d'autorisation OAuth."""
    print("\n" + "=" * 60)
    print("4. Génération de l'URL OAuth")
    print("=" * 60)

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8003/oauth/callback")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/contacts.readonly",
        "access_type": "offline",
        "prompt": "consent",
    }

    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    print("✅ URL d'autorisation générée avec succès!\n")
    print("URL complète:")
    print(f"{oauth_url}\n")

    # Afficher les paramètres
    print("Paramètres:")
    for key, value in params.items():
        if key == "client_id":
            display_value = value[:30] + "..." if len(value) > 30 else value
        else:
            display_value = value
        print(f"  {key:20} = {display_value}")

    return oauth_url


def test_service_connection():
    """Teste la connexion au service contacts."""
    print("\n" + "=" * 60)
    print("5. Test de connexion au service contacts")
    print("=" * 60)

    if not httpx:
        print("⚠️  Impossible de tester (httpx non installé)")
        return None

    service_url = "http://localhost:8003"

    try:
        print(f"Tentative de connexion à {service_url}/health...")
        response = httpx.get(f"{service_url}/health", timeout=2.0)

        if response.status_code == 200:
            data = response.json()
            print("✅ Service contacts accessible!")
            print(f"   Status: {data.get('status', 'unknown')}")
            print(f"   Service: {data.get('service', 'unknown')}")
            return True
        else:
            print(f"⚠️  Service répond mais status {response.status_code}")
            return False

    except httpx.ConnectError:
        print(f"❌ Impossible de se connecter à {service_url}")
        print("   Le service contacts n'est probablement pas démarré")
        print("\n   Démarrez-le avec:")
        print("   poetry run uvicorn contacts.main:app --host 0.0.0.0 --port 8003")
        return False

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def print_next_steps(oauth_url):
    """Affiche les prochaines étapes."""
    print("\n" + "=" * 60)
    print("📋 PROCHAINES ÉTAPES")
    print("=" * 60)

    print("\n1. Démarrer le service contacts (si pas déjà fait):")
    print("   poetry run uvicorn contacts.main:app --host 0.0.0.0 --port 8003")

    print("\n2. Configurer un véhicule avec le CLI tool:")
    print("   poetry add httpx rich  # Si pas déjà installé")
    print("   python scripts/configure_vehicle_oauth.py")

    print("\n3. Ou manuellement:")
    print("   a) Ouvrir cette URL dans le navigateur:")
    print(f"      {oauth_url[:80]}...")
    print("   b) Autoriser l'accès aux contacts")
    print("   c) Copier le code de l'URL de redirection")
    print("   d) Appeler /oauth/callback avec le code et vehicle_id")

    print("\n4. Tester l'endpoint:")
    print('   curl -H "X-Vehicle-Id: <vehicle-uuid>" \\')
    print('        "http://localhost:8003/v1/contacts?person_fields=names"')

    print("\n📚 Documentation complète:")
    print("   local/contacts-oauth/DEPLOYMENT_GUIDE.md")


def main():
    """Point d'entrée principal."""
    print("\n" + "=" * 60)
    print("🔍 TEST DE CONFIGURATION OAUTH GOOGLE")
    print("=" * 60)

    # Tests
    results = {
        "env_vars": test_env_vars(),
        "client_id": test_client_id_format(),
        "encryption_key": test_encryption_key_format(),
    }

    if not all([results["env_vars"], results["encryption_key"]]):
        print("\n" + "=" * 60)
        print("❌ CONFIGURATION INCOMPLÈTE")
        print("=" * 60)
        print("\nCorrigez les erreurs ci-dessus avant de continuer.")
        sys.exit(1)

    # Générer l'URL OAuth
    oauth_url = generate_oauth_url()

    # Tester le service
    service_ok = test_service_connection()

    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)

    env_status = "OK" if results["env_vars"] else "ERREUR"
    print(f"\n✅ Variables d'environnement : {env_status}")

    client_icon = "✅" if results["client_id"] else "⚠️"
    client_status = "OK" if results["client_id"] else "INHABITUEL"
    print(f"{client_icon} Format Client ID         : {client_status}")

    enc_status = "OK" if results["encryption_key"] else "ERREUR"
    print(f"✅ Clé de chiffrement       : {enc_status}")
    print("✅ URL OAuth                : OK")

    if service_ok is not None:
        svc_icon = "✅" if service_ok else "❌"
        svc_status = "ACCESSIBLE" if service_ok else "INACCESSIBLE"
        print(f"{svc_icon} Service contacts         : {svc_status}")

    if all(results.values()) and service_ok:
        print("\n🎉 CONFIGURATION COMPLÈTE ET VALIDE!")
        print_next_steps(oauth_url)
    elif all(results.values()):
        print("\n✅ Configuration OAuth valide")
        print("⚠️  Démarrez le service contacts pour continuer")
        print_next_steps(oauth_url)
    else:
        print("\n❌ Configuration incomplète")
        sys.exit(1)


if __name__ == "__main__":
    main()
