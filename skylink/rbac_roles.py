"""
Role and permission definitions for SkyLink RBAC.

This module defines the role-based access control model:
- Roles: aircraft_standard, aircraft_premium, ground_control, maintenance, admin
- Permissions: weather:read, contacts:read, telemetry:write, etc.

Security by Design: Principle of least privilege - each role has only
the minimum permissions required for its function.
"""

from enum import Enum
from typing import Set


class Permission(str, Enum):
    """Available permissions in the system."""

    # Weather access
    WEATHER_READ = "weather:read"

    # Contacts access (Google People API)
    CONTACTS_READ = "contacts:read"

    # Telemetry access
    TELEMETRY_WRITE = "telemetry:write"
    TELEMETRY_READ = "telemetry:read"

    # Configuration access
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"

    # Audit log access
    AUDIT_READ = "audit:read"


class Role(str, Enum):
    """Available roles in the system."""

    # Default aircraft role - basic operations
    AIRCRAFT_STANDARD = "aircraft_standard"

    # Premium aircraft - extended access (contacts, etc.)
    AIRCRAFT_PREMIUM = "aircraft_premium"

    # Ground control station - monitoring operations
    GROUND_CONTROL = "ground_control"

    # Maintenance personnel - diagnostic access
    MAINTENANCE = "maintenance"

    # System administrator - full access
    ADMIN = "admin"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.AIRCRAFT_STANDARD: {
        Permission.WEATHER_READ,
        Permission.TELEMETRY_WRITE,
    },
    Role.AIRCRAFT_PREMIUM: {
        Permission.WEATHER_READ,
        Permission.CONTACTS_READ,
        Permission.TELEMETRY_WRITE,
    },
    Role.GROUND_CONTROL: {
        Permission.WEATHER_READ,
        Permission.CONTACTS_READ,
        Permission.TELEMETRY_READ,
    },
    Role.MAINTENANCE: {
        Permission.WEATHER_READ,
        Permission.TELEMETRY_WRITE,
        Permission.TELEMETRY_READ,
        Permission.CONFIG_READ,
    },
    Role.ADMIN: {
        Permission.WEATHER_READ,
        Permission.CONTACTS_READ,
        Permission.TELEMETRY_WRITE,
        Permission.TELEMETRY_READ,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.AUDIT_READ,
    },
}

# Default role for tokens without explicit role
DEFAULT_ROLE = Role.AIRCRAFT_STANDARD


def get_permissions(role: Role | None) -> Set[Permission]:
    """
    Get permissions for a role.

    Args:
        role: The role to get permissions for

    Returns:
        Set of permissions for the role, or empty set if role is None/unknown
    """
    if role is None:
        return set()
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: Role | None, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.

    Args:
        role: The role to check
        permission: The permission to check for

    Returns:
        True if the role has the permission, False otherwise
    """
    return permission in get_permissions(role)


def get_role_from_string(role_str: str | None) -> Role:
    """
    Convert a string to a Role enum, with fallback to default.

    Args:
        role_str: The role string from JWT

    Returns:
        Role enum, or DEFAULT_ROLE if invalid/missing
    """
    if role_str is None:
        return DEFAULT_ROLE
    try:
        return Role(role_str)
    except ValueError:
        return DEFAULT_ROLE
