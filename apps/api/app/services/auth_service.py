"""Authentication: registration of a school + founding admin, login, logout,
refresh rotation, password reset. Also the membership listing used by `/auth/me`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..core import security
from ..core.errors import (
    ERR_ACCOUNT_DISABLED,
    ERR_ACCOUNT_LOCKED,
    ERR_AUTH_FAILED,
    ERR_NOT_FOUND,
    ERR_TOKEN_EXPIRED,
    ERR_TOKEN_REUSED,
    APIError,
    ValidationError,
)
from ..models import (
    ImpersonationSession,
    PasswordResetToken,
    RefreshToken,
    Role,
    School,
    SchoolMembership,
    User,
)
from .tenancy_service import create_school


@dataclass
class AuthResult:
    user: User
    access_token: str
    refresh_token: str
    refresh_token_id: uuid.UUID


def _issue_tokens(
    db: Session, user: User, *, device: str | None, ip: str | None
) -> AuthResult:
    """Create an access JWT and a new hashed refresh session (not yet committed)."""
    access_token = security.create_access_token(str(user.id))
    raw = security.generate_opaque_token()
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=security.hash_token(raw),
        device_label=device,
        ip=ip,
        expires_at=security.utcnow() + timedelta(days=settings.refresh_token_days),
    )
    db.add(refresh)
    db.flush()
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=raw,
        refresh_token_id=refresh.id,
    )


def _super_admin_role(db: Session, school_id: uuid.UUID) -> Role:
    role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == "super_admin")
    )
    if role is None:
        raise APIError(500, "ERR_PROVISIONING", "Super admin role not provisioned")
    return role


def register_school(
    db: Session,
    *,
    school_name: str,
    school_type: str,
    admin_email: str,
    admin_full_name: str,
    password: str,
    device: str | None = None,
    ip: str | None = None,
) -> AuthResult:
    """Create the school tenant + global admin user + membership, then log in."""
    email = admin_email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise ValidationError(
            "An account with this email already exists",
            {"email": "already registered"},
        )
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")

    user = User(
        email=email,
        password_hash=security.hash_password(password),
        full_name=admin_full_name,
    )
    db.add(user)
    db.flush()

    school = create_school(db, name=school_name, school_type=school_type)
    role = _super_admin_role(db, school.id)
    db.add(
        SchoolMembership(
            user_id=user.id, school_id=school.id, role_id=role.id
        )
    )
    db.flush()
    # committed by the router (single commit point per request)
    return _issue_tokens(db, user, device=device, ip=ip)


def login(
    db: Session,
    *,
    email: str,
    password: str,
    device: str | None = None,
    ip: str | None = None,
) -> AuthResult:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not security.verify_password(password, user.password_hash):
        raise APIError(401, ERR_AUTH_FAILED, "Invalid email or password")
    if user.status == "disabled":
        raise APIError(403, ERR_ACCOUNT_DISABLED, "Account disabled")
    if user.status == "locked":
        raise APIError(403, ERR_ACCOUNT_LOCKED, "Account locked")
    result = _issue_tokens(db, user, device=device, ip=ip)
    _log_auth(db, user, "login", ip=ip, details="Platform login" if user.is_superadmin else "School login")
    # committed by the router (single commit point per request)
    return result


def _log_auth(db: Session, user: User, action: str, *, ip: str | None, details: str) -> None:
    """Append to the platform audit trail. Never raises — auditing must not
    take down a login."""
    try:
        from ..models import AuditLog

        db.add(
            AuditLog(
                user_id=user.id,
                action=action,
                entity_type="user",
                entity_id=str(user.id),
                ip=ip,
                details=details,
            )
        )
    except Exception:  # pragma: no cover
        import logging

        logging.getLogger(__name__).exception("Failed to write auth audit log")


def logout(db: Session, refresh_token_raw: str | None) -> None:
    if not refresh_token_raw:
        return
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == security.hash_token(refresh_token_raw),
            RefreshToken.revoked_at.is_(None),
        )
    )
    if token is not None:
        token.revoked_at = security.utcnow()
        # committed by the router (single commit point per request)


def refresh_session(
    db: Session, refresh_token_raw: str, *, device: str | None, ip: str | None
) -> AuthResult:
    """Rotate the refresh token: revoke the presented one and issue a new pair.

    Presenting an already-revoked token is treated as possible theft: the whole
    family of that user's sessions is revoked.
    """
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == security.hash_token(refresh_token_raw)
        )
    )
    if token is None:
        raise APIError(401, ERR_TOKEN_EXPIRED, "Session not found")
    if token.revoked_at is not None:
        # Reuse = possible theft. This revocation MUST persist even though we
        # raise afterwards (normally an exception rolls the request back).
        db.execute(
            RefreshToken.__table__.update()
            .where(RefreshToken.user_id == token.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=security.utcnow())
        )
        db.commit()
        raise APIError(401, ERR_TOKEN_REUSED, "Session reuse detected — please log in again")
    if token.expires_at <= security.utcnow():
        raise APIError(401, ERR_TOKEN_EXPIRED, "Session expired")

    token.revoked_at = security.utcnow()
    db.flush()
    user = db.get(User, token.user_id)
    if user is None:
        raise APIError(401, ERR_TOKEN_EXPIRED, "Account not found")
    result = _issue_tokens(db, user, device=device, ip=ip)
    # committed by the router (single commit point per request)
    return result


def request_password_reset(db: Session, email: str) -> str | None:
    """Create a reset token. Returns the raw token in dev mode, else None.

    The response to the client is identical whether or not the email exists —
    we never reveal account existence.
    """
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        return None
    raw = security.generate_opaque_token()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=security.hash_token(raw),
        expires_at=security.utcnow() + timedelta(hours=1),
    )
    db.add(reset)
    # committed by the router (single commit point per request)
    return raw


def confirm_password_reset(db: Session, token_raw: str, new_password: str) -> None:
    if len(new_password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    reset = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == security.hash_token(token_raw)
        )
    )
    if (
        reset is None
        or reset.consumed_at is not None
        or reset.expires_at <= security.utcnow()
    ):
        raise APIError(400, ERR_TOKEN_EXPIRED, "Reset token invalid or expired")
    user = db.get(User, reset.user_id)
    if user is None:
        raise APIError(400, ERR_NOT_FOUND, "Account not found")
    user.password_hash = security.hash_password(new_password)
    reset.consumed_at = security.utcnow()
    # A reset means the old password may be compromised — drop every session.
    _revoke_sessions_except(db, user.id, keep_hash=None)
    _log_auth(db, user, "password_reset", ip=None, details="Password reset via token")
    # committed by the router (single commit point per request)


def change_password(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
    current_refresh_raw: str | None,
) -> None:
    """Change the signed-in user's password. Revokes every other session."""
    if len(new_password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if not security.verify_password(current_password, user.password_hash):
        raise APIError(401, ERR_AUTH_FAILED, "Current password is incorrect")
    user.password_hash = security.hash_password(new_password)
    _revoke_sessions_except(db, user.id, keep_hash=current_refresh_raw)
    _log_auth(db, user, "change_password", ip=None, details="Password changed")
    # committed by the router (single commit point per request)


def change_email(
    db: Session,
    user: User,
    *,
    current_password: str,
    new_email: str,
    current_refresh_raw: str | None,
) -> None:
    """Change the signed-in user's email. Revokes every other session."""
    email = new_email.strip().lower()
    if email == user.email:
        raise ValidationError("New email is the same as your current email")
    existing = db.scalar(select(User).where(User.email == email, User.id != user.id))
    if existing is not None:
        raise ValidationError("An account with this email already exists", {"email": "already in use"})
    if not security.verify_password(current_password, user.password_hash):
        raise APIError(401, ERR_AUTH_FAILED, "Current password is incorrect")
    user.email = email
    _revoke_sessions_except(db, user.id, keep_hash=current_refresh_raw)
    _log_auth(db, user, "change_email", ip=None, details=f"Email changed to {email}")
    # committed by the router (single commit point per request)


def _revoke_sessions_except(
    db: Session, user_id: uuid.UUID, *, keep_hash: str | None
) -> None:
    """Revoke all refresh sessions for a user except the one currently in use."""
    query = (
        RefreshToken.__table__.update()
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    )
    if keep_hash:
        query = query.where(RefreshToken.token_hash != security.hash_token(keep_hash))
    db.execute(query.values(revoked_at=security.utcnow()))


# --- Impersonation (support 'view as school admin') -------------------------

def enter_impersonation(
    db: Session,
    *,
    token: str,
    platform_user: User,
    ip: str | None,
) -> dict:
    """Validate a one-time impersonation token and activate the session.

    The caller (a platform admin, enforced by the router) receives the identity
    of the school admin the session was created for; the router then sets the
    impersonation cookie so subsequent requests resolve to that admin.
    """
    session = db.scalar(
        select(ImpersonationSession).where(
            ImpersonationSession.token_hash == security.hash_token(token)
        )
    )
    if session is None or session.ended_at is not None or session.expires_at <= security.utcnow():
        raise APIError(400, ERR_TOKEN_EXPIRED, "Impersonation token is invalid or expired")
    if session.platform_user_id != platform_user.id:
        raise APIError(403, ERR_AUTH_FAILED, "This session belongs to another platform admin")
    impersonated = db.get(User, session.impersonated_user_id)
    school = db.get(School, session.school_id)
    if impersonated is None or school is None:
        raise APIError(404, ERR_NOT_FOUND, "Impersonation target no longer exists")
    return {
        "token": token,
        "user_id": str(impersonated.id),
        "full_name": impersonated.full_name,
        "email": impersonated.email,
        "school_id": str(school.id),
        "school_name": school.name,
    }


def exit_impersonation(
    db: Session,
    *,
    token: str | None,
    platform_user: User,
    ip: str | None,
) -> dict:
    """End the impersonation session tied to ``token`` (from the cookie).

    Idempotent: no session / already ended / expired are all fine — the caller's
    cookie is cleared by the router regardless so they are never locked out.
    """
    if token:
        session = db.scalar(
            select(ImpersonationSession).where(
                ImpersonationSession.token_hash == security.hash_token(token)
            )
        )
        if session is not None and session.ended_at is None:
            session.ended_at = security.utcnow()
    from ..models import AuditLog

    db.add(
        AuditLog(
            user_id=platform_user.id,
            action="exit",
            entity_type="impersonation",
            ip=ip,
            details="Impersonation session ended",
        )
    )
    return {"ok": True}


# --- /auth/me ----------------------------------------------------------------
def user_memberships(db: Session, user_id: uuid.UUID) -> list[dict]:
    """All schools the user belongs to, with role + permission codes per school."""
    from .rbac_service import permissions_for_role

    rows = (
        db.execute(
            select(SchoolMembership, School, Role)
            .join(School, School.id == SchoolMembership.school_id)
            .outerjoin(Role, Role.id == SchoolMembership.role_id)
            .where(SchoolMembership.user_id == user_id)
            .order_by(School.name)
        )
        .all()
    )
    out: list[dict] = []
    for membership, school, role in rows:
        perms: list[str] = []
        if role is not None:
            perms = permissions_for_role(db, role.id)
        out.append(
            {
                "membership_id": str(membership.id),
                "school_id": str(school.id),
                "school_name": school.name,
                "school_slug": school.slug,
                "status": membership.status,  # plain VARCHAR column (see models/identity.py)
                "role": {"code": role.code, "name": role.name} if role else None,
                "permissions": perms,
                "ai_enabled": bool((school.settings or {}).get("ai_enabled", False)),
                "suspended": bool((school.settings or {}).get("suspended", False)),
            }
        )
    return out