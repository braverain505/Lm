"""Admin actions for the school copilot: chat commands that change records.

The copilot's Q&A side (see ``copilot_service``) resolves *questions* against
the school's rows and never writes. This module is the other half: a small,
deterministic command layer that turns a chat message like

    add Genesis John to Nursery 1

into a concrete, permission-checked, *confirmed* write.

Three rules shape the design, and they are the whole point:

1. **The model never executes anything.** Commands are parsed by the rules in
   this module, never offered to the LLM as a tool. A model that can be talked
   into "adding a student" can be talked into adding the wrong one; a parser
   either resolves the command against real rows or admits it cannot.
2. **Nothing happens without an explicit confirmation.** Every command first
   produces a :class:`Proposal` — what will change, spelled out with real names
   and numbers — which the user must answer with ``confirm``. The pending
   proposal rides on the conversation's ``context`` JSONB, so it survives turns.
   A write turn wrapped in a chat message is exactly the shape of an accident.
3. **Permissions are re-checked server-side per action.** The ``/copilot/ask``
   route is gated on ``ai.copilot`` (a leadership *tool*), which is not the same
   as the authority to admit a pupil, publish results or restructure academics.
   Each action names the permission codes it needs and the caller's real set is
   consulted at execution time, not at render time.

Every execution is also journalled to ``audit_logs`` — an appended-from-chat
write is still an administrative action, and the audit trail is where a school
finds out who did it.

Parsing is deliberately heuristic-but-strict: it prefers an *exact* normalized
name match (so "Nursery 1" never resolves to "Nursery 10"), and where a command
is missing a required field it asks for that field rather than inventing it.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import APIError
from ..core.permissions import (
    ACADEMICS_MANAGE,
    RESULTS_APPROVE,
    RESULTS_PUBLISH,
    RESULTS_VERIFY,
    STAFF_CREATE,
    STUDENTS_CREATE,
    STUDENTS_ENROLL,
)
from ..models import AcademicSession, AuditLog, ClassArm, Staff, Student, Term
from ..models.enums import AuditAction
from . import academics_service, people_service, results_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Matching helpers (self-contained: this module must not import copilot_service,
# which imports *this* — the dependency runs one way only).
# ---------------------------------------------------------------------------


def _tokens(q: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (q or "").lower()))


def _has(tokens: set[str], *words: str) -> bool:
    for word in words:
        wt = _tokens(word)
        if wt and wt <= tokens:
            return True
    return False


def _norm(value: str) -> str:
    """Lowercase alphanumeric-only form: ``"JSS 1 A"`` and ``"jss1a"`` both
    normalise to ``"jss1a"``, which is how a typed class name matches a stored
    one regardless of spacing."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _clause(value: str) -> str:
    """Collapse whitespace (used for prompt-visible name fragments)."""
    return " ".join((value or "").split())


# ---------------------------------------------------------------------------
# Proposal / reply value types
# ---------------------------------------------------------------------------

# Human-language prompts for each field a command can still be missing. Used
# both in the "I still need…" reply and in the field-supply step, so a bare
# reply ("male", "2025/2026") can be attributed to the right slot.
_FIELD_PROMPTS: dict[str, str] = {
    "gender": "their gender — reply \"male\" or \"female\"",
    "arm": "the class — reply with its name, e.g. \"Nursery 1\"",
    "session": "the academic session — reply with its name, e.g. \"2025/2026\"",
    "term": "the term — reply with its name, e.g. \"First Term\"",
    "student": "which student — reply with their name or admission number",
    "first_name": "the student's first name",
    "last_name": "the student's surname",
    "full_name": "the person's full name",
    "subject_name": "the subject's name",
    "arm_name": "what the class should be called, e.g. \"Nursery 3\"",
    "session_name": "what the session should be called, e.g. \"2027/2028\"",
    "term_name": "what the term should be called, e.g. \"Second Term\"",
}


@dataclass
class Proposal:
    """A parsed command awaiting confirmation.

    Serialised straight onto ``CopilotConversation.context['pending_action']``,
    so every value here must be JSON-safe (ids are strings, never UUIDs).
    """

    code: str
    title: str
    permissions: tuple[str, ...]
    detail: str
    params: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_context(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "permissions": list(self.permissions),
            "detail": self.detail,
            "params": self.params,
            "missing": list(self.missing),
            "notes": list(self.notes),
        }

    @classmethod
    def from_context(cls, raw: dict) -> Proposal:
        return cls(
            code=raw["code"],
            title=raw.get("title", raw["code"]),
            permissions=tuple(raw.get("permissions") or ()),
            detail=raw.get("detail", ""),
            params=dict(raw.get("params") or {}),
            missing=list(raw.get("missing") or []),
            notes=list(raw.get("notes") or []),
        )


@dataclass
class DirectReply:
    """A reply that is not a proposal and not a question — e.g. "I couldn't
    find a class called X", or the result of a cancelled/denied action."""

    text: str
    payload: dict


# ---------------------------------------------------------------------------
# Confirmation vocabulary
# ---------------------------------------------------------------------------
_AFFIRM_RE = re.compile(
    r"^\s*(yes|yeah|yep|y|ya|sure|confirm|confirmed|ok|okay|k|"
    r"do it|go ahead|proceed|please do|please proceed|that'?s right|correct)\b",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(
    r"^\s*(no|nope|nah|cancel|stop|abort|forget it|never ?mind|leave it)\b",
    re.IGNORECASE,
)
_GENDER_WORDS = {"male": "male", "m": None, "boy": "male", "boys": "male",
                 "female": "female", "f": None, "girl": "female", "girls": "female"}
_CREATE_VERBS = {"add", "create", "make", "start", "register", "setup", "new"}


def is_affirmation(text: str) -> bool:
    return bool(_AFFIRM_RE.match(text or ""))


def is_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.match(text or ""))


