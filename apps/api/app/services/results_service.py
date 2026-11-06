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

import re
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import (
    ERR_ASSIGNMENT,
    ERR_RESULT_LOCKED,
    ERR_SCORE_NEGATIVE,
    ERR_SCORE_OVER_MAX,
    ERR_SCORESHEET,
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
    TermResultArchive,
    User,
)
from ..models.enums import ResultStatus
from . import sections_service
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


def assigned_pairs_for(
    db: Session,
    school_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool = False,
) -> set[tuple[uuid.UUID, uuid.UUID]] | None:
    """The arm x subject pairs an actor may *read*, or ``None`` for no limit.

    Reads that would otherwise expose the whole school's results — the readiness
    board, the approval workbench, a single scoresheet — are filtered through
    this. Platform super-admins and results supervisors (anyone holding a
    workflow permission) get ``None``: everything in the school. Everyone else
    gets exactly the pairs they are the assigned teacher of, which is the empty
    set for a teacher with no assignments — never the whole school.

    ``None`` and ``set()`` are deliberately different: the first means
    unrestricted, the second means restricted to nothing.
    """
    if is_superadmin or (permission_codes & _SUPERVISOR_PERMISSIONS):
        return None

    staff = db.scalar(
        select(Staff).where(
            Staff.school_id == school_id,
            Staff.user_id == actor_id,
            Staff.is_deleted.is_(False),
        )
    )
    if staff is None:
        return set()

    rows = db.execute(
        select(SubjectAssignment.class_arm_id, SubjectAssignment.subject_id).where(
            SubjectAssignment.school_id == school_id,
            SubjectAssignment.teacher_id == staff.id,
        )
    ).all()
    return {(arm_id, subject_id) for arm_id, subject_id in rows}


# --- Effective assessment components -----------------------------------------
def effective_components(
    db: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    *,
    class_arm_id: uuid.UUID | None = None,
    section: str | None = None,
) -> list[AssessmentComponent]:
    """Components applying to a scope.

    Precedence, most specific first: an arm's own rows, then its section's
    rows, then the school-wide rows. A section's set replaces the school-wide
    one wholesale rather than merging by name — a school that marks primary
    differently has decided those components *are* the primary scoresheet, so a
    school-wide "Exam" must not leak into it. Arm rows still merge by name on
    top of whichever set applies, as they always have.

    ``section`` is looked up from the arm when only an arm is given. The whole
    idea only applies to a school that has chosen separate sections; in "same"
    mode every class uses the school-wide rows exactly as before.
    """
    if section is None and class_arm_id is not None:
        arm = db.get(ClassArm, class_arm_id)
        if arm is not None and arm.school_id == school_id:
            section = arm.section

    use_sections = section is not None and sections_service.is_separate(db, school_id)

    rows = list(
        db.scalars(
            select(AssessmentComponent).where(
                AssessmentComponent.school_id == school_id,
                AssessmentComponent.term_id == term_id,
                AssessmentComponent.is_active.is_(True),
            )
        )
    )
    arm: dict[str, AssessmentComponent] = {}
    school_rows: list[AssessmentComponent] = []
    for comp in rows:
        if comp.class_arm_id is not None:
            if comp.class_arm_id == class_arm_id:
                arm[comp.name] = comp
        else:
            school_rows.append(comp)

    # A section's own rows replace the school-wide set wholesale; without one
    # — and always in "same" mode — the school-wide rows are the structure, and
    # any section rows the school set aside are not mixed into them.
    scoped = (
        [comp for comp in school_rows if comp.section == section]
        if use_sections
        else []
    )
    base_rows = scoped or [comp for comp in school_rows if comp.section is None]

    merged: dict[str, AssessmentComponent] = {}
    merged.update(arm)
    for comp in base_rows:
        merged.setdefault(comp.name, comp)
    return sorted(merged.values(), key=lambda c: (c.sort_order, c.name))


def ensure_default_components(
    db: Session, school_id: uuid.UUID, term_id: uuid.UUID
) -> list[AssessmentComponent]:
    """Create a term's components when it has none.

    The school's own scoresheet is used when it has saved one, so the structure
    it defined once carries into every new term — the school-wide set always,
    and each section's own set when the school keeps them separate. Until then
    the built-in trio is created exactly as before — a school that never opens
    the editor sees no change at all.
    """
    components = effective_components(db, school_id, term_id)
    if components:
        return components

    saved = scoresheet_for(db, school_id)
    if saved is None:
        _seed_components(db, school_id, term_id, None, DEFAULT_SCORESHEET)
    else:
        _seed_components(db, school_id, term_id, None, saved["default"])
        if sections_service.is_separate(db, school_id):
            for section, rows in saved["sections"].items():
                _seed_components(db, school_id, term_id, section, rows)
    db.flush()
    return effective_components(db, school_id, term_id)


def _seed_components(
    db: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    section: str | None,
    rows,
) -> None:
    for sort_order, row in enumerate(rows):
        db.add(
            AssessmentComponent(
                school_id=school_id,
                term_id=term_id,
                section=section,
                name=row["name"],
                max_score=row["max_score"],
                weight=row["weight"],
                sort_order=sort_order,
            )
        )


def validate_component_weights(components: list[AssessmentComponent]) -> None:
    """Weights across the effective set must sum to 100."""
    total = round(sum(float(c.weight) for c in components), 2)
    if abs(total - 100.0) > 0.01:
        raise APIError(
            422, ERR_WEIGHT_SUM,
            f"Assessment component weights must sum to 100 (currently {total})",
            {"weight_sum": total},
        )


# --- The school's scoresheet --------------------------------------------------
# A school defines its assessment structure once — what the components are
# called (1st CA, 2nd CA, 3rd CA, Exam, Project ...) and what each is marked
# out of — and it is in force until the school changes it. It lives in
# ``schools.settings["scoresheet"]`` so it travels with the tenant and needs no
# schema change, and every new term is seeded from it by
# ``ensure_default_components``.
#
# Each component's share of the final 100 is derived from its mark limit in
# proportion to the others. That keeps the "one number per row" promise: a
# school setting 1st CA 10, 2nd CA 10, 3rd CA 10, Exam 100 needs to understand
# only that the exam is marked out of 100, and the result is still on the 0-100
# scale grade bands, averages and positions all assume.
DEFAULT_SCORESHEET: tuple[dict, ...] = (
    {"name": "1st CA", "max_score": 20.0, "weight": 20.0},
    {"name": "2nd CA", "max_score": 30.0, "weight": 30.0},
    {"name": "Exam", "max_score": 70.0, "weight": 50.0},
)

MAX_SCORESHEET_COMPONENTS = 12


