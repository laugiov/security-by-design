"""
Role-Based Access Control (RBAC) for SkyLink.

This module provides FastAPI dependencies for permission and role checking.

Usage:
    from skylink.rbac import require_permission, require_role
    from skylink.rbac_roles import Permission, Role

    @router.get("/contacts")
    async def get_contacts(
        token: dict = Depends(require_permission(Permission.CONTACTS_READ))
    ):
        ...

Security by Design: Authorization decisions are enforced at the endpoint
level and all access attempts are logged for audit purposes.
"""

from typing import List

from fastapi import Depends, HTTPException, Request, status

from skylink.audit import audit_logger
from skylink.auth import verify_jwt
from skylink.rbac_roles import (
    Permission,
    Role,
    get_role_from_string,
    has_permission,
)


class AuthorizationError(Exception):
    """Authorization error raised when access is denied."""

    def __init__(self, message: str, required: str, actual: str):
        super().__init__(message)
        self.required = required
        self.actual = actual


def require_permission(*permissions: Permission):
    """
    FastAPI dependency to require specific permissions.

    Creates a dependency that verifies the JWT and checks that the
    token's role has all required permissions.

    Args:
        *permissions: One or more permissions required to access the endpoint

    Returns:
        FastAPI dependency function that returns the token if authorized

    Raises:
        HTTPException: 401 if not authenticated, 403 if not authorized

    Example:
        @router.get("/contacts")
        async def get_contacts(
            token: dict = Depends(require_permission(Permission.CONTACTS_READ))
        ):
            ...
    """

    async def permission_checker(request: Request, token: dict = Depends(verify_jwt)) -> dict:
        # Extract role from token
        role_str = token.get("role")
        role = get_role_from_string(role_str)

        # Get client info for audit
        client_ip = request.client.host if request.client else None
        trace_id = getattr(request.state, "trace_id", None)
        actor_id = token.get("sub")
        endpoint = str(request.url.path)

        # Check all required permissions
        missing_permissions = []
        for permission in permissions:
            if not has_permission(role, permission):
                missing_permissions.append(permission.value)

        if missing_permissions:
            # Log authorization failure
            audit_logger.log_authorization_failure(
                actor_id=actor_id,
                role=role.value,
                required_permission=missing_permissions[0],
                endpoint=endpoint,
                trace_id=trace_id,
                ip_address=client_ip,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {missing_permissions[0]} required",
            )

        return token

    return permission_checker


def require_role(*roles: Role):
    """
    FastAPI dependency to require specific roles.

    Creates a dependency that verifies the JWT and checks that the
    token's role is one of the allowed roles.

    Args:
        *roles: One or more roles allowed to access the endpoint

    Returns:
        FastAPI dependency function that returns the token if authorized

    Raises:
        HTTPException: 401 if not authenticated, 403 if not authorized

    Example:
        @router.get("/admin/config")
        async def get_config(
            token: dict = Depends(require_role(Role.ADMIN, Role.MAINTENANCE))
        ):
            ...
    """

    async def role_checker(request: Request, token: dict = Depends(verify_jwt)) -> dict:
        # Extract role from token
        role_str = token.get("role")
        role = get_role_from_string(role_str)

        # Get client info for audit
        client_ip = request.client.host if request.client else None
        trace_id = getattr(request.state, "trace_id", None)
        actor_id = token.get("sub")
        endpoint = str(request.url.path)

        if role not in roles:
            # Log authorization failure
            audit_logger.log_authorization_failure(
                actor_id=actor_id,
                role=role.value,
                required_roles=[r.value for r in roles],
                endpoint=endpoint,
                trace_id=trace_id,
                ip_address=client_ip,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Role not authorized for this resource",
            )

        return token

    return role_checker


def get_current_role(token: dict = Depends(verify_jwt)) -> Role:
    """
    FastAPI dependency to get the current user's role.

    Args:
        token: JWT token from verify_jwt dependency

    Returns:
        The user's Role enum value

    Example:
        @router.get("/profile")
        async def get_profile(role: Role = Depends(get_current_role)):
            return {"role": role.value}
    """
    role_str = token.get("role")
    return get_role_from_string(role_str)


def get_current_permissions(token: dict = Depends(verify_jwt)) -> List[str]:
    """
    FastAPI dependency to get the current user's permissions.

    Args:
        token: JWT token from verify_jwt dependency

    Returns:
        List of permission strings the user has

    Example:
        @router.get("/my-permissions")
        async def get_permissions(perms: List[str] = Depends(get_current_permissions)):
            return {"permissions": perms}
    """
    from skylink.rbac_roles import get_permissions

    role_str = token.get("role")
    role = get_role_from_string(role_str)
    return [p.value for p in get_permissions(role)]
