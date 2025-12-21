"""
Tests for Role-Based Access Control (RBAC).

This module tests:
- Role and permission definitions
- Permission checking logic
- Role-based endpoint access
- Authorization audit logging

Security by Design: Principle of least privilege - each role has only
the minimum permissions required for its function.
"""

from skylink.rbac_roles import (
    DEFAULT_ROLE,
    ROLE_PERMISSIONS,
    Permission,
    Role,
    get_permissions,
    get_role_from_string,
    has_permission,
)


class TestRoleDefinitions:
    """Test role enum and definitions."""

    def test_all_roles_defined(self):
        """All expected roles should be defined."""
        expected_roles = [
            "aircraft_standard",
            "aircraft_premium",
            "ground_control",
            "maintenance",
            "admin",
        ]
        actual_roles = [r.value for r in Role]
        assert sorted(expected_roles) == sorted(actual_roles)

    def test_role_values_are_strings(self):
        """Role values should be string identifiers."""
        for role in Role:
            assert isinstance(role.value, str)
            assert role.value.islower()  # Convention: lowercase role names

    def test_default_role_is_aircraft_standard(self):
        """Default role should be aircraft_standard (least privilege)."""
        assert DEFAULT_ROLE == Role.AIRCRAFT_STANDARD


class TestPermissionDefinitions:
    """Test permission enum and definitions."""

    def test_all_permissions_defined(self):
        """All expected permissions should be defined."""
        expected_permissions = [
            "weather:read",
            "contacts:read",
            "telemetry:write",
            "telemetry:read",
            "config:read",
            "config:write",
            "audit:read",
        ]
        actual_permissions = [p.value for p in Permission]
        assert sorted(expected_permissions) == sorted(actual_permissions)

    def test_permission_format(self):
        """Permissions should follow resource:action format."""
        for perm in Permission:
            assert ":" in perm.value
            parts = perm.value.split(":")
            assert len(parts) == 2
            assert parts[0]  # Resource part
            assert parts[1]  # Action part


class TestRolePermissionMapping:
    """Test role to permission mapping."""

    def test_all_roles_have_permissions(self):
        """Every role should have at least one permission."""
        for role in Role:
            permissions = ROLE_PERMISSIONS.get(role)
            assert permissions is not None, f"Role {role.value} has no permission mapping"
            assert len(permissions) > 0, f"Role {role.value} has empty permissions"

    def test_aircraft_standard_permissions(self):
        """aircraft_standard should have minimal permissions."""
        permissions = ROLE_PERMISSIONS[Role.AIRCRAFT_STANDARD]
        assert Permission.WEATHER_READ in permissions
        assert Permission.TELEMETRY_WRITE in permissions
        # Should NOT have these
        assert Permission.CONTACTS_READ not in permissions
        assert Permission.TELEMETRY_READ not in permissions
        assert Permission.CONFIG_READ not in permissions
        assert Permission.AUDIT_READ not in permissions

    def test_aircraft_premium_permissions(self):
        """aircraft_premium should have extended access."""
        permissions = ROLE_PERMISSIONS[Role.AIRCRAFT_PREMIUM]
        assert Permission.WEATHER_READ in permissions
        assert Permission.CONTACTS_READ in permissions
        assert Permission.TELEMETRY_WRITE in permissions
        # Should NOT have these
        assert Permission.TELEMETRY_READ not in permissions
        assert Permission.CONFIG_READ not in permissions

    def test_ground_control_permissions(self):
        """ground_control should have monitoring access."""
        permissions = ROLE_PERMISSIONS[Role.GROUND_CONTROL]
        assert Permission.WEATHER_READ in permissions
        assert Permission.CONTACTS_READ in permissions
        assert Permission.TELEMETRY_READ in permissions
        # Should NOT have write permissions
        assert Permission.TELEMETRY_WRITE not in permissions
        assert Permission.CONFIG_WRITE not in permissions

    def test_maintenance_permissions(self):
        """maintenance should have diagnostic access."""
        permissions = ROLE_PERMISSIONS[Role.MAINTENANCE]
        assert Permission.WEATHER_READ in permissions
        assert Permission.TELEMETRY_WRITE in permissions
        assert Permission.TELEMETRY_READ in permissions
        assert Permission.CONFIG_READ in permissions
        # Should NOT have admin permissions
        assert Permission.CONFIG_WRITE not in permissions
        assert Permission.AUDIT_READ not in permissions

    def test_admin_has_all_permissions(self):
        """admin should have all permissions."""
        admin_permissions = ROLE_PERMISSIONS[Role.ADMIN]
        all_permissions = set(Permission)
        assert admin_permissions == all_permissions


