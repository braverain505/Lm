"""Staff (teachers + non-teaching) endpoints."""
import uuid

from fastapi import APIRouter, Depends, Query

from ..core.deps import ActiveSchool, DbSession, require_permission
from ..core.permissions import STAFF_CREATE, STAFF_EDIT, STAFF_VIEW, USERS_MANAGE
from ..schemas.people import (
    StaffAccountCreate,
    StaffAccountOut,
    StaffAccountUpdate,
    StaffCreate,
    StaffOut,
    StaffUpdate,
)
from ..services import academics_service, people_service

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=list[StaffOut])
def list_staff(
    db: DbSession,
    ctx=Depends(require_permission(STAFF_VIEW)),
    membership_type: str | None = Query(default=None),
):
    rows = people_service.list_staff(
        db, ctx.school.id, membership_type=membership_type
    )
    return people_service.serialize_staff_list(db, ctx.school.id, rows)


@router.post("", response_model=StaffOut, status_code=201)
def create_staff(
    payload: StaffCreate,
    db: DbSession,
    ctx=Depends(require_permission(STAFF_CREATE)),
):
    staff = people_service.create_staff(
        db, ctx.school.id,
        staff_no=payload.staff_no, full_name=payload.full_name,
        membership_type=payload.membership_type, gender=payload.gender,
        phone=payload.phone, email=str(payload.email) if payload.email else None,
        joined_date=payload.joined_date,
    )
    db.commit()
    return people_service.staff_to_out(db, ctx.school.id, staff)


@router.patch("/{staff_id}", response_model=StaffOut)
def update_staff(
    staff_id: uuid.UUID,
    payload: StaffUpdate,
    db: DbSession,
    ctx=Depends(require_permission(STAFF_EDIT)),
):
    staff = people_service.update_staff(
        db, ctx.school.id, staff_id,
        **payload.model_dump(exclude_unset=True),
    )
    db.commit()
    return people_service.staff_to_out(db, ctx.school.id, staff)


@router.post("/{staff_id}/account", response_model=StaffAccountOut, status_code=201)
def create_staff_account(
    staff_id: uuid.UUID,
    payload: StaffAccountCreate,
    db: DbSession,
    ctx=Depends(require_permission(USERS_MANAGE)),
):
    """Create a login account (email + password + role) for a staff member so
    they can sign in with their own credentials."""
    staff, role = people_service.create_staff_account(
        db, ctx.school.id, staff_id,
        email=str(payload.email), password=payload.password, role_id=payload.role_id,
    )
    db.commit()
    return StaffAccountOut(
        staff_id=staff.id,
        email=str(payload.email).strip().lower(),
        role_id=role.id,
        role_code=role.code,
        role_name=role.name,
    )


@router.patch("/{staff_id}/account", response_model=StaffAccountOut)
def update_staff_account(
    staff_id: uuid.UUID,
    payload: StaffAccountUpdate,
    db: DbSession,
    ctx=Depends(require_permission(USERS_MANAGE)),
):
    """Change a staff login: update email, reset password, or change role.

    Only the provided fields are changed; ``password`` may be left blank to
    keep the existing one."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        from ..core.errors import ValidationError

        raise ValidationError("Provide at least one field: email, password, or role_id")
    staff, role = people_service.update_staff_account(
        db, ctx.school.id, staff_id,
        email=str(payload.email) if payload.email is not None else None,
        password=payload.password,
        role_id=payload.role_id,
    )
    db.commit()
    return StaffAccountOut(
        staff_id=staff.id,
        email=str(staff.user.email).strip().lower() if staff.user else "",
        role_id=role.id,
        role_code=role.code,
        role_name=role.name,
    )


@router.delete("/{staff_id}", status_code=204)
def delete_staff(
    staff_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STAFF_EDIT)),
):
    """Soft-delete a staff member (unassigns subjects, revokes their login)."""
    people_service.delete_staff(db, ctx.school.id, staff_id)
    db.commit()


@router.get("/{staff_id}/assignments", response_model=list[dict])
def staff_assignments(
    staff_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STAFF_VIEW)),
):
    """The arms x subjects this staff member teaches (admin view)."""
    return academics_service.list_staff_assignments(db, ctx.school.id, staff_id)