"""Lumo platform administration: schools registry, premium toggles, suspension,
and cross-tenant account management.

The platform admin (a user with ``User.is_superadmin``) owns every tenant. This
service powers the admin dashboard: listing all registered schools, flipping the
premium (AI) add-on, disabling a school outright, creating school admin accounts,
and seeing every teacher across all tenants.
"""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.security import hash_password
from ..models import ClassArm, Role, School, SchoolMembership, Student, User


def school_ai_enabled(school: School) -> bool:
    """Whether the school has subscribed to the premium AI plan.

    Stored in the school's ``settings`` JSONB bucket (feature toggles), defaulting
    to disabled until the Lumo admin flips it on after payment.
    """
    return bool((school.settings or {}).get("ai_enabled", False))


def school_suspended(school: School) -> bool:
    """Whether the Lumo admin has disabled this school completely."""
    return bool((school.settings or {}).get("suspended", False))


def _require_school(db: Session, school_id: uuid.UUID) -> School:
    school = db.get(School, school_id)
    if school is None:
        from ..core.errors import NotFoundError

        raise NotFoundError("School not found")
    return school


def list_schools(db: Session) -> list[dict]:
    """Every registered school with usage counts + premium/suspension status."""
    student_counts = dict(
        db.execute(select(Student.school_id, func.count(Student.id)).group_by(Student.school_id)).all()
    )
    arm_counts = dict(
        db.execute(select(ClassArm.school_id, func.count(ClassArm.id)).group_by(ClassArm.school_id)).all()
    )
    schools = db.scalars(select(School).order_by(School.created_at.desc())).all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "short_name": s.short_name,
            "slug": s.slug,
            "school_type": s.school_type,
            "email": s.email,
            "phone": s.phone,
            "created_at": s.created_at,
            "students": student_counts.get(s.id, 0),
            "class_arms": arm_counts.get(s.id, 0),
            "ai_enabled": school_ai_enabled(s),
            "suspended": school_suspended(s),
        }
        for s in schools
    ]


def set_school_ai(db: Session, school_id: uuid.UUID, enabled: bool) -> School:
    """Enable/disable the premium AI plan for a school (Lumo admin only)."""
    school = _require_school(db, school_id)
    settings = dict(school.settings or {})
    settings["ai_enabled"] = bool(enabled)
    school.settings = settings
    db.flush()
    return school


def set_school_suspended(db: Session, school_id: uuid.UUID, suspended: bool) -> School:
    """Disable/enable a school completely (Lumo admin only). While suspended,
    every tenant-scoped API call for that school returns 403 ERR_SCHOOL_SUSPENDED."""
    school = _require_school(db, school_id)
    settings = dict(school.settings or {})
    settings["suspended"] = bool(suspended)
    school.settings = settings
    db.flush()
    return school


def create_school_admin(
    db: Session, school_id: uuid.UUID, full_name: str, email: str, password: str | None
) -> dict:
    """Create a school admin (super_admin role) for a registered school. If no
    password is supplied, a random one is generated and returned once so the Lumo
    admin can hand it to the school owner."""
    school = _require_school(db, school_id)
    from ..core.errors import ConflictError, ValidationError

    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("A user with that email already exists")

    role = db.scalar(select(Role).where(Role.school_id == school.id, Role.code == "super_admin"))
    if role is None:
        raise ValidationError("This school has no super_admin role template", {"school_id": str(school.id)})

    generated = password is None
    if password is None:
        password = secrets.token_urlsafe(9)
    user = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school.id, role_id=role.id))
    db.flush()
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "school_id": str(school.id),
        "school_name": school.name,
        "role_code": "super_admin",
        "password": password if generated else None,
    }


def list_teachers(db: Session) -> list[dict]:
    """Every teacher account across all registered schools.

    "Credentials" means the account identity Lumo can see for support/recovery —
    passwords are hashed and never exposed; use create/recovery flows instead.
    """
    rows = db.execute(
        select(User, School, Role.code)
        .join(SchoolMembership, SchoolMembership.user_id == User.id)
        .join(School, School.id == SchoolMembership.school_id)
        .join(Role, Role.id == SchoolMembership.role_id)
        .where(
            Role.code.in_(["super_admin", "director", "principal", "head_teacher", "teacher"]),
        )
        .order_by(School.name, User.full_name)
    ).all()
    return [
        {
            "school_id": str(school.id),
            "school_name": school.name,
            "user_id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role_code": role_code,
            "status": user.status,
            "created_at": user.created_at,
        }
        for user, school, role_code in rows
    ]