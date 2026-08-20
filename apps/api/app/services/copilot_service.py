"""School copilot: deterministic, data-grounded Q&A over a school's own data.

The final Phase 2 roadmap item. Like the other AI engines it honors "no fake
implementations":

* Local + deterministic: a catalog of question *intents* resolvable from the
  school's real rows (counts, enrollments, offerings, published results). Every
  answer is composed from actual numbers — nothing is invented or random.
* Honest about its limits: a question the engine can't resolve to a recognized
  intent is answered with a plain "I couldn't understand — here's what I can
  answer" (plus example phrasings), never a fabricated number.
* Published-only for performance questions: top performers, subject averages,
  term summaries and student reports read exclusively from the frozen
  ``published_snapshot`` of ``Result`` rows at ``published`` status — the same
  record report cards and the public portal render. Entry-progress questions
  (readiness) read live score counts by design.
* Metered exactly like slices 4–6: each assistant turn writes one ``AiUsage``
  row + one monthly ``UsageMeter`` bump under feature ``ai.copilot`` via
  ``ai_service._meter_inc``. Wiring a real LLM later only swaps the
  composition function; permissions, storage, and telemetry stay.

Conversations carry context: last-resolved slots (arm / subject /
student / term) persist between turns so follow-ups like "what about English?"
or "how many boys?" resolve against prior answers.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..models import (
    AcademicSession,
    ClassArm,
    CopilotConversation,
    CopilotMessage,
    Result,
    Student,
    StudentEnrollment,
    Subject,
    Term,
)
from ..models.enums import ResultStatus
from .ai_service import AI_FEATURE_COPILOT, _meter_inc
from .academics_service import (
    current_term,
    get_term,
    list_offerings,
    list_subjects,
)
from .people_service import list_enrollments, list_staff, list_students
from .results_service import readiness_for_term

# ----------------------------------------------------------------------------
# Matching helpers
# ----------------------------------------------------------------------------


def _tokens(q: str) -> set[str]:
    """Lowercased alphanumeric tokens of a question (ignores punctuation)."""
    return set(re.findall(r"[a-z0-9]+", (q or "").lower()))


def _name_in(tokens: set[str], name: str) -> bool:
    """True when every significant token of ``name`` appears among ``tokens``,
    matching exactly or through a shared 4-char stem (so "maths" resolves
    "Mathematics" and "1a" resolves "1A")."""
    nt = [t for t in _tokens(name) if len(t) >= 2]
    if not nt:
        return False
    return all(
        any(
            t == u or (len(t) >= 4 and len(u) >= 4 and t[:4] == u[:4])
            for u in tokens
        )
        for t in nt
    )


def _has(tokens: set[str], *words: str) -> bool:
    """True when any of ``words`` is a token of the question. Pass plurals too
    ("boy", "boys") — tokens are matched exactly here."""
    for w in words:
        wt = _tokens(w)
        if wt and wt <= tokens:
            return True
    return False


# ----------------------------------------------------------------------------
# Slot resolvers — everything resolved against the school's real rows
# ----------------------------------------------------------------------------


def _resolve_subject(
    db: Session, school_id: uuid.UUID, tokens: set[str]
) -> Subject | None:
    for s in list_subjects(db, school_id):
        if _name_in(tokens, s.name):
            return s
    return None


def _resolve_arm(db: Session, school_id: uuid.UUID, tokens: set[str]) -> ClassArm | None:
    arms = list(db.scalars(select(ClassArm).where(ClassArm.school_id == school_id)))
    for arm in arms:
        if _name_in(tokens, arm.full_name):
            return arm
    return None


def _resolve_student(
    db: Session, school_id: uuid.UUID, tokens: set[str]
) -> tuple[Student | None, str | None]:
    """Resolve a student by admission no or full name. When several students
    match, return an honest ambiguity message instead of guessing."""
    students = list_students(db, school_id)
    for s in students:
        if s.admission_no and _name_in(tokens, s.admission_no):
            return s, None
    candidates = [s for s in students if _name_in(tokens, s.full_name)]
    if len(candidates) == 1:
        return candidates[0], None
    if len(candidates) > 1:
        return None, (
            "Several students match that name. Please give the full name or "
            "admission number."
        )
    return None, None


def _terms_for_school(db: Session, school_id: uuid.UUID) -> list[Term]:
    return list(
        db.scalars(
            select(Term)
            .join(AcademicSession, AcademicSession.id == Term.academic_session_id)
            .where(AcademicSession.school_id == school_id)
            .order_by(Term.term_no)
        )
    )


def _first_arm(db: Session, school_id: uuid.UUID) -> ClassArm | None:
    return db.scalar(
        select(ClassArm)
        .where(ClassArm.school_id == school_id)
        .order_by(ClassArm.full_name)
    )


def _resolve_term(
    db: Session,
    school_id: uuid.UUID,
    question: str,
    conv_term_id: uuid.UUID | None,
) -> Term | None:
    """Conversation scope wins; otherwise an explicit term name in the question
    ("Second Term"); otherwise the school's current term."""
    if conv_term_id is not None:
        try:
            return get_term(db, school_id, conv_term_id)
        except NotFoundError:
            return None
    tokens = _tokens(question)
    for term in _terms_for_school(db, school_id):
        if _name_in(tokens, term.name):
            return term
    return current_term(db, school_id)


