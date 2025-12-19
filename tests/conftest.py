"""Pytest configuration for SkyLink tests.

This module configures pytest to:
1. Load .env.test file before running tests
2. Ensure test isolation with dedicated test keys
3. Provide fixtures for common test scenarios
"""

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv


def pytest_configure(config):
    """Load .env.test before running any tests.

    This ensures that all tests use the dedicated test keys
    from .env.test instead of the development keys from .env

    Security Notes:
        - .env.test contains FAKE keys generated only for testing
        - These keys are different from development and production keys
        - Test keys can be safely committed to version control
    """
    # Get project root directory
    project_root = Path(__file__).parent.parent
    env_test_path = project_root / ".env.test"

    if env_test_path.exists():
        # Load .env.test and override existing environment variables
        load_dotenv(env_test_path, override=True)
        print(f"\n✅ Loaded test environment from {env_test_path}")
    else:
        print(f"\n⚠️  Warning: {env_test_path} not found")

    # FALLBACK for CI/CD: Generate temporary test keys if not present
    if not os.getenv("PRIVATE_KEY_PEM") or not os.getenv("PUBLIC_KEY_PEM"):
        print("\nCI/CD detected: Generating temporary test keys...")
        try:
            # Generate temporary RSA key pair
            private_key_proc = (
                subprocess.run(  # nosec B603 B607 (hardcoded openssl command for CI/CD)
                    ["openssl", "genrsa", "2048"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            )
            private_key = private_key_proc.stdout

            # Generate public key from private
            public_key_proc = (
                subprocess.run(  # nosec B603 B607 (hardcoded openssl command for CI/CD)
                    ["openssl", "rsa", "-pubout"],
                    input=private_key,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            )
            public_key = public_key_proc.stdout

            # Set as environment variables
            os.environ["PRIVATE_KEY_PEM"] = private_key
            os.environ["PUBLIC_KEY_PEM"] = public_key
            print("✅ Temporary test keys generated for CI/CD")
        except Exception as e:
            print(f"Failed to generate test keys: {e}")
            raise
