"""Student progress tracking: is this pupil getting better at each subject?

The question a school asks is never "what did she score" — the marks sheet already
says that. It is **"is she improving?"**, and that needs a comparison against the
pupil's own earlier work, never against the class. A child who scored 45 twice is
steady; a child who went 30 → 45 is improving even though 45 is the lower number
of the two in the class list.

Two signals, in order of authority:

  * **Across terms.** The term totals a pupil has for a subject in this session
    (First → Second → Third), whatever stage those results are at. Two or more
    terms are needed before anything is claimed.
  * **Within the current term.** When the session holds only one term — which is
    true of every school today — the assessment components are the only time
    series that exists, so the same question is asked of them: 1st CA → 2nd CA →
    Exam, each normalised to a percentage so different mark limits compare.

Anything less than two observations is reported as ``insufficient`` rather than
guessed at. The UI says "needs a second term" instead of inventing a direction.

Marks are read regardless of result status (draft, submitted, verified…), because
this is an internal monitoring view for the office, not a parent-facing document;
each term carries its status so nobody mistakes an in-progress term for a final
one. Published cards are the separate, frozen record.

Core subjects are whatever the school has flagged with ``Subject.is_core``. When
nothing is flagged — the case today, for every school — the whole curriculum the
class offers is tracked and ``core_configured`` says so, so the page can explain
how to narrow it rather than showing an empty screen.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from ..core.errors import NotFoundError, PremiumRequiredError
from ..models import (
    AcademicSession,
    ClassArm,
    School,
    Student,
    Subject,
    SubjectOffering,
    Term,
)
from ..models.results import AssessmentComponent, Result, Score
from . import people_service, results_service

# A change smaller than this is noise on a 0–100 scale, not a trend.
THRESHOLD = 2.0


@dataclass(frozen=True)
class Trend:
    direction: str  # improving | declining | steady | insufficient
    delta: float | None  # latest movement (last − previous)
    change: float | None  # first to last, for the whole series
    samples: int
    basis: str  # terms | components | none

    def as_dict(self) -> dict:
        return {
            "direction": self.direction,
            "delta": self.delta,
            "change": self.change,
            "samples": self.samples,
            "basis": self.basis,
        }


def classify(values: Sequence[float], *, basis: str, threshold: float = THRESHOLD) -> Trend:
    """The direction of a series of marks, and by how much.

    The direction uses the latest movement — the last two observations — because
    a child who rose in the first term and fell in the second is declining, and
    an average of the whole series would hide that. ``change`` carries the whole
    span for context.
    """
    clean = [float(v) for v in values if v is not None]
    if len(clean) < 2:
        return Trend("insufficient", None, None, len(clean), "none")
    delta = round(clean[-1] - clean[-2], 2)
    change = round(clean[-1] - clean[0], 2)
    if delta >= threshold:
        direction = "improving"
    elif delta <= -threshold:
        direction = "declining"
    else:
        direction = "steady"
    return Trend(direction, delta, change, len(clean), basis)


def require_progress(school: School) -> None:
    """Premium gate. Student progress tracking is sold separately from the core
    management plan, so this is a billing toggle on the school, not a permission:
    even the school owner is refused until the Clearis admin enables it."""
    if not bool((school.settings or {}).get("progress_enabled", False)):
        raise PremiumRequiredError(
            "Student progress tracking is a premium feature. Ask Clearis to enable it "
            "for your school."
        )


def progress_for_arm(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, session_id: uuid.UUID
) -> dict:
    """Every pupil in a class, per subject, with the direction they are moving in."""
    arm = db.get(ClassArm, arm_id)
    if arm is None or arm.school_id != school_id:
        raise NotFoundError("Class arm not found")
    session = db.get(AcademicSession, session_id)
    if session is None or session.school_id != school_id:
        raise NotFoundError("Academic session not found")

    terms = list(
        db.scalars(
            select(Term)
            .where(
                Term.school_id == school_id,
                Term.academic_session_id == session_id,
            )
            .order_by(Term.term_no)
        )
    )
    term_by_id = {term.id: term for term in terms}

    enrollments = people_service.list_enrollments(db, school_id, arm_id)
    enrollment_ids = [e.id for e in enrollments]
    if not enrollment_ids:
        return _empty(arm, session, [], False)

    students = {
        s.id: s
        for s in db.scalars(
            select(Student)
            .options(
                load_only(Student.id, Student.admission_no, Student.first_name,
                          Student.middle_name, Student.last_name, Student.gender)
            )
            .where(Student.id.in_([e.student_id for e in enrollments]))
        )
    }

    # The class's curriculum, in the order the class offers it.
    offered = list(
        db.execute(
            select(Subject)
            .join(SubjectOffering, SubjectOffering.subject_id == Subject.id)
            .where(
                SubjectOffering.class_arm_id == arm_id,
                Subject.school_id == school_id,
            )
            .order_by(SubjectOffering.sort_order, Subject.name)
        ).scalars()
    )
    core_configured = any(subject.is_core for subject in offered)
    tracked = [s for s in offered if s.is_core] if core_configured else offered

    # Term totals, whatever stage they are at — one query for the whole class.
    results = db.execute(
        select(
            Result.student_enrollment_id,
            Result.subject_id,
            Result.term_id,
            Result.total,
            Result.status,
        ).where(
            Result.school_id == school_id,
            Result.student_enrollment_id.in_(enrollment_ids),
        )
    ).all()

    # Component marks for the current session, normalised per component below.
    components: dict[uuid.UUID, list[AssessmentComponent]] = {}
    for term in terms:
        components[term.id] = results_service.effective_components(
            db, school_id, term.id, class_arm_id=arm_id
        )
    component_ids = [c.id for comps in components.values() for c in comps]
    scores = (
        db.execute(
            select(
                Score.student_enrollment_id,
                Score.subject_id,
                Score.assessment_component_id,
                Score.score,
            ).where(
                Score.school_id == school_id,
                Score.student_enrollment_id.in_(enrollment_ids),
                Score.assessment_component_id.in_(component_ids or [None]),
            )
        ).all()
        if component_ids
        else []
    )
    score_map: dict[tuple, float] = {
        (row.student_enrollment_id, row.subject_id, row.assessment_component_id): float(row.score)
        for row in scores
    }

    # Per (enrollment, subject): term totals and the latest term's component run.
    totals: dict[tuple, dict] = {}
    statuses: dict[tuple, str] = {}
    for row in results:
        if row.total is None:
            continue
        totals.setdefault((row.student_enrollment_id, row.subject_id), {})[row.term_id] = round(
            float(row.total), 2
        )
        statuses[(row.student_enrollment_id, row.subject_id, row.term_id)] = row.status

    student_rows = []
    for enrollment in enrollments:
        student = students.get(enrollment.student_id)
        if student is None:
            continue
        subjects_out = []
        per_term_overall: dict[uuid.UUID, list[float]] = {}
        for subject in tracked:
            term_series = []
            for term in terms:
                value = totals.get((enrollment.id, subject.id), {}).get(term.id)
                if value is None:
                    continue
                term_series.append({"term_id": str(term.id), "term_name": term.name, "value": value,
                                    "status": statuses.get((enrollment.id, subject.id, term.id))})
                per_term_overall.setdefault(term.id, []).append(value)

            # The within-term signal: this term's components, as percentages.
            component_series: list[dict] = []
            component_term = None
            term_trend = classify([row["value"] for row in term_series], basis="terms")
            if term_trend.direction == "insufficient":
                for term in reversed(terms):
                    comps = components.get(term.id, [])
                    run = [
                        (comp, score_map.get((enrollment.id, subject.id, comp.id)))
                        for comp in comps
                    ]
                    run = [(comp, value) for comp, value in run if value is not None]
                    if len(run) >= 2:
                        component_series = [
                            {
                                "component_id": str(comp.id),
                                "name": comp.name,
                                "percent": round(value / float(comp.max_score) * 100, 2)
                                if float(comp.max_score)
                                else None,
                            }
                            for comp, value in run
                        ]
                        component_term = term.name
                        break
            trend = (
                term_trend
                if term_trend.direction != "insufficient"
                else classify([row["percent"] for row in component_series], basis="components")
            )

            if not term_series and not component_series:
                continue
            latest = term_series[-1]["value"] if term_series else (
                component_series[-1]["percent"] if component_series else None
            )
            subjects_out.append(
                {
                    "subject_id": str(subject.id),
                    "subject_name": subject.name,
                    "is_core": bool(subject.is_core),
                    "latest": latest,
                    "trend": trend.as_dict(),
                    "terms": term_series,
                    "components": (
                        {"term_name": component_term, "series": component_series}
                        if component_series
                        else None
                    ),
                }
            )

        overall_series = [
            {
                "term_id": str(term.id),
                "term_name": term.name,
                "value": round(sum(values) / len(values), 2),
            }
            for term in terms
            if (values := per_term_overall.get(term.id))
        ]
        overall_trend = classify([row["value"] for row in overall_series], basis="terms")
        student_rows.append(
            {
                "student_id": str(student.id),
                "admission_no": student.admission_no,
                "full_name": student.full_name,
                "gender": student.gender,
                "overall": {"series": overall_series, "trend": overall_trend.as_dict()},
                "subjects": subjects_out,
            }
        )

    student_rows.sort(key=lambda row: (row["full_name"] or "").lower())
    return {
        "arm": {"id": str(arm.id), "full_name": arm.full_name},
        "session": {"id": str(session.id), "name": session.name},
        "terms": [{"id": str(t.id), "name": t.name, "term_no": t.term_no} for t in terms],
        "subjects": [
            {"id": str(s.id), "name": s.name, "is_core": bool(s.is_core)} for s in tracked
        ],
        "core_configured": core_configured,
        "students": student_rows,
    }


def _empty(arm: ClassArm, session: AcademicSession, terms: list, core_configured: bool) -> dict:
    return {
        "arm": {"id": str(arm.id), "full_name": arm.full_name},
        "session": {"id": str(session.id), "name": session.name},
        "terms": [{"id": str(t.id), "name": t.name, "term_no": t.term_no} for t in terms],
        "subjects": [],
        "core_configured": core_configured,
        "students": [],
    }