# --- context slot resolvers (follow-ups carry prior answers forward) ----------
def _ctx_arm(db: Session, school_id: uuid.UUID, context: dict) -> ClassArm | None:
    raw = context.get("arm_id")
    if not raw:
        return None
    try:
        return db.get(ClassArm, uuid.UUID(str(raw)))
    except (ValueError, TypeError):
        return None


def _ctx_subject(db: Session, school_id: uuid.UUID, context: dict) -> Subject | None:
    raw = context.get("subject_id")
    if not raw:
        return None
    try:
        return db.get(Subject, uuid.UUID(str(raw)))
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------------
# Published results (the immutable record the copilot quotes)
# ----------------------------------------------------------------------------


def _published_rows(
    db: Session,
    school_id: uuid.UUID,
    *,
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
) -> list[dict]:
    """Every published result for an arm (optionally one subject), rendered from
    frozen ``published_snapshot`` — the same record report cards use."""
    stmt = (
        select(Result, Student, StudentEnrollment, Subject)
        .join(StudentEnrollment, StudentEnrollment.id == Result.student_enrollment_id)
        .join(Student, Student.id == StudentEnrollment.student_id)
        .join(Subject, Subject.id == Result.subject_id)
        .where(
            Result.school_id == school_id,
            Result.class_arm_id == arm_id,
            Result.term_id == term_id,
            Result.status == ResultStatus.PUBLISHED.value,
        )
    )
    if subject_id is not None:
        stmt = stmt.where(Result.subject_id == subject_id)
    rows: list[dict] = []
    for result, student, _env, subject in db.execute(stmt):
        snap = result.published_snapshot or {}
        total = (
            snap.get("total")
            if snap.get("total") is not None
            else (float(result.total) if result.total is not None else None)
        )
        rows.append(
            {
                "student_id": str(student.id),
                "admission_no": student.admission_no,
                "full_name": student.full_name,
                "gender": student.gender,
                "subject_id": str(subject.id),
                "subject_name": subject.name,
                "total": total,
                "grade_letter": snap.get("grade_letter") or result.grade_letter,
                "position": snap.get("position") or result.position,
            }
        )
    return rows


# ----------------------------------------------------------------------------
# Intent handlers. Uniform signature:
#     handler(db, school_id, *, question, tokens, term, context)
# returns (text, payload, updated_context) or None when it doesn't apply.
# Handlers run in order; the first match wins.
# ----------------------------------------------------------------------------


