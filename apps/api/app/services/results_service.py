"""Results engine: assessment components, score entry, computation, submission,
grade mapping, and the append-only event journal.

Invariants enforced here:
  * A score cell (enrollment, subject, component) holds exactly one value.
  * Values are clamped to the component's max (0 <= score <= max_score).
  * Totals are derived, never hand-edited: recomputed from the cells.
  * A result that has moved past ``draft`` cannot accept score edits.
  * A published result is immutable; its totals are snapshotted.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import (
    ERR_ASSIGNMENT,
    ERR_RESULT_LOCKED,
    ERR_SCORE_NEGATIVE,
    ERR_SCORE_OVER_MAX,
    ERR_WEIGHT_SUM,
    APIError,
    NotFoundError,
    ValidationError,
)
from ..core.permissions import (
    RESULTS_APPROVE,
    RESULTS_PUBLISH,
    RESULTS_VERIFY,
)
from ..models import (
    AcademicSession,
    AssessmentComponent,
    ClassArm,
    GradeBand,
    GradeScale,
    PsychomotorAssessment,
    Result,
    ResultComment,
    ResultEvent,
    Score,
    School,
    Staff,
    Student,
    StudentAttendance,
    StudentEnrollment,
    Subject,
    SubjectAssignment,
    SubjectOffering,
    Term,
)
from ..models.enums import ResultStatus
from .academics_service import get_arm, get_subject, get_term
from .people_service import get_student, list_enrollments


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Psychomotor / affective achievement vocabulary + the numeric spine used to
# average rows into a single level for the printable card.
PSYCHOMOTOR_LEVELS: dict[str, int] = {
    "Excellent": 5,
    "Very Good": 4,
    "Good": 3,
    "Fair": 2,
    "Poor": 1,
}
LEVEL_FOR_POINT: dict[int, str] = {
    5: "Excellent",
    4: "Very Good",
    3: "Good",
    2: "Fair",
    1: "Poor",
}


# --- Responsibility gating ---------------------------------------------------
# Roles that supervise the results life cycle (they hold one of the approval
# permissions) bypass the teacher-assignment gate: principals, VPs, head
# teachers and the exam office can act on any arm/subject of their school.
# Every other user with results.enter/submit must be *the assigned teacher*
# of that exact arm x subject — enforced server-side, never the frontend.
_SUPERVISOR_PERMISSIONS: frozenset[str] = frozenset(
    {RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH}
)


def require_assigned_teacher(
    db: Session,
    school_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool = False,
) -> None:
    """Raise ``ERR_ASSIGNMENT`` (403) unless the actor may work this arm x subject.

    Platform super-admins and supervisors (users holding a results workflow
    permission) may act anywhere. Everyone else — i.e. teachers bearing only
    results.enter/submit — must have an active ``SubjectAssignment`` for this
    arm x subject. School admins grant/revoke these via /academics/assignments.
    """
    if is_superadmin:
        return
    if permission_codes & _SUPERVISOR_PERMISSIONS:
        return

    staff = db.scalar(
        select(Staff).where(
            Staff.school_id == school_id,
            Staff.user_id == actor_id,
            Staff.is_deleted.is_(False),
        )
    )
    if staff is not None:
        assigned = db.scalar(
            select(SubjectAssignment).where(
                SubjectAssignment.school_id == school_id,
                SubjectAssignment.class_arm_id == arm_id,
                SubjectAssignment.subject_id == subject_id,
                SubjectAssignment.teacher_id == staff.id,
            )
        )
        if assigned is not None:
            return

    raise APIError(
        403,
        ERR_ASSIGNMENT,
        "You are not the assigned teacher for this subject in this class",
        {"arm_id": str(arm_id), "subject_id": str(subject_id)},
    )


# --- Effective assessment components -----------------------------------------
def effective_components(
    db: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    *,
    class_arm_id: uuid.UUID | None = None,
) -> list[AssessmentComponent]:
    """Components applying to a scope: school-wide (NULL arm) base rows,
    then arm-level overrides. Per name, the most specific scope wins."""
    rows = list(
        db.scalars(
            select(AssessmentComponent).where(
                AssessmentComponent.school_id == school_id,
                AssessmentComponent.term_id == term_id,
                AssessmentComponent.is_active.is_(True),
            )
        )
    )
    base: dict[str, AssessmentComponent] = {}
    arm: dict[str, AssessmentComponent] = {}
    for comp in rows:
        if comp.class_arm_id is not None and comp.class_arm_id == class_arm_id:
            arm[comp.name] = comp
        elif comp.class_arm_id is None:
            base[comp.name] = comp
    merged: dict[str, AssessmentComponent] = {}
    merged.update(arm)
    for name, comp in base.items():
        merged.setdefault(name, comp)
    return sorted(merged.values(), key=lambda c: (c.sort_order, c.name))


def ensure_default_components(
    db: Session, school_id: uuid.UUID, term_id: uuid.UUID
) -> list[AssessmentComponent]:
    """Create the standard CA/Exam fields for a term that has none."""
    components = effective_components(db, school_id, term_id)
    if components:
        return components

    for sort_order, (name, max_score, weight) in enumerate(
        (("1st CA", 20, 20), ("2nd CA", 30, 30), ("Exam", 70, 50))
    ):
        db.add(
            AssessmentComponent(
                school_id=school_id,
                term_id=term_id,
                name=name,
                max_score=max_score,
                weight=weight,
                sort_order=sort_order,
            )
        )
    db.flush()
    return effective_components(db, school_id, term_id)


def validate_component_weights(components: list[AssessmentComponent]) -> None:
    """Weights across the effective set must sum to 100."""
    total = round(sum(float(c.weight) for c in components), 2)
    if abs(total - 100.0) > 0.01:
        raise APIError(
            422, ERR_WEIGHT_SUM,
            f"Assessment component weights must sum to 100 (currently {total})",
            {"weight_sum": total},
        )


# --- Scorecard ----------------------------------------------------------------
def scorecard(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
) -> dict:
    """The full grid for one arm x subject x term."""
    arm = get_arm(db, school_id, arm_id)
    subject = get_subject(db, school_id, subject_id)
    term = get_term(db, school_id, term_id)
    enrollments = list_enrollments(db, school_id, arm_id)

    components = ensure_default_components(db, school_id, term.id)
    components = effective_components(db, school_id, term.id, class_arm_id=arm.id)

    enrollment_ids = [e.id for e in enrollments]
    scores: list[Score] = []
    if enrollment_ids:
        scores = list(
            db.scalars(
                select(Score).where(
                    Score.school_id == school_id,
                    Score.class_arm_id == arm_id,
                    Score.subject_id == subject_id,
                    Score.student_enrollment_id.in_(enrollment_ids),
                )
            )
        )
    score_map: dict[tuple[uuid.UUID, uuid.UUID], float] = {
        (s.student_enrollment_id, s.assessment_component_id): float(s.score)
        for s in scores
    }

    # Attach computed totals + state so the grid shows live progress at a glance.
    result_map: dict[uuid.UUID, Result] = {
        r.student_enrollment_id: r
        for r in (
            db.scalars(
                select(Result).where(
                    Result.school_id == school_id,
                    Result.class_arm_id == arm_id,
                    Result.subject_id == subject_id,
                    Result.term_id == term_id,
                )
            ).all()
        )
    }

    student_rows = []
    for env in enrollments:
        student = env.student
        result = result_map.get(env.id)
        student_rows.append(
            {
                "enrollment_id": str(env.id),
                "student_id": str(env.student_id),
                "admission_no": student.admission_no,
                "full_name": student.full_name,
                "scores": {
                    str(c.id): score_map.get((env.id, c.id))
                    for c in components
                },
                "total": float(result.total) if result and result.total is not None else None,
                "grade_letter": result.grade_letter if result else None,
                "status": result.status if result else "draft",
            }
        )

    return {
        "arm": {"id": str(arm.id), "full_name": arm.full_name},
        "subject": {"id": str(subject.id), "name": subject.name},
        "term": {"id": str(term.id), "name": term.name},
        "components": [
            {
                "id": str(c.id),
                "name": c.name,
                "max_score": float(c.max_score),
                "weight": float(c.weight),
            }
            for c in components
        ],
        "students": student_rows,
    }


# --- Bulk score entry ----------------------------------------------------------
def save_scores(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    entries: list[dict],
    actor_id: uuid.UUID,
    permission_codes: set[str] | None = None,
    is_superadmin: bool = False,
) -> dict:
    """Bulk upsert of score cells for one arm x subject x term.

    Responsibility-gated: the actor must be the assigned teacher of this
    arm x subject (or a supervisor). Validates every cell against its
    component max and refuses to edit any enrollment whose result has left
    the draft state.
    """
    require_assigned_teacher(
        db, school_id,
        actor_id=actor_id, arm_id=arm_id, subject_id=subject_id,
        permission_codes=permission_codes or set(), is_superadmin=is_superadmin,
    )
    arm = get_arm(db, school_id, arm_id)
    get_subject(db, school_id, subject_id)
    term = get_term(db, school_id, term_id)
    components = effective_components(
        db, school_id, term.id,
        class_arm_id=arm.id,
    )
    validate_component_weights(components)

    # Router passes pydantic UUIDs through, so key the map on the string form —
    # compare against str(cell_id) regardless of whether the caller sent a UUID
    # object or a JSON string.
    comp_by_id = {str(c.id): c for c in components}
    now = utcnow()

    for entry in entries:
        enrollment_id = entry["student_enrollment_id"]
        env = db.get(StudentEnrollment, enrollment_id)
        if env is None or env.school_id != school_id or env.class_arm_id != arm_id:
            raise NotFoundError("Enrollment not found in this class")

        existing_result = db.scalar(
            select(Result).where(
                Result.student_enrollment_id == enrollment_id,
                Result.subject_id == subject_id,
                Result.term_id == term_id,
            )
        )
        if (
            existing_result is not None
            and existing_result.status != ResultStatus.DRAFT.value
        ):
            raise APIError(
                409, ERR_RESULT_LOCKED,
                f"Result already {existing_result.status} — scores cannot be edited now",
            )

        for cell in entry.get("scores") or []:
            comp = comp_by_id.get(str(cell["assessment_component_id"]))
            if comp is None:
                raise ValidationError("Unknown assessment component")
            value = cell.get("score")
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValidationError("Score must be a number")
            if value < 0:
                raise APIError(422, ERR_SCORE_NEGATIVE, "Score cannot be negative")
            if value > float(comp.max_score):
                raise APIError(
                    422, ERR_SCORE_OVER_MAX,
                    f"{comp.name} accepts a maximum of {comp.max_score}",
                    {"component": comp.name, "max": float(comp.max_score)},
                )
            value = round(value, 2)

            existing = db.scalar(
                select(Score).where(
                    Score.student_enrollment_id == enrollment_id,
                    Score.subject_id == subject_id,
                    Score.assessment_component_id == comp.id,
                )
            )
            if existing is None:
                db.add(
                    Score(
                        school_id=school_id,
                        student_enrollment_id=enrollment_id,
                        class_arm_id=arm_id,
                        subject_id=subject_id,
                        assessment_component_id=comp.id,
                        score=value,
                        entered_by=actor_id,
                        entered_at=now,
                    )
                )
            else:
                existing.score = value
                existing.entered_by = actor_id

    db.flush()
    _recompute_arm_subject(db, school_id, arm_id, subject_id, term_id)
    db.flush()
    return scorecard(db, school_id, arm_id=arm_id, subject_id=subject_id, term_id=term_id)


# --- Computation ---------------------------------------------------------------
def _compute_total(
    db: Session,
    env: StudentEnrollment,
    subject_id: uuid.UUID,
    components: list[AssessmentComponent],
) -> float:
    """Weighted 0-100 total for one student x subject using the effective set."""
    comp_ids = [c.id for c in components]
    if not comp_ids:
        return 0.0
    rows = db.execute(
        select(Score).where(
            Score.student_enrollment_id == env.id,
            Score.subject_id == subject_id,
            Score.assessment_component_id.in_(comp_ids),
        )
    ).scalars().all()
    scores_by_comp = {s.assessment_component_id: float(s.score) for s in rows}
    total = 0.0
    for comp in components:
        value = scores_by_comp.get(comp.id)
        if value is None:
            continue
        total += comp.score_to_weighted(value)
    return round(total, 2)


def _grade_for(
    db: Session, school_id: uuid.UUID, session: AcademicSession, total: float
) -> tuple[str | None, float | None, str | None]:
    """Grade band lookup using the session's grade scale (fallback: school default)."""
    scale_id = session.grade_scale_id
    if scale_id is None:
        scale = db.scalar(
            select(GradeScale).where(
                GradeScale.school_id == school_id, GradeScale.is_default.is_(True)
            )
        )
        scale_id = scale.id if scale else None
    if scale_id is None:
        return None, None, None
    band = db.scalar(
        select(GradeBand).where(
            GradeBand.grade_scale_id == scale_id,
            GradeBand.min_score <= total,
            GradeBand.max_score >= total,
        )
    )
    if band is None:
        return None, None, None
    return band.letter, float(band.point), band.remark


