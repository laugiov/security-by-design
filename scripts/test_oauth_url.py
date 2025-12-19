#!/usr/bin/env python3
"""Test script to verify Google OAuth configuration.

This script verifies that:
1. Environment variables are defined
2. The client_id is valid
3. The authorization URL can be generated
4. The contacts service is accessible

Usage:
    python scripts/test_oauth_url.py
"""

import os
import sys
from urllib.parse import urlencode

# Check if httpx is available
try:
    import httpx
except ImportError:
    print("⚠️  httpx is not installed")
    print("   Install with: poetry add httpx")
    httpx = None


def test_env_vars():
    """Test that environment variables are defined."""
    print("\n" + "=" * 60)
    print("1. Environment Variables Verification")
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

    # Required variables
    for var_name, var_value in required_vars.items():
        if var_value:
            # Partially mask sensitive values
            if var_name == "GOOGLE_CLIENT_SECRET" or var_name == "ENCRYPTION_KEY":
                display_value = (
                    var_value[:10] + "..." + var_value[-10:] if len(var_value) > 20 else "***"
                )
            else:
                display_value = var_value[:30] + "..." if len(var_value) > 30 else var_value
            print(f"✅ {var_name:25} = {display_value}")
        else:
            print(f"❌ {var_name:25} = (not defined)")
            all_ok = False

    # Optional variables
    print("\nOptional variables:")
    for var_name, var_value in optional_vars.items():
        print(f"ℹ️  {var_name:25} = {var_value}")

    if not all_ok:
        print("\n❌ Some required variables are missing!")
        print("\nDefine them in your .env:")
        print('GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"')
        print('GOOGLE_CLIENT_SECRET="GOCSPX-your-secret"')
        print('ENCRYPTION_KEY="$(openssl rand -hex 32)"')
        return False

    print("\n✅ All required variables are defined!")
    return True


def test_client_id_format():
    """Verify Client ID format."""
    print("\n" + "=" * 60)
    print("2. Client ID Format Verification")
    print("=" * 60)

    client_id = os.getenv("GOOGLE_CLIENT_ID")

    if not client_id:
        print("❌ GOOGLE_CLIENT_ID not defined")
        return False

    # Verify Google OAuth client ID format
    if ".apps.googleusercontent.com" in client_id:
        print(f"✅ Valid Client ID format: {client_id[:30]}...")
        return True
    else:
        print(f"⚠️  Unusual Client ID format: {client_id}")
        print("   Expected format: xxxxx-xxxxx.apps.googleusercontent.com")
        return False


def test_encryption_key_format():
    """Verify encryption key format."""
    print("\n" + "=" * 60)
    print("3. Encryption Key Verification")
    print("=" * 60)

    encryption_key = os.getenv("ENCRYPTION_KEY")

    if not encryption_key:
        print("❌ ENCRYPTION_KEY not defined")
        return False

    # Verify it's a 64-character hex string (32 bytes)
    if len(encryption_key) == 64:
        try:
            bytes.fromhex(encryption_key)
            print("✅ Valid encryption key (32 bytes hex)")
            print(f"   Start: {encryption_key[:10]}...")
            return True
        except ValueError:
            print("❌ Invalid encryption key (not hex)")
            return False
    else:
        print(f"⚠️  Incorrect key length: {len(encryption_key)} characters (expected: 64)")
        print("   Generate a new key with: openssl rand -hex 32")
        return False


def generate_oauth_url():
    """Generate OAuth authorization URL."""
    print("\n" + "=" * 60)
    print("4. OAuth URL Generation")
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

    print("✅ Authorization URL generated successfully!\n")
    print("Full URL:")
    print(f"{oauth_url}\n")

    # Display parameters
    print("Parameters:")
    for key, value in params.items():
        if key == "client_id":
            display_value = value[:30] + "..." if len(value) > 30 else value
        else:
            display_value = value
        print(f"  {key:20} = {display_value}")

    return oauth_url