def _h_help(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    **_,
) -> tuple[str, dict, dict] | None:
    if "help" in tokens or "what can you do" in question.lower():
        text = (
            "I can answer questions about this school from its own records — "
            "student and staff counts, what subjects a class offers, result "
            "entry progress, published scores, top performers and class "
            "averages. Try: 'how many students are enrolled?', 'what subjects "
            "does JSS 1A offer?', 'who scored highest in Mathematics?', or "
            "'how did Aisha Bello do this term?'."
        )
        return text, {"intent": "help"}, {}
    return None


def _h_class_subjects(
    db: Session, school_id: uuid.UUID, *, tokens: set[str], context: dict, **_
) -> tuple[str, dict, dict] | None:
    if not _has(tokens, "subject", "subjects", "offer", "offers", "taught"):
        return None
    arm = _resolve_arm(db, school_id, tokens) or _ctx_arm(db, school_id, context)
    if arm is None:
        return None
    offerings = list_offerings(db, school_id, arm.id)
    names = sorted({o.subject.name for o in offerings})
    label = arm.full_name
    ctx = {
        **context,
        "arm_id": str(arm.id),
    }
    if not names:
        text = f"No subjects are set up for {label} yet."
    else:
        text = (
            f"{label} offers {len(names)} subject"
            f"{'s' if len(names) != 1 else ''}: {_join_names(names)}."
        )
    payload = {"class": label, "subject_names": names}
    return text, payload, ctx


def _h_class_snapshot(
    db: Session, school_id: uuid.UUID, *, tokens: set[str], context: dict, **_
) -> tuple[str, dict, dict] | None:
    if not _has(
        tokens, "student", "students", "boy", "boys", "girl", "girls", "enrolled"
    ):
        return None
    arm = _resolve_arm(db, school_id, tokens) or _ctx_arm(db, school_id, context)
    if arm is None:
        return None
    gender = (
        "male" if _has(tokens, "boy", "boys") else ("female" if _has(tokens, "girl", "girls") else None)
    )
    if arm is not None:
        rows = list_enrollments(db, school_id, arm.id)
        label = arm.full_name
        ctx = {**context, "arm_id": str(arm.id)}
    boys = sum(1 for env in rows if env.student.gender == "male")
    girls = sum(1 for env in rows if env.student.gender == "female")
    total = len(rows)
    if gender == "male":
        text = f"There are {boys} boy{'s' if boys != 1 else ''} in {label}."
    elif gender == "female":
        text = f"There are {girls} girl{'s' if girls != 1 else ''} in {label}."
    else:
        text = (
            f"{label} has {total} enrolled student{'s' if total != 1 else ''} "
            f"({boys} boy{'s' if boys != 1 else ''}, {girls} girl"
            f"{'s' if girls != 1 else ''})."
        )
    payload = {"class": label, "enrolled": total, "boys": boys, "girls": girls}
    return text, payload, ctx


def _h_student_report(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    term: Term | None,
    context: dict,
) -> tuple[str, dict, dict] | None:
    if not (
        _has(tokens, "report", "perform", "doing")
        or ("how" in tokens and "did" in tokens)
    ):
        return None
    student, ambiguity = _resolve_student(db, school_id, tokens)
    if ambiguity:
        return ambiguity, {"intent": "student_report", "ambiguous": True}, context
    if student is None:
        return None
    if term is None:
        return (
            "No term is set for this conversation — pick a term to see results.",
            {"intent": "student_report"},
            context,
        )
    from .results_service import report_card

    try:
        card = report_card(db, school_id, student_id=student.id, term_id=term.id)
    except NotFoundError:
        return (
            f"{student.full_name} has no published results for {term.name} yet.",
            {
                "intent": "student_report",
                "student": _student_brief(student),
                "term": term.name,
                "unpublished": True,
            },
            {**context, "student_id": str(student.id)},
        )
    summary = card["summary"]
    parts = [
        f"{card['student']['full_name']} ({card['student']['admission_no']}) "
        f"sits in {card['class_arm']['full_name']}."
    ]
    parts.append(
        f"For {card['term']['name']} they have {summary['subjects_published']} "
        f"published subject{'s' if summary['subjects_published'] != 1 else ''} "
        f"totalling {summary['total']} (average {summary['average']}, grade "
        f"{summary['grade_letter']})."
    )
    if summary.get("class_rank") is not None and summary.get("class_size"):
        parts.append(f"Class standing: {summary['class_rank']} of {summary['class_size']}.")
    return (
        " ".join(parts),
        {
            "intent": "student_report",
            "student": _student_brief(student),
            "term": card["term"],
            "class_arm": card["class_arm"],
            "summary": summary,
            "subjects": card["subjects"],
        },
        {**context, "student_id": str(student.id)},
    )


