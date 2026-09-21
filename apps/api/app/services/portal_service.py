"""Result portal: the school result code, per-student result codes, and the
public card-lookup helpers.

The portal is deliberately minimal and defensive:

* Every credential unlocks *published* results only — the report-card service
  already refuses anything not at the published stage.
* Every lookup failure (unknown school, unknown admission no, wrong code)
  answers the same generic ``NotFoundError`` so the endpoint can't be used
  to enumerate students or their credentials.
* Per-student result codes are issued by the exam office (see
  ``issue_student_result_code``); the legacy school-wide code is a different
  animal — see ``issue_school_pin``.
"""
import re
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..core.security import create_portal_token
from ..models import (
    Result,
    School,
    SchoolResultPin,
    Student,
    StudentEnrollment,
    StudentResultCode,
    Term,
)
from ..models.enums import ResultStatus
from .people_service import get_student
from .results_service import report_card

# --- School result code ------------------------------------------------------
#
# Shape: ``<INITIALS>-<BLOCK>`` — e.g. ``GVGS-7K42Q``. The initials half is
# derived from the school name so a parent holding the code can tell which
# school it belongs to, and the block is the random part.
CODE_BLOCK = 5
# Ambiguous glyphs are excluded on purpose: the code is read off a chalkboard or
# a WhatsApp message and typed by hand, so 0/O, 1/I/L and 5/S are traps.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INITIALS_MAX = 4
# Words that carry no meaning as an initial ("University *of* Lagos").
_INITIAL_STOPWORDS = frozenset({"OF", "AND", "THE", "FOR", "AT", "DE", "LA", "DU"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bad_credentials() -> NotFoundError:
    # One shape for every failure; never hint which field was wrong.
    return NotFoundError("Invalid portal credentials")


# --- School result code ----------------------------------------------------------
def school_initials(school: School) -> str:
    """Initials that name the school inside its result code.

    "Green Valley Grammar School" → ``GVGS``, "Test Academy" → ``TA``,
    "University of Lagos" → ``UL`` (``of`` is noise), "Clearis" → ``CLE``.
    A single-word ``short_name`` is already an abbreviation, so it is used as-is
    (``GVGS`` → ``GVGS``). Always 2–4 uppercase A–Z characters, falling back to
    ``SCH`` so a code can never be emitted without a human-readable prefix.
    """
    short = (school.short_name or "").strip()
    # A possessive is not an initial: "St. Mary's" is S M, not S M S.
    source = re.sub(r"['\u2019]s\b", "", short or school.name or "", flags=re.IGNORECASE)
    words = [w.upper() for w in re.findall(r"[A-Za-z]+", source)]
    meaningful = [w for w in words if w not in _INITIAL_STOPWORDS]

    if short and len(meaningful) == 1 and 2 <= len(meaningful[0]) <= INITIALS_MAX:
        letters = meaningful[0]
    elif len(meaningful) >= 2:
        letters = "".join(w[0] for w in meaningful[:INITIALS_MAX])
    elif meaningful:
        letters = meaningful[0][:3]
    else:
        letters = ""

    letters = re.sub(r"[^A-Z]", "", letters)
    return letters[:INITIALS_MAX] if len(letters) >= 2 else "SCH"


def _random_code_block() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_BLOCK))


def normalize_school_code(raw: str) -> str:
    """Upper-case, drop spaces. Parents type the code off a printout, so
    ``gvs 7k42q`` and ``GVS-7K42Q`` must be the same code."""
    return re.sub(r"\s+", "", (raw or "").upper())


def _code_candidates(normalized: str) -> list[str]:
    """Accept the code with the dash omitted (``GVS7K42Q``), which is what
    happens when someone retypes it without looking. The block length is fixed,
    so the split point is unambiguous."""
    if "-" in normalized or len(normalized) <= CODE_BLOCK:
        return [normalized]
    split = len(normalized) - CODE_BLOCK
    return [normalized, f"{normalized[:split]}-{normalized[split:]}"]


def _allocate_unique_code(db: Session, prefix: str) -> str:
    """A code that collides with no *live* school code or student code.

    Both tables live in the same public namespace — a parent types one code and
    does not know which kind it is — so uniqueness has to span both of them.
    """
    for _ in range(20):
        code = f"{prefix}-{_random_code_block()}"
        school_taken = db.scalar(
            select(SchoolResultPin.id).where(
                SchoolResultPin.code == code,
                SchoolResultPin.revoked_at.is_(None),
            )
        )
        student_taken = db.scalar(
            select(StudentResultCode.id).where(
                StudentResultCode.code == code,
                StudentResultCode.revoked_at.is_(None),
            )
        )
        if school_taken is None and student_taken is None:
            return code
    # pragma: no cover - 20 collisions in a row cannot happen
    raise ValidationError("Could not allocate a result code; please retry")