# ---------------------------------------------------------------------------
# Resolvers — actions address real rows, by name, or not at all
# ---------------------------------------------------------------------------


def _current_session(db: Session, school_id: uuid.UUID) -> AcademicSession | None:
    return db.scalar(
        select(AcademicSession).where(
            AcademicSession.school_id == school_id,
            AcademicSession.is_current.is_(True),
        )
    )


def _sessions(db: Session, school_id: uuid.UUID) -> list[AcademicSession]:
    return list(
        db.scalars(
            select(AcademicSession)
            .where(AcademicSession.school_id == school_id)
            .order_by(AcademicSession.name.desc())
        )
    )


def _session_name(db: Session, session_id) -> str:
    if not session_id:
        return ""
    try:
        row = db.get(AcademicSession, uuid.UUID(str(session_id)))
    except (ValueError, TypeError):
        return ""
    return row.name if row is not None else ""


def _ordered_arms(db: Session, school_id: uuid.UUID) -> list[ClassArm]:
    """Arms of the current session first, then the rest — so "Nursery 1" means
    this year's Nursery 1 unless the caller says otherwise."""
    current = _current_session(db, school_id)
    arms = list(db.scalars(select(ClassArm).where(ClassArm.school_id == school_id)))
    return sorted(
        arms,
        key=lambda a: (
            0 if current is not None and a.academic_session_id == current.id else 1,
            a.full_name,
        ),
    )


def resolve_arm_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> ClassArm | None:
    """Resolve a typed class name to exactly one arm.

    Exact normalised equality wins ("Nursery 1" only matches "Nursery 1", never
    "Nursery 10"); a prefix/containment pass is the fallback so "JSS1A" still
    finds "JSS 1 A", but it never narrows to a wrong exact match first.
    """
    key = _norm(phrase)
    if not key:
        return None
    arms = _ordered_arms(db, school_id)
    for arm in arms:
        if _norm(arm.name) == key or _norm(arm.full_name) == key:
            return arm
    for arm in arms:
        nk = _norm(arm.full_name)
        if not nk:
            continue
        if nk.startswith(key) or key.startswith(nk):
            return arm
    for arm in arms:
        nk = _norm(arm.full_name)
        if nk and (key in nk or nk in key):
            return arm
    return None


def find_arm_in_text(
    db: Session, school_id: uuid.UUID, text: str
) -> ClassArm | None:
    """The longest stored arm name appearing anywhere in a free question.

    Longest-match is what keeps "Nursery 10" from being read as "Nursery 1"
    when both exist.
    """
    q = _norm(text)
    if not q:
        return None
    best: ClassArm | None = None
    for arm in _ordered_arms(db, school_id):
        nk = _norm(arm.full_name)
        # Two characters is the floor: a class named "A" would otherwise be
        # "found" in almost every sentence that contains the letter a.
        if len(nk) < 2 or nk not in q:
            continue
        if best is None or len(nk) > len(_norm(best.full_name)):
            best = arm
    return best


def resolve_session_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> AcademicSession | None:
    key = _norm(phrase)
    if not key:
        return None
    sessions = _sessions(db, school_id)
    for session in sessions:
        if _norm(session.name) == key:
            return session
    for session in sessions:
        nk = _norm(session.name)
        if nk and (key in nk or nk in key):
            return session
    return None


def resolve_term_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> Term | None:
    key = _norm(phrase)
    if not key:
        return None
    terms = list(
        db.scalars(
            select(Term)
            .join(AcademicSession, AcademicSession.id == Term.academic_session_id)
            .where(AcademicSession.school_id == school_id)
        )
    )
    # The current term first: "First Term" means this session's First Term.
    current = academics_service.current_term(db, school_id)
    terms.sort(key=lambda t: (0 if current is not None and t.id == current.id else 1))
    for term in terms:
        if _norm(term.name) == key:
            return term
    for term in terms:
        nk = _norm(term.name)
        if nk and (key in nk or nk in key):
            return term
    return None


def _resolve_student_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> Student | None:
    key = _norm(phrase)
    if not key:
        return None
    students = people_service.list_students(db, school_id)
    for student in students:
        if student.admission_no and _norm(student.admission_no) == key:
            return student
    exact = [s for s in students if _norm(s.full_name) == key]
    if len(exact) == 1:
        return exact[0]
    # "Genesis" alone when only one Genesis exists is a fair read; two is not.
    partial = [s for s in students if key and key in _norm(s.full_name)]
    if len(partial) == 1:
        return partial[0]
    return None


def _student_ambiguity(
    db: Session, school_id: uuid.UUID, phrase: str
) -> list[Student]:
    key = _norm(phrase)
    return [s for s in people_service.list_students(db, school_id) if key and key in _norm(s.full_name)]


# ---------------------------------------------------------------------------
# Serial-number helpers (admission / staff numbers are generated, never guessed)
# ---------------------------------------------------------------------------


def _next_serial(existing: list[str], prefix: str) -> str:
    used: set[int] = set()
    for value in existing:
        if value and value.startswith(prefix):
            tail = value[len(prefix):]
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return f"{prefix}{n:03d}"


def _next_admission_no(db: Session, school_id: uuid.UUID) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"STU-{year}-"
    existing = list(
        db.scalars(
            select(Student.admission_no).where(Student.school_id == school_id)
        )
    )
    return _next_serial(existing, prefix)


def _next_staff_no(db: Session, school_id: uuid.UUID) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"STF-{year}-"
    existing = list(
        db.scalars(select(Staff.staff_no).where(Staff.school_id == school_id))
    )
    return _next_serial(existing, prefix)