def _h_subject_average(
    db: Session,
    school_id: uuid.UUID,
    *,
    tokens: set[str],
    term: Term | None,
    context: dict,
    **_
) -> tuple[str, dict, dict] | None:
    if not _has(tokens, "average", "mean", "avg"):
        return None
    subject = _resolve_subject(db, school_id, tokens) or _ctx_subject(db, school_id, context)
    if subject is None:
        return None
    if term is None:
        return (
            "No term is set for this conversation — pick a term to see results.",
            {"intent": "subject_average"},
            context,
        )
    arm = _resolve_arm(db, school_id, tokens) or _ctx_arm(db, school_id, context)
    arm = arm or _first_arm(db, school_id)
    rows = _published_rows(
        db, school_id, arm_id=arm.id, term_id=term.id, subject_id=subject.id
    )
    totals = [r["total"] for r in rows if r["total"] is not None]
    if not totals:
        return (
            f"No published scores for {subject.name} in {arm.full_name} for "
            f"{term.name} yet.",
            {
                "intent": "subject_average",
                "term": term.name,
                "arm": arm.full_name,
                "subject": subject.name,
                "published": 0,
            },
            {**context, "subject_id": str(subject.id), "arm_id": str(arm.id)},
        )
    avg = round(sum(totals) / len(totals), 2)
    text = (
        f"Average score in {subject.name} for {arm.full_name} in {term.name} "
        f"is {avg:.2f} across {len(totals)} published result"
        f"{'s' if len(totals) != 1 else ''}."
    )
    return (
        text,
        {
            "intent": "subject_average",
            "term": term.name,
            "arm": arm.full_name,
            "subject": subject.name,
            "published": len(totals),
            "average": avg,
            "min": min(totals),
            "max": max(totals),
        },
        {**context, "subject_id": str(subject.id), "arm_id": str(arm.id)},
    )


def _h_top_performers(
    db: Session,
    school_id: uuid.UUID,
    *,
    tokens: set[str],
    term: Term | None,
    context: dict,
    **_
) -> tuple[str, dict, dict] | None:
    if not _has(
        tokens, "top", "best", "highest", "scored", "performers", "rank", "ranking"
    ):
        return None
    subject = _resolve_subject(db, school_id, tokens) or _ctx_subject(db, school_id, context)
    if subject is None:
        return None
    if term is None:
        return (
            "No term is set for this conversation — pick a term to see results.",
            {"intent": "top_performers"},
            context,
        )
    arm = _resolve_arm(db, school_id, tokens) or _ctx_arm(db, school_id, context)
    arm = arm or _first_arm(db, school_id)
    rows = _published_rows(
        db, school_id, arm_id=arm.id, term_id=term.id, subject_id=subject.id
    )
    rows = [r for r in rows if r["total"] is not None]
    rows.sort(key=lambda r: r["total"], reverse=True)
    top = rows[:3]
    if not top:
        return (
            f"No published results for {subject.name} in {arm.full_name} for "
            f"{term.name} yet.",
            {
                "intent": "top_performers",
                "term": term.name,
                "arm": arm.full_name,
                "subject": subject.name,
                "rows": [],
            },
            {**context, "subject_id": str(subject.id), "arm_id": str(arm.id)},
        )
    names = _join_names([f"{r['full_name']} ({r['total']:.0f})" for r in top])
    text = (
        f"Top scorer{'s' if len(top) != 1 else ''} in {subject.name} "
        f"({arm.full_name}, {term.name}): {names}, ranked from published results."
    )
    return (
        text,
        {
            "intent": "top_performers",
            "term": term.name,
            "arm": arm.full_name,
            "subject": subject.name,
            "rows": top,
        },
        {**context, "subject_id": str(subject.id), "arm_id": str(arm.id)},
    )


