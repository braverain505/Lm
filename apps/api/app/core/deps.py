"""Request dependencies: identity, tenant resolution, and permission checks.

Authorization model:
  1. ``get_current_user`` resolves WHO you are (cookie or bearer JWT).
  2. ``get_school_context`` resolves WHICH school you're acting on from the
     ``X-School-Id`` header and loads your membership + permission set.
  3. ``require_permission(...)`` enforces a single permission code.

The JWT never carries tenant or role claims; everything is resolved server-side
on every request so role changes take effect immediately and cross-school access
is impossible by construction.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Annotated, Callable

from fastapi import Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ImpersonationSession, Permission, Role, RolePermission, School, SchoolMembership, User
from .database import get_db
from .errors import (
    ERR_ACCOUNT_DISABLED,
    ERR_ACCOUNT_LOCKED,
    ERR_IMPERSONATION_ACTIVE,
    ERR_MEMBERSHIP_SUSPENDED,
    ERR_UNAUTHENTICATED,
    APIError,
    NotMemberError,
    PermissionDeniedError,
    PremiumRequiredError,
)
from .permissions import ACCOUNTING_ROLES
from .security import decode_access_token, hash_token, utcnow

DbSession = Annotated[Session, Depends(get_db)]


@dataclass
class MembershipContext:
    user: User
    school: School
    membership: SchoolMembership
    role_code: str
    permission_codes: set[str] = field(default_factory=set)


def _unauth(detail: str) -> APIError:
    return APIError(401, ERR_UNAUTHENTICATED, detail)


def _active_impersonation(request: Request, db: Session) -> ImpersonationSession | None:
    """The currently-valid impersonation session for this request, if any.

    Impersonation rides on a separate httpOnly cookie holding the raw token
    (the DB stores its hash). When present and valid, the request resolves to
    the impersonated school admin instead of the platform admin.
    """
    raw = request.cookies.get(settings.impersonation_cookie)
    if not raw:
        return None
    session = db.scalar(
        select(ImpersonationSession).where(
            ImpersonationSession.token_hash == hash_token(raw)
        )
    )
    if session is None or session.ended_at is not None or session.expires_at <= utcnow():
        return None
    return session


def get_current_user(request: Request, db: DbSession) -> User:
    """Resolve identity from the session cookie or a Bearer token.

    Never trusts the token's claims beyond ``sub`` — the user row is reloaded
    every request so disabled/locked accounts are caught immediately.
    """
    token: str | None = None
    cookie = request.cookies.get(settings.cookie_name)
    if cookie:
        token = cookie
    if not token:
        auth: str | None = request.headers.get("Authorization")
        if auth and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise _unauth("Not authenticated")

    user_id = decode_access_token(token)
    if not user_id:
        raise _unauth("Invalid or expired session")

    user = db.get(User, uuid.UUID(user_id))
    if not user:
        raise _unauth("Account not found")
    if user.status == "disabled":
        raise APIError(403, ERR_ACCOUNT_DISABLED, "Account disabled")
    if user.status == "locked":
        raise APIError(403, ERR_ACCOUNT_LOCKED, "Account locked")
    session = _active_impersonation(request, db)
    if session is not None:
        impersonated = db.get(User, session.impersonated_user_id)
        if impersonated is not None and impersonated.status not in ("disabled", "locked"):
            return impersonated
    return user




def get_school_context(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
    x_school_id: Annotated[str | None, Header()] = None,
) -> MembershipContext:
    """Resolve the active school + membership + permissions for this request.

    Returns a neutral 404 when the user is not a member of the requested school
    (we deliberately don't reveal whether the school exists).
    """
    if not x_school_id:
        raise _unauth("Missing X-School-Id header")
    try:
        school_uuid = uuid.UUID(x_school_id)
    except ValueError:
        raise NotMemberError()

    # One round trip for membership + school + role + permission codes.
    #
    # This used to be four sequential queries (membership, school, role,
    # permission join). Every authenticated request pays this cost, and the
    # dashboard alone then makes ~30 more — so when the API and the database sit
    # in different regions (each query is a WAN hop) the four became the tax on
    # literally every screen. The permission codes ride along as a correlated
    # array so the caller still gets the same set without a second statement.
    permission_codes_sq = (
        select(func.array_agg(Permission.code))
        .select_from(RolePermission)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id == SchoolMembership.role_id)
        .correlate(SchoolMembership)
        .scalar_subquery()
    )

    row = db.execute(
        select(SchoolMembership, School, Role.code, permission_codes_sq)
        .join(School, School.id == SchoolMembership.school_id)
        .outerjoin(Role, Role.id == SchoolMembership.role_id)
        .where(
            SchoolMembership.user_id == user.id,
            SchoolMembership.school_id == school_uuid,
        )
    ).first()
    if row is None:
        raise NotMemberError()

    membership, school, role_code, permission_codes = row
    if membership.status == "suspended":
        raise APIError(403, ERR_MEMBERSHIP_SUSPENDED, "Membership suspended")

    if bool((school.settings or {}).get("suspended", False)):
        from .errors import SchoolSuspendedError

        raise SchoolSuspendedError()

    # ``array_agg`` is NULL when the role has no permissions at all.
    perms: set[str] = set(permission_codes or ())
    role_code = role_code or ""

    return MembershipContext(
        user=user,
        school=school,
        membership=membership,
        role_code=role_code,
        permission_codes=perms,
    )


# Alias for readability at call sites.
SchoolContext = MembershipContext


def require_permission(permission: str) -> Callable:
    """Dependency factory: ``require_permission("results.submit")`` -> a FastAPI
    dependency that resolves the school context and enforces the permission.

    Super admins bypass permission checks (they own the platform).
    """

    def checker(
        ctx: Annotated[MembershipContext, Depends(get_school_context)],
    ) -> MembershipContext:
        if permission not in ctx.permission_codes and not ctx.user.is_superadmin:
            raise PermissionDeniedError(
                f"You need the '{permission}' permission for this action"
            )
        return ctx

    return checker


def require_role(
    *role_codes: str,
    permission: str | None = None,
    message: str | None = None,
) -> Callable:
    """Dependency factory enforcing the caller's *school-scoped role code*.

    Permissions answer "what may you do"; this answers "who are you" — needed
    where a capability belongs to one office regardless of the permission set.
    The accounting ledger is the Accountant's alone, so a bursar handed the very
    same finance permissions still cannot post to the books.

    Roles are resolved from the membership of the school in ``X-School-Id``, so
    an accountant is the accountant of that one school only. Platform super
    admins bypass the check (they own the platform); while impersonating, the
    request resolves to the impersonated membership, so the bypass does not
    leak into a school.
    """
    allowed = frozenset(role_codes)

    def checker(
        ctx: Annotated[MembershipContext, Depends(get_school_context)],
    ) -> MembershipContext:
        # Platform super admins own the platform and bypass the role gate. While
        # impersonating, get_current_user resolves to the impersonated user
        # (is_superadmin=False), so the gate still applies inside the school.
        if ctx.user.is_superadmin:
            return ctx
        if ctx.role_code not in allowed:
            raise PermissionDeniedError(
                message or "Your school role does not grant access to this area"
            )
        if permission and permission not in ctx.permission_codes:
            raise PermissionDeniedError(
                f"You need the '{permission}' permission for this action"
            )
        return ctx

    return checker


def require_accountant(permission: str | None = None) -> Callable:
    """Accountant-only gate for the accounting desk (role code + permission).

    Both are checked: the role makes the desk the Accountant's own, and the
    permission lets the school still scope *which* accounting actions that
    accountant may take when it customises the role.
    """
    return require_role(
        *ACCOUNTING_ROLES,
        permission=permission,
        message="This is the Accountant's desk — only the school Accountant can do this.",
    )


AnyUser = Annotated[User, Depends(get_current_user)]
ActiveSchool = Annotated[MembershipContext, Depends(get_school_context)]


def require_platform_admin(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Platform-level access: only Clearis's own super admins (``is_superadmin``)
    may list/change tenant settings across schools. No school context is used —
    these routes are not scoped to a single tenant.

    While an impersonation session is active the caller is inside a school, so
    platform administration is explicitly blocked until they exit.
    """
    if request.cookies.get(settings.impersonation_cookie):
        raise APIError(
            403,
            ERR_IMPERSONATION_ACTIVE,
            "Platform administration is disabled while impersonating a school",
        )
    if not user.is_superadmin:
        raise PermissionDeniedError("Clearis platform admin access required")
    return user


def ensure_ai(
    ctx: Annotated[MembershipContext, Depends(get_school_context)],
) -> MembershipContext:
    """Premium gate for AI features. Unlike permissions (identity-based), this is
    a billing toggle on the school itself, so even the school owner is blocked
    until the Clearis admin enables the plan after payment."""
    if not bool((ctx.school.settings or {}).get("ai_enabled", False)):
        raise PremiumRequiredError()
    return ctx