"""E2E test using existing OAuth tokens from database.

This test validates the OAuth flow with REAL Google API using tokens
already configured in the database (via CLI tool).

⚠️  Prerequisites:
1. Aircraft must be configured with OAuth (via scripts/quick_oauth_setup.sh)
2. Database must contain valid tokens for the test aircraft
3. Internet connection required
"""

import asyncio
import os
from uuid import UUID

import pytest

from contacts.database import SessionLocal
from contacts.google_people import GooglePeopleClient
from contacts.oauth import GoogleOAuthClient

# Test aircraft ID (configured via CLI tool)
TEST_AIRCRAFT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.mark.e2e
@pytest.mark.skip(reason="E2E test requiring real Google API - run manually")
def test_fetch_contacts_with_existing_tokens():
    """Test fetching real Google contacts using existing OAuth tokens.

    This test:
    1. Retrieves OAuth tokens from database
    2. Calls Google People API with real access token
    3. Validates response structure
    4. Verifies real contact data
    """
    # ==================== SETUP ====================
    db = SessionLocal()

    # Get tokens directly from database (synchronous)
    from contacts.models import OAuthToken

    token_record = db.query(OAuthToken).filter(OAuthToken.aircraft_id == TEST_AIRCRAFT_ID).first()

    if token_record is None:
        db.close()
        pytest.skip(
            f"No OAuth tokens found for aircraft {TEST_AIRCRAFT_ID}. "
            f"Run 'scripts/quick_oauth_setup.sh' first."
        )

    access_token = token_record.access_token

    # ==================== TEST: Fetch Contacts ====================
    print(f"\n[E2E Test] Fetching contacts for aircraft {TEST_AIRCRAFT_ID}...")

    people_client = GooglePeopleClient(access_token=access_token)

    try:
        response = asyncio.run(
            people_client.list_contacts(
                person_fields="names,emailAddresses,phoneNumbers", page_size=5
            )
        )
    except Exception as e:
        pytest.fail(f"Failed to fetch contacts from Google API: {e}")

    # ==================== VALIDATE RESPONSE ====================
    assert "connections" in response, "Missing 'connections' in response"

    contacts = response["connections"]
    assert len(contacts) > 0, "No contacts returned (expected at least 1)"

    # Validate first contact structure
    first_contact = contacts[0]
    assert "resourceName" in first_contact, "Missing 'resourceName'"
    assert (
        "names" in first_contact or "emailAddresses" in first_contact
    ), "Contact must have either names or emailAddresses"

    # Print contacts for manual verification
    print(f"\n✅ Successfully fetched {len(contacts)} contacts:")
    for i, contact in enumerate(contacts[:3], 1):
        name = "N/A"
        if "names" in contact and contact["names"]:
            name = contact["names"][0].get("displayName", "N/A")

        email = "N/A"
        if "emailAddresses" in contact and contact["emailAddresses"]:
            email = contact["emailAddresses"][0].get("value", "N/A")

        print(f"  {i}. {name} ({email})")

    print("\n✅ E2E Test PASSED: Google People API is accessible")

    db.close()


@pytest.mark.e2e
@pytest.mark.skip(reason="E2E test requiring real Google API - run manually")
def test_token_refresh_with_existing_refresh_token():
    """Test refreshing access token using existing refresh token.

    This test:
    1. Retrieves refresh token from database
    2. Calls Google OAuth token endpoint to refresh
    3. Validates new access token
    4. Verifies new token works with Google People API
    """
    # ==================== SETUP ====================
    db = SessionLocal()

    # Get tokens directly from database (synchronous)
    from contacts.encryption import decrypt_token
    from contacts.models import OAuthToken

    token_record = db.query(OAuthToken).filter(OAuthToken.aircraft_id == TEST_AIRCRAFT_ID).first()

    if token_record is None:
        db.close()
        pytest.skip(
            f"No OAuth tokens found for aircraft {TEST_AIRCRAFT_ID}. "
            f"Run 'scripts/quick_oauth_setup.sh' first."
        )

    # Decrypt refresh token
    refresh_token = decrypt_token(token_record.refresh_token)
    old_access_token = token_record.access_token

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    assert client_id, "GOOGLE_CLIENT_ID not set"
    assert client_secret, "GOOGLE_CLIENT_SECRET not set"

    # ==================== TEST: Refresh Token ====================
    print(f"\n[E2E Test] Refreshing access token for aircraft {TEST_AIRCRAFT_ID}...")

    oauth_client = GoogleOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8003/oauth/callback",
    )

    try:
        new_tokens = asyncio.run(oauth_client.refresh_access_token(refresh_token))
    except Exception as e:
        pytest.fail(f"Failed to refresh access token: {e}")

    # ==================== VALIDATE NEW TOKEN ====================
    assert "access_token" in new_tokens, "Missing 'access_token' in refreshed tokens"
    assert "expires_in" in new_tokens, "Missing 'expires_in' in refreshed tokens"

    new_access_token = new_tokens["access_token"]
    assert new_access_token != old_access_token, "New access token should be different from old one"

    print(f"✅ New access token obtained: {new_access_token[:20]}...")

    # ==================== TEST: New Token Works ====================
    print("\n[E2E Test] Testing new access token with Google People API...")

    people_client = GooglePeopleClient(access_token=new_access_token)

    try:
        response = asyncio.run(people_client.list_contacts(person_fields="names", page_size=1))
    except Exception as e:
        pytest.fail(f"New access token doesn't work: {e}")

    assert "connections" in response, "New token failed to fetch contacts"

    print("✅ E2E Test PASSED: Token refresh works correctly")

    db.close()


if __name__ == "__main__":
    """Run E2E tests directly (for debugging)."""
    print("=" * 80)
    print("E2E Tests - OAuth with Existing Tokens")
    print("=" * 80)

    # Test 1
    print("\n" + "=" * 80)
    print("Test 1: Fetch Contacts")
    print("=" * 80)
    try:
        test_fetch_contacts_with_existing_tokens()
        print("\n✅ Test 1 PASSED")
    except pytest.skip.Exception as e:
        print(f"\n⏭️  Test 1 SKIPPED: {e}")
    except Exception as e:
        print(f"\n❌ Test 1 FAILED: {e}")

    # Test 2
    print("\n" + "=" * 80)
    print("Test 2: Token Refresh")
    print("=" * 80)
    try:
        test_token_refresh_with_existing_refresh_token()
        print("\n✅ Test 2 PASSED")
    except pytest.skip.Exception as e:
        print(f"\n⏭️  Test 2 SKIPPED: {e}")
    except Exception as e:
        print(f"\n❌ Test 2 FAILED: {e}")