def issue_school_pin(
    db: Session, *, school_id: uuid.UUID, actor_id: uuid.UUID | None
) -> SchoolResultPin:
    """Issue (or rotate) the school's result code, revoking whatever was live.

    ``create_all``-free: the caller commits. Retries on the astronomically
    unlikely collision with another live code.
    """
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")
    prefix = school_initials(school)

    for live in db.scalars(
        select(SchoolResultPin).where(
            SchoolResultPin.school_id == school_id,
            SchoolResultPin.revoked_at.is_(None),
        )
    ).all():
        live.revoked_at = _utcnow()

    code = _allocate_unique_code(db, prefix)
    row = SchoolResultPin(
        school_id=school_id,
        code=code,
        prefix=prefix,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


# --- Per-student result code -------------------------------------------------
#
# The credential the login screen actually asks for. Shaped exactly like the
# school code (``GVS-7K42Q``) but tied to one child, so the code alone opens
# that child's card and the parent never has to know an admission number.
def current_student_result_code(
    db: Session, *, school_id: uuid.UUID, student_id: uuid.UUID
) -> StudentResultCode | None:
    """The student's live result code, or None when none has been issued."""
    return db.scalar(
        select(StudentResultCode)
        .where(
            StudentResultCode.school_id == school_id,
            StudentResultCode.student_id == student_id,
            StudentResultCode.revoked_at.is_(None),
        )
        .order_by(StudentResultCode.created_at.desc())
        .limit(1)
    )


def issue_student_result_code(
    db: Session,
    *,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> StudentResultCode:
    """Issue (or rotate) one student's result code, revoking whatever was live.

    Rotating immediately invalidates the previous code; the old row is kept
    revoked for audit, so the school can always see which code was live when.
    """
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")
    get_student(db, school_id, student_id)  # raises if tenant mismatch / missing

    prefix = school_initials(school)
    for live in db.scalars(
        select(StudentResultCode).where(
            StudentResultCode.school_id == school_id,
            StudentResultCode.student_id == student_id,
            StudentResultCode.revoked_at.is_(None),
        )
    ).all():
        live.revoked_at = _utcnow()

    row = StudentResultCode(
        school_id=school_id,
        student_id=student_id,
        code=_allocate_unique_code(db, prefix),
        prefix=prefix,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def revoke_student_result_code(
    db: Session, *, school_id: uuid.UUID, student_id: uuid.UUID
) -> bool:
    """Withdraw a student's result code. False when there was nothing live."""
    row = current_student_result_code(db, school_id=school_id, student_id=student_id)
    if row is None:
        return False
    row.revoked_at = _utcnow()
    db.flush()
    return True


def student_result_codes(
    db: Session, *, school_id: uuid.UUID
) -> list[tuple[Student, StudentResultCode | None]]:
    """Every student in the school paired with their live code (or None).

    Feeds the Exam Office's code manager so it can hand out codes per child and
    spot who still needs one.
    """
    students = db.scalars(
        select(Student)
        .where(Student.school_id == school_id, Student.is_deleted.is_(False))
        .order_by(Student.last_name, Student.first_name, Student.admission_no)
    ).all()
    live = {
        row.student_id: row
        for row in db.scalars(
            select(StudentResultCode).where(
                StudentResultCode.school_id == school_id,
                StudentResultCode.revoked_at.is_(None),
            )
        )
    }
    return [(s, live.get(s.id)) for s in students]


def issue_missing_student_result_codes(
    db: Session, *, school_id: uuid.UUID, actor_id: uuid.UUID | None
) -> int:
    """Issue a code for every student who does not have one yet.

    The one-click path for a new term: existing codes are left alone, only the
    gaps are filled. Returns how many were issued.
    """
    issued = 0
    for student, row in student_result_codes(db, school_id=school_id):
        if row is None:
            issue_student_result_code(
                db, school_id=school_id, student_id=student.id, actor_id=actor_id
            )
            issued += 1
    return issued


def current_school_pin(db: Session, school_id: uuid.UUID) -> SchoolResultPin | None:
    """The school's live result code, or None when it has never issued one."""
    return db.scalar(
        select(SchoolResultPin)
        .where(
            SchoolResultPin.school_id == school_id,
            SchoolResultPin.revoked_at.is_(None),
        )
        .order_by(SchoolResultPin.created_at.desc())
        .limit(1)
    )


def revoke_school_pin(db: Session, school_id: uuid.UUID) -> bool:
    """Withdraw the school code: parents can no longer check results until a
    new one is issued. Returns False when there was nothing live to revoke."""
    row = current_school_pin(db, school_id)
    if row is None:
        return False
    row.revoked_at = _utcnow()
    db.flush()
    return True


def resolve_school_pin(
    db: Session, *, code: str, admission_no: str
) -> tuple[School, Student]:
    """Resolve a school result code + admission number into (school, student).

    The code only says *which school*; the admission number says which child in
    it. Any failure raises the same generic 404 as the per-student PIN so the
    endpoint cannot be used to enumerate schools, students or live codes.

    There is no per-code lockout here on purpose: the code is shared by every
    family in the school, so a counter would let one attacker lock all of them
    out. The public endpoint's per-IP rate limit is the brute-force answer.
    """
    normalized = normalize_school_code(code)
    if not normalized:
        raise _bad_credentials()

    row = None
    for candidate in _code_candidates(normalized):
        row = db.scalar(
            select(SchoolResultPin)
            .where(
                SchoolResultPin.code == candidate,
                SchoolResultPin.revoked_at.is_(None),
            )
            .order_by(SchoolResultPin.created_at.desc())
            .limit(1)
        )
        if row is not None:
            break
    if row is None:
        raise _bad_credentials()

    school = db.get(School, row.school_id)
    if school is None:
        raise _bad_credentials()
    student = db.scalar(
        select(Student).where(
            Student.school_id == row.school_id,
            Student.admission_no == admission_no.strip(),
            Student.is_deleted.is_(False),
        )
    )
    if student is None:
        raise _bad_credentials()

    row.last_used_at = _utcnow()
    row.use_count = (row.use_count or 0) + 1
    db.flush()
    return school, student


def resolve_result_code(
    db: Session, *, code: str, admission_no: str | None = None
) -> tuple[School, Student]:
    """Resolve a public result code into (school, student).

    A *per-student* code names the child on its own, so it is tried first and
    the admission number is ignored. If no student code matches, the legacy
    *school-wide* code path runs, which still needs the admission number. Every
    failure answers the same generic 404 so the endpoint cannot be used to
    enumerate students or live codes.
    """
    normalized = normalize_school_code(code)
    if not normalized:
        raise _bad_credentials()

    for candidate in _code_candidates(normalized):
        row = db.scalar(
            select(StudentResultCode)
            .where(
                StudentResultCode.code == candidate,
                StudentResultCode.revoked_at.is_(None),
            )
            .order_by(StudentResultCode.created_at.desc())
            .limit(1)
        )
        if row is None:
            continue
        school = db.get(School, row.school_id)
        student = db.scalar(
            select(Student).where(
                Student.id == row.student_id,
                Student.school_id == row.school_id,
                Student.is_deleted.is_(False),
            )
        )
        if school is None or student is None:
            raise _bad_credentials()
        row.last_used_at = _utcnow()
        row.use_count = (row.use_count or 0) + 1
        db.flush()
        return school, student

    # No student code matched: fall back to the school-wide code, which is only
    # usable with an admission number.
    return resolve_school_pin(db, code=code, admission_no=admission_no or "")


def portal_token(school: School, student: Student) -> str:
    return create_portal_token(str(student.id), str(school.id))


def published_terms(
    db: Session, *, school_id: uuid.UUID, student_id: uuid.UUID
) -> list[Term]:
    """Every term this student has at least one *published* result in, newest
    first. Feeds the portal's term picker so a parent can re-open an earlier
    term, not just the latest."""
    session_ids = list(
        db.scalars(
            select(StudentEnrollment.academic_session_id).where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.student_id == student_id,
            )
        )
    )
    if not session_ids:
        return []
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
    out: list[Term] = []
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
            out.append(term)
    return out


def latest_published_term_id(
    db: Session, *, school_id: uuid.UUID, student_id: uuid.UUID
) -> uuid.UUID:
    """The most recent term (current session first) in which this student has
    at least one published result. 404 when there is none yet."""
    terms = published_terms(db, school_id=school_id, student_id=student_id)
    if not terms:
        raise NotFoundError("No published results for this student yet")
    return terms[0].id


def report_card_for_portal(
    db: Session, *, student_id: uuid.UUID, school_id: uuid.UUID, term_id: uuid.UUID
) -> dict:
    """Thin wrapper so the public route renders exactly like the staff card."""
    return report_card(db, school_id, student_id=student_id, term_id=term_id)