def _subject_code(db: Session, school_id: uuid.UUID, name: str) -> str:
    base = re.sub(r"[^A-Za-z]", "", name).upper()[:3] or "SUB"
    taken = {s.code.upper() for s in academics_service.list_subjects(db, school_id)}
    if base not in taken:
        return base
    for i in range(2, 100):
        candidate = f"{base}{i}"[:16]
        if candidate not in taken:
            return candidate
    return f"{base}{uuid.uuid4().hex[:4].upper()}"[:16]


# ---------------------------------------------------------------------------
# Parsing primitives
# ---------------------------------------------------------------------------

_NAME_NOISE = {
    "a", "an", "the", "new", "student", "students", "pupil", "pupils",
    "child", "please", "to", "into", "in", "as", "called", "named",
    "staff", "teacher", "member", "of", "non-teaching", "non", "teaching",
    "class", "arm", "subject", "session", "term", "add", "admit", "enrol",
    "enroll", "register", "create", "make", "start", "hire", "employ",
    "for", "and", "my", "our", "all", "results", "result", "first",
    "second", "third",
}

_ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
}


def _clean_phrase(value: str, drop: set[str] | None = None) -> str:
    """Strip command scaffolding from a captured name fragment."""
    words = []
    for word in re.split(r"\s+", (value or "").strip()):
        low = word.lower().strip(",")
        if not low:
            continue
        if low in _NAME_NOISE and (drop is None or low in drop):
            continue
        words.append(word.strip(",.?"))
    return " ".join(w for w in words if w)


def _extract_gender(tokens: set[str], phrase: str) -> tuple[str | None, str]:
    """Pull a gender out of a phrase ("Genesis John male" -> male)."""
    for word in list(tokens):
        mapped = _GENDER_WORDS.get(word)
        if mapped:
            cleaned = " ".join(
                w for w in phrase.split() if w.lower() != word
            )
            return mapped, cleaned
    return None, phrase


def _is_create(tokens: set[str]) -> bool:
    return bool(tokens & _CREATE_VERBS) or ("set" in tokens and "up" in tokens)


# ---------------------------------------------------------------------------
# Command detectors. Each returns Proposal | DirectReply | None.
# Order matters: the most specific command shape wins.
# ---------------------------------------------------------------------------

_RESULT_VERBS: dict[str, tuple[str, str, str]] = {
    # verb -> (action code, title, audit action)
    "publish": ("publish_results", "Publish results", AuditAction.PUBLISH.value),
    "release": ("publish_results", "Publish results", AuditAction.PUBLISH.value),
    "approve": ("approve_results", "Approve results", AuditAction.APPROVE.value),
    "verify": ("verify_results", "Verify results", AuditAction.OTHER.value),
    "submit": ("submit_results", "Submit results", AuditAction.SUBMIT.value),
    "compile": ("compile_results", "Compile results", AuditAction.PUBLISH.value),
}

_RESULT_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "publish_results": (RESULTS_PUBLISH,),
    "approve_results": (RESULTS_APPROVE,),
    "verify_results": (RESULTS_VERIFY,),
    "submit_results": (RESULTS_VERIFY,),
    "compile_results": (RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH),
}