def _h_term_summary(
    db: Session,
    school_id: uuid.UUID,
    *,
    tokens: set[str],
    term: Term | None,
    context: dict,
    **_
) -> tuple[str, dict, dict] | None:
    if not (_has(tokens, "overall", "summary", "generally", "perform") or "term" in tokens):
        return None
    if term is None:
        return (
            "No term is set for this conversation — pick a term to see results.",
            {"intent": "term_summary"},
            context,
        )
    arm = _resolve_arm(db, school_id, tokens) or _ctx_arm(db, school_id, context)
    arm = arm or _first_arm(db, school_id)
    rows = _published_rows(db, school_id, arm_id=arm.id, term_id=term.id)
    if not rows:
        return (
            f"No published results for {arm.full_name} in {term.name} yet — "
            f"approve and publish results first.",
            {
                "intent": "term_summary",
                "term": term.name,
                "arm": arm.full_name,
                "published_cards": 0,
            },
            {**context, "arm_id": str(arm.id)},
        )
    per_student: dict[str, list[float]] = {}
    for r in rows:
        per_student.setdefault(r["student_id"], []).append(r["total"])
    aggregates = sorted(
        ((sid, round(sum(v), 2)) for sid, v in per_student.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    class_average = round(sum(t for _, t in aggregates) / len(aggregates), 2)
    top_id, top_total = aggregates[0]
    top_name = next(r["full_name"] for r in rows if r["student_id"] == top_id)
    text = (
        f"For {term.name}, {arm.full_name} has {len(aggregates)} student"
        f"{'s' if len(aggregates) != 1 else ''} with published results; the "
        f"class average is {class_average:.2f}. Top student: {top_name} "
        f"({top_total:.0f})."
    )
    return (
        text,
        {
            "intent": "term_summary",
            "term": term.name,
            "arm": arm.full_name,
            "published_cards": len(aggregates),
            "class_average": class_average,
            "top": {"full_name": top_name, "total": top_total},
        },
        {**context, "arm_id": str(arm.id)},
    )


def _h_readiness(
    db: Session,
    school_id: uuid.UUID,
    *,
    tokens: set[str],
    term: Term | None,
    context: dict,
    **_
) -> tuple[str, dict, dict] | None:
    if not _has(
        tokens, "readiness", "entry", "progress", "submitted", "entered", "status"
    ):
        return None
    if term is None:
        return (
            "No term is set for this conversation — pick a term to see readiness.",
            {"intent": "readiness"},
            context,
        )
    rows = readiness_for_term(db, school_id, term.id)
    by_arm: dict[str, dict] = {}
    for r in rows:
        agg = by_arm.setdefault(
            r["arm_name"],
            {
                "arm_name": r["arm_name"],
                "students": r["student_count"],
                "entered": 0,
                "submitted": 0,
            },
        )
        agg["entered"] += r["entered"]
        agg["submitted"] += r["submitted"]
    summaries: list[dict] = []
    lines: list[str] = []
    for arm_name in sorted(by_arm):
        agg = by_arm[arm_name]
        summaries.append(agg)
        lines.append(
            f"{arm_name}: {agg['entered']}/{agg['students']} students entered, "
            f"{agg['submitted']} submitted"
        )
    if not summaries:
        return (
            f"No arms have score entry recorded for {term.name}.",
            {"intent": "readiness", "term": term.name, "arms": []},
            context,
        )
    return (
        f"Score entry for {term.name} — " + "; ".join(lines) + ".",
        {"intent": "readiness", "term": term.name, "arms": summaries},
        context,
    )


def _h_school_overview(
    db: Session, school_id: uuid.UUID, *, tokens: set[str], **_
) -> tuple[str, dict, dict] | None:
    if not _has(tokens, "how", "many", "overview", "count", "enrolled"):
        return None
    students = len(list_students(db, school_id))
    teachers = len(list_staff(db, school_id, membership_type="teaching"))
    arms = len(list(db.scalars(select(ClassArm).where(ClassArm.school_id == school_id))))
    subjects = len(list_subjects(db, school_id))
    if _has(tokens, "student", "students") and not (
        _has(tokens, "teacher", "staff")
        or _has(tokens, "subject", "subjects")
        or _has(tokens, "arm", "arms", "class", "classes")
    ):
        text = f"There are {students} enrolled student{'s' if students != 1 else ''}."
        payload = {"students": students}
    elif _has(tokens, "teacher", "staff"):
        text = f"There are {teachers} teaching staff on record."
        payload = {"teachers": teachers}
    elif _has(tokens, "subject", "subjects"):
        text = f"There are {subjects} subject{'s' if subjects != 1 else ''} set up."
        payload = {"subjects": subjects}
    elif _has(tokens, "arm", "arms") or _has(tokens, "class", "classes"):
        text = f"The school runs {arms} class arm{'s' if arms != 1 else ''}."
        payload = {"arms": arms}
    else:
        text = (
            f"This school has {students} enrolled students, {teachers} teaching "
            f"staff, {subjects} subjects, and {arms} class arms."
        )
        payload = {
            "students": students,
            "teachers": teachers,
            "subjects": subjects,
            "arms": arms,
        }
    return text, payload, {}


_INTERNAL_ORDER = [
    ("help", _h_help),
    ("class_subjects", _h_class_subjects),
    ("class_snapshot", _h_class_snapshot),
    ("student_report", _h_student_report),
    ("subject_average", _h_subject_average),
    ("top_performers", _h_top_performers),
    ("term_summary", _h_term_summary),
    ("readiness", _h_readiness),
    ("school_overview", _h_school_overview),
]


def _answer(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    term: Term | None,
    context: dict,
) -> tuple[str, str, dict, dict]:
    """Resolve a question to an intent. Returns (intent, text, payload,
    updated_context). Unknown questions answer honestly — never fabricated."""
    tokens = _tokens(question)
    for intent, handler in _INTERNAL_ORDER:
        out = handler(
            db, school_id, question=question, tokens=tokens, term=term, context=context
        )
        if out is not None:
            text, payload, new_ctx = out
            payload.setdefault("intent", intent)
            return intent, text, payload, new_ctx
    text = (
        "I couldn't understand that question against this school's records. "
        "I can answer questions like: 'how many students are enrolled?', "
        "'what subjects does JSS 1A offer?', 'who scored highest in "
        "Mathematics?', 'what's the average score in English?', or 'how did "
        "Aisha Bello do this term?'."
    )
    payload = {"intent": "unknown"}
    return "unknown", text, payload, context


# ----------------------------------------------------------------------------
# Public service API
# ----------------------------------------------------------------------------


def _title_for(question: str) -> str:
    words = question.split()
    title = " ".join(words[:7])
    if len(words) > 7:
        title += "…"
    return title[:200] or "New conversation"


def ask_copilot(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    conversation_id: str | None = None,
    term_id: uuid.UUID | None = None,
    actor_id: uuid.UUID,
) -> tuple[CopilotConversation, CopilotMessage]:
    """Append one turn to a conversation (creating it if needed) and answer.

    Stores the user question + the assistant answer (with intent + payload),
    then meters the assistant turn exactly once under ``ai.copilot``.
    """
    question = (question or "").strip()
    if not question:
        raise ValidationError("Question is required")

    conversation: CopilotConversation | None = None
    if conversation_id:
        try:
            conversation = db.get(CopilotConversation, uuid.UUID(conversation_id))
        except (ValueError, TypeError):
            conversation = None
        if conversation is None or conversation.school_id != school_id:
            raise NotFoundError("Conversation not found")
        if conversation.term_id is None and term_id is not None:
            conversation.term_id = term_id
    if conversation is None:
        conversation = CopilotConversation(
            school_id=school_id,
            title=_title_for(question),
            term_id=term_id,
            created_by=actor_id,
        )
        db.add(conversation)
        db.flush()

    db.add(
        CopilotMessage(
            school_id=school_id,
            conversation_id=conversation.id,
            role="user",
            content=question,
        )
    )
    term = _resolve_term(db, school_id, question, conversation.term_id)
    started = time.perf_counter()
    intent, text, payload, new_ctx = _answer(
        db, school_id, question=question, term=term, context=conversation.context or {}
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    conversation.context = new_ctx
    message = CopilotMessage(
        school_id=school_id,
        conversation_id=conversation.id,
        role="assistant",
        content=text,
        intent=intent,
        answer_payload=payload,
    )
    db.add(message)
    _meter_inc(db, school_id, actor_id, AI_FEATURE_COPILOT, question, text, latency_ms)
    db.flush()
    return conversation, message


def get_conversation(
    db: Session, school_id: uuid.UUID, conversation_id: str
) -> CopilotConversation:
    try:
        conversation = db.get(CopilotConversation, uuid.UUID(conversation_id))
    except (ValueError, TypeError):
        conversation = None
    if conversation is None or conversation.school_id != school_id:
        raise NotFoundError("Conversation not found")
    return conversation


def get_conversations(
    db: Session, school_id: uuid.UUID
) -> list[CopilotConversation]:
    return list(
        db.scalars(
            select(CopilotConversation)
            .where(CopilotConversation.school_id == school_id)
            .order_by(CopilotConversation.created_at.desc())
        )
    )


def conversation_messages(
    db: Session, conversation: CopilotConversation
) -> list[CopilotMessage]:
    return list(
        db.scalars(
            select(CopilotMessage)
            .where(CopilotMessage.conversation_id == conversation.id)
            .order_by(CopilotMessage.created_at)
        )
    )


def intents_catalog() -> list[dict]:
    """Descriptions + example phrasings the UI renders as suggested chips."""
    return [
        {
            "id": "school_overview",
            "name": "School overview",
            "examples": ["How many students are enrolled?", "How many teachers are there?"],
        },
        {
            "id": "class_snapshot",
            "name": "Class snapshot",
            "examples": ["How many students are in JSS 1A?", "How many boys are in JSS 1B?"],
        },
        {
            "id": "class_subjects",
            "name": "Subjects in a class",
            "examples": ["What subjects does JSS 1A offer?"],
        },
        {
            "id": "readiness",
            "name": "Results readiness",
            "examples": ["How is score entry going this term?", "What's the results readiness?"],
        },
        {
            "id": "top_performers",
            "name": "Top performers",
            "examples": ["Who scored highest in Mathematics?", "Top three students in English"],
        },
        {
            "id": "subject_average",
            "name": "Subject average",
            "examples": ["What's the average score in Mathematics?"],
        },
        {
            "id": "student_report",
            "name": "Student report",
            "examples": ["How did Aisha Bello do this term?"],
        },
        {
            "id": "term_summary",
            "name": "Term summary",
            "examples": ["How did JSS 1A do overall this term?"],
        },
    ]


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _student_brief(student: Student) -> dict:
    return {
        "student_id": str(student.id),
        "admission_no": student.admission_no,
        "full_name": student.full_name,
    }