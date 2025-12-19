"""Tests for main application module."""

import pytest
from fastapi.testclient import TestClient

from skylink.main import add, app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["docs"] == "/docs"
    assert data["openapi"] == "/openapi.json"
    # Verify security headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "no-store" in response.headers["Cache-Control"]


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "skylink"


def test_robots_txt():
    """Test robots.txt endpoint."""
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in response.text
    assert "Disallow:" in response.text


def test_sitemap_xml():
    """Test sitemap.xml endpoint."""
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert '<?xml version="1.0"' in response.text
    assert "urlset" in response.text


def test_security_headers_middleware():
    """Test that security headers are added to all responses."""
    response = client.get("/health")
    # ZAP 10021 - X-Content-Type-Options
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    # Anti-clickjacking
    assert response.headers["X-Frame-Options"] == "DENY"
    # ZAP 10049 - Cache control
    assert "no-store" in response.headers["Cache-Control"]
    assert "no-cache" in response.headers["Cache-Control"]
    # ZAP 90004 - Spectre isolation
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    # Bonus headers
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "geolocation=()" in response.headers["Permissions-Policy"]


def test_add():
    """Test add function."""
    assert add(2, 3) == 5
    assert add(0, 0) == 0
    assert add(-1, 1) == 0
    assert add(10, -5) == 5


def test_add_type_validation():
    """Test add function with different types."""
    # This will pass as Python accepts int types
    result = add(1, 2)
    assert isinstance(result, int)


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (1, 1, 2),
        (5, 5, 10),
        (100, 200, 300),
        (-10, 10, 0),
    ],
)
def test_add_parametrized(a, b, expected):
    """Test add function with multiple inputs."""
    assert add(a, b) == expected


def test_app_title_and_version():
    """Test FastAPI app configuration."""
    assert app.title == "SkyLink API Gateway"
    assert app.version == "0.1.0"
    assert "API Gateway for Microservices" in app.description


def test_app_has_all_routers():
    """Test that all routers are registered."""
    router_paths = [route.path for route in app.routes]
    assert "/auth/token" in router_paths
    # NOTE: /weather/health removed (proxy-only router with /weather/current endpoint)
    assert "/weather/current" in router_paths
    # NOTE: /contacts/health removed in MR #7 (proxy-only router with /contacts/ endpoint)
    assert "/contacts/" in router_paths
    assert "/telemetry/health" in router_paths


def test_app_openapi_schema():
    """Test that OpenAPI schema is generated."""
    schema = app.openapi()
    assert schema is not None
    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "SkyLink API Gateway"


def test_metrics_endpoint():
    """Test Prometheus /metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Prometheus text format
    assert "text/plain" in response.headers["content-type"]
    # Check standard metrics
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text
    # Check custom rate limit metric
    assert "rate_limit_exceeded_total" in response.text
    # Check process metrics
    assert "process_" in response.text


def test_metrics_not_in_openapi():
    """Test that /metrics endpoint is excluded from OpenAPI schema."""
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/metrics" not in paths