def _current_term(db: Session, school_id: uuid.UUID) -> Term | None:
    """The term a school is working in, if it has activated one."""
    return db.scalar(
        select(Term)
        .where(Term.school_id == school_id, Term.is_current.is_(True))
        .order_by(Term.term_no)
    )


def _term_has_published_results(
    db: Session, school_id: uuid.UUID, term_id: uuid.UUID
) -> bool:
    """Whether a term's results are already out — the point past which its
    scoresheet must not move."""
    published = db.scalar(
        select(func.count())
        .select_from(Result)
        .where(
            Result.school_id == school_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
        )
    )
    return bool(published)


def _clean_rows(raw) -> list[dict] | None:
    """One scoresheet's components, read defensively.

    It is hand-editable JSON, so anything malformed — a missing name, a zero
    mark, weights that no longer total 100 — falls back to the built-in
    default rather than breaking score entry or a report card.
    """
    if not isinstance(raw, list) or not raw:
        return None
    rows: list[dict] = []
    for order, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return None
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        try:
            max_score = float(entry.get("max_score"))
            weight = float(entry.get("weight"))
        except (TypeError, ValueError):
            return None
        if max_score <= 0 or weight <= 0:
            return None
        key = entry.get("key")
        rows.append(
            {
                "key": key if isinstance(key, str) and key else uuid.uuid4().hex,
                "name": " ".join(name.split()),
                "max_score": round(max_score, 2),
                "weight": round(weight, 2),
                "sort_order": order,
            }
        )
    if abs(round(sum(r["weight"] for r in rows), 2) - 100.0) > 0.01:
        return None
    return rows


def _clean_scoresheet(raw) -> dict | None:
    """The stored scoresheet as ``{"default": rows, "sections": {name: rows}}``.

    A bare list is the shape written before sections existed and reads as a
    school-wide scoresheet with no section of its own — the same structure
    every class uses, which is exactly what it was.
    """
    if isinstance(raw, list):
        rows = _clean_rows(raw)
        return {"default": rows, "sections": {}} if rows else None
    if not isinstance(raw, dict):
        return None
    default = _clean_rows(raw.get("default"))
    if default is None:
        return None
    sections: dict[str, list[dict]] = {}
    stored = raw.get("sections")
    if isinstance(stored, dict):
        for name in sections_service.SECTIONS:
            rows = _clean_rows(stored.get(name))
            if rows:
                sections[name] = rows
    return {"default": default, "sections": sections}


def scoresheet_for(db: Session, school_id: uuid.UUID) -> dict | None:
    """The school's own scoresheet, or None if it has never saved one."""
    school = db.get(School, school_id)
    raw = (school.settings or {}).get("scoresheet") if school else None
    return _clean_scoresheet(raw)


def scoresheet_rows_for(
    db: Session, school_id: uuid.UUID, section: str | None
) -> list[dict]:
    """The rows in force for a section: its own set, else the school-wide one.

    Mirrors ``effective_components`` for callers that want the structure before
    a term has any components of its own.
    """
    saved = scoresheet_for(db, school_id)
    if saved is None:
        return list(DEFAULT_SCORESHEET)
    if section is not None and sections_service.is_separate(db, school_id):
        rows = saved["sections"].get(section)
        if rows:
            return rows
    return saved["default"]


def _derive_weights(marks: list[float]) -> list[float]:
    """Each component's share of 100, in proportion to its mark limit.

    Rounded to two places, with the rounding residue put on the largest
    component so the set totals exactly 100 (``save_scores`` enforces that).
    """
    total = sum(marks)
    weights = [round(mark / total * 100.0, 2) for mark in marks]
    residue = round(100.0 - sum(weights), 2)
    if residue:
        index = max(range(len(weights)), key=lambda i: weights[i])
        weights[index] = round(weights[index] + residue, 2)
    return weights


def _normalise_rows(rows: list[dict], *, where: str = "") -> list[dict]:
    """Validate one scoresheet's components and derive their shares."""
    if not rows:
        raise APIError(
            422, ERR_SCORESHEET,
            f"The {where}scoresheet needs at least one component",
        )
    if len(rows) > MAX_SCORESHEET_COMPONENTS:
        raise APIError(
            422, ERR_SCORESHEET,
            f"A scoresheet can have at most {MAX_SCORESHEET_COMPONENTS} components",
        )

    cleaned: list[dict] = []
    seen: set[str] = set()
    for raw in rows:
        name = " ".join(str(raw.get("name") or "").split())
        if not name:
            raise APIError(422, ERR_SCORESHEET, f"Every {where}component needs a name")
        if len(name) > 60:
            raise APIError(
                422, ERR_SCORESHEET,
                f'"{name}" is too long — component names are at most 60 characters',
            )
        if name.casefold() in seen:
            raise APIError(
                422, ERR_SCORESHEET, f'"{name}" appears more than once'
            )
        seen.add(name.casefold())
        try:
            max_score = float(raw.get("max_score"))
        except (TypeError, ValueError):
            raise APIError(
                422, ERR_SCORESHEET, f'"{name}" needs a mark limit'
            )
        if max_score <= 0 or max_score > 1000:
            raise APIError(
                422, ERR_SCORESHEET,
                f'"{name}" must be marked out of a number between 1 and 1000',
            )
        key = raw.get("key")
        cleaned.append(
            {
                "key": key if isinstance(key, str) and key else uuid.uuid4().hex,
                "name": name,
                "max_score": round(max_score, 2),
            }
        )

    weights = _derive_weights([row["max_score"] for row in cleaned])
    for order, (row, weight) in enumerate(zip(cleaned, weights)):
        row["weight"] = weight
        row["sort_order"] = order
    return cleaned


def _normalise_scoresheet(payload: dict) -> dict:
    """Validate what a school saved: the school-wide scoresheet, and a set per
    section when it keeps its sections separate."""
    mode = payload.get("mode")
    if mode not in sections_service.SECTION_MODES:
        raise APIError(
            422, ERR_SCORESHEET,
            'Sections must be set to "same" or "separate"',
        )

    resolved: dict = {
        "default": _normalise_rows(list(payload.get("default") or [])),
        "sections": {},
    }
    raw_sections = payload.get("sections") or {}
    if not isinstance(raw_sections, dict):
        raise APIError(422, ERR_SCORESHEET, "Sections must be a set of scoresheets")
    for section in sections_service.SECTIONS:
        rows = raw_sections.get(section)
        if rows is None:
            continue
        resolved["sections"][section] = _normalise_rows(
            list(rows), where=f"{sections_service.SECTION_LABELS[section].lower()} "
        )
    return resolved


