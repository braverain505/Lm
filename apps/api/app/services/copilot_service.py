"""School copilot: conversational, data-grounded Q&A over a school's own data.

Each turn is answered in two layers, and the layering *is* the design:

1. **The rules engine resolves facts.** A catalog of question *intents*
   (counts, enrollments, offerings, published results) is resolved against the
   school's real rows and composed into an answer with actual numbers — nothing
   invented or random. This is also what pins the conversation's context slots
   (arm / subject / student / term), so follow-ups like "what about English?"
   or "how many boys?" resolve against prior answers.
2. **An LLM writes the answer**, given those resolved facts as its grounding
   brief. It may phrase things conversationally and answer questions the intent
   catalog has no handler for, but every number it is allowed to know comes from
   step 1 — the prompt forbids inventing any, and the school's real counts,
   arms, subjects, score-entry progress and published performance ride along in
   the brief.

When there is no LLM configured, the provider fails, times out, or returns
something unusable, the turn falls back to the deterministic text from step 1.
That fallback is not a degraded mode — it is the documented offline behaviour,
which is why the intent tests still pin it exactly.

Published-only for performance questions: top performers, subject averages,
term summaries and student reports read exclusively from the frozen
``published_snapshot`` of ``Result`` rows at ``published`` status — the same
record report cards and the public portal render. Entry-progress questions
(readiness) read live score counts by design.

Metered exactly like the other AI engines: each assistant turn writes one
``AiUsage`` row + one monthly ``UsageMeter`` bump under feature ``ai.copilot``
via ``ai_service._meter_inc``, carrying the real provider/model/token counts
when an LLM produced the text. The answer's ``source`` (``llm`` or ``rules``) is
recorded in ``answer_payload`` so the UI can say which one answered.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
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
from . import copilot_actions
from .ai_service import AI_FEATURE_COPILOT, _check_ai_quota, _meter_inc
from .llm_client import complete_text
from .academics_service import (
    current_term,
    get_term,
    list_offerings,
    list_subjects,
)
from .people_service import list_enrollments, list_staff, list_students
from .results_service import readiness_for_term

logger = logging.getLogger(__name__)

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
# Small talk — a greeting is not a query
# ----------------------------------------------------------------------------
# Phrases that mean "hello" / "how are you" / "thanks" rather than a question
# about the school. Matched on the raw question because word order matters here.
_SMALL_TALK_PATTERNS = re.compile(
    r"^\s*(hi|hey|hello|yo|howdy|greetings)\b"
    r"|\bgood (morning|afternoon|evening)\b"
    r"|\bhow (are|r) (you|u|things)\b"
    r"|\bhow'?s (it going|things|life)\b"
    r"|\bwhat'?s up\b"
    r"|\bhow am i\b"
    r"|\b(who|what) are you\b"
    r"|\byour name\b"
    r"|\bthank(s| you)\b",
    re.IGNORECASE,
)

# If the question carries any of these, it is a real query that merely opens
# with a greeting ("hi, how many students are enrolled?") — route it to the
# intent catalog, not to small talk.
_DATA_CUES = {
    "student", "students", "teacher", "teachers", "staff", "subject",
    "subjects", "class", "classes", "arm", "arms", "level", "levels",
    "result", "results", "score", "scores", "average", "top", "report",
    "reports", "readiness", "enrolled", "enrollment", "boy", "boys",
    "girl", "girls", "term", "terms", "performance", "attendance",
    "name", "names", "roster",
}

# Words that mean the question is about marks, not about who is in the class —
# used to keep "who scored highest?" away from the roster handler.
# Roster answers are bounded the same way the LLM brief is: a school with
# thousands of pupils must not return its whole roll in one response.
_MAX_ROSTER_ROWS = 300

_PERFORMANCE_WORDS = {
    "scored", "score", "scores", "scoring", "highest", "best", "top",
    "average", "avg", "mean", "perform", "performed", "performance",
    "rank", "ranking", "grade", "grades", "result", "results",
}


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


def _h_small_talk(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    **_,
) -> tuple[str, dict, dict] | None:
    """Greetings, "how are you" and thanks.

    A greeting must not be answered with a data dump — "how are you doing?"
    contains the word "how", and before this handler existed that was enough to
    trigger the school-overview intent. Any question that actually names school
    data is passed through to the catalog, so "hi, how many students?" is still
    a real query.
    """
    if not _SMALL_TALK_PATTERNS.search(question or ""):
        return None
    if tokens & _DATA_CUES:
        return None
    q = question.lower()
    if re.search(r"how am i\b", q):
        text = (
            "I keep this school's records rather than your personal marks, so I "
            "can't grade you. Ask me about a class, a student, or the school's "
            "published results and I'll have a real answer."
        )
    elif re.search(r"how (are|r) (you|u|things)\b|how'?s (it going|things|life)\b", q):
        text = (
            "I'm well, thank you — and ready to help. I answer questions about "
            "this school from its own records: students, staff, classes, "
            "subjects, score entry and published results."
        )
    else:
        text = (
            "Hello! I'm this school's copilot. I answer questions about it from "
            "its own records — students, staff, classes, subjects, score entry "
            "and published results. What would you like to know?"
        )
    return text, {"intent": "small_talk"}, {}


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
            "student and staff counts, who is in a class, what subjects a class "
            "offers, result entry progress, published scores, top performers and "
            "class averages. Try: 'how many students are enrolled?', 'give me "
            "the names in JSS 1A', 'what subjects does JSS 1A offer?', 'who "
            "scored highest in Mathematics?', or 'how did Aisha Bello do this "
            "term?'.\n\n" + copilot_actions.command_help()
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


def _h_class_roster(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    context: dict,
    **_,
) -> tuple[str, dict, dict] | None:
    """The names of the students in a class — "give me the names".

    The count snapshot answers *how many*; this answers *who*. An explicit
    "in/of/for <class>" clause wins, then the longest class name in the
    question, then the arm already pinned on the conversation — so a bare
    "give me the names" right after "how many students are in Nursery 1"
    lists that class.
    """
    # "all" is deliberately not a cue: it is far too common in count questions.
    wants_names = _has(
        tokens, "name", "names", "roster", "register", "list", "everyone"
    )
    asks_who = "who" in tokens and not (tokens & _PERFORMANCE_WORDS)
    if not (wants_names or asks_who):
        return None

    arm = None
    clause = re.search(
        r"\b(?:in|of|for|from)\s+(?:class\s+)?(?P<arm>.+?)\s*$", question, re.IGNORECASE
    )
    if clause:
        arm = copilot_actions.resolve_arm_by_phrase(db, school_id, clause.group("arm"))
    arm = arm or copilot_actions.find_arm_in_text(db, school_id, question)
    arm = arm or _ctx_arm(db, school_id, context)
    if arm is None:
        return None

    rows = list_enrollments(db, school_id, arm.id)
    students = sorted(
        rows, key=lambda env: (env.student.last_name or "", env.student.first_name or "")
    )
    label = arm.full_name
    brief = [
        {
            "student_id": str(env.student.id),
            "admission_no": env.student.admission_no,
            "full_name": env.student.full_name,
            "gender": env.student.gender,
        }
        for env in students
    ]
    ctx = {**context, "arm_id": str(arm.id)}
    if not brief:
        return (
            f"{label} has no enrolled students yet.",
            {"intent": "class_roster", "class": label, "count": 0, "students": []},
            ctx,
        )
    shown = brief[:40]
    listed = _join_names(
        [f"{s['full_name']} ({s['admission_no']})" for s in shown]
    )
    more = "" if len(brief) <= len(shown) else f" and {len(brief) - len(shown)} more"
    text = (
        f"{label} has {len(brief)} enrolled student"
        f"{'s' if len(brief) != 1 else ''}: {listed}{more}."
    )
    # The count is exact; the rows are bounded so a 2,000-pupil school does not
    # put its whole roster into one answer payload.
    return (
        text,
        {
            "intent": "class_roster",
            "class": label,
            "count": len(brief),
            "students": brief[:_MAX_ROSTER_ROWS],
            "truncated": len(brief) > _MAX_ROSTER_ROWS,
        },
        ctx,
    )


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
    # Deliberately not keyed on a bare "how": that word appears in greetings and
    # in questions belonging to other intents ("how did the class do overall?").
    if not _has(tokens, "many", "overview", "count", "enrolled"):
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
    ("small_talk", _h_small_talk),
    ("help", _h_help),
    ("class_subjects", _h_class_subjects),
    # Roster before the count snapshot: "list the students in JSS 1A" names
    # them, while "how many students are in JSS 1A" carries none of the roster
    # cues and still falls through to the count handler.
    ("class_roster", _h_class_roster),
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


# ----------------------------------------------------------------------------
# The LLM layer: the rules engine supplies the facts, the model writes it up
# ----------------------------------------------------------------------------

# The brief is a prompt, so it is bounded on purpose: a school with 60 arms and
# 90 subjects must not turn one question into a 200 KB request (and a bill).
_MAX_ARMS_IN_BRIEF = 30
_MAX_SUBJECTS_IN_BRIEF = 40
_MAX_HISTORY_TURNS = 6
_MAX_HISTORY_CHARS = 300
_MAX_ANSWER_CHARS = 2000

_COPILOT_SYSTEM = (
    "You are the Clearis school copilot, answering questions about ONE school "
    "from the records supplied in the brief below.\n\n"
    "Absolute rules:\n"
    "1. Every number, name and figure you state MUST come from the brief. Never "
    "estimate, never extrapolate, never invent one — not even a plausible "
    "example.\n"
    "2. If the brief does not contain what is being asked, say plainly that you "
    "do not have that information, then name one or two things you *can* answer "
    "from the brief.\n"
    "3. Performance figures (scores, averages, positions, published cards) "
    "reflect only PUBLISHED results. Say so when it matters; a subject with no "
    "published scores is not a subject with a score of zero.\n"
    "4. Answer in 1 to 4 sentences of clear British English. Plain text only — "
    "no markdown, no headings, no bullet characters, no code fences.\n"
    "5. Address the question asked. Do not summarise the whole brief.\n"
    "6. If the user greets you or makes small talk, reply briefly and warmly in "
    "one sentence, then invite a question about the school. Do not recite the "
    "brief or volunteer unrelated figures."
)


def _class_arms_for_brief(
    db: Session, school_id: uuid.UUID
) -> list[tuple[ClassArm, int]]:
    """Each class arm with its live enrollment count, ordered by name.

    Counted from live enrollments rather than read off a cached total, so the
    brief can never disagree with the counts the intents report. One grouped
    query rather than one per arm: the brief is built on every turn, and a
    school with sixty arms must not cost sixty round-trips.
    """
    counts = dict(
        db.execute(
            select(StudentEnrollment.class_arm_id, func.count())
            .where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.is_current.is_(True),
                StudentEnrollment.status == "active",
            )
            .group_by(StudentEnrollment.class_arm_id)
        ).all()
    )
    arms = sorted(
        db.scalars(select(ClassArm).where(ClassArm.school_id == school_id)),
        key=lambda a: a.full_name,
    )
    return [(arm, int(counts.get(arm.id, 0))) for arm in arms[:_MAX_ARMS_IN_BRIEF]]


def _grounding_brief(
    db: Session,
    school_id: uuid.UUID,
    *,
    term: Term | None,
    deterministic_text: str,
    deterministic_payload: dict,
) -> str:
    """The school's real facts, as plain text, for one prompt.

    Everything the model is permitted to state lives in here: the counts, the
    class arms, the subjects, this term's score-entry progress and the resolved
    facts behind the rules answer. Nothing is derived or guessed — each line is
    read from the school's own rows.
    """
    from ..models import School

    school = db.get(School, school_id)
    name = school.name if school is not None else "this school"
    school_type = school.school_type if school is not None else "school"

    lines: list[str] = [f"School name: {name} ({school_type})"]

    current = db.scalar(
        select(AcademicSession).where(
            AcademicSession.school_id == school_id,
            AcademicSession.is_current.is_(True),
        )
    )
    if current is not None:
        lines.append(f"Current academic session: {current.name}")

    students = len(list_students(db, school_id))
    teachers = len(list_staff(db, school_id, membership_type="teaching"))
    subjects = list_subjects(db, school_id)
    lines.append(
        f"Totals: {students} enrolled students, {teachers} teaching staff, "
        f"{len(subjects)} subjects"
    )

    arms = _class_arms_for_brief(db, school_id)
    if arms:
        joined = "; ".join(f"{arm.full_name} ({count} students)" for arm, count in arms)
        lines.append(f"Class arms: {joined}")
    else:
        lines.append("Class arms: none set up")

    if subjects:
        shown = [s.name for s in subjects[:_MAX_SUBJECTS_IN_BRIEF]]
        suffix = "" if len(subjects) <= _MAX_SUBJECTS_IN_BRIEF else ", …"
        lines.append(f"Subjects: {', '.join(shown)}{suffix}")

    if term is not None:
        lines.append(f"Term in scope: {term.name}")
        try:
            readiness = readiness_for_term(db, school_id, term.id)
        except Exception:  # pragma: no cover - readiness is best-effort context
            logger.warning("Copilot brief: readiness unavailable", exc_info=True)
            readiness = []
        by_arm: dict[str, dict[str, int]] = {}
        for row in readiness:
            agg = by_arm.setdefault(
                row["arm_name"], {"students": 0, "entered": 0, "submitted": 0}
            )
            agg["students"] += row["student_count"]
            agg["entered"] += row["entered"]
            agg["submitted"] += row["submitted"]
        if by_arm:
            lines.append(
                "Score entry for this term: "
                + "; ".join(
                    f"{arm}: {agg['entered']}/{agg['students']} students entered, "
                    f"{agg['submitted']} submitted"
                    for arm, agg in sorted(by_arm.items())
                )
            )
        else:
            lines.append("Score entry for this term: nothing entered yet")

    lines.append(
        "Facts the school's own rules engine resolved for this exact question "
        "(treat as authoritative):"
    )
    lines.append(f"  answer: {deterministic_text}")
    lines.append("  payload: " + json.dumps(deterministic_payload, default=str)[:4000])
    lines.append(
        "If the payload's intent is 'unknown', the rules engine could not match "
        "the question — answer from the school facts above, or say you do not "
        "have it."
    )
    return "\n".join(lines)


def _history_for_prompt(messages: list[CopilotMessage]) -> str:
    """The last few turns, so follow-ups read naturally.

    Bounded twice (turn count and per-message characters) because the thread
    grows without limit and the prompt must not.
    """
    recent = [m for m in messages[-(_MAX_HISTORY_TURNS * 2) :] if m.content]
    if not recent:
        return "(this is the first question in the conversation)"
    lines = []
    for message in recent:
        who = "User" if message.role == "user" else "Copilot"
        text = " ".join(message.content.split())[:_MAX_HISTORY_CHARS]
        lines.append(f"{who}: {text}")
    return "\n".join(lines)


def _llm_answer(
    *,
    question: str,
    brief: str,
    history: str,
) -> tuple[str, str, int, int, int, str] | None:
    """One Groq attempt at the conversational answer.

    Returns ``(text, model, tokens_in, tokens_out, latency_ms, provider)``, or
    ``None`` for every failure mode — no key, network error, timeout, or an
    answer that fails the honesty checks below. A caller that gets ``None`` uses
    the deterministic text, which is the documented offline behaviour.
    """
    from ..config import settings

    if not settings.groq_api_key:
        return None

    user = (
        f"Conversation so far:\n{history}\n\n"
        f"Current question: {question}\n\n"
        f"--- SCHOOL BRIEF (the only facts you may use) ---\n{brief}\n"
        f"--- END BRIEF ---\n\n"
        f"Answer the current question now."
    )
    res = complete_text(
        system=_COPILOT_SYSTEM,
        user=user,
        temperature=0.2,
        max_tokens=700,
    )
    if res is None:
        return None
    text = " ".join(res.text.split())
    # Reject rather than repair: a rambling or truncated answer is a worse
    # document than the deterministic one, and a very short one is usually the
    # model deflecting the whole brief.
    if len(text) < 20 or len(text) > _MAX_ANSWER_CHARS:
        logger.warning("Copilot LLM answer unusable (len=%d); falling back", len(text))
        return None
    return text, res.model, res.tokens_in, res.tokens_out, res.latency_ms, "groq"


def _title_for(question: str) -> str:
    words = question.split()
    title = " ".join(words[:7])
    if len(words) > 7:
        title += "…"
    return title[:200] or "New conversation"


# ---------------------------------------------------------------------------
# Admin command layer
#
# A turn is either a *command* (parse → confirm → execute) or a *question*
# (the rules engine + LLM). Commands never reach the LLM: a model that phrases
# an answer must not be able to phrase a write. The pending proposal lives on
# the conversation's ``context`` JSONB so confirmation survives across turns.
# ---------------------------------------------------------------------------


def _run_proposal(
    db: Session,
    school_id: uuid.UUID,
    proposal: copilot_actions.Proposal,
    *,
    actor_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool,
) -> tuple[str, dict]:
    reply = copilot_actions.execute_proposal(
        db,
        school_id,
        proposal,
        actor_id=actor_id,
        permission_codes=permission_codes,
        is_superadmin=is_superadmin,
    )
    return reply.text, reply.payload


def _resume_pending(
    db: Session,
    school_id: uuid.UUID,
    *,
    context: dict,
    question: str,
    actor_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool,
) -> tuple[str, dict] | None:
    """Handle a turn that arrives while a proposal is awaiting confirmation.

    ``None`` means "drop the proposal and let this turn be handled as a fresh
    command or a question" — which is what happens when the user asks about
    something else entirely.
    """
    raw = context.get("pending_action")
    if not raw:
        return None
    proposal = copilot_actions.Proposal.from_context(raw)

    if copilot_actions.is_cancellation(question):
        context.pop("pending_action", None)
        return (
            "Cancelled — nothing was changed.",
            copilot_actions.proposal_payload(proposal, "cancelled"),
        )

    if proposal.missing:
        if copilot_actions.apply_reply(db, school_id, proposal, question):
            context["pending_action"] = proposal.to_context()
            if not proposal.missing and copilot_actions.is_affirmation(question):
                context.pop("pending_action", None)
                return _run_proposal(
                    db, school_id, proposal,
                    actor_id=actor_id, permission_codes=permission_codes,
                    is_superadmin=is_superadmin,
                )
            return (
                copilot_actions.render_proposal(proposal),
                copilot_actions.proposal_payload(proposal, "pending"),
            )
        # Not a field value. If it is a whole new command, replace the pending
        # one; otherwise keep asking rather than silently dropping the action.
        if copilot_actions.detect_action(
            db, school_id, question=question, context=context
        ) is None:
            return (
                copilot_actions.render_proposal(proposal),
                copilot_actions.proposal_payload(proposal, "pending"),
            )
        context.pop("pending_action", None)
        return None

    if copilot_actions.is_affirmation(question):
        context.pop("pending_action", None)
        return _run_proposal(
            db, school_id, proposal,
            actor_id=actor_id, permission_codes=permission_codes,
            is_superadmin=is_superadmin,
        )

    # Nothing missing and no confirmation: the user moved on. Drop the proposal
    # and answer whatever they actually asked.
    context.pop("pending_action", None)
    return None


def _start_command(
    db: Session,
    school_id: uuid.UUID,
    *,
    context: dict,
    question: str,
    permission_codes: set[str],
    is_superadmin: bool,
) -> tuple[str, dict] | None:
    """Parse a fresh admin command, or ``None`` when it is just a question."""
    parsed = copilot_actions.detect_action(
        db, school_id, question=question, context=context
    )
    if parsed is None:
        return None
    if isinstance(parsed, copilot_actions.DirectReply):
        return parsed.text, parsed.payload

    proposal = parsed
    missing = copilot_actions.missing_permissions(
        proposal, permission_codes, is_superadmin=is_superadmin
    )
    if missing:
        # Say so up front rather than after a confirmation round-trip; the same
        # check runs again at execution time.
        denied = copilot_actions.deny(proposal, missing)
        return denied.text, denied.payload

    context["pending_action"] = proposal.to_context()
    return (
        copilot_actions.render_proposal(proposal),
        copilot_actions.proposal_payload(proposal, "pending"),
    )


def _command_reply(
    db: Session,
    school_id: uuid.UUID,
    *,
    context: dict,
    question: str,
    actor_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool,
) -> tuple[str, dict] | None:
    """Deterministic admin-command handling for one turn.

    Returns ``(text, payload)`` when the turn was a command, or ``None`` to
    fall through to the normal Q&A engine. Mutates ``context`` in place (the
    pending proposal).
    """
    if context.get("pending_action"):
        handled = _resume_pending(
            db, school_id,
            context=context, question=question, actor_id=actor_id,
            permission_codes=permission_codes, is_superadmin=is_superadmin,
        )
        if handled is not None:
            return handled
    return _start_command(
        db, school_id,
        context=context, question=question,
        permission_codes=permission_codes, is_superadmin=is_superadmin,
    )


def ask_copilot(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    conversation_id: str | None = None,
    term_id: uuid.UUID | None = None,
    actor_id: uuid.UUID,
    permission_codes: set[str] | None = None,
    is_superadmin: bool = False,
) -> tuple[CopilotConversation, CopilotMessage]:
    """Append one turn to a conversation (creating it if needed) and answer.

    A turn is one of two things:

    * An **admin command** ("add Genesis John to Nursery 1") — parsed
      deterministically, gated on the caller's real permissions, and executed
      only after an explicit "confirm". Commands never reach the LLM.
    * A **question** — the rules engine resolves it to facts (and pins the
      context slots follow-ups depend on), then the LLM phrases the answer from
      those facts, falling back to the rules text whenever the model is
      unavailable or its output is unusable.

    Stores the user question + the assistant answer (with intent + payload and
    which layer produced the text), then meters the assistant turn exactly once
    under ``ai.copilot``, carrying the real provider/model/token counts when an
    LLM produced it.
    """
    question = (question or "").strip()
    if not question:
        raise ValidationError("Question is required")
    _check_ai_quota(db, school_id)  # credits gate: copilot turns are metered below

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

    # The prior turns, read BEFORE this question is written, so the prompt can
    # append the current turn exactly once.
    history = conversation_messages(db, conversation)

    pending_user_turns = [
        CopilotMessage(
            school_id=school_id,
            conversation_id=conversation.id,
            role="user",
            content=question,
        )
    ]
    db.add(pending_user_turns[0])
    db.flush()

    started = time.perf_counter()

    # --- Admin command layer -------------------------------------------------
    # Runs before anything else: a command must not be reinterpreted as a
    # question, and its outcome must not be paraphrased by the model. The
    # conversation context is copied out so a proposal can be added/cleared and
    # written back once (JSONB needs an explicit reassignment to be seen).
    context = dict(conversation.context or {})
    command = _command_reply(
        db, school_id,
        context=context, question=question, actor_id=actor_id,
        permission_codes=permission_codes or set(), is_superadmin=is_superadmin,
    )
    # Write the context back even when the turn is a plain question: a pending
    # proposal that was abandoned (or a slot the command layer cleared) has to
    # be persisted, not silently resurrected by the next turn's JSONB read.
    conversation.context = context
    if command is not None:
        text, payload = command
        payload = {**payload, "source": "command"}
        message = CopilotMessage(
            school_id=school_id,
            conversation_id=conversation.id,
            role="assistant",
            content=text,
            intent=payload.get("intent"),
            answer_payload=payload,
        )
        db.add(message)
        _meter_inc(
            db, school_id, actor_id, AI_FEATURE_COPILOT, question, text,
            int((time.perf_counter() - started) * 1000),
        )
        db.flush()
        return conversation, message

    term = _resolve_term(db, school_id, question, conversation.term_id)

    # Layer 1 — the rules engine. Always runs: it is both the offline answer and
    # the grounding brief the model is allowed to reason from, and it is what
    # advances the conversation's context slots.
    intent, rules_text, payload, new_ctx = _answer(
        db, school_id, question=question, term=term, context=conversation.context or {}
    )
    conversation.context = new_ctx

    # Layer 2 — the LLM writes the answer up, grounded on layer 1.
    text = rules_text
    provider = None
    model = None
    tokens_in = None
    tokens_out = None
    source = "rules"
    try:
        brief = _grounding_brief(
            db,
            school_id,
            term=term,
            deterministic_text=rules_text,
            deterministic_payload=payload,
        )
        llm = _llm_answer(
            question=question,
            brief=brief,
            history=_history_for_prompt([*history, *pending_user_turns]),
        )
    except Exception:  # a brief or a provider must never fail the turn
        logger.exception("Copilot LLM layer failed; using the rules answer")
        llm = None
    if llm is not None:
        text, model, tokens_in, tokens_out, _llm_latency, provider = llm
        source = "llm"

    latency_ms = int((time.perf_counter() - started) * 1000)

    # The resolved facts travel with the answer either way, so the UI can render
    # its cards and so `source` records which layer produced the prose.
    payload = {**payload, "source": source}
    if model:
        payload["model"] = model

    message = CopilotMessage(
        school_id=school_id,
        conversation_id=conversation.id,
        role="assistant",
        content=text,
        intent=intent,
        answer_payload=payload,
    )
    db.add(message)
    _meter_inc(
        db,
        school_id,
        actor_id,
        AI_FEATURE_COPILOT,
        question,
        text,
        latency_ms,
        **({"provider": provider, "model": model, "tokens_in": tokens_in, "tokens_out": tokens_out} if provider else {}),
    )
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


def delete_conversation(
    db: Session, school_id: uuid.UUID, conversation_id: str
) -> None:
    """Delete a thread and every message in it.

    The thread is the user's own scratch space, not a school record, so it is
    hard-deleted (the ``messages`` relationship cascades) and there is no audit
    entry — an audit trail is for changes to pupils, staff and results, not for
    clearing your own chat. Tenant isolation is enforced by ``get_conversation``:
    a thread belonging to another school is a 404, never a delete.
    """
    conversation = get_conversation(db, school_id, conversation_id)
    db.delete(conversation)
    db.flush()


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
            "id": "class_roster",
            "name": "Class list",
            "examples": ["Give me the names in JSS 1A", "Who is in Nursery 1?"],
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