def recompute_result(
    db: Session,
    school_id: uuid.UUID,
    *,
    enrollment_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    session: AcademicSession,
    components: list[AssessmentComponent],
    arm_id: uuid.UUID,
) -> Result:
    env = db.get(StudentEnrollment, enrollment_id)
    total = _compute_total(db, env, subject_id, components)
    letter, point, remark = _grade_for(db, school_id, session, total)
    result = db.scalar(
        select(Result).where(
            Result.student_enrollment_id == enrollment_id,
            Result.subject_id == subject_id,
            Result.term_id == term_id,
        )
    )
    if result is None:
        result = Result(
            school_id=school_id,
            student_enrollment_id=enrollment_id,
            subject_id=subject_id,
            term_id=term_id,
            class_arm_id=arm_id,
        )
        db.add(result)
    result.total = total
    result.grade_letter = letter
    result.grade_point = point
    result.remark = remark
    result.recomputed_at = utcnow()
    return result


def _subjects_for_arm(db: Session, arm_id: uuid.UUID) -> list[Subject]:
    """Subjects offered at the arm (drives grids + readiness)."""
    arm = db.get(ClassArm, arm_id)
    if arm is None:
        return []
    offering_ids = db.scalars(
        select(SubjectOffering.subject_id).where(
            SubjectOffering.class_arm_id == arm.id
        )
    ).all()
    subjects = [db.get(Subject, sid) for sid in offering_ids]
    return [s for s in subjects if s is not None]


