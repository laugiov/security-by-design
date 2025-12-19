"""End-to-end tests for Google OAuth2 flow with REAL Google APIs.

⚠️  IMPORTANT: These tests require manual execution with real Google OAuth credentials.
⚠️  They are NOT run in CI/CD by default (marked with @pytest.mark.skip).

To run these tests manually:

1. Set up Google Cloud OAuth credentials (see local/contacts-oauth/GOOGLE_CLOUD_SETUP.md)

2. Configure environment variables:
   export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
   export GOOGLE_CLIENT_SECRET="your-client-secret"
   export GOOGLE_REDIRECT_URI="http://localhost:8003/oauth/callback"
   export ENCRYPTION_KEY="$(openssl rand -hex 32)"
   export DATABASE_URL="sqlite:///:memory:"  # Or your test database

3. Obtain an authorization code manually:
   - Open browser: https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&response_type=code&scope=https://www.googleapis.com/auth/contacts.readonly&access_type=offline&prompt=consent
   - Authorize with your Google account
   - Copy the authorization code from the redirect URL

4. Update the test with your authorization code (it's a one-time code, expires quickly)

5. Run the test:
   poetry run pytest tests/e2e/test_google_oauth_e2e.py -v -s --no-skip

Note: The --no-skip flag is a hypothetical example. By default, these tests are skipped.
To run them, remove the @pytest.mark.skip decorator manually.
"""

import os

import pytest

from contacts.google_people import GooglePeopleClient
from contacts.oauth import GoogleOAuthClient

# ==================== E2E Test Markers ====================
# These tests are skipped by default to avoid breaking CI/CD

pytestmark = pytest.mark.e2e  # Mark all tests in this module as E2E


@pytest.mark.skip(reason="E2E test requiring manual setup - see docstring for instructions")
class TestGoogleOAuthE2E:
    """E2E tests for Google OAuth2 flow with real Google APIs.

    Prerequisites:
    - Valid Google Cloud OAuth credentials in environment variables
    - Manual authorization code obtained from Google consent screen
    - Internet connection
    """

    def test_oauth_complete_flow_with_real_google_api(self):
        """Test complete OAuth flow: exchange code → fetch contacts → refresh token.

        This test validates the entire OAuth2 flow end-to-end:
        1. Exchange authorization code for access/refresh tokens
        2. Use access token to fetch real contacts from Google People API
        3. Refresh the access token using refresh token

        Setup required:
        1. Set environment variables (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, etc.)
        2. Obtain authorization code from Google (see module docstring)
        3. Update AUTHORIZATION_CODE below with your fresh code
        """
        # ==================== SETUP ====================
        # TODO: Replace with your authorization code (obtain manually)
        AUTHORIZATION_CODE = "4/0AfJohXm..."  # ⚠️  Must be fresh (< 10 minutes old)

        # Verify environment variables are set
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        assert client_id, "GOOGLE_CLIENT_ID environment variable is required"
        assert client_secret, "GOOGLE_CLIENT_SECRET environment variable is required"
        assert redirect_uri, "GOOGLE_REDIRECT_URI environment variable is required"

        # ==================== TEST PHASE 1: Exchange Code for Tokens ====================
        print("\n[Phase 1] Exchanging authorization code for tokens...")

        oauth_client = GoogleOAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        # Exchange code for tokens (REAL API CALL)
        try:
            tokens_response = oauth_client.exchange_code_for_tokens(AUTHORIZATION_CODE)
        except Exception as e:
            pytest.fail(
                f"Failed to exchange authorization code: {e}\n"
                f"Hint: Authorization codes expire after 10 minutes. "
                f"Obtain a fresh code and update AUTHORIZATION_CODE in the test."
            )

        # Validate response structure
        assert "access_token" in tokens_response, "Missing access_token in response"
        assert "refresh_token" in tokens_response, "Missing refresh_token in response"
        assert "expires_in" in tokens_response, "Missing expires_in in response"
        assert "scope" in tokens_response, "Missing scope in response"

        # Extract tokens
        access_token = tokens_response["access_token"]
        refresh_token = tokens_response["refresh_token"]
        granted_scopes = tokens_response["scope"]

        print(f"✅ Received access_token: {access_token[:20]}...")
        print(f"✅ Received refresh_token: {refresh_token[:20]}...")
        print(f"✅ Granted scopes: {granted_scopes}")

        # Validate scopes
        assert oauth_client.validate_scopes(
            granted_scopes
        ), "Required scope 'contacts.readonly' not granted"

        # ==================== TEST PHASE 2: Fetch Contacts with Access Token ====================
        print("\n[Phase 2] Fetching contacts from Google People API...")

        people_client = GooglePeopleClient(access_token=access_token, timeout=10.0)

        # Fetch contacts (REAL API CALL)
        try:
            contacts_response = people_client.list_contacts(
                person_fields="names,emailAddresses,phoneNumbers", page_size=10
            )
        except Exception as e:
            pytest.fail(f"Failed to fetch contacts: {e}")

        # Validate response structure
        assert (
            "connections" in contacts_response or contacts_response.get("totalPeople") == 0
        ), "Invalid People API response"

        total_contacts = contacts_response.get("totalPeople", 0)
        connections = contacts_response.get("connections", [])

        print(f"✅ Total contacts: {total_contacts}")
        print(f"✅ Fetched {len(connections)} contacts in this page")

        if len(connections) > 0:
            # Print first contact (anonymized)
            first_contact = connections[0]
            names = first_contact.get("names", [{}])
            display_name = names[0].get("displayName", "N/A") if names else "N/A"
            print(f"✅ First contact name: {display_name}")

        # ==================== TEST PHASE 3: Refresh Access Token ====================
        print("\n[Phase 3] Refreshing access token...")

        # Refresh token (REAL API CALL)
        try:
            refreshed_tokens = oauth_client.refresh_access_token(refresh_token)
        except Exception as e:
            pytest.fail(
                f"Failed to refresh access token: {e}\n"
                f"Hint: Refresh tokens can be revoked. "
                f"Check your Google account permissions."
            )

        # Validate response structure
        assert "access_token" in refreshed_tokens, "Missing access_token in refresh response"
        assert "expires_in" in refreshed_tokens, "Missing expires_in in refresh response"

        new_access_token = refreshed_tokens["access_token"]
        print(f"✅ New access_token: {new_access_token[:20]}...")

        # Verify new token is different from old token
        assert new_access_token != access_token, "New access token should be different"

        # ==================== TEST PHASE 4: Use Refreshed Token ====================
        print("\n[Phase 4] Verifying refreshed token works...")

        people_client_refreshed = GooglePeopleClient(access_token=new_access_token, timeout=10.0)

        # Fetch contacts with refreshed token (REAL API CALL)
        try:
            contacts_response_2 = people_client_refreshed.list_contacts(
                person_fields="names", page_size=5
            )
        except Exception as e:
            pytest.fail(f"Failed to fetch contacts with refreshed token: {e}")

        # Validate response
        assert "totalPeople" in contacts_response_2, "Invalid response with refreshed token"

        print(f"✅ Refreshed token works! Total contacts: {contacts_response_2['totalPeople']}")

        print("\n" + "=" * 60)
        print("🎉 E2E TEST PASSED: Complete OAuth flow validated!")
        print("=" * 60)

    def test_oauth_error_handling_with_invalid_code(self):
        """Test error handling when using an invalid authorization code.

        This test validates that the OAuth client properly handles errors
        when an invalid or expired authorization code is used.
        """
        # ==================== SETUP ====================
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        assert client_id, "GOOGLE_CLIENT_ID environment variable is required"

        oauth_client = GoogleOAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        # ==================== TEST: Invalid Authorization Code ====================
        print("\n[Test] Trying to exchange invalid authorization code...")

        INVALID_CODE = "INVALID_CODE_12345"

        # Should raise InvalidCodeError or similar
        with pytest.raises(Exception) as exc_info:
            oauth_client.exchange_code_for_tokens(INVALID_CODE)

        print(f"✅ Correctly raised exception: {type(exc_info.value).__name__}")
        print(f"✅ Error message: {str(exc_info.value)}")

        print("\n" + "=" * 60)
        print("🎉 E2E ERROR HANDLING TEST PASSED!")
        print("=" * 60)


