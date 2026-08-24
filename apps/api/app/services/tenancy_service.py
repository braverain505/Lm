"""Tenancy: school provisioning at onboarding + the seeded permission catalog.

The two idempotent entry points here matter:
  * ``ensure_permission_catalog`` — global catalog, seeded once.
  * ``provision_school_roles`` — copies the global role templates into the new
    school's own role rows. From then on the school owns its roles and can
    customize them without affecting any other tenant.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Campus, Permission, Role, RolePermission
from ..core.errors import ConflictError
from ..core.permissions import PERMISSION_CATALOG, ROLE_TEMPLATES
from ..models.school import School


def ensure_permissions(db: Session) -> None:
    """Idempotently insert the global permission catalog."""
    existing = set(db.scalars(select(Permission.code)).all())
    for code, domain, description in PERMISSION_CATALOG:
        if code not in existing:
            db.add(Permission(code=code, domain=domain, description=description))
    db.flush()


@dataclass
class ProvisionedRole:
    role: Role
    code: str


def provision_school_roles(db: Session, school_id) -> list[Role]:
    """Create the school's default roles from the templates (idempotent per code)."""
    ensure_permissions(db)
    existing = {
        code for code, in db.execute(
            select(Role.code).where(Role.school_id == school_id)
        )
    }
    created: list[Role] = []
    for code, template in ROLE_TEMPLATES.items():
        if code in existing:
            continue
        role = Role(
            school_id=school_id,
            code=code,
            name=template["name"],
            is_system=template.get("is_system", False),
            description=f"Default {template['name']} role",
        )
        db.add(role)
        db.flush()

        perm_codes = set(template.get("permissions") or [])
        if perm_codes:
            perms = db.scalars(
                select(Permission).where(Permission.code.in_(perm_codes))
            ).all()
            for p in perms:
                db.add(RolePermission(role_id=role.id, permission_id=p.id))
        created.append(role)
    db.flush()
    return created


def sync_role_templates(db: Session, school_id) -> None:
    """Reconcile an existing school's *system* roles with the current templates.

    Both directions are reconciled:
      * adding a permission to a template (e.g. ``results.comment``) only
        affects schools created after the change; this closes the gap for orgs
        provisioned earlier;
      * removing a permission from a template (e.g. finance codes from the
        admin templates) strips it from existing schools' system roles too.

    Non-system roles are the school's own — never touched. Idempotent.
    """
    ensure_permissions(db)
    perm_by_code = {
        p.code: p for p in db.scalars(select(Permission)).all()
    }
    for code, template in ROLE_TEMPLATES.items():
        role = db.scalar(
            select(Role).where(
                Role.school_id == school_id, Role.code == code, Role.is_system.is_(True)
            )
        )
        if role is None:
            role = Role(
                school_id=school_id,
                code=code,
                name=template["name"],
                is_system=True,
                description=f"Default {template['name']} role",
            )
            db.add(role)
            db.flush()
        want = set(template.get("permissions") or [])
        have = set(
            db.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            ).all()
        )
        for code_name in want - have:
            p = perm_by_code.get(code_name)
            if p is None:
                continue
            db.add(RolePermission(role_id=role.id, permission_id=p.id))
        stale = have - want
        if stale:
            perm_ids = [
                perm_by_code[c].id for c in stale if c in perm_by_code
            ]
            if perm_ids:
                db.execute(
                    delete(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id.in_(perm_ids),
                    )
                )
    db.flush()


def sync_all_school_role_templates(db: Session) -> None:
    """Reconcile every tenant's system roles with the current templates.

    Called once at startup so policy changes in the templates (e.g. moving
    finance permissions off the admin roles) reach schools provisioned earlier.
    """
    for (school_id,) in db.execute(select(School.id)).all():
        sync_role_templates(db, school_id)


def ensure_default_campus(db: Session, school: School) -> Campus:
    campus = db.scalar(
        select(Campus).where(Campus.school_id == school.id, Campus.is_primary.is_(True))
    )
    if campus is None:
        campus = Campus(
            school_id=school.id, name="Main Campus", is_primary=True
        )
        db.add(campus)
        db.flush()
    return campus


def slugify(name: str) -> str:
    import re
    import unicodedata

    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("utf-8")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "school"


def create_school(
    db: Session,
    *,
    name: str,
    school_type: str,
    slug: str | None = None,
    established_year: int | None = None,
    website: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    state: str | None = None,
    country: str = "NG",
) -> School:
    """Create a school tenant, its default campus, and its role set."""
    target = slug or slugify(name)
    if db.scalar(select(School).where(School.slug == target)):
        raise ConflictError("A school with this name already exists")

    school = School(
        name=name,
        slug=target,
        school_type=school_type,
        established_year=established_year,
        website=website,
        email=email,
        phone=phone,
        address=address,
        state=state,
        country=country,
        settings={},
    )
    db.add(school)
    db.flush()
    provision_school_roles(db, school.id)
    ensure_default_campus(db, school)
    # Every tenant starts with the default SaaS subscription (14-day trial);
    # the Super Admin upgrades it after payment. Idempotent + never destructive.
    from .subscription_service import ensure_default_plans, provision_subscription

    ensure_default_plans(db)
    provision_subscription(db, school.id)
    db.flush()
    return school