def _recompute_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
) -> None:
    """Recompute result totals + class positions for one arm x subject x term."""
    arm = get_arm(db, school_id, arm_id)
    term = get_term(db, school_id, term_id)
    session = db.get(AcademicSession, arm.academic_session_id)
    components = effective_components(
        db, school_id, term.id,
        class_arm_id=arm.id,
    )
    for env in list_enrollments(db, school_id, arm_id):
        recompute_result(
            db, school_id,
            enrollment_id=env.id, subject_id=subject_id, term_id=term.id,
            session=session, components=components, arm_id=arm_id,
        )
    _recompute_positions(db, school_id, arm_id, subject_id, term_id)


def _recompute_positions(
    db: Session,
    school_id: uuid.UUID,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
) -> None:
    rows = list(
        db.scalars(
            select(Result).where(
                Result.class_arm_id == arm_id,
                Result.subject_id == subject_id,
                Result.term_id == term_id,
                Result.total.is_not(None),
            )
        )
    )
    rows.sort(key=lambda r: -(r.total or 0))
    for i, row in enumerate(rows, start=1):
        row.position = i
    db.flush()


# --- Submission ----------------------------------------------------------------
def submit_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
    permission_codes: set[str] | None = None,
    is_superadmin: bool = False,
) -> int:
    """Submit all draft results for one arm x subject x term.

    Responsibility-gated like score entry: only the assigned teacher (or a
    supervisor) may submit. Enrollments without any score cell are left draft
    so the readiness dashboard keeps showing them as pending. Returns the
    number submitted.
    """
    require_assigned_teacher(
        db, school_id,
        actor_id=actor_id, arm_id=arm_id, subject_id=subject_id,
        permission_codes=permission_codes or set(), is_superadmin=is_superadmin,
    )
    results = list(
        db.scalars(
            select(Result).where(
                Result.class_arm_id == arm_id,
                Result.subject_id == subject_id,
                Result.term_id == term_id,
                Result.status == ResultStatus.DRAFT.value,
            )
        )
    )
    count = 0
    for result in results:
        has_scores = db.scalar(
            select(Score.id)
            .where(
                Score.student_enrollment_id == result.student_enrollment_id,
                Score.subject_id == subject_id,
            )
            .limit(1)
        )
        if not has_scores:
            continue
        result.status = ResultStatus.SUBMITTED.value
        result.submitted_at = utcnow()
        result.submitted_by = actor_id
        db.add(
            ResultEvent(
                school_id=school_id,
                result_id=result.id,
                actor_id=actor_id,
                action="submit",
                from_status=ResultStatus.DRAFT.value,
                to_status=ResultStatus.SUBMITTED.value,
            )
        )
        count += 1
    db.flush()
    return count