# ==================== MANUAL TEST EXECUTION NOTES ====================

"""
MANUAL EXECUTION CHECKLIST:

Before running these tests, complete the following steps:

□ 1. Create Google Cloud OAuth credentials
     - Follow: local/contacts-oauth/GOOGLE_CLOUD_SETUP.md
     - Download client_secret.json

□ 2. Set environment variables:
     export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
     export GOOGLE_CLIENT_SECRET="GOCSPX-your-secret"
     export GOOGLE_REDIRECT_URI="http://localhost:8003/oauth/callback"
     export ENCRYPTION_KEY="$(openssl rand -hex 32)"

□ 3. Obtain authorization code:
     - Open browser with OAuth consent URL (see module docstring)
     - Authorize with your Google account
     - Copy code from redirect URL: ...?code=4/0AfJohXm...

□ 4. Update test_oauth_complete_flow_with_real_google_api():
     - Replace AUTHORIZATION_CODE with your fresh code
     - Authorization codes expire after 10 minutes!

□ 5. Remove @pytest.mark.skip decorator from test class

□ 6. Run E2E tests:
     poetry run pytest tests/e2e/test_google_oauth_e2e.py -v -s

□ 7. After successful run, re-add @pytest.mark.skip decorator
     (to prevent accidental CI/CD execution)

Expected output:
  - test_oauth_complete_flow_with_real_google_api: PASSED
  - test_oauth_error_handling_with_invalid_code: PASSED

If tests fail:
  - Check error messages carefully
  - Verify environment variables are set correctly
  - Ensure authorization code is fresh (< 10 minutes old)
  - Check Google Cloud Console for API quotas/limits
  - Review local/contacts-oauth/ERROR_HANDLING.md
"""