def test_service_connection():
    """Test connection to contacts service."""
    print("\n" + "=" * 60)
    print("5. Contacts Service Connection Test")
    print("=" * 60)

    if not httpx:
        print("⚠️  Cannot test (httpx not installed)")
        return None

    service_url = "http://localhost:8003"

    try:
        print(f"Attempting connection to {service_url}/health...")
        response = httpx.get(f"{service_url}/health", timeout=2.0)

        if response.status_code == 200:
            data = response.json()
            print("✅ Contacts service accessible!")
            print(f"   Status: {data.get('status', 'unknown')}")
            print(f"   Service: {data.get('service', 'unknown')}")
            return True
        else:
            print(f"⚠️  Service responds but status {response.status_code}")
            return False

    except httpx.ConnectError:
        print(f"❌ Cannot connect to {service_url}")
        print("   The contacts service is probably not started")
        print("\n   Start it with:")
        print("   poetry run uvicorn contacts.main:app --host 0.0.0.0 --port 8003")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def print_next_steps(oauth_url):
    """Display next steps."""
    print("\n" + "=" * 60)
    print("📋 NEXT STEPS")
    print("=" * 60)

    print("\n1. Start the contacts service (if not already done):")
    print("   poetry run uvicorn contacts.main:app --host 0.0.0.0 --port 8003")

    print("\n2. Configure an aircraft with the CLI tool:")
    print("   poetry add httpx rich  # If not already installed")
    print("   python scripts/configure_aircraft_oauth.py")

    print("\n3. Or manually:")
    print("   a) Open this URL in the browser:")
    print(f"      {oauth_url[:80]}...")
    print("   b) Authorize contacts access")
    print("   c) Copy the code from the redirect URL")
    print("   d) Call /oauth/callback with the code and aircraft_id")

    print("\n4. Test the endpoint:")
    print('   curl -H "X-Aircraft-Id: <aircraft-uuid>" \\')
    print('        "http://localhost:8003/v1/contacts?person_fields=names"')

    print("\n📚 Complete documentation:")
    print("   local/contacts-oauth/DEPLOYMENT_GUIDE.md")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("🔍 GOOGLE OAUTH CONFIGURATION TEST")
    print("=" * 60)

    # Tests
    results = {
        "env_vars": test_env_vars(),
        "client_id": test_client_id_format(),
        "encryption_key": test_encryption_key_format(),
    }

    if not all([results["env_vars"], results["encryption_key"]]):
        print("\n" + "=" * 60)
        print("❌ INCOMPLETE CONFIGURATION")
        print("=" * 60)
        print("\nCorrect the errors above before continuing.")
        sys.exit(1)

    # Generate OAuth URL
    oauth_url = generate_oauth_url()

    # Test the service
    service_ok = test_service_connection()

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    env_status = "OK" if results["env_vars"] else "ERROR"
    print(f"\n✅ Environment variables    : {env_status}")

    client_icon = "✅" if results["client_id"] else "⚠️"
    client_status = "OK" if results["client_id"] else "UNUSUAL"
    print(f"{client_icon} Client ID format        : {client_status}")

    enc_status = "OK" if results["encryption_key"] else "ERROR"
    print(f"✅ Encryption key           : {enc_status}")
    print("✅ OAuth URL                : OK")

    if service_ok is not None:
        svc_icon = "✅" if service_ok else "❌"
        svc_status = "ACCESSIBLE" if service_ok else "INACCESSIBLE"
        print(f"{svc_icon} Contacts service        : {svc_status}")

    if all(results.values()) and service_ok:
        print("\n🎉 COMPLETE AND VALID CONFIGURATION!")
        print_next_steps(oauth_url)
    elif all(results.values()):
        print("\n✅ Valid OAuth configuration")
        print("⚠️  Start the contacts service to continue")
        print_next_steps(oauth_url)
    else:
        print("\n❌ Incomplete configuration")
        sys.exit(1)


if __name__ == "__main__":
    main()
