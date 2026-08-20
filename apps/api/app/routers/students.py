"""Student management: profiles, enrollments, guardians."""
import uuid

from fastapi import APIRouter, Depends, Query

from ..core.deps import ActiveSchool, DbSession, require_permission
from ..core.permissions import (
    STUDENTS_CREATE,
    STUDENTS_DELETE,
    STUDENTS_EDIT,
    STUDENTS_ENROLL,
    STUDENTS_VIEW,
)
from ..schemas.people import (
    ClassChangeRequest,
    EnrollmentCreate,
    EnrollmentOut,
    GuardianCreate,
    GuardianLink,
    GuardianOut,
    PromotionRequest,
    StudentCreate,
    StudentOut,
    StudentUpdate,
)
from ..schemas.portal import PinSet, PinSetOut
from ..services import people_service, portal_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
def list_students(
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_VIEW)),
    arm_id: uuid.UUID | None = None,
    q: str | None = None,
):
    rows = people_service.list_students(db, ctx.school.id, arm_id=arm_id, q=q)
    return [StudentOut.model_validate(s) for s in rows]


@router.post("", response_model=StudentOut, status_code=201)
def create_student(
    payload: StudentCreate,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_CREATE)),
):
    student = people_service.create_student(
        db, ctx.school.id,
        admission_no=payload.admission_no,
        first_name=payload.first_name,
        last_name=payload.last_name,
        middle_name=payload.middle_name,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        state=payload.state,
        lga=payload.lga,
        blood_group=payload.blood_group,
        medical_notes=payload.medical_notes,
        previous_school=payload.previous_school,
        address=payload.address,
        photo_url=payload.photo_url,
    )
    db.commit()
    return StudentOut.model_validate(student)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_VIEW)),
):
    student = people_service.get_student(db, ctx.school.id, student_id)
    return StudentOut.model_validate(student)


@router.patch("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdate,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_EDIT)),
):
    student = people_service.update_student(
        db, ctx.school.id, student_id, **payload.model_dump(exclude_unset=True)
    )
    db.commit()
    return StudentOut.model_validate(student)


@router.delete("/{student_id}", status_code=204)
def delete_student(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_DELETE)),
):
    people_service.delete_student(db, ctx.school.id, student_id)
    db.commit()


# --- Enrollments ---------------------------------------------------------------
@router.post("/enrollments", response_model=EnrollmentOut, status_code=201)
def enroll(
    payload: EnrollmentCreate,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_ENROLL)),
):
    enrollment = people_service.enroll_student(
        db, ctx.school.id,
        student_id=payload.student_id, arm_id=payload.arm_id,
        session_id=payload.session_id, enrolled_at=payload.enrolled_at,
    )
    db.commit()
    return EnrollmentOut.model_validate(enrollment)


@router.get("/arms/{arm_id}/enrollments", response_model=list[EnrollmentOut])
def list_arm_enrollments(
    arm_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_VIEW)),
):
    return [
        EnrollmentOut.model_validate(e)
        for e in people_service.list_enrollments(db, ctx.school.id, arm_id)
    ]


@router.get("/{student_id}/enrollments", response_model=list[dict])
def student_enrollment_history(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_VIEW)),
):
    """This student's enrollment history across sessions (arm names + status)."""
    return people_service.enrollment_summary(db, ctx.school.id, student_id)


@router.post("/promote", response_model=dict)
def promote_students(
    payload: PromotionRequest,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_ENROLL)),
):
    """Advance currently-enrolled students to the next session, following a
    per-source-class → target-class mapping supplied by the admin. Optionally
    restrict to specific students."""
    result = people_service.promote_students(
        db, ctx.school.id,
        from_session_id=payload.from_session_id,
        to_session_id=payload.to_session_id,
        target_arms=[p.model_dump() for p in payload.target_arms],
        student_ids=payload.student_ids,
    )
    db.commit()
    return result


@router.post("/{student_id}/class-change", response_model=dict)
def change_class(
    student_id: uuid.UUID,
    payload: ClassChangeRequest,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_ENROLL)),
):
    """Move a student to a specific class the admin picks within the given
    session (manual promote/demote target)."""
    result = people_service.change_student_class(
        db, ctx.school.id,
        student_id=student_id,
        session_id=payload.session_id,
        target_arm_id=payload.target_arm_id,
    )
    db.commit()
    return result


# --- Guardians ------------------------------------------------------------------
@router.get("/{student_id}/guardians", response_model=list[GuardianOut])
def list_guardians(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_VIEW)),
):
    links = people_service.list_guardians(db, ctx.school.id, student_id)
    return [GuardianOut.model_validate(link["guardian"]) for link in links]


@router.post("/{student_id}/guardians", response_model=GuardianOut, status_code=201)
def add_guardian(
    student_id: uuid.UUID,
    payload: GuardianCreate,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_EDIT)),
):
    guardian = people_service.create_guardian(
        db, ctx.school.id,
        full_name=payload.full_name, phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        address=payload.address, occupation=payload.occupation,
    )
    people_service.link_guardian(
        db, ctx.school.id,
        student_id=student_id, guardian_id=guardian.id,
        relationship="guardian", is_primary=False,
    )
    db.commit()
    return GuardianOut.model_validate(guardian)

@router.put("/{student_id}/pin", response_model=PinSetOut)
def set_pin(
    student_id: uuid.UUID,
    payload: PinSet,
    db: DbSession,
    ctx=Depends(require_permission(STUDENTS_EDIT)),
):
    """Issue or rotate a student's result-portal PIN (4–6 digits)."""
    portal_service.set_student_pin(
        db,
        school_id=ctx.school.id,
        student_id=student_id,
        actor_id=ctx.user.id,
        pin=payload.pin,
    )
    db.commit()
    return PinSetOut(student_id=student_id)
