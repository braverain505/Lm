"""RBAC: role CRUD, role-permission editing, and permission resolution."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import Permission, Role, RolePermission, SchoolMembership
from .tenancy_service import ensure_permissions


def list_roles(db: Session, school_id: uuid.UUID) -> list[Role]:
    return list(
        db.scalars(
            select(Role)
            .where(Role.school_id == school_id)
            .order_by(Role.is_system.desc(), Role.name)
        )
    )


def get_role(db: Session, school_id: uuid.UUID, role_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)
    if role is None or role.school_id != school_id:
        raise NotFoundError("Role not found")
    return role


def permissions_for_role(db: Session, role_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.code)
        )
    )


def create_role(
    db: Session, school_id: uuid.UUID, *, code: str, name: str, permissions: list[str]
) -> Role:
    if db.scalar(select(Role).where(Role.school_id == school_id, Role.code == code)):
        raise ConflictError(f"A role with code '{code}' already exists")
    _validate_codes(db, permissions)
    role = Role(
        school_id=school_id,
        code=code,
        name=name,
        is_system=False,
        description=f"Custom role {name}",
    )
    db.add(role)
    db.flush()
    _set_permissions(db, role, permissions)
    return role


def update_role(
    db: Session,
    school_id: uuid.UUID,
    role_id: uuid.UUID,
    *,
    name: str | None = None,
    permissions: list[str] | None = None,
) -> Role:
    role = get_role(db, school_id, role_id)
    if name is not None:
        role.name = name
    if permissions is not None:
        _validate_codes(db, permissions)
        _set_permissions(db, role, permissions)
    db.flush()
    return role


def delete_role(db: Session, school_id: uuid.UUID, role_id: uuid.UUID) -> None:
    role = get_role(db, school_id, role_id)
    if role.is_system:
        raise ValidationError("System default roles cannot be deleted")
    memberships = db.scalar(
        select(SchoolMembership.id).where(SchoolMembership.role_id == role_id).limit(1)
    )
    if memberships:
        raise ConflictError("Role is assigned to users and cannot be deleted")
    db.delete(role)
    db.flush()


def _set_permissions(db: Session, role: Role, codes: list[str]) -> None:
    db.execute(
        delete(RolePermission).where(RolePermission.role_id == role.id)
    )
    if codes:
        perms = db.scalars(
            select(Permission).where(Permission.code.in_(codes))
        ).all()
        db.add_all(
            RolePermission(role_id=role.id, permission_id=p.id) for p in perms
        )
    db.flush()


def _validate_codes(db: Session, codes: list[str]) -> None:
    ensure_permissions(db)
    known = set(db.scalars(select(Permission.code)).all())
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise ValidationError("Unknown permission code(s)", {"codes": unknown[:10]})


def list_permission_catalog(db: Session) -> list[Permission]:
    ensure_permissions(db)
    return list(db.scalars(select(Permission).order_by(Permission.domain, Permission.code)))