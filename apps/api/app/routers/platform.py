"""Lumo platform administration: the global admin's view across all schools.

Every route requires a platform admin (``User.is_superadmin``) — no school
context. This is where Lumo sees every registered school, turns the premium
(AI) plan on/off after a school subscribes, disables a school outright, creates
school admin accounts, and reviews every teacher account on the platform.
"""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import DbSession, require_platform_admin
from ..schemas.platform import (
    SchoolAdminCreate,
    SchoolAdminCreated,
    SchoolAdminOut,
    SchoolAiUpdate,
    SchoolSuspendedUpdate,
    TeacherOut,
)
from ..services import platform_service

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/schools", response_model=list[SchoolAdminOut])
def list_all_schools(
    db: DbSession,
    _admin=Depends(require_platform_admin),
):
    """Every registered school with usage counts, premium + suspension status."""
    return [SchoolAdminOut(**row) for row in platform_service.list_schools(db)]


@router.patch("/schools/{school_id}/ai", response_model=SchoolAdminOut)
def toggle_school_ai(
    school_id: uuid.UUID,
    payload: SchoolAiUpdate,
    db: DbSession,
    _admin=Depends(require_platform_admin),
):
    """Enable or disable the premium AI plan for one school."""
    school = platform_service.set_school_ai(db, school_id, payload.enabled)
    db.commit()
    row = next(
        (r for r in platform_service.list_schools(db) if r["id"] == str(school.id)),
        None,
    )
    return SchoolAdminOut(**row)


@router.patch("/schools/{school_id}/status", response_model=SchoolAdminOut)
def set_school_status(
    school_id: uuid.UUID,
    payload: SchoolSuspendedUpdate,
    db: DbSession,
    _admin=Depends(require_platform_admin),
):
    """Disable or re-enable a school completely."""
    school = platform_service.set_school_suspended(db, school_id, payload.suspended)
    db.commit()
    row = next(
        (r for r in platform_service.list_schools(db) if r["id"] == str(school.id)),
        None,
    )
    return SchoolAdminOut(**row)


@router.post("/schools/{school_id}/admins", response_model=SchoolAdminCreated, status_code=201)
def create_school_admin(
    school_id: uuid.UUID,
    payload: SchoolAdminCreate,
    db: DbSession,
    _admin=Depends(require_platform_admin),
):
    """Create a school admin (super_admin) for a registered school."""
    created = platform_service.create_school_admin(
        db,
        school_id,
        full_name=payload.full_name.strip(),
        email=payload.email.strip().lower(),
        password=payload.password,
    )
    db.commit()
    return SchoolAdminCreated(**created)


@router.get("/teachers", response_model=list[TeacherOut])
def list_all_teachers(
    db: DbSession,
    _admin=Depends(require_platform_admin),
):
    """Every teacher/leader account across all registered schools."""
    return [TeacherOut(**row) for row in platform_service.list_teachers(db)]