def _sync_term_components(
    db: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    rows: list[dict],
    previous: list[dict],
    *,
    section: str | None = None,
) -> None:
    """Make one scope's school-wide components match its scoresheet.

    ``section`` is the scope: None for the school-wide set, or the section
    whose own set this is. Components are matched to existing rows by their
    stable ``key`` (falling back to the name), so renaming a row updates the
    component in place and the scores already entered against it survive. Rows
    no longer in the scoresheet are deactivated, never deleted — their score
    cells stay for the record. Arm-level overrides are left untouched.
    """
    existing = list(
        db.scalars(
            select(AssessmentComponent).where(
                AssessmentComponent.school_id == school_id,
                AssessmentComponent.term_id == term_id,
                AssessmentComponent.class_arm_id.is_(None),
                AssessmentComponent.section == section,
            )
        )
    )
    by_name = {comp.name: comp for comp in existing}
    by_key = {row["key"]: row for row in previous}

    matched: list[tuple[AssessmentComponent | None, dict]] = []
    used_ids: set[int] = set()
    for row in rows:
        comp = None
        before = by_key.get(row["key"])
        if before is not None:
            comp = by_name.get(before["name"])
        if comp is None:
            comp = by_name.get(row["name"])
        if comp is not None:
            used_ids.add(id(comp))
        matched.append((comp, row))

    # Deactivate what the school removed before touching names, so a rename
    # cannot collide with the row it is replacing.
    for comp in existing:
        if id(comp) not in used_ids:
            comp.is_active = False

    # Park renamed components under a unique name so switching two rows' names
    # (or reusing a deactivated row's name) cannot trip the uniqueness index.
    for comp, row in matched:
        if comp is not None and comp.name != row["name"]:
            comp.name = f"__pending__{uuid.uuid4().hex[:12]}"
    db.flush()

    for comp, row in matched:
        if comp is None:
            db.add(
                AssessmentComponent(
                    school_id=school_id,
                    term_id=term_id,
                    class_arm_id=None,
                    section=section,
                    name=row["name"],
                    max_score=row["max_score"],
                    weight=row["weight"],
                    sort_order=row["sort_order"],
                    is_active=True,
                )
            )
            continue
        comp.name = row["name"]
        comp.max_score = row["max_score"]
        comp.weight = row["weight"]
        comp.sort_order = row["sort_order"]
        comp.is_active = True
    db.flush()


def scoresheet_state(db: Session, school_id: uuid.UUID) -> dict:
    """What the school's scoresheet is, and where it applies right now.

    Always answers with the school-wide set, each section's own set where the
    school has one, and every report card design pinned to a section.
    """
    from . import report_card_service  # local: keeps the module graph acyclic

    saved = scoresheet_for(db, school_id)
    term = _current_term(db, school_id)
    locked = bool(
        term is not None
        and saved is not None
        and _term_has_published_results(db, school_id, term.id)
    )

    if saved is not None:
        default = saved["default"]
        sections = dict(saved["sections"])
    else:
        components = (
            effective_components(db, school_id, term.id) if term is not None else []
        )
        if components:
            default = [
                {
                    "key": str(comp.id),
                    "name": comp.name,
                    "max_score": float(comp.max_score),
                    "weight": float(comp.weight),
                    "sort_order": order,
                }
                for order, comp in enumerate(components)
            ]
        else:
            default = [
                {**row, "key": f"default-{order}", "sort_order": order}
                for order, row in enumerate(DEFAULT_SCORESHEET)
            ]
        sections = {}

    return {
        "mode": sections_service.mode_for(db, school_id),
        "default": default,
        "sections": {
            section: (
                sections[section]
                if section in sections
                else [
                    {**row, "sort_order": order}
                    for order, row in enumerate(default)
                ]
            )
            for section in sections_service.SECTIONS
        },
        "marks_total": round(sum(float(row["max_score"]) for row in default), 2),
        "is_custom": saved is not None,
        "applied_term_id": term.id if term is not None else None,
        "applied_term_name": term.name if term is not None else None,
        "locked": locked,
        "report_cards": report_card_service.report_card_sections(db, school_id),
    }


def update_scoresheet(
    db: Session, school_id: uuid.UUID, payload: dict
) -> dict:
    """Store the school's structure and put it in force for the current term.

    Storing it is always allowed — it is what future terms will inherit. The
    current term is updated too unless its results are already published, in
    which case the change waits for the next term rather than altering marks a
    school has handed out.
    """
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")

    previous = scoresheet_for(db, school_id) or {"default": [], "sections": {}}
    resolved = _normalise_scoresheet(payload)

    settings = dict(school.settings or {})
    settings["section_mode"] = payload["mode"]
    settings["scoresheet"] = resolved
    school.settings = settings
    db.flush()

    term = _current_term(db, school_id)
    if term is None or _term_has_published_results(db, school_id, term.id):
        return scoresheet_state(db, school_id)

    _sync_term_components(
        db, school_id, term.id, resolved["default"], previous["default"]
    )
    for section in sections_service.SECTIONS:
        rows = resolved["sections"].get(section)
        before = previous["sections"].get(section)
        if not rows and not before:
            continue
        _sync_term_components(
            db, school_id, term.id, rows or [], before or [], section=section
        )

    return scoresheet_state(db, school_id)


# --- Per-school results policy ------------------------------------------------
# A school can ask for the final term's card to show the session average built
# from every term's average, not just the current term. It is opt-in because it
# is a school's academic policy, not a platform-wide rule: the default card is
# unchanged, and the switch lives in the school's own settings bucket.
DEFAULT_RESULTS_POLICY: dict = {
    "combine_previous_terms": False,
    "final_term_no": 3,
}


def results_policy_for(db: Session, school_id: uuid.UUID) -> dict:
    """The school's results policy, with every missing key defaulted.

    Stored in ``schools.settings["results_policy"]`` so it travels with the
    tenant and needs no schema change per policy. Unknown/legacy values fall
    back to the defaults rather than failing a report card render.
    """
    school = db.get(School, school_id)
    raw = (school.settings or {}).get("results_policy") if school else None
    policy = dict(DEFAULT_RESULTS_POLICY)
    if isinstance(raw, dict):
        if isinstance(raw.get("combine_previous_terms"), bool):
            policy["combine_previous_terms"] = raw["combine_previous_terms"]
        try:
            final_term = int(raw.get("final_term_no", policy["final_term_no"]))
        except (TypeError, ValueError):
            final_term = policy["final_term_no"]
        policy["final_term_no"] = min(6, max(1, final_term))
    return policy


def update_results_policy(
    db: Session,
    school_id: uuid.UUID,
    *,
    combine_previous_terms: bool,
    final_term_no: int,
) -> dict:
    """Persist the policy on the school, returning the stored shape."""
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")
    settings = dict(school.settings or {})
    settings["results_policy"] = {
        "combine_previous_terms": bool(combine_previous_terms),
        "final_term_no": min(6, max(1, int(final_term_no))),
    }
    school.settings = settings
    db.flush()
    return results_policy_for(db, school_id)