def _detect_results_action(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    context: dict,
    **__,
) -> Proposal | DirectReply | None:
    verb = next((v for v in _RESULT_VERBS if v in tokens), None)
    if verb is None or not _has(tokens, "result", "results"):
        return None
    code, title, _audit = _RESULT_VERBS[verb]

    # Term: an explicitly named term ("for First Term"), else the live term.
    term_phrase = None
    match = re.search(r"\b(first|second|third)\s+term\b", question, re.IGNORECASE)
    if match:
        term_phrase = match.group(0)
    term = resolve_term_by_phrase(db, school_id, term_phrase) if term_phrase else None
    term = term or (academics_service.current_term(db, school_id) if not term_phrase else None)

    # Arm: whatever is left after the verb/result/term scaffolding is stripped.
    rest = question
    if match:
        rest = f"{rest[: match.start()]} {rest[match.end():]}"
    rest = re.sub(r"\b(publish|release|approve|verify|submit|compile)\b", " ", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\bresults?\b", " ", rest, flags=re.IGNORECASE)
    rest = re.sub(r"\b(for|of|in|the|all|my|our)\b", " ", rest, flags=re.IGNORECASE)
    arm_phrase = _clause(rest).strip(" ,.")
    arm = resolve_arm_by_phrase(db, school_id, arm_phrase) if arm_phrase else None
    if arm is None and not arm_phrase and context.get("arm_id"):
        contextual = db.get(ClassArm, _as_uuid(context.get("arm_id")))
        arm = contextual if contextual is not None and contextual.school_id == school_id else None

    missing: list[str] = []
    if arm is None:
        missing.append("arm")
    if term is None:
        missing.append("term")

    params = {
        "arm_id": str(arm.id) if arm else None,
        "arm_name": arm.full_name if arm else (arm_phrase or ""),
        "term_id": str(term.id) if term else None,
        "term_name": term.name if term else (term_phrase or ""),
        "audit": _RESULT_VERBS[verb][2],
    }
    if arm is not None and term is not None:
        detail = (
            f"{title} for {arm.full_name} in {term.name}. "
            "This runs across every subject offered in that class; rows that "
            "are not in the right state are left untouched."
        )
    else:
        detail = f"{title}."
    return Proposal(
        code=code,
        title=title,
        permissions=_RESULT_PERMISSIONS[code],
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_create_session(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "session" not in tokens or not _is_create(tokens):
        return None
    if _has(tokens, "result", "results", "term", "class", "arm", "subject"):
        return None
    rest = re.sub(
        r"\b(add|create|make|start|new|a|an|the|called|named|academic|"
        r"set|up|please|session)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    name = _clause(rest).strip(" ,.")
    missing = [] if name else ["session_name"]
    return Proposal(
        code="create_session",
        title="Create a session",
        permissions=(ACADEMICS_MANAGE,),
        detail=f"Create academic session {name}." if name else "Create an academic session.",
        params={"name": name},
        missing=missing,
    )


def _detect_create_term(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "term" not in tokens or not _is_create(tokens):
        return None
    if _has(tokens, "result", "results"):
        return None

    # term_no and name come from an ordinal word ("second term"), or a digit.
    term_no: int | None = None
    name = ""
    for word, number in _ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", question, re.IGNORECASE):
            term_no = number
            name = f"{word.capitalize()} Term"
            break
    if term_no is None:
        digits = [int(t) for t in tokens if t.isdigit() and 1 <= int(t) <= 3]
        if digits:
            term_no = digits[0]
            name = f"Term {term_no}"

    # A session named in the question wins; otherwise the live session.
    session = None
    for candidate in _sessions(db, school_id):
        key = _norm(candidate.name)
        if key and key in _norm(question):
            session = candidate
            break
    session = session or _current_session(db, school_id)

    missing: list[str] = []
    if session is None:
        missing.append("session")
    if term_no is None:
        missing.append("term_name")
    params = {
        "name": name,
        "term_no": term_no,
        "session_id": str(session.id) if session else None,
        "session_name": session.name if session else "",
    }
    if session is not None and term_no is not None:
        detail = f"Create {name} in {session.name}."
    elif session is not None:
        detail = f"Create a term in {session.name}."
    else:
        detail = "Create a term."
    return Proposal(
        code="create_term",
        title="Create a term",
        permissions=(ACADEMICS_MANAGE,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_create_arm(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if not _has(tokens, "class", "arm") or not _is_create(tokens):
        return None
    if _has(tokens, "subject", "session", "term", "result", "results"):
        return None
    rest = re.sub(
        r"\b(add|create|make|start|new|a|an|the|called|named|class|arm|"
        r"please)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    name = _clause(rest).strip(" ,.")
    session = _current_session(db, school_id)
    missing: list[str] = []
    if not name:
        missing.append("arm_name")
    if session is None:
        missing.append("session")
    params = {
        "arm_name": name,
        "session_id": str(session.id) if session else None,
        "session_name": session.name if session else "",
    }
    detail = (
        f"Create class {name} in {session.name}." if name and session else "Create a class."
    )
    return Proposal(
        code="create_class_arm",
        title="Create a class",
        permissions=(ACADEMICS_MANAGE,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_create_subject(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "subject" not in tokens or not _is_create(tokens):
        return None
    if _has(tokens, "session", "term", "result", "results"):
        return None
    rest = re.sub(
        r"\b(add|create|make|start|new|a|an|the|called|named|subject|"
        r"please)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    name = _clause(rest).strip(" ,.")
    missing = [] if name else ["subject_name"]
    code = _subject_code(db, school_id, name) if name else ""
    return Proposal(
        code="create_subject",
        title="Create a subject",
        permissions=(ACADEMICS_MANAGE,),
        detail=f"Create subject {name} (code {code})." if name else "Create a subject.",
        params={"name": name, "code": code},
        missing=missing,
    )


def _detect_add_staff(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if not _has(tokens, "teacher", "staff", "librarian", "accountant", "cleaner"):
        return None
    if not _is_create(tokens) and "hire" not in tokens and "employ" not in tokens:
        return None
    membership_type = (
        "non_teaching"
        if re.search(r"\bnon[- ]?teaching\b", question, re.IGNORECASE)
        else "teaching"
    )
    rest = re.sub(
        r"\b(add|create|make|start|new|a|an|the|called|named|staff|teacher|"
        r"member|of|hire|employ|please|as|non-?teaching|non|teaching|"
        r"librarian|accountant|cleaner)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    name = _clause(rest).strip(" ,.")
    missing = [] if name else ["full_name"]
    staff_no = _next_staff_no(db, school_id)
    return Proposal(
        code="add_staff",
        title="Add a staff member",
        permissions=(STAFF_CREATE,),
        detail=(
            f"Add {name} as a {'non-teaching' if membership_type != 'teaching' else 'teaching'} "
            f"staff member (staff number {staff_no})."
            if name
            else "Add a staff member."
        ),
        params={"full_name": name, "membership_type": membership_type, "staff_no": staff_no},
        missing=missing,
    )


_ADMIT_HEAD = (
    r"^\s*(?:please\s+|can you\s+|could you\s+|i want to\s+|i'd like to\s+)*"
    r"(?:add|admit|enrol|enroll|register)\s+"
    r"(?:(?:a|an|the|new)\s+)*(?:student|pupil|child)?\s*"
)


def _detect_admit_student(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    context: dict,
    **__,
) -> Proposal | DirectReply | None:
    match = re.match(
        _ADMIT_HEAD + r"(?P<name>.+?)\s+to\s+(?P<arm>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        match = re.match(
            _ADMIT_HEAD + r"(?P<name>.+?)\s+(?:into|in)\s+(?P<arm>.+?)\s*$",
            question,
            re.IGNORECASE,
        )
    if not match:
        return None
    if _has(tokens, "result", "results", "subject", "session", "term"):
        return None

    raw_name = match.group("name")
    arm_phrase = match.group("arm")
    gender, raw_name = _extract_gender(tokens, raw_name)
    name = _clean_phrase(raw_name, drop={"student", "pupil", "child", "new"})
    arm = resolve_arm_by_phrase(db, school_id, arm_phrase)

    words = [w for w in name.split() if w]
    first_name = " ".join(words[:-1]) if len(words) > 1 else (words[0] if words else "")
    last_name = words[-1] if len(words) > 1 else ""
    admission_no = _next_admission_no(db, school_id)

    missing: list[str] = []
    if not first_name:
        missing.append("first_name")
    if not last_name:
        missing.append("last_name")
    if gender is None:
        missing.append("gender")
    if arm is None:
        missing.append("arm")

    notes: list[str] = []
    if name:
        same = people_service.list_students(db, school_id, q=name)
        exact = [s for s in same if _norm(s.full_name) == _norm(name)]
        if exact:
            notes.append(
                f"a student called {name} already exists "
                f"({exact[0].admission_no}) — this would create a second record"
            )

    params = {
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "admission_no": admission_no,
        "arm_id": str(arm.id) if arm else None,
        "arm_name": arm.full_name if arm else _clause(arm_phrase),
        "session_id": str(arm.academic_session_id) if arm else None,
    }
    if arm is not None and not missing:
        detail = (
            f"Admit {first_name} {last_name} ({gender}) to {arm.full_name} "
            f"with admission number {admission_no}."
        )
    elif arm is not None:
        detail = (
            f"Admit {first_name or 'the student'} {last_name} to {arm.full_name} "
            f"with a generated admission number ({admission_no})."
        )
    else:
        detail = "Admit a student."
    return Proposal(
        code="admit_student",
        title="Admit a student",
        permissions=(STUDENTS_CREATE, STUDENTS_ENROLL),
        detail=detail,
        params=params,
        missing=missing,
        notes=notes,
    )


def _detect_change_class(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    context: dict,
    **__,
) -> Proposal | DirectReply | None:
    match = re.match(
        r"^\s*(?:please\s+)?(?:move|transfer|change)\s+(?P<name>.+?)"
        r"\s+(?:to|into)\s+(?P<arm>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    name_phrase = _clause(match.group("name"))
    arm_phrase = _clause(match.group("arm"))
    name_phrase = re.sub(r"^(?:student|pupil)\s+", "", name_phrase, flags=re.IGNORECASE)
    arm = resolve_arm_by_phrase(db, school_id, arm_phrase)
    student = _resolve_student_by_phrase(db, school_id, name_phrase)

    if student is None:
        candidates = _student_ambiguity(db, school_id, name_phrase)
        if len(candidates) > 1:
            listed = ", ".join(f"{s.full_name} ({s.admission_no})" for s in candidates[:5])
            return DirectReply(
                text=(
                    f"Several students match \"{name_phrase}\": {listed}. "
                    "Reply with the exact full name or admission number and I'll move them."
                ),
                payload={"intent": "change_class", "ambiguous": True},
            )
        return DirectReply(
            text=(
                f"I couldn't find a student called \"{name_phrase}\" in this school's records. "
                "Reply with the exact full name or admission number."
            ),
            payload={"intent": "change_class", "not_found": True},
        )

    missing: list[str] = []
    if arm is None:
        missing.append("arm")

    params = {
        "student_id": str(student.id),
        "student_name": student.full_name,
        "admission_no": student.admission_no,
        "arm_id": str(arm.id) if arm else None,
        "arm_name": arm.full_name if arm else arm_phrase,
        "session_id": str(arm.academic_session_id) if arm else None,
    }
    detail = (
        f"Move {student.full_name} ({student.admission_no}) to {arm.full_name}."
        if arm is not None
        else f"Move {student.full_name} ({student.admission_no}) to a new class."
    )
    return Proposal(
        code="change_class",
        title="Move a student's class",
        permissions=(STUDENTS_ENROLL,),
        detail=detail,
        params=params,
        missing=missing,
    )


_DETECTORS = (
    _detect_results_action,
    _detect_create_session,
    _detect_create_term,
    _detect_create_arm,
    _detect_create_subject,
    _detect_add_staff,
    _detect_admit_student,
    _detect_change_class,
)


def detect_action(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    context: dict,
) -> Proposal | DirectReply | None:
    """Parse a chat message into an admin command, or ``None`` for a question."""
    tokens = _tokens(question)
    for detector in _DETECTORS:
        out = detector(
            db, school_id, question=question, tokens=tokens, context=context or {}
        )
        if out is not None:
            return out
    return None


# ---------------------------------------------------------------------------
# Rendering, permission checks and execution
# ---------------------------------------------------------------------------


def render_proposal(proposal: Proposal) -> str:
    """The confirmation prompt: exactly what will change, and what is missing."""
    if proposal.missing:
        needed = "; ".join(_FIELD_PROMPTS.get(m, m) for m in proposal.missing)
        parts = [proposal.detail, f"Before I can run it I still need {needed}."]
        if proposal.notes:
            parts.extend(f"Note: {note}." for note in proposal.notes)
        # While a command is half-specified the copilot stays on it, so it must
        # say how to get out of that: a bare question will re-ask, by design.
        parts.append('Reply with that, or say "cancel" to drop it.')
        return " ".join(parts)
    parts = [proposal.detail]
    if proposal.notes:
        parts.extend(f"Note: {note}." for note in proposal.notes)
    parts.append('Reply "confirm" to proceed, or "cancel" to drop it.')
    return " ".join(parts)


def proposal_payload(proposal: Proposal, status: str) -> dict:
    return {
        "intent": proposal.code,
        "action": {
            "code": proposal.code,
            "title": proposal.title,
            "status": status,
            "detail": proposal.detail,
            "params": proposal.params,
            "missing": proposal.missing,
            "permissions": list(proposal.permissions),
        },
    }


def missing_permissions(
    proposal: Proposal, permission_codes: set[str], *, is_superadmin: bool
) -> list[str]:
    if is_superadmin:
        return []
    return [p for p in proposal.permissions if p not in permission_codes]


def deny(proposal: Proposal, missing: list[str]) -> DirectReply:
    wanted = ", ".join(f"'{code}'" for code in missing)
    return DirectReply(
        text=(
            f"I can't run that: it needs the {wanted} permission, which your account "
            "doesn't hold. Ask a school admin to grant it, or do it from the "
            "relevant page."
        ),
        payload={
            **proposal_payload(proposal, "denied"),
            "missing_permissions": missing,
        },
    )


def _as_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _audit(
    db: Session,
    school_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: str | None,
    new: dict | None,
    details: str | None = None,
) -> None:
    db.add(
        AuditLog(
            school_id=school_id,
            user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            new=new,
            details=details,
        )
    )
    db.flush()


def _done(proposal: Proposal, text: str, result: dict) -> DirectReply:
    payload = proposal_payload(proposal, "done")
    payload["action"]["result"] = result
    return DirectReply(text=text, payload=payload)


def _failed(proposal: Proposal, message: str) -> DirectReply:
    payload = proposal_payload(proposal, "failed")
    payload["action"]["error"] = message
    return DirectReply(text=f"That didn't go through: {message}", payload=payload)


# --- Execution ---------------------------------------------------------------


def _execute_admit(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    arm = academics_service.get_arm(db, school_id, _as_uuid(p["arm_id"]))
    student = people_service.create_student(
        db,
        school_id,
        admission_no=p["admission_no"],
        first_name=p["first_name"],
        last_name=p["last_name"],
        gender=p["gender"],
    )
    people_service.enroll_student(
        db,
        school_id,
        student_id=student.id,
        arm_id=arm.id,
        session_id=arm.academic_session_id,
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.CREATE.value,
        entity_type="student",
        entity_id=str(student.id),
        new={
            "operation": "copilot_admit_student",
            "admission_no": student.admission_no,
            "full_name": student.full_name,
            "class_arm": arm.full_name,
        },
        details="Admitted via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Admitted {student.full_name} ({student.admission_no}) and enrolled "
        f"them in {arm.full_name}.",
        {
            "student_id": str(student.id),
            "admission_no": student.admission_no,
            "full_name": student.full_name,
            "class_arm": arm.full_name,
        },
    )


def _execute_change_class(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    arm = academics_service.get_arm(db, school_id, _as_uuid(p["arm_id"]))
    result = people_service.change_student_class(
        db,
        school_id,
        student_id=_as_uuid(p["student_id"]),
        session_id=arm.academic_session_id,
        target_arm_id=arm.id,
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.UPDATE.value,
        entity_type="student",
        entity_id=str(p["student_id"]),
        new={"operation": "copilot_change_class", **result},
        details="Class changed via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Moved {p['student_name']} to {result['arm_name']}.",
        result,
    )


def _execute_add_staff(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    staff = people_service.create_staff(
        db,
        school_id,
        staff_no=p["staff_no"],
        full_name=p["full_name"],
        membership_type=p["membership_type"],
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.CREATE.value,
        entity_type="staff",
        entity_id=str(staff.id),
        new={
            "operation": "copilot_add_staff",
            "staff_no": staff.staff_no,
            "full_name": staff.full_name,
            "membership_type": staff.membership_type,
        },
        details="Staff record created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Added {staff.full_name} to staff as {staff.staff_no}.",
        {
            "staff_id": str(staff.id),
            "staff_no": staff.staff_no,
            "full_name": staff.full_name,
            "membership_type": staff.membership_type,
        },
    )


def _execute_create_subject(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    subject = academics_service.create_subject(
        db, school_id, name=p["name"], code=p["code"]
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.CREATE.value,
        entity_type="subject",
        entity_id=str(subject.id),
        new={"operation": "copilot_create_subject", "name": subject.name, "code": subject.code},
        details="Subject created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Created subject {subject.name} with code {subject.code}.",
        {"subject_id": str(subject.id), "name": subject.name, "code": subject.code},
    )


def _execute_create_arm(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    session = academics_service.get_session(db, school_id, _as_uuid(p["session_id"]))
    arm = academics_service.create_arm(
        db, school_id, session_id=session.id, name=p["arm_name"]
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.CREATE.value,
        entity_type="class_arm",
        entity_id=str(arm.id),
        new={
            "operation": "copilot_create_class",
            "name": arm.full_name,
            "session": session.name,
        },
        details="Class created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Created class {arm.full_name} in {session.name}.",
        {"arm_id": str(arm.id), "name": arm.full_name, "session": session.name},
    )


def _execute_create_session(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    session = academics_service.create_session(
        db, school_id, name=p["name"], start_date=None, end_date=None
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.CREATE.value,
        entity_type="academic_session",
        entity_id=str(session.id),
        new={"operation": "copilot_create_session", "name": session.name},
        details="Session created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Created academic session {session.name}. Activate it from "
        "Academics when you're ready to use it.",
        {"session_id": str(session.id), "name": session.name},
    )


def _execute_create_term(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    session = academics_service.get_session(db, school_id, _as_uuid(p["session_id"]))
    name = p.get("name") or f"Term {p['term_no']}"
    term = academics_service.create_term(
        db, school_id, session_id=session.id, term_no=int(p["term_no"]), name=name
    )
    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=AuditAction.CREATE.value,
        entity_type="term",
        entity_id=str(term.id),
        new={"operation": "copilot_create_term", "name": term.name, "session": session.name},
        details="Term created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Created {term.name} in {session.name}.",
        {"term_id": str(term.id), "name": term.name, "session": session.name},
    )


def _execute_results(
    db: Session,
    school_id: uuid.UUID,
    proposal: Proposal,
    *,
    actor_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool,
) -> DirectReply:
    """Run a results transition across every subject offered in the class.

    The per-subject service calls already refuse rows that are not in the right
    state, so "publish" on a class with nothing approved is a no-op rather than
    an error — the summary says so honestly.
    """
    p = proposal.params
    arm_id = _as_uuid(p["arm_id"])
    term_id = _as_uuid(p["term_id"])
    arm = academics_service.get_arm(db, school_id, arm_id)
    term = academics_service.get_term(db, school_id, term_id)
    academics_service.require_active_term(db, school_id, term.id)

    offerings = academics_service.list_offerings(db, school_id, arm.id)
    subjects = sorted({o.subject_id: o.subject for o in offerings}.items(), key=lambda kv: kv[1].name)

    per_subject: list[dict] = []
    totals: dict[str, int] = {}
    for subject_id, subject in subjects:
        if proposal.code == "publish_results":
            moved = results_service.publish_arm_subject(
                db, school_id, arm_id=arm.id, subject_id=subject_id,
                term_id=term.id, actor_id=actor_id,
            )
            key = "published"
        elif proposal.code == "approve_results":
            moved = results_service.approve_arm_subject(
                db, school_id, arm_id=arm.id, subject_id=subject_id,
                term_id=term.id, actor_id=actor_id,
            )
            key = "approved"
        elif proposal.code == "verify_results":
            moved = results_service.verify_arm_subject(
                db, school_id, arm_id=arm.id, subject_id=subject_id,
                term_id=term.id, actor_id=actor_id,
            )
            key = "verified"
        elif proposal.code == "submit_results":
            moved = results_service.submit_arm_subject(
                db, school_id, arm_id=arm.id, subject_id=subject_id,
                term_id=term.id, actor_id=actor_id,
                permission_codes=permission_codes, is_superadmin=is_superadmin,
            )
            key = "submitted"
        else:  # compile_results
            summary = results_service.compile_arm_subject(
                db, school_id, arm_id=arm.id, subject_id=subject_id,
                term_id=term.id, actor_id=actor_id,
                permission_codes=permission_codes, is_superadmin=is_superadmin,
            )
            per_subject.append({"subject": subject.name, **summary})
            for name, value in summary.items():
                totals[name] = totals.get(name, 0) + value
            continue
        if moved:
            per_subject.append({"subject": subject.name, key: moved})
        totals[key] = totals.get(key, 0) + moved

    if not subjects:
        return _failed(
            proposal,
            f"{arm.full_name} has no subjects offered this session, so there was "
            "nothing to work on.",
        )

    moved_total = sum(totals.values())
    if moved_total == 0:
        text = (
            f"Nothing changed. No rows for {arm.full_name} in {term.name} were in "
            f"the state a '{proposal.title.lower()}' can move — check the results "
            "workbench for what is still pending."
        )
    else:
        summary = ", ".join(f"{k} {v}" for k, v in sorted(totals.items()))
        text = f"Done. {arm.full_name} · {term.name}: {summary}."

    _audit(
        db,
        school_id,
        actor_id=actor_id,
        action=p.get("audit", AuditAction.OTHER.value),
        entity_type="result",
        entity_id=str(arm.id),
        new={
            "operation": f"copilot_{proposal.code}",
            "class_arm": arm.full_name,
            "term": term.name,
            "totals": totals,
        },
        details="Results pipeline run via the school copilot chat command",
    )
    payload = {
        "class": arm.full_name,
        "term": term.name,
        "totals": totals,
        "subjects": per_subject,
    }
    return _done(proposal, text, payload)


_EXECUTORS = {
    "admit_student": _execute_admit,
    "change_class": _execute_change_class,
    "add_staff": _execute_add_staff,
    "create_subject": _execute_create_subject,
    "create_class_arm": _execute_create_arm,
    "create_session": _execute_create_session,
    "create_term": _execute_create_term,
}


def execute_proposal(
    db: Session,
    school_id: uuid.UUID,
    proposal: Proposal,
    *,
    actor_id: uuid.UUID,
    permission_codes: set[str],
    is_superadmin: bool = False,
) -> DirectReply:
    """Run a confirmed proposal.

    Never raises for an expected failure: a conflict (duplicate admission
    number), a validation error (a term's session not activated) or a
    permission gap all come back as an honest reply, because a chat turn that
    500s tells the user nothing. Genuinely unexpected exceptions still surface
    to the caller so they are logged rather than swallowed.
    """
    missing = missing_permissions(proposal, permission_codes, is_superadmin=is_superadmin)
    if missing:
        return deny(proposal, missing)

    # A command is several writes in one turn (create the student, then enrol
    # them). If the second step fails the first must not survive, so the whole
    # action runs inside a SAVEPOINT: a failure unwinds the action's rows while
    # the conversation turn itself still commits with an honest reply.
    savepoint = db.begin_nested()
    try:
        if proposal.code in _EXECUTORS:
            reply = _EXECUTORS[proposal.code](db, school_id, proposal, actor_id=actor_id)
        elif proposal.code in _RESULT_PERMISSIONS:
            reply = _execute_results(
                db, school_id, proposal,
                actor_id=actor_id, permission_codes=permission_codes,
                is_superadmin=is_superadmin,
            )
        else:
            reply = _failed(proposal, f"I don't know how to run '{proposal.code}'.")
        savepoint.commit()
        return reply
    except APIError as exc:
        savepoint.rollback()
        return _failed(proposal, exc.message)
    except Exception:  # pragma: no cover - defensive: never 500 a chat turn
        savepoint.rollback()
        logger.exception("Copilot action %s failed", proposal.code)
        return _failed(
            proposal,
            "something went wrong on the server while running it; nothing was changed",
        )


# ---------------------------------------------------------------------------
# Missing-field resolution: a bare reply fills the pending proposal's gap
# ---------------------------------------------------------------------------

_NAME_FIELDS = {"first_name", "last_name", "full_name", "subject_name", "arm_name", "session_name", "term_name"}


def apply_reply(
    db: Session, school_id: uuid.UUID, proposal: Proposal, message: str
) -> bool:
    """Try to read a user's reply as the value of a field the proposal lacks.

    Returns True when something was consumed. Only the fields actually missing
    are considered, so a reply can never silently overwrite a resolved slot.
    """
    text = _clause(message)
    if not text:
        return False
    tokens = _tokens(text)
    consumed = False

    for field_name in list(proposal.missing):
        if field_name == "gender":
            gender, _ = _extract_gender(tokens, text)
            if gender:
                proposal.params["gender"] = gender
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "arm":
            arm = resolve_arm_by_phrase(db, school_id, text)
            if arm is not None:
                proposal.params["arm_id"] = str(arm.id)
                proposal.params["arm_name"] = arm.full_name
                if "session_id" in proposal.params:
                    proposal.params["session_id"] = str(arm.academic_session_id)
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "session":
            session = resolve_session_by_phrase(db, school_id, text)
            if session is not None:
                proposal.params["session_id"] = str(session.id)
                if "session_name" in proposal.params:
                    proposal.params["session_name"] = session.name
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "term":
            term = resolve_term_by_phrase(db, school_id, text)
            if term is not None:
                proposal.params["term_id"] = str(term.id)
                proposal.params["term_name"] = term.name
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "student":
            student = _resolve_student_by_phrase(db, school_id, text)
            if student is not None:
                proposal.params["student_id"] = str(student.id)
                proposal.params["student_name"] = student.full_name
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "term_name":
            term_no = None
            for word, number in _ORDINALS.items():
                if word in tokens:
                    term_no = number
                    break
            if term_no is not None:
                proposal.params["term_no"] = term_no
                proposal.params["name"] = f"{text.title()} Term" if "term" in tokens else text
                proposal.missing.remove(field_name)
                consumed = True
            else:
                digits = [t for t in tokens if t.isdigit() and 1 <= int(t) <= 3]
                if digits:
                    proposal.params["term_no"] = int(digits[0])
                    proposal.params["name"] = text
                    proposal.missing.remove(field_name)
                    consumed = True
        elif field_name in _NAME_FIELDS:
            value = text
            if field_name == "first_name":
                proposal.params["first_name"] = value
            elif field_name == "last_name":
                proposal.params["last_name"] = value
            elif field_name == "full_name":
                proposal.params["full_name"] = value
            elif field_name == "subject_name":
                proposal.params["name"] = value
                proposal.params["code"] = _subject_code(db, school_id, value)
            elif field_name == "arm_name":
                proposal.params["arm_name"] = value
            elif field_name == "session_name":
                proposal.params["name"] = value
            elif field_name == "term_name":
                proposal.params["name"] = value
            proposal.missing.remove(field_name)
            consumed = True
    if consumed:
        proposal.detail = _refresh_detail(db, school_id, proposal)
    return consumed


def _refresh_detail(db: Session, school_id: uuid.UUID, proposal: Proposal) -> str:
    """Rebuild the human summary after fields were filled in."""
    p = proposal.params
    if proposal.code == "admit_student":
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        gender = p.get("gender")
        arm = p.get("arm_name")
        if name and gender and arm:
            return (
                f"Admit {name} ({gender}) to {arm} with admission number "
                f"{p.get('admission_no')}."
            )
    if proposal.code == "create_class_arm" and p.get("arm_name"):
        return f"Create class {p['arm_name']} in {p.get('session_name') or 'the current session'}."
    if proposal.code == "create_session" and p.get("name"):
        return f"Create academic session {p['name']}."
    if proposal.code == "create_term" and p.get("session_name"):
        label = p.get("name") or f"term {p.get('term_no')}"
        return f"Create {label} in {p['session_name']}."
    if proposal.code == "create_subject" and p.get("name"):
        return f"Create subject {p['name']} (code {p.get('code')})."
    if proposal.code == "add_staff" and p.get("full_name"):
        return f"Add {p['full_name']} to staff as {p.get('staff_no')}."
    if proposal.code in _RESULT_PERMISSIONS and p.get("arm_name") and p.get("term_name"):
        return (
            f"{proposal.title} for {p['arm_name']} in {p['term_name']}. "
            "This runs across every subject offered in that class."
        )
    if proposal.code == "change_class" and p.get("arm_name"):
        return f"Move {p.get('student_name')} to {p['arm_name']}."
    return proposal.detail


# ---------------------------------------------------------------------------
# Catalog — what the copilot can do, for help text and the UI
# ---------------------------------------------------------------------------
COMMAND_EXAMPLES: list[dict] = [
    {"code": "admit_student", "example": "add Genesis John to Nursery 1",
     "permissions": [STUDENTS_CREATE, STUDENTS_ENROLL]},
    {"code": "list_roster", "example": "list the students in Nursery 1",
     "permissions": ["students.view"]},
    {"code": "change_class", "example": "move Genesis John to Nursery 2",
     "permissions": [STUDENTS_ENROLL]},
    {"code": "add_staff", "example": "add teacher Grace Ade",
     "permissions": [STAFF_CREATE]},
    {"code": "create_subject", "example": "create subject Further Mathematics",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "create_class_arm", "example": "create class Nursery 3",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "create_session", "example": "create session 2027/2028",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "create_term", "example": "create second term in 2025/2026",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "submit_results", "example": "submit results for JSS 1 A",
     "permissions": [RESULTS_VERIFY]},
    {"code": "compile_results", "example": "compile results for JSS 1 A",
     "permissions": [RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH]},
]


def command_help() -> str:
    lines = [
        "I can also carry out administrative commands — I'll show you exactly "
        "what will change and wait for you to reply \"confirm\":",
    ]
    for item in COMMAND_EXAMPLES:
        lines.append(f"  • {item['example']}")
    lines.append(
        "Commands are checked against your permissions, and every one I run is "
        "written to the audit log."
    )
    return "\n".join(lines)