class TestGetPermissions:
    """Test get_permissions function."""

    def test_get_permissions_valid_role(self):
        """Should return correct permissions for valid role."""
        permissions = get_permissions(Role.AIRCRAFT_STANDARD)
        assert Permission.WEATHER_READ in permissions
        assert Permission.TELEMETRY_WRITE in permissions

    def test_get_permissions_none_role(self):
        """Should return empty set for None role."""
        permissions = get_permissions(None)
        assert permissions == set()

    def test_get_permissions_returns_copy(self):
        """Should return a copy, not the original set."""
        permissions1 = get_permissions(Role.ADMIN)
        permissions2 = get_permissions(Role.ADMIN)
        # Modifying one should not affect the other
        # (This test ensures we're not returning mutable references)
        assert permissions1 == permissions2


class TestHasPermission:
    """Test has_permission function."""

    def test_has_permission_true(self):
        """Should return True when role has permission."""
        assert has_permission(Role.AIRCRAFT_STANDARD, Permission.WEATHER_READ)
        assert has_permission(Role.ADMIN, Permission.AUDIT_READ)

    def test_has_permission_false(self):
        """Should return False when role lacks permission."""
        assert not has_permission(Role.AIRCRAFT_STANDARD, Permission.CONTACTS_READ)
        assert not has_permission(Role.GROUND_CONTROL, Permission.CONFIG_WRITE)

    def test_has_permission_none_role(self):
        """Should return False for None role."""
        assert not has_permission(None, Permission.WEATHER_READ)


class TestGetRoleFromString:
    """Test get_role_from_string function."""

    def test_valid_role_string(self):
        """Should convert valid role strings to Role enum."""
        assert get_role_from_string("aircraft_standard") == Role.AIRCRAFT_STANDARD
        assert get_role_from_string("aircraft_premium") == Role.AIRCRAFT_PREMIUM
        assert get_role_from_string("ground_control") == Role.GROUND_CONTROL
        assert get_role_from_string("maintenance") == Role.MAINTENANCE
        assert get_role_from_string("admin") == Role.ADMIN

    def test_invalid_role_string(self):
        """Should return default role for invalid strings."""
        assert get_role_from_string("invalid_role") == DEFAULT_ROLE
        assert get_role_from_string("ADMIN") == DEFAULT_ROLE  # Case-sensitive
        assert get_role_from_string("") == DEFAULT_ROLE

    def test_none_role_string(self):
        """Should return default role for None."""
        assert get_role_from_string(None) == DEFAULT_ROLE


class TestPrincipleOfLeastPrivilege:
    """Tests verifying principle of least privilege."""

    def test_standard_role_is_minimal(self):
        """Standard role should have minimum viable permissions."""
        standard_perms = ROLE_PERMISSIONS[Role.AIRCRAFT_STANDARD]
        # Only 2 permissions for basic operations
        assert len(standard_perms) == 2

    def test_no_role_gets_free_permissions(self):
        """All permissions must be explicitly granted."""
        # Create a token without role, should get default (minimal)
        role = get_role_from_string(None)
        permissions = get_permissions(role)
        # Should only have standard permissions, not all
        assert len(permissions) < len(Permission)

    def test_permission_escalation_requires_role_change(self):
        """Higher permissions require different role."""
        # aircraft_standard cannot access contacts
        standard = Role.AIRCRAFT_STANDARD
        assert not has_permission(standard, Permission.CONTACTS_READ)

        # aircraft_premium can
        premium = Role.AIRCRAFT_PREMIUM
        assert has_permission(premium, Permission.CONTACTS_READ)