def _result_enrollments(
    db: Session, school_id: uuid.UUID, arm_id: uuid.UUID
) -> list[StudentEnrollment]:
    """Every enrollment in the arm — the population a term's results belong to.

    Unlike the roster default, this includes completed enrollments: a term can
    be reopened after promotion, and its score grid, workbench and report-card
    index must still show the students who sat it.
    """
    return list_enrollments(db, school_id, arm_id, include_inactive=True)


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
    enrollments = _result_enrollments(db, school_id, arm_id)

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
    """Grade band lookup using the session's grade scale (fallback: school default).

    If no grade scale or bands are configured, falls back to a standard
    grading scale: A (70–100), B (60–69), C (50–59), D (40–49), F (<40).
    """
    scale_id = session.grade_scale_id
    if scale_id is None:
        scale = db.scalar(
            select(GradeScale).where(
                GradeScale.school_id == school_id, GradeScale.is_default.is_(True)
            )
        )
        scale_id = scale.id if scale else None
    if scale_id is not None:
        band = db.scalar(
            select(GradeBand).where(
                GradeBand.grade_scale_id == scale_id,
                GradeBand.min_score <= total,
                GradeBand.max_score >= total,
            )
        )
        if band is not None:
            return band.letter, float(band.point), band.remark
    # Fallback: standard grading scale
    if total >= 70:
        return "A", 4.0, None
    if total >= 60:
        return "B", 3.0, None
    if total >= 50:
        return "C", 2.0, None
    if total >= 40:
        return "D", 1.0, None
    return "F", 0.0, None


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
    """Subjects that count as a results cell at the arm (drives grids +
    readiness).

    A cell exists when the arm *offers* the subject or a teacher is *assigned*
    to it. Critically, it also exists when the arm already carries *scores or
    results* for the subject: a teacher can open a grid and save marks for any
    subject in their arm, so readiness and the approval workbench must never
    hide scores that were genuinely entered — otherwise an admin cannot see or
    process them.
    """
    arm = db.get(ClassArm, arm_id)
    if arm is None:
        return []

    subject_ids: set[uuid.UUID] = set()
    subject_ids.update(
        db.scalars(
            select(SubjectOffering.subject_id).where(
                SubjectOffering.class_arm_id == arm.id
            )
        ).all()
    )
    subject_ids.update(
        db.scalars(
            select(SubjectAssignment.subject_id).where(
                SubjectAssignment.class_arm_id == arm.id
            )
        ).all()
    )
    subject_ids.update(
        db.scalars(
            select(Result.subject_id).where(Result.class_arm_id == arm.id)
        ).all()
    )
    subject_ids.update(
        db.scalars(
            select(Score.subject_id).where(Score.class_arm_id == arm.id)
        ).all()
    )

    subjects = [db.get(Subject, sid) for sid in subject_ids]
    return sorted(
        (s for s in subjects if s is not None and s.school_id == arm.school_id),
        key=lambda s: s.name,
    )


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
    for env in _result_enrollments(db, school_id, arm_id):
        recompute_result(
            db, school_id,
            enrollment_id=env.id, subject_id=subject_id, term_id=term.id,
            session=session, components=components, arm_id=arm_id,
        )
    _recompute_positions(db, school_id, arm_id, subject_id, term_id)


def _group_arms(
    db: Session, school_id: uuid.UUID, arm: ClassArm
) -> list[ClassArm]:
    """Every arm ranked together with ``arm``: the classes sharing its
    ``group_name`` in the same session. An arm with no group is a group of one,
    which is what makes the feature opt-in — an ungrouped school ranks exactly
    as it did before class groups existed."""
    if not arm.group_name:
        return [arm]
    return list(
        db.scalars(
            select(ClassArm)
            .where(
                ClassArm.school_id == school_id,
                ClassArm.academic_session_id == arm.academic_session_id,
                ClassArm.group_name == arm.group_name,
            )
            .order_by(ClassArm.full_name, ClassArm.id)
        )
    )


def _group_arm_ids(
    db: Session, school_id: uuid.UUID, arm: ClassArm
) -> list[uuid.UUID]:
    return [a.id for a in _group_arms(db, school_id, arm)]


