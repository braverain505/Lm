"""Academic structure: sessions, terms, classes, subjects, offerings,
assignments. Every function is school-scoped by the ``school_id`` argument.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    AcademicSession,
    ClassArm,
    Staff,
    Subject,
    SubjectAssignment,
    SubjectOffering,
    Term,
)
from ..models.enums import SessionStatus, TermStatus


# --- Sessions ---------------------------------------------------------------
def list_sessions(db: Session, school_id: uuid.UUID) -> list[AcademicSession]:
    return list(
        db.scalars(
            select(AcademicSession)
            .where(AcademicSession.school_id == school_id)
            .order_by(AcademicSession.name.desc())
        )
    )


def get_session(db: Session, school_id: uuid.UUID, session_id: uuid.UUID) -> AcademicSession:
    s = db.get(AcademicSession, session_id)
    if s is None or s.school_id != school_id:
        raise NotFoundError("Academic session not found")
    return s


def create_session(
    db: Session,
    school_id: uuid.UUID,
    *,
    name: str,
    start_date: date | None,
    end_date: date | None,
    is_current: bool = False,
    grade_scale_id: uuid.UUID | None = None,
) -> AcademicSession:
    if db.scalar(
        select(AcademicSession.id).where(
            AcademicSession.school_id == school_id, AcademicSession.name == name
        )
    ):
        raise ConflictError("A session with this name already exists")
    session = AcademicSession(
        school_id=school_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
        grade_scale_id=grade_scale_id,
    )
    db.add(session)
    if is_current:
        _clear_current_session(db, school_id)
        session.is_current = True
    db.flush()
    return session


def update_session(
    db: Session,
    school_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    is_current: bool | None = None,
    status: str | None = None,
) -> AcademicSession:
    session = get_session(db, school_id, session_id)
    if name is not None:
        session.name = name
    if start_date is not None:
        session.start_date = start_date
    if end_date is not None:
        session.end_date = end_date
    if status is not None:
        session.status = status
    if is_current is not None:
        if is_current and not session.is_current:
            _clear_current_session(db, school_id)
            session.is_current = True
        elif not is_current:
            session.is_current = False
    db.flush()
    return session


def _clear_current_session(db: Session, school_id: uuid.UUID) -> None:
    db.query(AcademicSession).filter(
        AcademicSession.school_id == school_id, AcademicSession.is_current.is_(True)
    ).update({AcademicSession.is_current: False})


def activate_session(db: Session, school_id: uuid.UUID, session_id: uuid.UUID) -> AcademicSession:
    """Admin activates a session: marks it open + current, retiring any other
    current session. All result work happens inside activated sessions."""
    session = get_session(db, school_id, session_id)
    _clear_current_session(db, school_id)
    session.is_current = True
    session.status = SessionStatus.OPEN.value
    db.flush()
    return session


def activate_term(db: Session, school_id: uuid.UUID, term_id: uuid.UUID) -> Term:
    """Admin activates a term inside its (activated) session: marks it open +
    current, retiring any other current term in the same session."""
    term = get_term(db, school_id, term_id)
    get_session(db, school_id, term.academic_session_id)  # validate ownership
    db.query(Term).filter(
        Term.academic_session_id == term.academic_session_id,
        Term.is_current.is_(True),
    ).update({Term.is_current: False})
    term.is_current = True
    term.status = TermStatus.OPEN.value
    db.flush()
    return term


def require_active_term(db: Session, school_id: uuid.UUID, term_id: uuid.UUID) -> None:
    """Guard used by every results write: a term only accepts work when both it
    and its session have been activated by an admin (status = open)."""
    term = get_term(db, school_id, term_id)
    session = db.get(AcademicSession, term.academic_session_id)
    if session is None or session.status != SessionStatus.OPEN.value:
        raise ValidationError(
            "This term's academic session is not activated — an admin must activate the session before any results work"
        )
    if term.status != TermStatus.OPEN.value:
        raise ValidationError(
            f"The {term.name} term is not activated — an admin must activate it before any results work"
        )


# --- Terms -------------------------------------------------------------------
def list_terms(db: Session, school_id: uuid.UUID, session_id: uuid.UUID) -> list[Term]:
    return list(
        db.scalars(
            select(Term)
            .where(Term.school_id == school_id, Term.academic_session_id == session_id)
            .order_by(Term.term_no)
        )
    )


def get_term(db: Session, school_id: uuid.UUID, term_id: uuid.UUID) -> Term:
    t = db.get(Term, term_id)
    if t is None or t.school_id != school_id:
        raise NotFoundError("Term not found")
    return t


def create_term(
    db: Session,
    school_id: uuid.UUID,
    *,
    session_id: uuid.UUID,
    term_no: int,
    name: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Term:
    get_session(db, school_id, session_id)  # validate ownership
    if db.scalar(
        select(Term.id).where(
            Term.academic_session_id == session_id, Term.term_no == term_no
        )
    ):
        raise ConflictError(f"Term {term_no} already exists for this session")
    term = Term(
        school_id=school_id,
        academic_session_id=session_id,
        term_no=term_no,
        name=name,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(term)
    db.flush()
    return term


def current_term(db: Session, school_id: uuid.UUID) -> Term | None:
    return db.scalar(
        select(Term)
        .join(AcademicSession, AcademicSession.id == Term.academic_session_id)
        .where(
            AcademicSession.school_id == school_id,
            AcademicSession.is_current.is_(True),
            Term.is_current.is_(True),
        )
    )


# --- Classes ------------------------------------------------------------------
def list_arms(db: Session, school_id: uuid.UUID, session_id: uuid.UUID) -> list[ClassArm]:
    return list(
        db.scalars(
            select(ClassArm)
            .where(ClassArm.school_id == school_id, ClassArm.academic_session_id == session_id)
            .order_by(ClassArm.full_name)
        )
    )


def get_arm(db: Session, school_id: uuid.UUID, arm_id: uuid.UUID) -> ClassArm:
    arm = db.get(ClassArm, arm_id)
    if arm is None or arm.school_id != school_id:
        raise NotFoundError("Class not found")
    return arm


def create_arm(
    db: Session,
    school_id: uuid.UUID,
    *,
    session_id: uuid.UUID,
    name: str,
    campus_id: uuid.UUID | None = None,
    class_teacher_id: uuid.UUID | None = None,
) -> ClassArm:
    """Create a class for a session. ``name`` is the class label itself
    (e.g. 'JSS 1A') — there are no separate class levels."""
    get_session(db, school_id, session_id)
    if db.scalar(
        select(ClassArm.id).where(
            ClassArm.school_id == school_id,
            ClassArm.academic_session_id == session_id,
            ClassArm.name == name,
        )
    ):
        raise ConflictError(f"{name} already exists this session")
    arm = ClassArm(
        school_id=school_id,
        academic_session_id=session_id,
        campus_id=campus_id,
        name=name,
        full_name=name,
        class_teacher_id=class_teacher_id,
    )
    db.add(arm)
    db.flush()
    return arm


# --- Subjects ------------------------------------------------------------------
def list_subjects(db: Session, school_id: uuid.UUID) -> list[Subject]:
    return list(
        db.scalars(
            select(Subject).where(Subject.school_id == school_id).order_by(Subject.name)
        )
    )


def get_subject(db: Session, school_id: uuid.UUID, subject_id: uuid.UUID) -> Subject:
    s = db.get(Subject, subject_id)
    if s is None or s.school_id != school_id:
        raise NotFoundError("Subject not found")
    return s


def create_subject(
    db: Session, school_id: uuid.UUID, *, name: str, code: str
) -> Subject:
    if db.scalar(
        select(Subject.id).where(Subject.school_id == school_id, Subject.code == code)
    ):
        raise ConflictError(f"A subject with code '{code}' already exists")
    subject = Subject(school_id=school_id, name=name, code=code)
    db.add(subject)
    db.flush()
    return subject


def update_subject(
    db: Session,
    school_id: uuid.UUID,
    subject_id: uuid.UUID,
    *,
    name: str | None,
    code: str | None,
    is_core: bool | None,
    is_active: bool | None,
) -> Subject:
    subject = get_subject(db, school_id, subject_id)
    if code is not None and code != subject.code:
        if db.scalar(
            select(Subject.id).where(
                Subject.school_id == school_id, Subject.code == code
            )
        ):
            raise ConflictError(f"A subject with code '{code}' already exists")
        subject.code = code
    if name is not None:
        subject.name = name
    if is_core is not None:
        subject.is_core = is_core
    if is_active is not None:
        subject.is_active = is_active
    db.flush()
    return subject


# --- Offerings ----------------------------------------------------------------
def list_offerings(
    db: Session, school_id: uuid.UUID, arm_id: uuid.UUID
) -> list[SubjectOffering]:
    get_arm(db, school_id, arm_id)
    return list(
        db.scalars(
            select(SubjectOffering)
            .where(SubjectOffering.school_id == school_id)
            .where(SubjectOffering.class_arm_id == arm_id)
            .order_by(SubjectOffering.sort_order, SubjectOffering.subject_id)
        )
    )


def add_offering(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, subject_id: uuid.UUID
) -> SubjectOffering:
    get_arm(db, school_id, arm_id)
    get_subject(db, school_id, subject_id)
    if db.scalar(
        select(SubjectOffering.id).where(
            SubjectOffering.class_arm_id == arm_id,
            SubjectOffering.subject_id == subject_id,
        )
    ):
        raise ConflictError("Subject already offered at this class")
    offering = SubjectOffering(
        school_id=school_id, class_arm_id=arm_id, subject_id=subject_id
    )
    db.add(offering)
    db.flush()
    return offering


def remove_offering(db: Session, school_id: uuid.UUID, offering_id: uuid.UUID) -> None:
    offering = db.get(SubjectOffering, offering_id)
    if offering is None or offering.school_id != school_id:
        raise NotFoundError("Offering not found")
    db.delete(offering)
    db.flush()


# --- Assignments ----------------------------------------------------------------
def list_assignments(
    db: Session, school_id: uuid.UUID, arm_id: uuid.UUID
) -> list[SubjectAssignment]:
    get_arm(db, school_id, arm_id)
    return list(
        db.scalars(
            select(SubjectAssignment)
            .where(SubjectAssignment.school_id == school_id)
            .where(SubjectAssignment.class_arm_id == arm_id)
            .order_by(SubjectAssignment.subject_id)
        )
    )


def assign_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    teacher_id: uuid.UUID,
) -> SubjectAssignment:
    get_arm(db, school_id, arm_id)
    get_subject(db, school_id, subject_id)
    teacher = db.get(Staff, teacher_id)
    if teacher is None or teacher.school_id != school_id:
        raise NotFoundError("Teacher not found")
    existing = db.scalar(
        select(SubjectAssignment).where(
            SubjectAssignment.class_arm_id == arm_id,
            SubjectAssignment.subject_id == subject_id,
        )
    )
    if existing is not None:
        existing.teacher_id = teacher_id  # re-teach = swap teacher on the same row
        db.flush()
        return existing
    assignment = SubjectAssignment(
        school_id=school_id,
        class_arm_id=arm_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
    )
    db.add(assignment)
    db.flush()
    return assignment


def unassign_subject(db: Session, school_id: uuid.UUID, assignment_id: uuid.UUID) -> None:
    assignment = db.get(SubjectAssignment, assignment_id)
    if assignment is None or assignment.school_id != school_id:
        raise NotFoundError("Assignment not found")
    db.delete(assignment)
    db.flush()


def list_my_assignments(
    db: Session, school_id: uuid.UUID, user_id: uuid.UUID
) -> list[dict]:
    """The arms x subjects a logged-in user is the assigned teacher for.

    Drives the teacher's 'My subjects' workload page. Supervisors (who can act
    on any arm/subject via the results workflow permissions) don't need this —
    it is genuinely only meaningful for teachers.
    """
    staff = db.scalar(
        select(Staff).where(
            Staff.school_id == school_id,
            Staff.user_id == user_id,
            Staff.is_deleted.is_(False),
        )
    )
    if staff is None:
        return []
    return list_staff_assignments(db, school_id, staff.id)


def list_staff_assignments(
    db: Session, school_id: uuid.UUID, staff_id: uuid.UUID
) -> list[dict]:
    """The arms x subjects a specific staff member teaches (admin view)."""
    staff = db.get(Staff, staff_id)
    if staff is None or staff.school_id != school_id:
        return []
    assignments = list(
        db.scalars(
            select(SubjectAssignment)
            .where(
                SubjectAssignment.school_id == school_id,
                SubjectAssignment.teacher_id == staff.id,
            )
            .order_by(SubjectAssignment.class_arm_id, SubjectAssignment.subject_id)
        )
    )
    rows = []
    for a in assignments:
        arm = db.get(ClassArm, a.class_arm_id)
        subject = db.get(Subject, a.subject_id)
        rows.append(
            {
                "arm_id": str(a.class_arm_id),
                "arm_name": arm.full_name if arm else "",
                "subject_id": str(a.subject_id),
                "subject_name": subject.name if subject else "",
                "assignment_id": str(a.id),
            }
        )
    return rows