# --- Approval workflow -------------------------------------------------------
def _transition(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
    from_status: str,
    to_status: str,
    action: str,
    note: str | None = None,
    clear_submitted: bool = False,
    stamps: dict | None = None,
) -> int:
    """Advance every result of one arm x subject x term from one state to the
    next, journaling one ``ResultEvent`` per row. Skips rows already past the
    source state; rows in an incompatible state are left untouched and reported
    so the caller can surface a conflict when NOTHING moved. ``stamps`` applies
    extra per-row columns (e.g. ``approved_at``/``approved_by``) alongside the
    status flip."""
    rows = list(
        db.scalars(
            select(Result).where(
                Result.class_arm_id == arm_id,
                Result.subject_id == subject_id,
                Result.term_id == term_id,
                Result.status == from_status,
            )
        )
    )
    now = utcnow()
    for result in rows:
        result.status = to_status
        for key, value in (stamps or {}).items():
            setattr(result, key, value)
        if clear_submitted:
            result.submitted_at = None
        db.add(
            ResultEvent(
                school_id=school_id,
                result_id=result.id,
                actor_id=actor_id,
                action=action,
                from_status=from_status,
                to_status=to_status,
                note=note,
                created_at=now,
            )
        )
    db.flush()
    return len(rows)


def _build_published_snapshot(
    db: Session,
    school_id: uuid.UUID,
    *,
    result: Result,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
) -> dict:
    """Freeze the per-subject facts a report card needs: totals, grades,
    position, and the component scores that produced them. Nothing derived
    may drift after publish."""
    arm = db.get(ClassArm, arm_id)
    components = effective_components(
        db, school_id, term_id,
        class_arm_id=arm_id,
    )
    scores: list[Score] = list(
        db.scalars(
            select(Score).where(
                Score.student_enrollment_id == result.student_enrollment_id,
                Score.subject_id == subject_id,
            )
        )
    )
    score_map = {
        str(s.assessment_component_id): float(s.score) for s in scores
    }
    return {
        "total": float(result.total) if result.total is not None else None,
        "grade_letter": result.grade_letter,
        "grade_point": float(result.grade_point) if result.grade_point is not None else None,
        "remark": result.remark,
        "position": result.position,
        "components": [
            {
                "id": str(c.id),
                "name": c.name,
                "max_score": float(c.max_score),
                "weight": float(c.weight),
                "score": score_map.get(str(c.id)),
            }
            for c in components
        ],
    }


def verify_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> int:
    return _transition(
        db, school_id,
        arm_id=arm_id, subject_id=subject_id, term_id=term_id, actor_id=actor_id,
        from_status=ResultStatus.SUBMITTED.value, to_status=ResultStatus.VERIFIED.value,
        action="verify",
    )


def approve_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> int:
    return _transition(
        db, school_id,
        arm_id=arm_id, subject_id=subject_id, term_id=term_id, actor_id=actor_id,
        from_status=ResultStatus.VERIFIED.value, to_status=ResultStatus.APPROVED.value,
        action="approve",
        stamps={"approved_at": utcnow(), "approved_by": actor_id},
    )


def publish_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> int:
    """approve -> published, freezing ``published_snapshot`` per row so report
    cards and the public portal render immutable totals."""
    rows = list(
        db.scalars(
            select(Result).where(
                Result.class_arm_id == arm_id,
                Result.subject_id == subject_id,
                Result.term_id == term_id,
                Result.status == ResultStatus.APPROVED.value,
            )
        )
    )
    now = utcnow()
    for result in rows:
        result.status = ResultStatus.PUBLISHED.value
        result.published_at = now
        result.published_snapshot = _build_published_snapshot(
            db, school_id,
            result=result, arm_id=arm_id, subject_id=subject_id, term_id=term_id,
        )
        db.add(
            ResultEvent(
                school_id=school_id,
                result_id=result.id,
                actor_id=actor_id,
                action="publish",
                from_status=ResultStatus.APPROVED.value,
                to_status=ResultStatus.PUBLISHED.value,
                created_at=now,
            )
        )
    db.flush()
    return len(rows)


def reject_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str,
) -> int:
    """An approver bounces submitted/verified/approved rows back to draft with a
    reason, unlocking re-entry by the assigned teacher."""
    rows = list(
        db.scalars(
            select(Result).where(
                Result.class_arm_id == arm_id,
                Result.subject_id == subject_id,
                Result.term_id == term_id,
                Result.status.in_(
                    [
                        ResultStatus.SUBMITTED.value,
                        ResultStatus.VERIFIED.value,
                        ResultStatus.APPROVED.value,
                    ]
                ),
            )
        )
    )
    now = utcnow()
    for result in rows:
        prev = result.status
        result.status = ResultStatus.DRAFT.value
        result.submitted_at = None
        db.add(
            ResultEvent(
                school_id=school_id,
                result_id=result.id,
                actor_id=actor_id,
                action="reject",
                from_status=prev,
                to_status=ResultStatus.DRAFT.value,
                note=reason,
                created_at=now,
            )
        )
    db.flush()
    return len(rows)


def ensure_results_exist(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
) -> int:
    """Create draft Result rows for every enrollment x offered subject so the
    readiness dashboard can count the untouched cells."""
    subjects = _subjects_for_arm(db, arm_id)
    enrollments = list_enrollments(db, school_id, arm_id)
    created = 0
    for env in enrollments:
        for subject in subjects:
            exists = db.scalar(
                select(Result.id).where(
                    Result.student_enrollment_id == env.id,
                    Result.subject_id == subject.id,
                    Result.term_id == term_id,
                )
            )
            if not exists:
                db.add(
                    Result(
                        school_id=school_id,
                        student_enrollment_id=env.id,
                        subject_id=subject.id,
                        term_id=term_id,
                        class_arm_id=arm_id,
                    )
                )
                created += 1
    db.flush()
    return created