def _recompute_positions(
    db: Session,
    school_id: uuid.UUID,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
) -> None:
    """Rank one subject's results for a term across the whole class group.

    The ranking population is every arm in ``arm_id``'s group (just the one arm
    when it has no group). A pupil who does not offer the subject has no result
    row at all, so they are simply absent from the ranking rather than scored
    zero — subjects are per-class offerings, and a Commercial pupil is not
    ranked in Physics.
    """
    # The totals this ranks were usually staged by the caller a moment ago
    # (``recompute_result`` adds a row per pupil but does not flush it), and a
    # session with ``autoflush=False`` — the test harness, and any session built
    # that way — would otherwise rank an empty set and leave every position
    # null. Flush so the ranking always sees the rows it is meant to rank.
    db.flush()
    arm = get_arm(db, school_id, arm_id)
    rows = list(
        db.scalars(
            select(Result).where(
                Result.class_arm_id.in_(_group_arm_ids(db, school_id, arm)),
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
    cards and the public portal render immutable totals.

    Positions are re-ranked across the whole class group first, so a class is
    never published against a half-filled group.
    """
    _recompute_positions(db, school_id, arm_id, subject_id, term_id)
    arm = get_arm(db, school_id, arm_id)
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
    _refresh_group_positions(
        db, school_id,
        arm=arm, subject_id=subject_id, term_id=term_id, exclude_arm_id=arm_id,
    )
    db.flush()
    return len(rows)


def _refresh_group_positions(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm: ClassArm,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    exclude_arm_id: uuid.UUID,
) -> None:
    """Keep an already-published class's frozen ``position`` in step with its
    class group.

    A report card is immutable, with one deliberate exception: position is
    relative to the group, so it has to track the group. Publishing SS 1 Science
    before SS 1 Arts must not leave Science's cards claiming a standing out of
    22 that the school reads as out of 27. Only ``position`` is rewritten —
    ``total``, ``grade_letter``, ``grade_point`` and the component scores stay
    frozen exactly as published.

    A no-op for an arm with no group: its group is itself, so there are no
    siblings and nothing is touched.
    """
    sibling_ids = [
        group_arm.id
        for group_arm in _group_arms(db, school_id, arm)
        if group_arm.id != exclude_arm_id
    ]
    if not sibling_ids:
        return
    for result in db.scalars(
        select(Result).where(
            Result.class_arm_id.in_(sibling_ids),
            Result.subject_id == subject_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
        )
    ):
        snapshot = dict(result.published_snapshot or {})
        if snapshot.get("position") == result.position:
            continue
        snapshot["position"] = result.position
        # Reassign rather than mutate: SQLAlchemy only sees a JSONB change when
        # the attribute is set to a new object.
        result.published_snapshot = snapshot


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
    enrollments = _result_enrollments(db, school_id, arm_id)
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
    """Per-arm per-subject progress for the readiness dashboard.

    This used to ask the database two questions per student per subject per
    class (does a score exist? has their result been submitted?), which is
    thousands of round trips on a real school and made the dashboard take
    seconds. The work is now a fixed handful of grouped queries: one for the
    classes, one for their current enrollments, one per source of subjects, and
    one each for the score cells and result statuses.
    """
    arms = list(
        db.scalars(
            select(ClassArm)
            .where(ClassArm.school_id == school_id)
            .order_by(ClassArm.full_name)
        )
    )
    if not arms:
        return []
    arm_ids = [arm.id for arm in arms]

    enrollments_by_arm: dict[uuid.UUID, list[uuid.UUID]] = {arm_id: [] for arm_id in arm_ids}
    enrollment_ids: list[uuid.UUID] = []
    # ``completed`` enrollments are part of the class for a term that has
    # already been closed (and possibly promoted away). Without them a reopened
    # past term would show an empty readiness board.
    for enrollment_id, arm_id in db.execute(
        select(StudentEnrollment.id, StudentEnrollment.class_arm_id).where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.class_arm_id.in_(arm_ids),
            StudentEnrollment.status.in_(("active", "completed")),
        )
    ).all():
        enrollments_by_arm[arm_id].append(enrollment_id)
        enrollment_ids.append(enrollment_id)

    # A subject counts for an arm when it is offered, assigned to a teacher, or
    # already carries results/scores there — the same rule as _subjects_for_arm.
    subject_ids_by_arm: dict[uuid.UUID, set[uuid.UUID]] = {arm_id: set() for arm_id in arm_ids}
    subject_pairs = [
        *db.execute(
            select(SubjectOffering.class_arm_id, SubjectOffering.subject_id).where(
                SubjectOffering.class_arm_id.in_(arm_ids)
            )
        ).all(),
        *db.execute(
            select(SubjectAssignment.class_arm_id, SubjectAssignment.subject_id).where(
                SubjectAssignment.class_arm_id.in_(arm_ids)
            )
        ).all(),
        *db.execute(
            select(Result.class_arm_id, Result.subject_id)
            .where(Result.class_arm_id.in_(arm_ids))
            .distinct()
        ).all(),
        *db.execute(
            select(Score.class_arm_id, Score.subject_id)
            .where(Score.class_arm_id.in_(arm_ids))
            .distinct()
        ).all(),
    ]
    for arm_id, subject_id in subject_pairs:
        subject_ids_by_arm[arm_id].add(subject_id)

    subject_ids = {sid for ids in subject_ids_by_arm.values() for sid in ids}
    subjects = (
        {
            subject.id: subject
            for subject in db.scalars(
                select(Subject).where(
                    Subject.school_id == school_id, Subject.id.in_(subject_ids)
                )
            )
        }
        if subject_ids
        else {}
    )

    entered_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    result_status: dict[tuple[uuid.UUID, uuid.UUID], str] = {}
    if enrollment_ids and subject_ids:
        entered_pairs = {
            (subject_id, enrollment_id)
            for subject_id, enrollment_id in db.execute(
                select(Score.subject_id, Score.student_enrollment_id)
                .where(
                    Score.student_enrollment_id.in_(enrollment_ids),
                    Score.subject_id.in_(subject_ids),
                )
                .distinct()
            ).all()
        }
        result_status = {
            (subject_id, enrollment_id): status
            for subject_id, enrollment_id, status in db.execute(
                select(
                    Result.subject_id, Result.student_enrollment_id, Result.status
                ).where(
                    Result.school_id == school_id,
                    Result.term_id == term_id,
                    Result.student_enrollment_id.in_(enrollment_ids),
                    Result.subject_id.in_(subject_ids),
                )
            ).all()
        }

    submitted_statuses = {
        ResultStatus.SUBMITTED.value,
        ResultStatus.VERIFIED.value,
        ResultStatus.APPROVED.value,
        ResultStatus.PUBLISHED.value,
    }

    rows: list[dict] = []
    for arm in arms:
        arm_subjects = sorted(
            (subjects[sid] for sid in subject_ids_by_arm[arm.id] if sid in subjects),
            key=lambda subject: subject.name,
        )
        arm_enrollments = enrollments_by_arm[arm.id]
        total = len(arm_enrollments)
        for subject in arm_subjects:
            entered = sum(
                1 for eid in arm_enrollments if (subject.id, eid) in entered_pairs
            )
            submitted = sum(
                1
                for eid in arm_enrollments
                if (subject.id, eid) in entered_pairs
                and result_status.get((subject.id, eid)) in submitted_statuses
            )
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
        enrollments = _result_enrollments(db, school_id, arm.id)
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
# `published_snapshot`. Totals, grades and component scores can never drift
# after publish, so the printed card is an immutable record. The one exception
# is `position`, which is relative to the class group and so is refreshed when a
# sibling class in the group publishes (see ``_refresh_group_positions``).
def _published_totals(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_ids: Sequence[uuid.UUID],
    term_id: uuid.UUID,
) -> dict[uuid.UUID, list[float]]:
    """Published per-subject totals (from frozen snapshots), grouped by
    enrollment, for one class group (or a single class, when its group is
    itself) x term."""
    tbl: dict[uuid.UUID, list[float]] = {}
    if not arm_ids:
        return tbl
    # Deliberately not ``list_enrollments``: that only returns *current*
    # enrollments, but a card from a closed (possibly promoted-away) session
    # still needs its class standing. Every enrollment in these arms belongs to
    # the arms' session, which is the population the published results came
    # from.
    env_ids = list(
        db.scalars(
            select(StudentEnrollment.id).where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.class_arm_id.in_(arm_ids),
            )
        )
    )
    if not env_ids:
        return tbl
    for result in db.scalars(
        select(Result).where(
            Result.school_id == school_id,
            Result.class_arm_id.in_(arm_ids),
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


def _grouped_subject_totals(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    term_ids: list[uuid.UUID],
    core_only: bool = False,
) -> dict[uuid.UUID, dict]:
    """Published totals per subject across an arm and one or more terms.

    ``scorers`` maps enrollment id to the student's summed published total and
    the number of terms that contributed, so a single-term call and a whole
    session call share one query (the session view divides by ``terms`` to get
    the subject average). Published snapshots are the source, exactly like the
    card, so a printed card and this list agree.

    Unlike the card's ``_grouped_core_totals``, this includes every subject that
    has published results — the leadership list is the school's record of who
    topped each subject, not only the designated core ones. Pass
    ``core_only=True`` to mirror the card.
    """
    groups: dict[uuid.UUID, dict] = {}
    if not term_ids:
        return groups
    stmt = (
        select(Result, Subject, StudentEnrollment, Student)
        .join(Subject, Subject.id == Result.subject_id)
        .join(StudentEnrollment, StudentEnrollment.id == Result.student_enrollment_id)
        .join(Student, Student.id == StudentEnrollment.student_id)
        .where(
            Result.school_id == school_id,
            Result.class_arm_id == arm_id,
            Result.term_id.in_(term_ids),
            Result.status == ResultStatus.PUBLISHED.value,
        )
    )
    if core_only:
        stmt = stmt.where(Subject.is_core.is_(True))
    for result, subject, env, stu in db.execute(stmt).all():
        snap = result.published_snapshot or {}
        total = snap.get("total")
        if total is None:
            total = result.total
        if total is None:
            continue
        g = groups.setdefault(
            subject.id,
            {"subject_id": subject.id, "name": subject.name, "scorers": {}},
        )
        scorer = g["scorers"].setdefault(
            str(env.id), {"name": stu.full_name, "total": 0.0, "terms": 0}
        )
        scorer["total"] += float(total)
        scorer["terms"] += 1
    return groups


def _top_scorers(scorers: list[dict], key: str) -> tuple[float, list[dict]]:
    """The highest value on ``key`` and everyone who holds it (ties included)."""
    top = max(s[key] for s in scorers)
    leaders = sorted((s for s in scorers if s[key] == top), key=lambda s: s["name"])
    return top, leaders


def _session_terms(
    db: Session, school_id: uuid.UUID, session_id: uuid.UUID
) -> list[Term]:
    """Every term of a session, in order — the units a session average spans."""
    session = db.scalar(
        select(AcademicSession).where(
            AcademicSession.id == session_id,
            AcademicSession.school_id == school_id,
        )
    )
    if session is None:
        raise NotFoundError("Academic session not found")
    return list(
        db.scalars(
            select(Term)
            .where(
                Term.school_id == school_id,
                Term.academic_session_id == session_id,
            )
            .order_by(Term.term_no)
        )
    )


def best_in_subjects_for_term(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """Every subject's top score and its leaders in an arm × term.

    This is the term half of the leadership list. It covers all published
    subjects (the card's ribbon stays core-only) and is empty until at least
    one result has been published.
    """
    get_arm(db, school_id, arm_id)
    get_term(db, school_id, term_id)
    out: list[dict] = []
    for g in _grouped_subject_totals(
        db, school_id, arm_id=arm_id, term_ids=[term_id]
    ).values():
        if not g["scorers"]:
            continue
        top, leaders = _top_scorers(list(g["scorers"].values()), "total")
        out.append(
            {
                "subject_id": str(g["subject_id"]),
                "subject_name": g["name"],
                "top_score": round(top, 2),
                "leader_count": len(leaders),
                "leaders": [s["name"] for s in leaders],
            }
        )
    out.sort(key=lambda r: r["subject_name"])
    return out


def best_in_subjects_for_session(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, session_id: uuid.UUID
) -> list[dict]:
    """Every subject's session leader in an arm.

    A student's session mark for a subject is the mean of the published term
    totals for it, so terms with no published result are skipped rather than
    dragging the average down. The leader is the highest such mean; ties are
    kept together.
    """
    get_arm(db, school_id, arm_id)
    terms = _session_terms(db, school_id, session_id)
    out: list[dict] = []
    for g in _grouped_subject_totals(
        db,
        school_id,
        arm_id=arm_id,
        term_ids=[t.id for t in terms],
    ).values():
        if not g["scorers"]:
            continue
        for scorer in g["scorers"].values():
            scorer["average"] = (
                round(scorer["total"] / scorer["terms"], 2) if scorer["terms"] else 0.0
            )
        top, leaders = _top_scorers(list(g["scorers"].values()), "average")
        out.append(
            {
                "subject_id": str(g["subject_id"]),
                "subject_name": g["name"],
                "top_average": top,
                # How many terms the subject was published in — the page labels
                # the session column with this so a two-term session is honest.
                "term_count": max(s["terms"] for s in g["scorers"].values()),
                "leader_count": len(leaders),
                "leaders": [s["name"] for s in leaders],
            }
        )
    out.sort(key=lambda r: r["subject_name"])
    return out


def best_in_subjects_breakdown(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, session_id: uuid.UUID
) -> dict:
    """Term-by-term and whole-session subject leaders for one arm.

    One payload for the leadership report: ``terms`` holds a block per term that
    has published results, and ``session_subjects`` the averaged leaders across
    the session. Both cover every published subject.
    """
    arm = get_arm(db, school_id, arm_id)
    session = db.scalar(
        select(AcademicSession).where(
            AcademicSession.id == session_id,
            AcademicSession.school_id == school_id,
        )
    )
    if session is None:
        raise NotFoundError("Academic session not found")
    terms_payload: list[dict] = []
    for term in _session_terms(db, school_id, session_id):
        subjects = best_in_subjects_for_term(
            db, school_id, arm_id=arm_id, term_id=term.id
        )
        if not subjects:
            continue
        terms_payload.append(
            {
                "term_id": str(term.id),
                "term_name": term.name,
                "term_no": term.term_no,
                "subjects": subjects,
            }
        )
    return {
        "arm": {"id": str(arm.id), "full_name": arm.full_name},
        "session": {"id": str(session.id), "name": session.name},
        "terms": terms_payload,
        "session_subjects": best_in_subjects_for_session(
            db, school_id, arm_id=arm_id, session_id=session_id
        ),
    }


def report_index(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """Which students in an arm have published results this term — the 'cards
    ready to print' index. Everyone in the arm is listed (with
    ``subjects_published = 0`` for those still pending), so the UI can show
    who is ready and who isn't."""
    get_arm(db, school_id, arm_id)
    get_term(db, school_id, term_id)
    enrollments = _result_enrollments(db, school_id, arm_id)
    tally = _published_totals(db, school_id, arm_ids=[arm_id], term_id=term_id)
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
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID | None = None,
    arm_ids: Sequence[uuid.UUID] | None = None,
    term_id: uuid.UUID,
) -> list[dict]:
    """All printable cards for one class — or several, when a class group is
    asked for — this term (published only). Students with no published subjects
    are skipped — same rule as the single-card endpoint."""
    if arm_ids is None:
        if arm_id is None:
            raise ValidationError("Either arm_id or arm_ids is required")
        arm_ids = [arm_id]
    cards = []
    for target in arm_ids:
        for row in report_index(db, school_id, arm_id=target, term_id=term_id):
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


def broadsheet_group(
    db: Session,
    school_id: uuid.UUID,
    *,
    group_name: str,
    session_id: uuid.UUID,
    term_id: uuid.UUID,
) -> list[dict]:
    """The class group's broadsheet: every published card in the group, in
    position order.

    Cards carry each pupil's *own* subjects, so a sheet drawn over SS 1 has
    Science, Arts and Commercial subjects side by side with a pupil blank
    wherever their class does not offer a subject. Ordering by the group
    standing is what makes it readable as one list rather than three.
    """
    term = get_term(db, school_id, term_id)
    if term.academic_session_id != session_id:
        raise ValidationError("That term does not belong to that session")
    arms = list(
        db.scalars(
            select(ClassArm)
            .where(
                ClassArm.school_id == school_id,
                ClassArm.academic_session_id == session_id,
                ClassArm.group_name == group_name,
            )
            .order_by(ClassArm.full_name, ClassArm.id)
        )
    )
    if not arms:
        raise NotFoundError(f"No classes are grouped as {group_name!r}")
    cards = report_cards_bulk(
        db, school_id, arm_ids=[a.id for a in arms], term_id=term_id
    )
    cards.sort(
        key=lambda card: (
            card["summary"].get("class_rank") is None,
            card["summary"].get("class_rank") or 0,
            card["class_arm"]["full_name"],
            card["student"]["full_name"],
        )
    )
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


def is_homeroom_teacher(
    db: Session,
    school_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
) -> bool:
    """Whether the actor is the homeroom (class) teacher of the student's arm
    for the given term — i.e. the arm's ``class_teacher`` account is theirs.
    """
    try:
        env = _enrollment_for_term(db, school_id, student_id=student_id, term_id=term_id)
    except NotFoundError:
        return False
    arm = db.get(ClassArm, env.class_arm_id)
    if arm is None or arm.class_teacher_id is None:
        return False
    teacher = db.get(Staff, arm.class_teacher_id)
    return teacher is not None and teacher.user_id == actor_user_id


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
    return is_homeroom_teacher(
        db, school_id, actor_user_id=actor_user_id, student_id=student_id, term_id=term_id
    )


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


def _published_subject_totals(
    db: Session, school_id: uuid.UUID, *, enrollment_id: uuid.UUID, term_id: uuid.UUID
) -> list[dict]:
    """Published subject totals for one enrollment in one term, from snapshots."""
    rows = db.execute(
        select(Result, Subject)
        .join(Subject, Subject.id == Result.subject_id)
        .where(
            Result.school_id == school_id,
            Result.student_enrollment_id == enrollment_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
        )
        .order_by(Subject.name)
    ).all()
    out: list[dict] = []
    for result, subject in rows:
        snap = result.published_snapshot or {}
        total = snap.get("total")
        if total is None:
            total = result.total
        if total is None:
            continue
        out.append(
            {
                "subject_id": str(subject.id),
                "subject_name": subject.name,
                "total": float(total),
            }
        )
    return out


def cumulative_for_term(
    db: Session,
    school_id: uuid.UUID,
    *,
    enrollment_id: uuid.UUID,
    term: Term,
) -> dict:
    """Term-by-term averages and the session average for one student.

    The school's rule is "the final term's card also shows the average of the
    term averages": each term's average is the mean of that term's published
    subject totals, and the session average is the mean of those term averages.
    Only terms with published results count, so an incomplete session shows the
    record that genuinely exists instead of a zero.

    Published snapshots are the source, exactly like the card itself, so an
    archived card and a live one agree.
    """
    terms = list(
        db.scalars(
            select(Term)
            .where(
                Term.school_id == school_id,
                Term.academic_session_id == term.academic_session_id,
            )
            .order_by(Term.term_no)
        )
    )
    per_term: list[dict] = []
    subjects: dict[str, dict] = {}
    for sibling in terms:
        rows = _published_subject_totals(
            db, school_id, enrollment_id=enrollment_id, term_id=sibling.id
        )
        if not rows:
            continue
        average = round(sum(row["total"] for row in rows) / len(rows), 2)
        per_term.append(
            {
                "term_id": str(sibling.id),
                "term_name": sibling.name,
                "term_no": sibling.term_no,
                "average": average,
                "subjects_published": len(rows),
            }
        )
        for row in rows:
            item = subjects.setdefault(
                row["subject_id"],
                {
                    "subject_id": row["subject_id"],
                    "subject_name": row["subject_name"],
                    "terms": [],
                },
            )
            item["terms"].append(
                {
                    "term_id": str(sibling.id),
                    "term_name": sibling.name,
                    "term_no": sibling.term_no,
                    "total": row["total"],
                }
            )

    for item in subjects.values():
        values = [row["total"] for row in item["terms"] if row["total"] is not None]
        item["average"] = round(sum(values) / len(values), 2) if values else None

    current = next((row for row in per_term if row["term_id"] == str(term.id)), None)
    session_average = (
        round(sum(row["average"] for row in per_term) / len(per_term), 2)
        if per_term
        else None
    )
    return {
        "terms": per_term,
        "term_average": current["average"] if current else None,
        "session_average": session_average,
        "subjects": sorted(subjects.values(), key=lambda row: row["subject_name"]),
    }


def report_card(
    db: Session, school_id: uuid.UUID, *, student_id: uuid.UUID, term_id: uuid.UUID
) -> dict:
    """The printable term report for one student: only published subjects,
    rendered from frozen snapshots, with class standing computed across the
    student's whole class group. Subjects not published yet are simply absent;
    404 when none are."""
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

    # Class standing: rank this pupil against everyone in the class group who
    # has at least one published subject.
    #
    # By AVERAGE, not by sum of totals. Inside one class the two rank the same,
    # but a group is made of classes offering different numbers of subjects
    # (SS 1 Science sits nine, SS 1 Arts eight), and ranking by sum would simply
    # reward whichever stream teaches the most subjects. The average asks the
    # question the school actually means: how well did this child do in the
    # subjects they offer?
    totals = _published_totals(
        db, school_id, arm_ids=_group_arm_ids(db, school_id, arm), term_id=term_id
    )
    mine_total = round(sum(totals.get(env.id, [])), 2)
    avg = round(mine_total / len(subject_rows), 2)
    averages = sorted(
        (round(sum(v) / len(v), 2) for v in totals.values() if v), reverse=True
    )
    class_size = len(averages)
    class_rank = 1 + sum(1 for a in averages if a > avg) if class_size else None

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

    # Opt-in cumulative block: only on the school's configured final term, and
    # only when the school has turned the policy on. The default card carries
    # no extra section.
    policy = results_policy_for(db, school_id)
    cumulative = None
    if policy["combine_previous_terms"] and term.term_no == policy["final_term_no"]:
        cumulative = cumulative_for_term(
            db, school_id, enrollment_id=env.id, term=term
        )
        cumulative["final_term_no"] = policy["final_term_no"]

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
        # The class's section rides along so an archived card can be redrawn in
        # the design its own section prints with.
        "class_arm": {
            "id": str(arm.id),
            "full_name": arm.full_name,
            "section": arm.section,
        },
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
            # The class group the standing was taken over ("SS 1"), so the card
            # can say what the position is a position *in*. Null when the class
            # stands alone — then it is a position in the class, as before.
            "class_group": arm.group_name or None,
        },
        "best_in_subjects": best_in_subjects,
        "cumulative": cumulative,
    }


