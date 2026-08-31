"""Academic structure endpoints (sessions, terms, arms, subjects, offerings,
assignments). Views need academics.view; writes need academics.manage."""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import ActiveSchool, DbSession, require_permission
from ..core.permissions import ACADEMICS_MANAGE, ACADEMICS_VIEW
from ..schemas.academics import (
    ArmCreate,
    ArmOut,
    AssignmentCreate,
    AssignmentOut,
    OfferingCreate,
    OfferingOut,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
    TermCreate,
    TermOut,
)
from ..services import academics_service

router = APIRouter(prefix="/academics", tags=["academics"])


# --- Sessions ---------------------------------------------------------------
@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    return [
        SessionOut.model_validate(s)
        for s in academics_service.list_sessions(db, ctx.school.id)
    ]


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_VIEW)),
):
    return SessionOut.model_validate(
        academics_service.get_session(db, ctx.school.id, session_id)
    )


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(
    payload: SessionCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    session = academics_service.create_session(
        db, ctx.school.id, name=payload.name,
        start_date=payload.start_date, end_date=payload.end_date,
        is_current=payload.is_current,
    )
    db.commit()
    return SessionOut.model_validate(session)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(
    session_id: uuid.UUID,
    payload: SessionUpdate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    session = academics_service.update_session(
        db, ctx.school.id, session_id,
        name=payload.name, start_date=payload.start_date,
        end_date=payload.end_date, is_current=payload.is_current,
        status=payload.status,
    )
    db.commit()
    return SessionOut.model_validate(session)


@router.post("/sessions/{session_id}/activate", response_model=SessionOut)
def activate_session(
    session_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    """Admin activates a session (open + current). Until then, no results work
    is allowed inside its terms."""
    session = academics_service.activate_session(db, ctx.school.id, session_id)
    db.commit()
    return SessionOut.model_validate(session)


# --- Terms --------------------------------------------------------------------
@router.get("/sessions/{session_id}/terms", response_model=list[TermOut])
def list_terms(session_id: uuid.UUID, db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    return [
        TermOut.model_validate(t)
        for t in academics_service.list_terms(db, ctx.school.id, session_id)
    ]


@router.post("/terms", response_model=TermOut, status_code=201)
def create_term(
    payload: TermCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    term = academics_service.create_term(
        db, ctx.school.id,
        session_id=payload.session_id, term_no=payload.term_no,
        name=payload.name, start_date=payload.start_date, end_date=payload.end_date,
    )
    db.commit()
    return TermOut.model_validate(term)


@router.post("/terms/{term_id}/activate", response_model=TermOut)
def activate_term(
    term_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    """Admin activates a term (open + current) inside its session. Until then,
    no results work is allowed for this term."""
    term = academics_service.activate_term(db, ctx.school.id, term_id)
    db.commit()
    return TermOut.model_validate(term)


@router.post("/terms/{term_id}/close", response_model=TermOut)
def close_term(
    term_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    """Admin closes a term. Once closed, no result mutations are allowed.
    Results entered in the term remain viewable but immutable."""
    term = academics_service.close_term(db, ctx.school.id, term_id)
    db.commit()
    return TermOut.model_validate(term)


# --- Class arms ----------------------------------------------------------------
@router.get("/sessions/{session_id}/arms", response_model=list[ArmOut])
def list_arms(session_id: uuid.UUID, db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    return [
        ArmOut.model_validate(a)
        for a in academics_service.list_arms(db, ctx.school.id, session_id)
    ]


@router.post("/arms", response_model=ArmOut, status_code=201)
def create_arm(
    payload: ArmCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    arm = academics_service.create_arm(
        db, ctx.school.id,
        session_id=payload.session_id,
        name=payload.name, campus_id=payload.campus_id,
    )
    db.commit()
    return ArmOut.model_validate(arm)


# --- Subjects -------------------------------------------------------------------
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    return [
        SubjectOut.model_validate(s)
        for s in academics_service.list_subjects(db, ctx.school.id)
    ]


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(
    payload: SubjectCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    subject = academics_service.create_subject(
        db, ctx.school.id, name=payload.name, code=payload.code
    )
    db.commit()
    return SubjectOut.model_validate(subject)


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: uuid.UUID,
    payload: SubjectUpdate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    """Update a subject — including the ``is_core`` flag that drives the
    "Best in Core Subject" award on report cards."""
    subject = academics_service.update_subject(
        db,
        ctx.school.id,
        subject_id,
        name=payload.name,
        code=payload.code,
        is_core=payload.is_core,
        is_active=payload.is_active,
    )
    db.commit()
    return SubjectOut.model_validate(subject)


# --- Offerings -------------------------------------------------------------------
@router.get("/arms/{arm_id}/offerings", response_model=list[OfferingOut])
def list_offerings(arm_id: uuid.UUID, db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    return [
        OfferingOut.model_validate(o)
        for o in academics_service.list_offerings(db, ctx.school.id, arm_id)
    ]


@router.post("/offerings", response_model=OfferingOut, status_code=201)
def add_offering(
    payload: OfferingCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    offering = academics_service.add_offering(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
    )
    db.commit()
    return OfferingOut.model_validate(offering)


@router.delete("/offerings/{offering_id}", status_code=204)
def remove_offering(offering_id: uuid.UUID, db: DbSession, ctx=Depends(require_permission(ACADEMICS_MANAGE))):
    academics_service.remove_offering(db, ctx.school.id, offering_id)
    db.commit()


# --- Assignments -----------------------------------------------------------------
@router.get("/arms/{arm_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(arm_id: uuid.UUID, db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    return [
        AssignmentOut.model_validate(a)
        for a in academics_service.list_assignments(db, ctx.school.id, arm_id)
    ]


@router.get("/my-assignments", response_model=list[dict])
def my_assignments(db: DbSession, ctx=Depends(require_permission(ACADEMICS_VIEW))):
    """The arms x subjects this user is the assigned teacher for."""
    return academics_service.list_my_assignments(db, ctx.school.id, ctx.user.id)


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(
    payload: AssignmentCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    assignment = academics_service.assign_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        teacher_id=payload.teacher_id,
    )
    db.commit()
    return AssignmentOut.model_validate(assignment)


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: uuid.UUID, db: DbSession, ctx=Depends(require_permission(ACADEMICS_MANAGE))):
    academics_service.unassign_subject(db, ctx.school.id, assignment_id)
    db.commit()