"""Result portal: per-student PINs and the public card-lookup helpers.

The portal is deliberately minimal and defensive:

* PINs unlock *published* results only — the report-card service already
  refuses anything not at the published stage.
* Every lookup failure (unknown school, unknown admission no, wrong PIN)
  answers the same generic ``NotFoundError`` so the endpoint can't be used
  to enumerate students or their PINs.
* PINs are stored hashed as SHA-256 of ``school_id:student_id:pin`` and
  replaced (never mutated) on rotation, with old rows kept for audit.
"""
import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..core.security import create_portal_token
from ..models import Result, School, Student, StudentEnrollment, StudentPin, Term
from ..models.enums import ResultStatus
from .people_service import get_student
from .results_service import report_card

PIN_MIN = 4
PIN_MAX = 6


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bad_credentials() -> NotFoundError:
    # One shape for every failure; never hint which field was wrong.
    return NotFoundError("Invalid portal credentials")


def _pin_hash(school_id: uuid.UUID, student_id: uuid.UUID, pin: str) -> str:
    return hashlib.sha256(
        f"{school_id}:{student_id}:{pin}".encode("utf-8")
    ).hexdigest()


def set_student_pin(
    db: Session,
    *,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    actor_id: uuid.UUID,
    pin: str,
) -> StudentPin:
    """Issue a PIN for a student. Digit-only, 4–6 chars; replaces the current
    live PIN (revoking it) so each student has exactly one live row."""
    if not (pin.isdigit() and PIN_MIN <= len(pin) <= PIN_MAX):
        raise ValidationError(f"PIN must be {PIN_MIN}-{PIN_MAX} digits")
    get_student(db, school_id, student_id)  # raises if tenant mismatch

    for live in db.scalars(
        select(StudentPin).where(
            StudentPin.school_id == school_id,
            StudentPin.student_id == student_id,
            StudentPin.revoked_at.is_(None),
        )
    ).all():
        live.revoked_at = _utcnow()

    row = StudentPin(
        school_id=school_id,
        student_id=student_id,
        pin_hash=_pin_hash(school_id, student_id, pin),
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def resolve_pin(
    db: Session, *, school_slug: str, admission_no: str, pin: str
) -> tuple[School, Student]:
    """Resolve a portal credential. Any failure raises the same generic 404;
    a successful check stamps ``last_used_at``."""
    school = db.scalar(select(School).where(School.slug == school_slug))
    if school is None:
        raise _bad_credentials()
    student = db.scalar(
        select(Student).where(
            Student.school_id == school.id,
            Student.admission_no == admission_no,
            Student.is_deleted.is_(False),
        )
    )
    if student is None:
        raise _bad_credentials()
    row = db.scalar(
        select(StudentPin)
        .where(
            StudentPin.school_id == school.id,
            StudentPin.student_id == student.id,
            StudentPin.revoked_at.is_(None),
        )
        .order_by(StudentPin.created_at.desc())
        .limit(1)
    )
    if row is None or not hmac.compare_digest(
        row.pin_hash, _pin_hash(school.id, student.id, pin)
    ):
        raise _bad_credentials()

    row.last_used_at = _utcnow()
    db.flush()
    return school, student


def portal_token(school: School, student: Student) -> str:
    return create_portal_token(str(student.id), str(school.id))


def latest_published_term_id(
    db: Session, *, school_id: uuid.UUID, student_id: uuid.UUID
) -> uuid.UUID:
    """The most recent term (current session first) in which this student has
    at least one published result. 404 when there is none yet."""
    session_ids = list(
        db.scalars(
            select(StudentEnrollment.academic_session_id).where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.student_id == student_id,
            )
        )
    )
    if not session_ids:
        raise _bad_credentials()
    terms = list(
        db.scalars(
            select(Term)
            .where(
                Term.school_id == school_id,
                Term.academic_session_id.in_(session_ids),
            )
            .order_by(Term.academic_session_id.desc(), Term.term_no.desc())
        )
    )
    for term in terms:
        has_published = db.scalar(
            select(Result.id).where(
                Result.school_id == school_id,
                Result.term_id == term.id,
                Result.status == ResultStatus.PUBLISHED.value,
                Result.student_enrollment_id.in_(
                    select(StudentEnrollment.id).where(
                        StudentEnrollment.school_id == school_id,
                        StudentEnrollment.student_id == student_id,
                        StudentEnrollment.academic_session_id
                        == term.academic_session_id,
                    )
                ),
            ).limit(1)
        )
        if has_published:
            return term.id
    raise NotFoundError("No published results for this student yet")


def report_card_for_portal(
    db: Session, *, student_id: uuid.UUID, school_id: uuid.UUID, term_id: uuid.UUID
) -> dict:
    """Thin wrapper so the public route renders exactly like the staff card."""
    return report_card(db, school_id, student_id=student_id, term_id=term_id)