# --- Reopening a term: archive the old cards, then unlock the rows -------------
def archive_term_results(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID,
    reason: str,
    actor_id: uuid.UUID | None = None,
) -> TermResultArchive | None:
    """Freeze every published card of a term.

    Called when a term closes (the archive is the record of every completed
    term) and, for a term closed before archiving existed, before it is
    reopened. Returns ``None`` when the term has no published results — there is
    nothing a parent could be holding, so no archive row is written. The card
    payload is the same document the report-card screen printed, including the
    layout that was live at the time; restoring a card later therefore displays
    the exact version, not today's template.
    """
    from fastapi.encoders import jsonable_encoder

    from . import report_card_service  # local: keeps the module graph acyclic

    term = get_term(db, school_id, term_id)
    published = db.execute(
        select(Result.student_enrollment_id, Result.class_arm_id)
        .where(
            Result.school_id == school_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
        )
        .distinct()
    ).all()
    if not published:
        return None

    cards: list[dict] = []
    seen_students: set[uuid.UUID] = set()
    class_ids: set[uuid.UUID] = set()
    for enrollment_id, class_arm_id in published:
        env = db.get(StudentEnrollment, enrollment_id)
        if env is None or env.student_id in seen_students:
            continue
        try:
            card = report_card(
                db, school_id, student_id=env.student_id, term_id=term_id
            )
        except NotFoundError:
            continue
        cards.append(card)
        seen_students.add(env.student_id)
        class_ids.add(class_arm_id)

    if not cards:
        return None

    cards.sort(
        key=lambda card: (
            card["class_arm"]["full_name"],
            card["student"]["full_name"],
        )
    )
    session = db.get(AcademicSession, term.academic_session_id)
    actor = db.get(User, actor_id) if actor_id is not None else None
    now = utcnow()
    version = (
        db.scalar(
            select(func.max(TermResultArchive.version)).where(
                TermResultArchive.school_id == school_id,
                TermResultArchive.term_id == term.id,
            )
        )
        or 0
    ) + 1

    archive = TermResultArchive(
        school_id=school_id,
        term_id=term.id,
        academic_session_id=term.academic_session_id,
        version=version,
        reason=reason,
        archived_by=actor_id,
        archived_at=now,
        student_count=len(cards),
        class_count=len(class_ids),
        payload={
            "archived_at": now.isoformat(),
            "archived_by_name": actor.full_name if actor is not None else None,
            "reason": reason,
            "term": {
                "id": str(term.id),
                "name": term.name,
                "term_no": term.term_no,
            },
            "session": {
                "id": str(term.academic_session_id),
                "name": session.name if session is not None else None,
            },
            "layout": report_card_service.default_layout(db, school_id),
            # A school that keeps its sections separate prints its cards in more
            # than one design, so every section's is frozen, not just the
            # school-wide one.
            "layouts": {
                section: report_card_service.default_layout(
                    db, school_id, section=section
                )
                for section in sections_service.SECTIONS
            },
            # Dates (report_date, next_term_date) are Python ``date`` objects on
            # the card dict; normalise them the same way the HTTP response does
            # so the JSONB column accepts the payload.
            "students": jsonable_encoder(cards),
        },
    )
    db.add(archive)
    db.flush()
    return archive


