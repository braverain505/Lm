"""School (tenant) profile, campuses, and lightweight dashboard overview."""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..core.deps import ActiveSchool, DbSession, require_permission
from ..core.errors import ConflictError
from ..core.permissions import CAMPUS_MANAGE, SCHOOL_MANAGE
from ..models import (
    AcademicSession,
    Campus,
    ClassArm,
    Staff,
    Student,
    Subject,
    Term,
)

router = APIRouter(prefix="/schools", tags=["schools"])


class SchoolOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    short_name: str | None
    slug: str
    school_type: str
    currency: str
    timezone: str
    email: str | None
    phone: str | None
    logo_url: str | None
    established_year: int | None
    website: str | None
    address: str | None
    state: str | None
    country: str


class CampusOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    is_primary: bool
    address: str | None


class CampusCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = None


class SchoolPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    short_name: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    currency: str | None = None
    logo_url: str | None = None


class Overview(BaseModel):
    students: int
    staff: int
    teachers: int
    classes: int
    subjects: int
    current_session: str | None
    terms: int


@router.get("/me", response_model=SchoolOut)
def school_me(ctx: ActiveSchool):
    return SchoolOut.model_validate(ctx.school)


@router.patch("/me")
def update_school(payload: SchoolPatch, db: DbSession, ctx=Depends(require_permission(SCHOOL_MANAGE))):
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(ctx.school, key, value)
    db.commit()
    return SchoolOut.model_validate(ctx.school)


@router.get("/me/campuses", response_model=list[CampusOut])
def list_campuses(ctx: ActiveSchool, db: DbSession):
    rows = db.scalars(
        select(Campus).where(Campus.school_id == ctx.school.id).order_by(Campus.name)
    ).all()
    return [CampusOut.model_validate(c) for c in rows]


@router.post("/me/campuses", response_model=CampusOut, status_code=201)
def create_campus(payload: CampusCreate, db: DbSession, ctx=Depends(require_permission(CAMPUS_MANAGE))):
    if db.scalar(
        select(Campus.id).where(
            Campus.school_id == ctx.school.id, Campus.name == payload.name
        )
    ):
        raise ConflictError("A campus with this name already exists")
    campus = Campus(school_id=ctx.school.id, name=payload.name, address=payload.address)
    db.add(campus)
    db.commit()
    return CampusOut.model_validate(campus)


@router.get("/me/overview", response_model=Overview)
def overview(ctx: ActiveSchool, db: DbSession):
    school_id = ctx.school.id
    students = db.scalar(
        select(func.count()).select_from(Student).where(
            Student.school_id == school_id, Student.is_deleted.is_(False)
        )
    )
    staff_all = db.scalar(
        select(func.count()).select_from(Staff).where(
            Staff.school_id == school_id, Staff.is_deleted.is_(False)
        )
    )
    teachers = db.scalar(
        select(func.count()).select_from(Staff).where(
            Staff.school_id == school_id,
            Staff.membership_type == "teaching",
            Staff.is_deleted.is_(False),
        )
    )
    classes = db.scalar(select(func.count()).select_from(ClassArm).where(ClassArm.school_id == school_id))
    subjects = db.scalar(select(func.count()).select_from(Subject).where(Subject.school_id == school_id))
    current = db.scalar(
        select(AcademicSession.name).where(
            AcademicSession.school_id == school_id, AcademicSession.is_current.is_(True)
        )
    )
    terms = db.scalar(select(func.count()).select_from(Term).where(Term.school_id == school_id))
    return Overview(
        students=students or 0,
        staff=staff_all or 0,
        teachers=teachers or 0,
        classes=classes or 0,
        subjects=subjects or 0,
        current_session=current,
        terms=terms or 0,
    )