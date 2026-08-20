"""Password hashing (bcrypt), JWT access tokens, opaque refresh tokens.

* Access tokens: short-lived signed JWTs carrying only ``sub`` (user UUID) —
  never roles or school ids. Everything else is resolved server-side per request.
* Refresh tokens: opaque, single-use, stored as SHA-256 in the DB.
* The first two password reset steps issue DB-backed hashed tokens.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..config import settings


# --- Passwords --------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


# --- Access tokens (JWT) ----------------------------------------------------
def create_access_token(user_id: str, expires_minutes: int | None = None) -> str:
    """Short-lived signed JWT. Claims: sub (user id), iat, exp. No tenant claims."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.access_token_minutes
    )
    payload = {"sub": str(user_id), "iat": now, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Returns the user id (sub) or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def create_portal_token(
    student_id: str, school_id: str, expires_minutes: int = 30
) -> str:
    """Short-lived JWT proving 'this student may read their own published
    results at this school'. Carries ``scope=portal`` in addition to ``sub``
    and ``school`` so the public report endpoint can independently authorize."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": student_id,
        "school": school_id,
        "scope": "portal",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_portal_token(token: str) -> dict | None:
    """Returns the portal claims dict, or None if invalid/expired/wrong scope."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
    if payload.get("scope") != "portal":
        return None
    return payload


# --- Opaque hashed tokens ----------------------------------------------------
def generate_opaque_token() -> str:
    """Random URL-safe token (refresh / reset / verify)."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Deterministic hash used for DB storage; constant-time compare on lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "create_portal_token",
    "decode_portal_token",
    "generate_opaque_token",
    "hash_token",
    "tokens_equal",
    "utcnow",
]