def latest_term_archive(
    db: Session, school_id: uuid.UUID, *, term_id: uuid.UUID
) -> TermResultArchive | None:
    """The most recent archive version of one term, if it has one."""
    return db.scalar(
        select(TermResultArchive)
        .where(
            TermResultArchive.school_id == school_id,
            TermResultArchive.term_id == term_id,
        )
        .order_by(TermResultArchive.version.desc())
        .limit(1)
    )


def list_term_archives(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> list[TermResultArchive]:
    """The school's archive, newest first, optionally narrowed to a term/session."""
    query = select(TermResultArchive).where(TermResultArchive.school_id == school_id)
    if term_id is not None:
        query = query.where(TermResultArchive.term_id == term_id)
    if session_id is not None:
        query = query.where(TermResultArchive.academic_session_id == session_id)
    return list(db.scalars(query.order_by(TermResultArchive.archived_at.desc())))


def get_term_archive(
    db: Session, school_id: uuid.UUID, archive_id: uuid.UUID
) -> TermResultArchive:
    """One archive row, scoped to the school so another tenant's id is a 404."""
    row = db.scalar(
        select(TermResultArchive).where(
            TermResultArchive.id == archive_id,
            TermResultArchive.school_id == school_id,
        )
    )
    if row is None:
        raise NotFoundError("Result archive not found")
    return row


def archive_summary(row: TermResultArchive) -> dict:
    """The list-row shape: metadata only, never the whole card payload."""
    payload = row.payload or {}
    term = payload.get("term") or {}
    session = payload.get("session") or {}
    return {
        "id": row.id,
        "term_id": row.term_id,
        "term_name": term.get("name"),
        "term_no": term.get("term_no"),
        "session_id": row.academic_session_id,
        "session_name": session.get("name"),
        "version": row.version,
        "reason": row.reason,
        "archived_at": row.archived_at,
        "archived_by_name": payload.get("archived_by_name"),
        "student_count": row.student_count,
        "class_count": row.class_count,
    }


def reset_term_for_reopen(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str,
) -> int:
    """Send a term's in-flight/published results back to draft.

    Called only after the cards have been archived. Score cells are untouched,
    so the grid still opens on the values the school entered; what changes is
    that the rows may be edited and re-compiled through the normal pipeline.
    Every reset is journaled with the reopen reason.
    """
    rows = list(
        db.scalars(
            select(Result).where(
                Result.school_id == school_id,
                Result.term_id == term_id,
                Result.status != ResultStatus.DRAFT.value,
            )
        )
    )
    now = utcnow()
    for result in rows:
        previous = result.status
        result.status = ResultStatus.DRAFT.value
        result.submitted_at = None
        result.approved_at = None
        result.approved_by = None
        result.published_at = None
        result.published_snapshot = None
        db.add(
            ResultEvent(
                school_id=school_id,
                result_id=result.id,
                actor_id=actor_id,
                action="reopen",
                from_status=previous,
                to_status=ResultStatus.DRAFT.value,
                note=reason,
                created_at=now,
            )
        )
    db.flush()
    return len(rows)