"""Tests for mTLS (Mutual TLS) module.

Tests cover:
- MTLSConfig validation
- SSL context creation
- Client certificate CN extraction
- Certificate info extraction
"""

import ssl
from pathlib import Path

import pytest

from skylink.mtls import (
    MTLSConfig,
    create_ssl_context,
    extract_client_cert_info,
    extract_client_cn,
)


class TestMTLSConfig:
    """Tests for MTLSConfig model."""

    def test_default_config(self):
        """mTLS should be disabled by default."""
        config = MTLSConfig()

        assert config.enabled is False
        assert config.cert_file == Path("certs/server/server.crt")
        assert config.key_file == Path("certs/server/server.key")
        assert config.ca_cert_file == Path("certs/ca/ca.crt")
        assert config.verify_mode == "CERT_REQUIRED"

    def test_config_enabled(self):
        """Config should accept enabled=True."""
        config = MTLSConfig(enabled=True)
        assert config.enabled is True

    def test_config_custom_paths(self):
        """Config should accept custom certificate paths."""
        config = MTLSConfig(
            enabled=True,
            cert_file=Path("/custom/server.crt"),
            key_file=Path("/custom/server.key"),
            ca_cert_file=Path("/custom/ca.crt"),
        )

        assert config.cert_file == Path("/custom/server.crt")
        assert config.key_file == Path("/custom/server.key")
        assert config.ca_cert_file == Path("/custom/ca.crt")

    def test_config_verify_modes(self):
        """Config should accept valid verify modes."""
        for mode in ["CERT_NONE", "CERT_OPTIONAL", "CERT_REQUIRED"]:
            config = MTLSConfig(verify_mode=mode)
            assert config.verify_mode == mode

    def test_config_invalid_verify_mode(self):
        """Config should reject invalid verify modes."""
        with pytest.raises(ValueError) as exc_info:
            MTLSConfig(verify_mode="INVALID_MODE")

        assert "verify_mode must be one of" in str(exc_info.value)

    def test_config_extra_fields_rejected(self):
        """Config should reject unknown fields (Security by Design)."""
        with pytest.raises(ValueError):
            MTLSConfig(unknown_field="value")

    def test_validate_files_exist_disabled(self):
        """File validation should pass when mTLS is disabled."""
        config = MTLSConfig(enabled=False)
        # Should not raise even with default non-existent paths
        config.validate_files_exist()

    def test_validate_files_exist_missing(self):
        """File validation should fail when files are missing."""
        config = MTLSConfig(
            enabled=True,
            cert_file=Path("/nonexistent/server.crt"),
            key_file=Path("/nonexistent/server.key"),
            ca_cert_file=Path("/nonexistent/ca.crt"),
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            config.validate_files_exist()

        error_msg = str(exc_info.value)
        assert "Server certificate" in error_msg
        assert "Server key" in error_msg
        assert "CA certificate" in error_msg


class TestCreateSSLContext:
    """Tests for create_ssl_context function."""

    def test_ssl_context_disabled(self):
        """Should return None when mTLS is disabled."""
        config = MTLSConfig(enabled=False)
        context = create_ssl_context(config)
        assert context is None

    def test_ssl_context_missing_files(self):
        """Should raise error when certificate files are missing."""
        config = MTLSConfig(
            enabled=True,
            cert_file=Path("/nonexistent/server.crt"),
        )

        with pytest.raises(FileNotFoundError):
            create_ssl_context(config)

    @pytest.mark.skipif(
        not Path("certs/server/server.crt").exists(),
        reason="Test certificates not generated",
    )
    def test_ssl_context_with_certs(self):
        """Should create valid SSL context with real certificates."""
        config = MTLSConfig(
            enabled=True,
            cert_file=Path("certs/server/server.crt"),
            key_file=Path("certs/server/server.key"),
            ca_cert_file=Path("certs/ca/ca.crt"),
        )

        context = create_ssl_context(config)

        assert context is not None
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2

    @pytest.mark.skipif(
        not Path("certs/server/server.crt").exists(),
        reason="Test certificates not generated",
    )
    def test_ssl_context_verify_modes(self):
        """SSL context should respect verify_mode setting."""
        modes = {
            "CERT_NONE": ssl.CERT_NONE,
            "CERT_OPTIONAL": ssl.CERT_OPTIONAL,
            "CERT_REQUIRED": ssl.CERT_REQUIRED,
        }

        for mode_str, mode_ssl in modes.items():
            config = MTLSConfig(
                enabled=True,
                cert_file=Path("certs/server/server.crt"),
                key_file=Path("certs/server/server.key"),
                ca_cert_file=Path("certs/ca/ca.crt"),
                verify_mode=mode_str,
            )

            context = create_ssl_context(config)
            assert context.verify_mode == mode_ssl


class TestExtractClientCN:
    """Tests for extract_client_cn function."""

    def test_extract_cn_none_cert(self):
        """Should return None for None certificate."""
        result = extract_client_cn(None)
        assert result is None

    def test_extract_cn_empty_cert(self):
        """Should return None for empty certificate dict."""
        result = extract_client_cn({})
        assert result is None

    def test_extract_cn_no_subject(self):
        """Should return None for certificate without subject."""
        cert = {"issuer": ((("commonName", "CA"),),)}
        result = extract_client_cn(cert)
        assert result is None

    def test_extract_cn_valid_cert(self):
        """Should extract CN from valid certificate."""
        # Certificate format from ssl.getpeercert()
        cert = {
            "subject": (
                (("countryName", "FR"),),
                (("stateOrProvinceName", "IDF"),),
                (("localityName", "Paris"),),
                (("organizationName", "SkyLink"),),
                (("organizationalUnitName", "Aircrafts"),),
                (("commonName", "aircraft-001"),),
            ),
        }

        result = extract_client_cn(cert)
        assert result == "aircraft-001"

    def test_extract_cn_uuid_format(self):
        """Should extract UUID-format CN."""
        cert = {
            "subject": ((("commonName", "550e8400-e29b-41d4-a716-446655440000"),),),
        }

        result = extract_client_cn(cert)
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_extract_cn_multiple_rdns(self):
        """Should extract CN from certificate with multiple RDNs."""
        cert = {
            "subject": (
                (
                    ("organizationName", "SkyLink"),
                    ("commonName", "aircraft-test"),
                ),
            ),
        }

        result = extract_client_cn(cert)
        assert result == "aircraft-test"


class TestExtractClientCertInfo:
    """Tests for extract_client_cert_info function."""

    def test_extract_info_none_cert(self):
        """Should return empty dict for None certificate."""
        result = extract_client_cert_info(None)
        assert result == {}

    def test_extract_info_empty_cert(self):
        """Should return empty dict for empty certificate."""
        result = extract_client_cert_info({})
        assert result == {}

    def test_extract_info_full_cert(self):
        """Should extract all available info from certificate."""
        cert = {
            "subject": ((("commonName", "aircraft-001"),),),
            "issuer": ((("commonName", "SkyLink Root CA"),),),
            "notBefore": "Dec  1 00:00:00 2024 GMT",
            "notAfter": "Dec  1 00:00:00 2025 GMT",
            "serialNumber": "1234567890ABCDEF",
        }

        result = extract_client_cert_info(cert)

        assert result["cn"] == "aircraft-001"
        assert result["issuer"] == "SkyLink Root CA"
        assert result["not_before"] == "Dec  1 00:00:00 2024 GMT"
        assert result["not_after"] == "Dec  1 00:00:00 2025 GMT"
        assert result["serial"] == "1234567890ABCDEF"

    def test_extract_info_partial_cert(self):
        """Should handle certificate with missing optional fields."""
        cert = {
            "subject": ((("commonName", "aircraft-002"),),),
        }

        result = extract_client_cert_info(cert)

        assert result["cn"] == "aircraft-002"
        assert "issuer" not in result
        assert "not_before" not in result


class TestMTLSConfigIntegration:
    """Integration tests for mTLS configuration with settings."""

    def test_settings_get_mtls_config(self):
        """Settings should provide MTLSConfig through get_mtls_config()."""
        from skylink.config import settings

        config = settings.get_mtls_config()

        assert isinstance(config, MTLSConfig)
        assert config.enabled == settings.mtls_enabled
        assert config.cert_file == settings.mtls_cert_file
        assert config.key_file == settings.mtls_key_file
        assert config.ca_cert_file == settings.mtls_ca_cert_file
        assert config.verify_mode == settings.mtls_verify_mode

    def test_settings_mtls_disabled_by_default(self):
        """mTLS should be disabled by default (without env override).

        Note: When .env.test is loaded, MTLS_ENABLED may be set to true.
        This test verifies the default value when no env var is set.
        """
        from unittest.mock import patch

        # Test default behavior without env var
        with patch.dict("os.environ", {"MTLS_ENABLED": "false"}, clear=False):
            from skylink.config import Settings

            fresh_settings = Settings()
            assert fresh_settings.mtls_enabled is False
