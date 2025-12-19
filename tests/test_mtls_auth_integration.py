"""Tests for mTLS + JWT authentication integration.

Tests cover:
- JWT verification with mTLS cross-validation
- CN vs JWT subject matching
- Middleware certificate extraction
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from starlette.datastructures import State

from skylink.auth import verify_jwt_with_mtls


class TestVerifyJWTWithMTLS:
    """Tests for verify_jwt_with_mtls function."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with state."""
        request = MagicMock(spec=Request)
        request.state = State()
        return request

    @pytest.fixture
    def valid_claims(self):
        """Valid JWT claims."""
        return {
            "sub": "vehicle-test-001",
            "aud": "skylink",
            "iat": 1700000000,
            "exp": 1700000900,
        }

    @pytest.mark.asyncio
    async def test_mtls_disabled_passes_jwt_only(self, mock_request, valid_claims):
        """When mTLS is disabled, only JWT is validated."""
        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = False

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = valid_claims

                result = await verify_jwt_with_mtls(
                    mock_request,
                    authorization="Bearer valid_token",
                )

                assert result == valid_claims
                mock_verify.assert_called_once()

    @pytest.mark.asyncio
    async def test_mtls_enabled_no_cn_passes(self, mock_request, valid_claims):
        """When mTLS enabled but no client CN, JWT is still validated."""
        mock_request.state.mtls_cn = None

        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = True

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = valid_claims

                result = await verify_jwt_with_mtls(
                    mock_request,
                    authorization="Bearer valid_token",
                )

                assert result == valid_claims

    @pytest.mark.asyncio
    async def test_mtls_enabled_matching_cn_passes(self, mock_request, valid_claims):
        """When mTLS enabled and CN matches JWT subject, validation passes."""
        mock_request.state.mtls_cn = "vehicle-test-001"  # Matches valid_claims["sub"]

        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = True

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = valid_claims

                result = await verify_jwt_with_mtls(
                    mock_request,
                    authorization="Bearer valid_token",
                )

                assert result == valid_claims

    @pytest.mark.asyncio
    async def test_mtls_enabled_mismatched_cn_fails(self, mock_request, valid_claims):
        """When mTLS enabled and CN doesn't match JWT subject, 403 is raised."""
        mock_request.state.mtls_cn = "different-vehicle"  # Doesn't match valid_claims["sub"]

        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = True

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = valid_claims

                with pytest.raises(HTTPException) as exc_info:
                    await verify_jwt_with_mtls(
                        mock_request,
                        authorization="Bearer valid_token",
                    )

                assert exc_info.value.status_code == 403
                assert "Certificate CN does not match" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_mtls_enabled_uuid_cn_matches(self, mock_request):
        """UUID format CN should match UUID format JWT subject."""
        uuid_claims = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "aud": "skylink",
            "iat": 1700000000,
            "exp": 1700000900,
        }
        mock_request.state.mtls_cn = "550e8400-e29b-41d4-a716-446655440000"

        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = True

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = uuid_claims

                result = await verify_jwt_with_mtls(
                    mock_request,
                    authorization="Bearer valid_token",
                )

                assert result == uuid_claims

    @pytest.mark.asyncio
    async def test_jwt_failure_propagates(self, mock_request):
        """JWT verification failure should propagate as 401."""
        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = True

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.side_effect = HTTPException(
                    status_code=401,
                    detail="Invalid token",
                )

                with pytest.raises(HTTPException) as exc_info:
                    await verify_jwt_with_mtls(
                        mock_request,
                        authorization="Bearer invalid_token",
                    )

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_state_attribute_handles_gracefully(self, valid_claims):
        """Should handle request without mtls_cn state attribute."""
        request = MagicMock(spec=Request)
        request.state = State()  # No mtls_cn attribute

        with patch("skylink.auth.settings") as mock_settings:
            mock_settings.mtls_enabled = True

            with patch("skylink.auth.verify_jwt", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = valid_claims

                # Should not raise, just skip mTLS validation
                result = await verify_jwt_with_mtls(
                    request,
                    authorization="Bearer valid_token",
                )

                assert result == valid_claims


class TestMTLSMiddleware:
    """Tests for mTLS extraction middleware."""

    @pytest.mark.asyncio
    async def test_middleware_extracts_cn(self):
        """Middleware should extract CN from client certificate."""
        from skylink.middlewares import mtls_extraction_middleware

        # Create mock request with transport and SSL
        mock_ssl_object = MagicMock()
        mock_ssl_object.getpeercert.return_value = {
            "subject": ((("commonName", "vehicle-test"),),),
        }

        mock_transport = MagicMock()
        mock_transport.get_extra_info.return_value = mock_ssl_object

        mock_request = MagicMock(spec=Request)
        mock_request.scope = {"transport": mock_transport}
        mock_request.state = State()

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        response = await mtls_extraction_middleware(mock_request, mock_call_next)

        assert mock_request.state.mtls_cn == "vehicle-test"
        assert mock_request.state.mtls_verified is True
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_middleware_no_transport(self):
        """Middleware should handle request without transport."""
        from skylink.middlewares import mtls_extraction_middleware

        mock_request = MagicMock(spec=Request)
        mock_request.scope = {}  # No transport
        mock_request.state = State()

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        response = await mtls_extraction_middleware(mock_request, mock_call_next)

        assert mock_request.state.mtls_cn is None
        assert mock_request.state.mtls_verified is False
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_middleware_no_ssl_object(self):
        """Middleware should handle transport without SSL object."""
        from skylink.middlewares import mtls_extraction_middleware

        mock_transport = MagicMock()
        mock_transport.get_extra_info.return_value = None  # No SSL

        mock_request = MagicMock(spec=Request)
        mock_request.scope = {"transport": mock_transport}
        mock_request.state = State()

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        await mtls_extraction_middleware(mock_request, mock_call_next)

        assert mock_request.state.mtls_cn is None
        assert mock_request.state.mtls_verified is False

    @pytest.mark.asyncio
    async def test_middleware_cert_extraction_error(self):
        """Middleware should handle certificate extraction errors gracefully."""
        from skylink.middlewares import mtls_extraction_middleware

        mock_ssl_object = MagicMock()
        mock_ssl_object.getpeercert.side_effect = Exception("SSL error")

        mock_transport = MagicMock()
        mock_transport.get_extra_info.return_value = mock_ssl_object

        mock_request = MagicMock(spec=Request)
        mock_request.scope = {"transport": mock_transport}
        mock_request.state = State()

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        # Should not raise, just continue without mTLS
        response = await mtls_extraction_middleware(mock_request, mock_call_next)

        assert mock_request.state.mtls_cn is None
        assert mock_request.state.mtls_verified is False
        assert response == mock_response