# --- Readiness ----------------------------------------------------------------
def readiness_for_term(db: Session, school_id: uuid.UUID, term_id: uuid.UUID) -> list[dict]:
    """Per-arm per-subject progress for the readiness dashboard."""
    arms = list(
        db.scalars(
            select(ClassArm)
            .where(ClassArm.school_id == school_id)
            .order_by(ClassArm.full_name)
        )
    )
    rows: list[dict] = []
    for arm in arms:
        subjects = _subjects_for_arm(db, arm.id)
        enrollments = list_enrollments(db, school_id, arm.id)
        total = len(enrollments)
        for subject in subjects:
            entered = 0
            submitted = 0
            for env in enrollments:
                has_scores = bool(
                    db.scalar(
                        select(Score.id)
                        .where(
                            Score.student_enrollment_id == env.id,
                            Score.subject_id == subject.id,
                        )
                        .limit(1)
                    )
                )
                if has_scores:
                    entered += 1
                    result = db.scalar(
                        select(Result).where(
                            Result.student_enrollment_id == env.id,
                            Result.subject_id == subject.id,
                            Result.term_id == term_id,
                        )
                    )
                    if result and result.status in (
                        ResultStatus.SUBMITTED.value,
                        ResultStatus.VERIFIED.value,
                        ResultStatus.APPROVED.value,
                        ResultStatus.PUBLISHED.value,
                    ):
                        submitted += 1
            rows.append(
                {
                    "arm_id": str(arm.id),
                    "arm_name": arm.full_name,
                    "subject_id": str(subject.id),
                    "subject_name": subject.name,
                    "student_count": total,
                    "entered": entered,
                    "submitted": submitted,
                    "pending": max(0, total - entered),
                    "entered_pct": round((entered / total * 100), 1) if total else 0,
                }
            )
    return rows


# --- Approval workbench -------------------------------------------------------
def workbench_for_term(db: Session, school_id: uuid.UUID, term_id: uuid.UUID) -> list[dict]:
    """Per arm x subject, where each stage of the review funnel stands. This is
    the approvers' page: pick a row to verify, approve, publish or reject."""
    arms = list(
        db.scalars(
            select(ClassArm)
            .where(ClassArm.school_id == school_id)
            .order_by(ClassArm.full_name)
        )
    )
    rows: list[dict] = []
    for arm in arms:
        subjects = _subjects_for_arm(db, arm.id)
        enrollments = list_enrollments(db, school_id, arm.id)
        for subject in subjects:
            results = list(
                db.scalars(
                    select(Result).where(
                        Result.class_arm_id == arm.id,
                        Result.subject_id == subject.id,
                        Result.term_id == term_id,
                    )
                )
            )
            counts = {
                "draft": 0, "submitted": 0, "verified": 0,
                "approved": 0, "published": 0, "rejected": 0,
            }
            entered = 0
            for r in results:
                has_scores = db.scalar(
                    select(Score.id)
                    .where(
                        Score.student_enrollment_id == r.student_enrollment_id,
                        Score.subject_id == subject.id,
                    )
                    .limit(1)
                )
                if has_scores:
                    entered += 1
                status = r.status if r.status in counts else "draft"
                counts[status] += 1
            rows.append(
                {
                    "arm_id": str(arm.id),
                    "term_id": str(term_id),
                    "arm_name": arm.full_name,
                    "subject_id": str(subject.id),
                    "subject_name": subject.name,
                    "enrolled": len(enrollments),
                    "entered": entered,
                    "draft": counts["draft"],
                    "submitted": counts["submitted"],
                    "verified": counts["verified"],
                    "approved": counts["approved"],
                    "published": counts["published"],
                    "rejected": counts["rejected"],
                }
            )
    return rows


