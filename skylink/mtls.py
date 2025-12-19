"""mTLS (Mutual TLS) module for SkyLink Gateway.

This module provides mutual TLS authentication between vehicles and the Gateway.
Vehicles must present a valid certificate signed by our CA to establish a connection.

Security by Design:
- Certificates are verified against a trusted CA
- Client CN (Common Name) is extracted for correlation with JWT
- TLS 1.2+ enforced with strong cipher suites
- Certificate paths are validated before use

Usage:
    # Create SSL context for server
    from skylink.mtls import MTLSConfig, create_ssl_context

    config = MTLSConfig(enabled=True)
    ssl_context = create_ssl_context(config)

    # Run uvicorn with SSL
    uvicorn.run(app, ssl=ssl_context)
"""

import ssl
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MTLSConfig(BaseModel):
    """Configuration for mTLS (Mutual TLS).

    Attributes:
        enabled: Whether mTLS is enabled (default: False)
        cert_file: Path to server certificate file
        key_file: Path to server private key file
        ca_cert_file: Path to CA certificate for client verification
        verify_mode: Client certificate verification mode
    """

    model_config = {"extra": "forbid"}  # Reject unknown fields (Security by Design)

    enabled: bool = Field(
        default=False,
        description="Enable mTLS authentication",
    )
    cert_file: Path = Field(
        default=Path("certs/server/server.crt"),
        description="Path to server certificate file",
    )
    key_file: Path = Field(
        default=Path("certs/server/server.key"),
        description="Path to server private key file",
    )
    ca_cert_file: Path = Field(
        default=Path("certs/ca/ca.crt"),
        description="Path to CA certificate for client verification",
    )
    verify_mode: str = Field(
        default="CERT_REQUIRED",
        description="Client cert verification: CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED",
    )

    @field_validator("verify_mode")
    @classmethod
    def validate_verify_mode(cls, v: str) -> str:
        """Validate verify_mode is a valid SSL option."""
        valid_modes = {"CERT_NONE", "CERT_OPTIONAL", "CERT_REQUIRED"}
        if v not in valid_modes:
            raise ValueError(f"verify_mode must be one of {valid_modes}")
        return v

    def validate_files_exist(self) -> None:
        """Validate that all required certificate files exist.

        Raises:
            FileNotFoundError: If any required file is missing
        """
        if not self.enabled:
            return

        missing_files = []
        if not self.cert_file.exists():
            missing_files.append(f"Server certificate: {self.cert_file}")
        if not self.key_file.exists():
            missing_files.append(f"Server key: {self.key_file}")
        if not self.ca_cert_file.exists():
            missing_files.append(f"CA certificate: {self.ca_cert_file}")

        if missing_files:
            raise FileNotFoundError(
                "mTLS certificate files not found:\n  - " + "\n  - ".join(missing_files)
            )


def create_ssl_context(config: MTLSConfig) -> Optional[ssl.SSLContext]:
    """Create SSL context for mTLS server.

    Creates an SSL context configured for mutual TLS authentication.
    The server will require clients to present a valid certificate
    signed by the configured CA.

    Args:
        config: mTLS configuration

    Returns:
        ssl.SSLContext configured for mTLS, or None if mTLS is disabled

    Raises:
        FileNotFoundError: If certificate files are missing
        ssl.SSLError: If certificate configuration fails

    Security Notes:
        - TLS 1.2 minimum version enforced
        - Only strong cipher suites allowed
        - Client certificate verification enabled by default
    """
    if not config.enabled:
        return None

    # Validate files exist before creating context
    config.validate_files_exist()

    # Create SSL context for server-side TLS
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Set minimum TLS version (TLS 1.2+)
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Load server certificate and private key
    context.load_cert_chain(
        certfile=str(config.cert_file),
        keyfile=str(config.key_file),
    )

    # Load CA certificate for client verification
    context.load_verify_locations(cafile=str(config.ca_cert_file))

    # Configure client certificate verification mode
    verify_modes = {
        "CERT_NONE": ssl.CERT_NONE,
        "CERT_OPTIONAL": ssl.CERT_OPTIONAL,
        "CERT_REQUIRED": ssl.CERT_REQUIRED,
    }
    context.verify_mode = verify_modes[config.verify_mode]

    # Configure strong cipher suites (OWASP recommendations)
    # Prefer ECDHE for forward secrecy, AESGCM for AEAD
    context.set_ciphers("ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20:!aNULL:!MD5:!DSS:!RC4")

    return context


def extract_client_cn(peer_cert: Optional[dict]) -> Optional[str]:
    """Extract Common Name (CN) from client certificate.

    The CN should contain the vehicle_id for correlation with JWT tokens.
    This enables cross-validation between mTLS identity and JWT subject.

    Args:
        peer_cert: Certificate dictionary from ssl.getpeercert()

    Returns:
        Common Name from client certificate, or None if not available

    Example:
        >>> cert = ssl_socket.getpeercert()
        >>> vehicle_id = extract_client_cn(cert)
        >>> # vehicle_id = "vehicle-001" or "550e8400-e29b-..."
    """
    if not peer_cert:
        return None

    # Certificate subject is a tuple of RDNs (Relative Distinguished Names)
    # Each RDN is a tuple of (attribute_type, value)
    # Format: (('commonName', 'vehicle-001'),)
    subject = peer_cert.get("subject", ())

    for rdn in subject:
        for attr_type, value in rdn:
            if attr_type == "commonName":
                return value

    return None


def extract_client_cert_info(peer_cert: Optional[dict]) -> dict:
    """Extract detailed information from client certificate.

    Useful for logging and debugging (without exposing sensitive data).

    Args:
        peer_cert: Certificate dictionary from ssl.getpeercert()

    Returns:
        Dictionary with certificate information:
            - cn: Common Name (vehicle_id)
            - issuer: Certificate issuer CN
            - not_before: Validity start date
            - not_after: Validity end date
            - serial: Certificate serial number
    """
    if not peer_cert:
        return {}

    info = {}

    # Extract CN from subject
    cn = extract_client_cn(peer_cert)
    if cn:
        info["cn"] = cn

    # Extract issuer CN
    issuer = peer_cert.get("issuer", ())
    for rdn in issuer:
        for attr_type, value in rdn:
            if attr_type == "commonName":
                info["issuer"] = value
                break

    # Validity dates
    if "notBefore" in peer_cert:
        info["not_before"] = peer_cert["notBefore"]
    if "notAfter" in peer_cert:
        info["not_after"] = peer_cert["notAfter"]

    # Serial number (as hex string)
    if "serialNumber" in peer_cert:
        info["serial"] = peer_cert["serialNumber"]

    return info