# --- Report cards ----------------------------------------------------------
# A report card renders ONLY published results, from each row's frozen
# `published_snapshot`. Totals, grades, positions and component scores can
# never drift after publish, so the printed card is an immutable record.
def _published_totals(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> dict[uuid.UUID, list[float]]:
    """Published per-subject totals (from frozen snapshots), grouped by
    enrollment, for one arm x term."""
    tbl: dict[uuid.UUID, list[float]] = {}
    env_ids = [e.id for e in list_enrollments(db, school_id, arm_id)]
    if not env_ids:
        return tbl
    for result in db.scalars(
        select(Result).where(
            Result.school_id == school_id,
            Result.class_arm_id == arm_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
            Result.student_enrollment_id.in_(env_ids),
        )
    ).all():
        snap = result.published_snapshot or {}
        if snap.get("total") is not None:
            tbl.setdefault(result.student_enrollment_id, []).append(
                float(snap["total"])
            )
    return tbl


def _grouped_core_totals(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> dict[uuid.UUID, dict]:
    """Published totals per core subject across an arm × term.

    Each group maps ``scorers`` = {enrollment_id: {"total", "name"}} so callers
    can compute the top score and its (co-)leaders from frozen snapshots.
    """
    groups: dict[uuid.UUID, dict] = {}
    rows = db.execute(
        select(Result, Subject, StudentEnrollment, Student)
        .join(Subject, Subject.id == Result.subject_id)
        .join(StudentEnrollment, StudentEnrollment.id == Result.student_enrollment_id)
        .join(Student, Student.id == StudentEnrollment.student_id)
        .where(
            Result.school_id == school_id,
            Result.class_arm_id == arm_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
            Subject.is_core.is_(True),
        )
    ).all()
    for result, subject, env, stu in rows:
        snap = result.published_snapshot or {}
        total = snap.get("total")
        if total is None:
            total = result.total
        if total is None:
            continue
        g = groups.setdefault(
            result.subject_id,
            {"subject_id": result.subject_id, "name": subject.name, "scorers": {}},
        )
        g["scorers"][str(env.id)] = {"total": float(total), "name": stu.full_name}
    return groups


def _best_in_core_subjects(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
    env_id: uuid.UUID,
) -> list[dict]:
    """Which core subjects the given enrollment is (co-)best at this term.

    Returns one row per core subject where the student holds the arm's top
    score (ties included), e.g. the card's "Best in Mathematics" ribbon.
    """
    out: list[dict] = []
    for g in _grouped_core_totals(db, school_id, arm_id=arm_id, term_id=term_id).values():
        scorers = g["scorers"]
        if str(env_id) not in scorers:
            continue
        top = max(s["total"] for s in scorers.values())
        leaders = [s for s in scorers.items() if s[1]["total"] == top]
        if str(env_id) not in {eid for eid, _ in leaders}:
            continue
        out.append(
            {
                "subject_id": str(g["subject_id"]),
                "subject_name": g["name"],
                "top_score": top,
                "is_best": True,
                "tied": len(leaders) > 1,
                "co_leaders": [
                    s["name"] for _, s in sorted(leaders, key=lambda x: x[1]["name"])
                ],
            }
        )
    return out


def best_in_subjects_overview(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """Every core subject's top score and its leaders in an arm × term.

    The admin/class-leadership view of who is best in which subject; empty when
    no core subjects are designated or nothing is published yet.
    """
    out: list[dict] = []
    for g in _grouped_core_totals(db, school_id, arm_id=arm_id, term_id=term_id).values():
        top = max(s["total"] for s in g["scorers"].values())
        leaders = sorted(
            (s for s in g["scorers"].values() if s["total"] == top),
            key=lambda s: s["name"],
        )
        out.append(
            {
                "subject_id": str(g["subject_id"]),
                "subject_name": g["name"],
                "top_score": top,
                "leader_count": len(leaders),
                "leaders": [s["name"] for s in leaders],
            }
        )
    out.sort(key=lambda r: r["subject_name"])
    return out


def report_index(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """Which students in an arm have published results this term — the 'cards
    ready to print' index. Everyone in the arm is listed (with
    ``subjects_published = 0`` for those still pending), so the UI can show
    who is ready and who isn't."""
    get_arm(db, school_id, arm_id)
    get_term(db, school_id, term_id)
    enrollments = list_enrollments(db, school_id, arm_id)
    tally = _published_totals(db, school_id, arm_id=arm_id, term_id=term_id)
    rows = []
    for env in enrollments:
        row_totals = tally.get(env.id, [])
        rows.append(
            {
                "student_id": str(env.student_id),
                "enrollment_id": str(env.id),
                "admission_no": env.student.admission_no,
                "full_name": env.student.full_name,
                "subjects_published": len(row_totals),
                "total": round(sum(row_totals), 2) if row_totals else None,
            }
        )
    return rows


def report_cards_bulk(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """All printable cards for an arm this term (published only). Students
    with no published subjects are skipped — same rule as the single-card
    endpoint."""
    cards = []
    for row in report_index(db, school_id, arm_id=arm_id, term_id=term_id):
        try:
            cards.append(
                report_card(
                    db,
                    school_id,
                    student_id=uuid.UUID(row["student_id"]),
                    term_id=term_id,
                )
            )
        except NotFoundError:
            continue
    return cards


def cumulative_for_session(
    db: Session, school_id: uuid.UUID, *, student_id: uuid.UUID, session_id: uuid.UUID
) -> dict:
    """Aggregate published subject totals across every term in a session."""
    get_student(db, school_id, student_id)
    terms = list(
        db.scalars(
            select(Term).where(
                Term.school_id == school_id,
                Term.academic_session_id == session_id,
            ).order_by(Term.term_no)
        )
    )
    if not terms:
        raise NotFoundError("No terms found for this academic session")
    rows = db.execute(
        select(Result, Subject, Term)
        .join(Subject, Subject.id == Result.subject_id)
        .join(Term, Term.id == Result.term_id)
        .where(
            Result.school_id == school_id,
            Result.student_enrollment_id.in_(
                select(StudentEnrollment.id).where(
                    StudentEnrollment.school_id == school_id,
                    StudentEnrollment.student_id == student_id,
                    StudentEnrollment.academic_session_id == session_id,
                )
            ),
            Result.term_id.in_([term.id for term in terms]),
            Result.status == ResultStatus.PUBLISHED.value,
        )
        .order_by(Subject.name, Term.term_no)
    ).all()
    grouped: dict[uuid.UUID, dict] = {}
    for result, subject, term in rows:
        item = grouped.setdefault(subject.id, {"subject_id": str(subject.id), "subject_name": subject.name, "terms": []})
        snapshot = result.published_snapshot or {}
        item["terms"].append({"term_id": str(term.id), "term_name": term.name, "total": snapshot.get("total", result.total)})
    for item in grouped.values():
        values = [float(row["total"]) for row in item["terms"] if row["total"] is not None]
        item["average"] = round(sum(values) / len(values), 2) if values else None
    return {"session": {"id": str(session_id), "name": terms[0].session.name}, "subjects": list(grouped.values())}


def _enrollment_for_term(
    db: Session, school_id: uuid.UUID, *, student_id: uuid.UUID, term_id: uuid.UUID
) -> StudentEnrollment:
    """The student's enrollment in the term's session — the same rule the
    report card uses. 404 when not enrolled."""
    get_student(db, school_id, student_id)
    term = get_term(db, school_id, term_id)
    env = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.academic_session_id == term.academic_session_id,
        )
    )
    if env is None:
        from ..core.errors import NotFoundError

        raise NotFoundError("Student is not enrolled in this term's session")
    return env


def can_comment_on(
    db: Session,
    school_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    has_comment_perm: bool,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
) -> bool:
    """Whether the actor may write a result comment for this student × term.

    Allowed for roles holding ``results.comment`` (principal / VP) and for the
    student's homeroom (class) teacher.
    """
    if has_comment_perm:
        return True
    try:
        env = _enrollment_for_term(db, school_id, student_id=student_id, term_id=term_id)
    except NotFoundError:
        return False
    arm = db.get(ClassArm, env.class_arm_id)
    if arm is None or arm.class_teacher_id is None:
        return False
    teacher = db.get(Staff, arm.class_teacher_id)
    return teacher is not None and teacher.user_id == actor_user_id


def list_psychomotor(
    db: Session, school_id: uuid.UUID, *, student_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """The psychomotor/affective rows for one student × term (report-card
    order: sort_order, then learning area)."""
    env = _enrollment_for_term(db, school_id, student_id=student_id, term_id=term_id)
    rows = db.scalars(
        select(PsychomotorAssessment)
        .where(
            PsychomotorAssessment.school_id == school_id,
            PsychomotorAssessment.student_enrollment_id == env.id,
            PsychomotorAssessment.term_id == term_id,
        )
        .order_by(PsychomotorAssessment.sort_order, PsychomotorAssessment.learning_area)
    ).all()
    return [
        {
            "learning_area": r.learning_area,
            "achievement_level": r.achievement_level,
        }
        for r in rows
    ]


def save_psychomotor(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    rows: list[dict],
    actor_id: uuid.UUID,
) -> list[dict]:
    """Replace the psychomotor rows for one student × term.

    The list is the source of truth — areas and levels are configurable data,
    so schools choose their own vocabulary (Excellent/Very Good/Good/Fair/
    Poor or A/B/C). Rows are deleted + reinserted atomically.
    """
    env = _enrollment_for_term(db, school_id, student_id=student_id, term_id=term_id)
    db.execute(
        sa_delete(PsychomotorAssessment).where(
            PsychomotorAssessment.school_id == school_id,
            PsychomotorAssessment.student_enrollment_id == env.id,
            PsychomotorAssessment.term_id == term_id,
        )
    )
    seen: set[str] = set()
    for order, item in enumerate(rows):
        area = item["learning_area"].strip()
        if not area or area in seen:
            continue
        seen.add(area)
        db.add(
            PsychomotorAssessment(
                school_id=school_id,
                student_enrollment_id=env.id,
                term_id=term_id,
                learning_area=area,
                achievement_level=item["achievement_level"].strip() or "Good",
                sort_order=order,
            )
        )
    db.flush()
    return list_psychomotor(db, school_id, student_id=student_id, term_id=term_id)


def compile_arm_subject(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
    permission_codes: set[str] | None = None,
    is_superadmin: bool = False,
) -> dict:
    """One-click compile: submit draft → verify → approve → publish.

    Runs the full approval pipeline for one arm × subject × term so the
    admin can finalize results in a single action. Returns a summary of
    how many results moved through each stage.
    """
    _require_active_term = None  # caller already checks
    require_assigned_teacher(
        db, school_id,
        actor_id=actor_id, arm_id=arm_id, subject_id=subject_id,
        permission_codes=permission_codes or set(), is_superadmin=is_superadmin,
    )

    submitted = submit_arm_subject(
        db, school_id, arm_id=arm_id, subject_id=subject_id,
        term_id=term_id, actor_id=actor_id,
        permission_codes=permission_codes, is_superadmin=is_superadmin,
    )
    verified = verify_arm_subject(
        db, school_id, arm_id=arm_id, subject_id=subject_id,
        term_id=term_id, actor_id=actor_id,
    )
    approved = approve_arm_subject(
        db, school_id, arm_id=arm_id, subject_id=subject_id,
        term_id=term_id, actor_id=actor_id,
    )
    published = publish_arm_subject(
        db, school_id, arm_id=arm_id, subject_id=subject_id,
        term_id=term_id, actor_id=actor_id,
    )
    return {
        "submitted": submitted,
        "verified": verified,
        "approved": approved,
        "published": published,
    }


def grade_bands_for_term(
    db: Session, school_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """The session's grading key for a term (school default scale fallback).

    Shared by the report card (printed grading key) and the live grade
    preview during score entry.
    """
    term = get_term(db, school_id, term_id)
    session = term.session
    scale_id = session.grade_scale_id if session is not None else None
    if scale_id is None:
        scale = db.scalar(
            select(GradeScale).where(
                GradeScale.school_id == school_id,
                GradeScale.is_default.is_(True),
            )
        )
        scale_id = scale.id if scale is not None else None
    bands = (
        db.scalars(
            select(GradeBand)
            .where(GradeBand.grade_scale_id == scale_id)
            .order_by(GradeBand.min_score.desc())
        ).all()
        if scale_id is not None
        else []
    )
    return [
        {
            "letter": b.letter,
            "min_score": float(b.min_score),
            "max_score": float(b.max_score),
            "remark": b.remark,
        }
        for b in bands
    ]


def report_card(
    db: Session, school_id: uuid.UUID, *, student_id: uuid.UUID, term_id: uuid.UUID
) -> dict:
    """The printable term report for one student: only published subjects,
    rendered from frozen snapshots, with class standing computed across the
    arm. Subjects not published yet are simply absent; 404 when none are."""
    term = get_term(db, school_id, term_id)
    student = get_student(db, school_id, student_id)
    env = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.academic_session_id == term.academic_session_id,
        )
    )
    if env is None:
        raise NotFoundError("Student is not enrolled in this term's session")
    arm = get_arm(db, school_id, env.class_arm_id)

    rows = db.execute(
        select(Result, Subject)
        .join(Subject, Subject.id == Result.subject_id)
        .where(
            Result.school_id == school_id,
            Result.student_enrollment_id == env.id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
        )
        .order_by(Subject.name)
    ).all()
    subject_rows = []
    for result, subject in rows:
        snap = result.published_snapshot or {}
        subject_rows.append(
            {
                "subject_id": str(subject.id),
                "subject_name": subject.name,
                "total": (
                    snap.get("total")
                    if snap.get("total") is not None
                    else (float(result.total) if result.total is not None else None)
                ),
                "grade_letter": snap.get("grade_letter") or result.grade_letter,
                "grade_point": snap.get("grade_point") or result.grade_point,
                "remark": snap.get("remark") or result.remark,
                "position": snap.get("position") or result.position,
                "components": snap.get("components", []),
                "is_core": subject.is_core,
            }
        )
    if not subject_rows:
        raise NotFoundError("No published results for this student in this term")

    # Class standing: rank this student's aggregate over classmates who have
    # at least one published subject.
    totals = _published_totals(db, school_id, arm_id=arm.id, term_id=term_id)
    aggregates = sorted(
        (round(sum(v), 2) for v in totals.values()), reverse=True
    )
    class_size = len(aggregates)
    mine_total = round(sum(totals.get(env.id, [])), 2)
    class_rank = (
        1 + sum(1 for t in aggregates if t > mine_total) if class_size else None
    )

    avg = round(mine_total / len(subject_rows), 2)
    session = term.session
    letter, point, remark = _grade_for(db, school_id, session, avg)

    # --- Premium card extras -------------------------------------------------
    school = db.get(School, school_id)
    school_settings = school.settings if school else {}
    motto = school_settings.get("motto") if isinstance(school_settings, dict) else None

    # Psychomotor / affective learning areas (dynamic list, averaged).
    psycho_rows = db.scalars(
        select(PsychomotorAssessment)
        .where(
            PsychomotorAssessment.school_id == school_id,
            PsychomotorAssessment.student_enrollment_id == env.id,
            PsychomotorAssessment.term_id == term_id,
        )
        .order_by(
            PsychomotorAssessment.sort_order,
            PsychomotorAssessment.learning_area,
        )
    ).all()
    psychomotor = [
        {
            "learning_area": p.learning_area,
            "achievement_level": p.achievement_level,
        }
        for p in psycho_rows
    ]
    psych_average = None
    if psycho_rows:
        points = [
            PSYCHOMOTOR_LEVELS.get(p.achievement_level, 3) for p in psycho_rows
        ]
        avg_point = round(sum(points) / len(points))
        psych_average = LEVEL_FOR_POINT.get(avg_point, "Good")

    # Attendance within this term's date window.
    attendance_pct = None
    if term.start_date is not None and term.end_date is not None:
        records = db.scalars(
            select(StudentAttendance).where(
                StudentAttendance.school_id == school_id,
                StudentAttendance.student_id == student_id,
                StudentAttendance.date >= term.start_date.isoformat(),
                StudentAttendance.date <= term.end_date.isoformat(),
            )
        ).all()
        if records:
            present = sum(1 for r in records if r.status in ("present", "late"))
            attendance_pct = round(present / len(records) * 100, 1)

    # Homeroom teacher (the arm's class teacher).
    homeroom_teacher = None
    if arm.class_teacher_id is not None:
        teacher = db.get(Staff, arm.class_teacher_id)
        if teacher is not None:
            homeroom_teacher = teacher.full_name

    # Grading key from the session's grade scale (fallback: school default).
    grading_key = grade_bands_for_term(db, school_id, term.id)

    # Next term begins: the following term in this session, else the first term
    # of the next session (by start date), else the current term's end date.
    next_term_date = None
    nxt = db.scalar(
        select(Term).where(
            Term.academic_session_id == session.id,
            Term.term_no == (term.term_no + 1),
        )
    )
    if nxt is not None:
        next_term_date = nxt.start_date
    if next_term_date is None:
        next_sessions = db.scalars(
            select(AcademicSession)
            .where(AcademicSession.school_id == school_id)
            .order_by(AcademicSession.start_date, AcademicSession.created_at)
        ).all()
        this_start = session.start_date or date.min
        for s in next_sessions:
            if s.id != session.id and (s.start_date or date.max) > this_start:
                first_term = db.scalar(
                    select(Term)
                    .where(Term.academic_session_id == s.id)
                    .order_by(Term.term_no)
                    .limit(1)
                )
                if first_term is not None:
                    next_term_date = first_term.start_date
                break
    if next_term_date is None and nxt is not None:
        next_term_date = nxt.end_date

    # Comments: one stored remark per role (principal / vice_principal /
    # homeroom). The card carries whatever has been saved for each slot.
    comment_rows = {
        c.role: c
        for c in db.scalars(
            select(ResultComment).where(
                ResultComment.school_id == school_id,
                ResultComment.student_enrollment_id == env.id,
                ResultComment.term_id == term_id,
            )
        ).all()
    }
    comments = {
        role: (comment_rows[role].body if role in comment_rows else None)
        for role in ("principal", "vice_principal", "homeroom")
    }

    # Best in core subject: subjects where this student holds the arm's top
    # score this term (ties supported).
    best_in_subjects = _best_in_core_subjects(
        db, school_id, arm_id=arm.id, term_id=term_id, env_id=env.id
    )

    return {
        "school": {
            "name": school.name if school else "School",
            "short_name": school.short_name if school else None,
            "motto": motto,
            "logo_url": school.logo_url if school else None,
        },
        "student": {
            "student_id": str(student.id),
            "admission_no": student.admission_no,
            "full_name": student.full_name,
            "gender": student.gender,
            "photo_url": student.photo_url,
            "date_of_birth": student.date_of_birth,
        },
        "enrollment_id": str(env.id),
        "term": {"id": str(term.id), "name": term.name},
        "session": {
            "id": str(term.academic_session_id),
            "name": session.name if session else str(term.academic_session_id),
        },
        "class_arm": {"id": str(arm.id), "full_name": arm.full_name},
        "academic_year": session.name if session else str(term.academic_session_id),
        "report_date": date.today(),
        "subjects": subject_rows,
        "psychomotor": psychomotor,
        "psychomotor_average": psych_average,
        "conduct": psych_average,
        "attendance_pct": attendance_pct,
        "homeroom_teacher": homeroom_teacher,
        "next_term_date": next_term_date,
        "next_term_label": (
            next_term_date.strftime("%A, %d %B %Y") if next_term_date else None
        ),
        "grading_key": grading_key,
        "comments": comments,
        "summary": {
            "subjects_published": len(subject_rows),
            "total": mine_total,
            "average": avg,
            "grade_letter": letter,
            "remark": remark,
            "class_rank": class_rank,
            "class_size": class_size,
        },
        "best_in_subjects": best_in_subjects,
    }