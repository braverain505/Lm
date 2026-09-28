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
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import APIError
from ..core.permissions import (
    ACADEMICS_MANAGE,
    ATTENDANCE_MARK,
    CAMPUS_MANAGE,
    FEES_CREATE,
    FEES_PAY,
    RESULTS_APPROVE,
    RESULTS_PUBLISH,
    RESULTS_VERIFY,
    ROLES_MANAGE,
    SCHOOL_MANAGE,
    STAFF_CREATE,
    STUDENTS_CREATE,
    STUDENTS_DELETE,
    STUDENTS_EDIT,
    STUDENTS_ENROLL,
    USERS_MANAGE,
)
from ..models import (
    AcademicSession,
    AuditLog,
    Campus,
    ClassArm,
    FeeStructure,
    Role,
    School,
    Staff,
    Student,
    Subject,
    Term,
)
from ..models.enums import AuditAction
from ..schemas.fees import FeeStructureIn
from . import (
    academics_service,
    attendance_service,
    fees_service,
    people_service,
    rbac_service,
    results_service,
)

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


# A command is rarely typed bare. "please add…", "can you add…", "I want you to
# add…" all mean the same write, so the polite preamble is stripped before the
# verb is read. Without this a natural sentence like "I want you to add Genesis
# John to Nursery 2" matched no detector at all and fell through to the LLM,
# which answered "I can't do that" — the exact bug this fixes.
_POLITE = (
    r"(?:please\s+|kindly\s+|can you\s+|could you\s+|would you\s+|will you\s+|"
    # "I'd like" contracts to no space after the I, hence the two shapes.
    r"i(?:'d like|'d love| want| need| would like)(?:\s+you)?\s+to\s+|"
    # "I wanted to say you should…", "I was saying that you can…": a whole
    # sentence of intent can sit in front of the verb. The trailing words are
    # *speech* verbs only (say/tell/mention/ask) — never a command verb, or the
    # preamble would swallow the "add" it is supposed to introduce.
    r"i\s+(?:just\s+|really\s+)?(?:want|wanted|need|needed|meant|intend|intended|"
    r"was saying|wanted to say|am saying)\s+"
    r"(?:to\s+)?(?:say|tell you|mention|ask you|note)?\s*(?:that\s+)?"
    r"(?:you\s+(?:should|can|could|must|may|might|need to|have to)\s+)?|"
    r"you\s+(?:should|can|could|must|may|might|need to|have to)\s+|"
    r"help me\s+|go ahead and\s+|let'?s\s+)*"
)


def _strip_polite(value: str) -> str:
    """Drop a leading "please / can you / I want you to" preamble."""
    return re.sub(r"^\s*" + _POLITE, "", value or "", flags=re.IGNORECASE)


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
    "campus_name": "what the campus should be called, e.g. \"Ikeja\"",
    "role_name": "what the role should be called, e.g. \"Bursar\"",
    "role": "the role — reply with its name, e.g. \"teacher\"",
    "staff": "which staff member — reply with their name or staff number",
    "teacher": "which teacher — reply with their name or staff number",
    "subject": "the subject — reply with its name, e.g. \"Mathematics\"",
    "amount": "the amount, e.g. \"50000\"",
    "fee": "the fee — reply with the fee structure's name, e.g. \"School Fees\"",
    "fee_name": "what the fee should be called, e.g. \"School Fees\"",
    "school_name": "the school's new name",
    "short_name": "the school's short name",
    "phone": "the phone number",
    "email": "the email address",
    "address": "the address",
    "website": "the website address",
    "currency": "the currency code, e.g. \"NGN\"",
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


def find_arms_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> list[ClassArm]:
    """Every arm a typed class name could mean, best tier first.

    Exact normalised equality wins ("Nursery 1" only matches "Nursery 1", never
    "Nursery 10"); a prefix pass is the fallback so "JSS1A" still finds
    "JSS 1 A", then a containment pass. All the matches of the winning tier are
    returned: a *question* only needs the most likely class, but a *write* must
    be able to tell "this names two classes" from "this names one".
    """
    key = _norm(phrase)
    if not key:
        return []
    arms = _ordered_arms(db, school_id)
    for tier in ("exact", "prefix", "contains"):
        matches: list[ClassArm] = []
        for arm in arms:
            nk = _norm(arm.full_name)
            if tier == "exact":
                hit = _norm(arm.name) == key or nk == key
            elif tier == "prefix":
                if not nk:
                    hit = False
                elif nk.startswith(key):
                    hit = True
                elif key.startswith(nk):
                    # "JSS1A class" is the arm plus a filler word. A longer tail
                    # means the fragment is a sentence, not a class name
                    # ("Nursery 1 and Hauwa Manuel in nursery 2"), and must not
                    # resolve to whatever class it happens to start with.
                    hit = key[len(nk):] in _ARM_TAIL_WORDS
                else:
                    hit = False
            else:
                hit = bool(nk) and (key in nk or nk in key)
            if hit:
                matches.append(arm)
        if matches:
            return matches
    return []


def resolve_arm_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> ClassArm | None:
    """The single best arm for a typed class name, or ``None``.

    This is the read-side resolver: for a question the most likely class is
    exactly what is wanted. Writes use :func:`_unique_arm` instead, which
    refuses an ambiguous phrase rather than guessing at it.
    """
    matches = find_arms_by_phrase(db, school_id, phrase)
    return matches[0] if matches else None


# Words that describe "a class" rather than naming one: "add him to a class"
# must be read as a missing class, not as a class literally called "a class".
_ARM_FILLER = {"", "class", "aclass", "theclass", "arm", "section", "newclass"}
# "JSS1A class" is the stored name "JSS 1 A" plus one of these; anything else
# after the name means the phrase was a sentence, not a class name.
_ARM_TAIL_WORDS = {"class", "classes", "arm", "arms", "section", "sections", "stream", "group"}
_CONNECTIVE_RE = re.compile(r"\b(?:and|then|also)\b", re.IGNORECASE)


def _arm_phrase(value: str) -> str:
    """Tidy the class fragment a command named (" in the  Nursery 1 . " ->
    "Nursery 1"), returning "" when it names no class in particular."""
    phrase = _clause(value).strip(" ,.")
    while True:
        stripped = re.sub(r"^(?:a|an|the|new|some)\s+", "", phrase, flags=re.IGNORECASE)
        if stripped == phrase:
            break
        phrase = stripped
    if _norm(phrase) in _ARM_FILLER:
        return ""
    return phrase


def _unique_arm(
    db: Session, school_id: uuid.UUID, phrase: str
) -> tuple[ClassArm | None, list[ClassArm]]:
    """Resolve a class for a *write*: only when the phrase names exactly one.

    Returns ``(arm, matches)``. ``arm`` is ``None`` both when nothing matched
    and when several classes matched — the caller turns ``matches`` into the
    "which one did you mean?" note instead of silently picking the first.
    """
    key = _norm(phrase)
    if key and _CONNECTIVE_RE.search(_clause(phrase)):
        # "…in Nursery 1 and Hauwa Manuel in nursery 2" is a sentence, not a
        # class name, so only an exact stored name may match it — the loose
        # passes would happily hand back "Nursery 1" and drop the second pupil.
        arms = _ordered_arms(db, school_id)
        exact = [
            arm for arm in arms
            if _norm(arm.name) == key or _norm(arm.full_name) == key
        ]
        return (exact[0], exact) if len(exact) == 1 else (None, exact)
    matches = find_arms_by_phrase(db, school_id, phrase)
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def _swallowed_conjunction(proposal: Proposal) -> bool:
    """True when a parsed field still carries the " and " that ended a clause.

    It is how a one-command reading of a two-command message gives itself away:
    "add Amina John in Nursery 1 and Hauwa Manuel in nursery 2" parses as one
    admission whose class phrase is the entire tail of the sentence.
    """
    return any(
        isinstance(value, str) and _CONNECTIVE_RE.search(value)
        for value in proposal.params.values()
    )


def _list_names(names: list[str]) -> str:
    """"A, B and C" — readable in a chat sentence."""
    if len(names) <= 1:
        return names[0] if names else ""
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _arm_note(
    db: Session, school_id: uuid.UUID, phrase: str, matches: list[ClassArm]
) -> str | None:
    """Why a named class could not be pinned down — spelled out for the user.

    "Still needed: arm" is the honest answer when the user did not name a class,
    but a confusing one when they named a class this school does not have. The
    note says which case it is and what the real options are.
    """
    # Exactly one match means the class *was* resolved — there is nothing to
    # explain. Only a phrase that fits several classes, or none, is worth a note.
    if not _norm(phrase) or len(matches) == 1:
        return None
    if matches:
        listed = ", ".join(arm.full_name for arm in matches[:6])
        return (
            f'"{phrase}" fits more than one class ({listed}) — say exactly which, '
            f'e.g. "{matches[0].full_name}"'
        )
    known = [arm.full_name for arm in _ordered_arms(db, school_id)][:10]
    if not known:
        return (
            f'this school has no classes yet — create one first with '
            f'"create class {phrase}"'
        )
    return (
        f'I have no class called "{phrase}"; the classes on file are '
        f'{_list_names(known)}. Say which one, or create it with '
        f'"create class {phrase}"'
    )


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


def _find_student_in_text(
    db: Session, school_id: uuid.UUID, text: str
) -> Student | None:
    """The longest stored student name appearing anywhere in a free command.

    Longest-match matters here the way it does for class arms: "Aisha Bello"
    must win over a colleague whose surname is a prefix of it, and a name must
    be at least four characters so a two-letter pupil cannot match the word
    "for" inside an unrelated spell.
    """
    q = _norm(text)
    if not q:
        return None
    best: Student | None = None
    for student in people_service.list_students(db, school_id):
        nk = _norm(student.full_name)
        if len(nk) < 4 or nk not in q:
            continue
        if best is None or len(nk) > len(_norm(best.full_name)):
            best = student
    return best


def _resolve_subject_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> Subject | None:
    key = _norm(phrase)
    if not key:
        return None
    for subject in academics_service.list_subjects(db, school_id):
        if _norm(subject.name) == key or _norm(subject.code) == key:
            return subject
    return None


def _find_subject_in_text(
    db: Session, school_id: uuid.UUID, text: str
) -> Subject | None:
    """The longest stored subject name appearing in a free command."""
    q = _norm(text)
    if not q:
        return None
    best: Subject | None = None
    for subject in academics_service.list_subjects(db, school_id):
        nk = _norm(subject.name)
        if len(nk) < 3 or nk not in q:
            continue
        if best is None or len(nk) > len(_norm(best.name)):
            best = subject
    return best


def _resolve_staff_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> Staff | None:
    key = _norm(phrase)
    if not key:
        return None
    staff = people_service.list_staff(db, school_id)
    for member in staff:
        if member.staff_no and _norm(member.staff_no) == key:
            return member
    exact = [m for m in staff if _norm(m.full_name) == key]
    if len(exact) == 1:
        return exact[0]
    partial = [m for m in staff if key and key in _norm(m.full_name)]
    if len(partial) == 1:
        return partial[0]
    return None


def _staff_ambiguity(
    db: Session, school_id: uuid.UUID, phrase: str
) -> list[Staff]:
    key = _norm(phrase)
    return [m for m in people_service.list_staff(db, school_id) if key and key in _norm(m.full_name)]


def _resolve_role_by_name(
    db: Session, school_id: uuid.UUID, phrase: str
) -> Role | None:
    key = _norm(phrase)
    if not key:
        return None
    roles = rbac_service.list_roles(db, school_id)
    for role in roles:
        if _norm(role.code) == key or _norm(role.name) == key:
            return role
    for role in roles:
        nk = _norm(role.name)
        if nk and (key in nk or nk in key):
            return role
    return None


def _resolve_fee_structure_by_phrase(
    db: Session, school_id: uuid.UUID, phrase: str
) -> FeeStructure | None:
    key = _norm(phrase)
    if not key:
        return None
    structures = fees_service.list_fee_structures(db, school_id)
    for structure in structures:
        if _norm(structure.name) == key:
            return structure
    for structure in structures:
        nk = _norm(structure.name)
        if nk and (key in nk or nk in key):
            return structure
    return None


def _find_fee_structure_in_text(
    db: Session, school_id: uuid.UUID, text: str
) -> FeeStructure | None:
    """The longest stored fee-structure name appearing in a free command."""
    q = _norm(text)
    if not q:
        return None
    best = None
    for structure in fees_service.list_fee_structures(db, school_id):
        nk = _norm(structure.name)
        if len(nk) < 4 or nk not in q:
            continue
        if best is None or len(nk) > len(_norm(best.name)):
            best = structure
    return best


_ATT_STATUS_WORDS = {
    "present": "present",
    "absent": "absent",
    "late": "late",
    "excused": "excused",
}

_PAYMENT_METHODS = {
    "cash": "cash",
    "card": "card",
    "transfer": "bank_transfer",
    "bank": "bank_transfer",
    "pos": "pos",
    "paystack": "paystack",
    "flutterwave": "flutterwave",
    "cheque": "other",
    "check": "other",
}

_FEE_TYPES = {
    "tuition": "tuition",
    "boarding": "boarding",
    "activity": "activity",
    "activities": "activity",
    "examination": "examination",
    "exam": "examination",
    "uniform": "uniform",
    "development": "development",
    "transport": "transport",
    "other": "other",
}


def _parse_date(text: str) -> str | None:
    """An explicit YYYY-MM-DD, else today/yesterday."""
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text or "")
    if match:
        return match.group(1)
    lowered = (text or "").lower()
    today = datetime.now(timezone.utc).date()
    if "today" in lowered:
        return today.isoformat()
    if "yesterday" in lowered:
        return (today - timedelta(days=1)).isoformat()
    return None


def _parse_amount(text: str) -> float | None:
    """A money-ish figure: ``50000``, ``50,000`` or ``50k``."""
    match = re.search(r"([0-9][0-9,]*(?:\.\d+)?)\s*k\b", text or "", re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", "")) * 1000
    match = re.search(r"([0-9][0-9,]*(?:\.\d+)?)", text or "")
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def _role_code_for(name: str) -> str:
    code = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return code[:50] or "custom_role"


def _temporary_password() -> str:
    """A one-time password shown to the admin, mirroring the platform flow."""
    return secrets.token_urlsafe(9)


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


def _next_admission_no(
    db: Session, school_id: uuid.UUID, *, claimed: list[str] | None = None
) -> str:
    """The next free admission number.

    ``claimed`` carries numbers already planned earlier in the same message: two
    admissions typed together are parsed before either is written, so without it
    both would be offered the same number and the second insert would fail.
    """
    year = datetime.now(timezone.utc).year
    prefix = f"STU-{year}-"
    existing = list(
        db.scalars(
            select(Student.admission_no).where(Student.school_id == school_id)
        )
    )
    return _next_serial(existing + list(claimed or []), prefix)


def _next_staff_no(
    db: Session, school_id: uuid.UUID, *, claimed: list[str] | None = None
) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"STF-{year}-"
    existing = list(
        db.scalars(select(Staff.staff_no).where(Staff.school_id == school_id))
    )
    return _next_serial(existing + list(claimed or []), prefix)


def _reserve_serial(context: dict, key: str, allocate) -> str:
    """Allocate a generated number and reserve it for the rest of this message.

    ``allocate`` takes the numbers claimed so far. Only a batch installs one of
    these lists (see :func:`_detect_batch`), so a one-off command just gets a
    throwaway list and never writes parser state onto the conversation.
    """
    claimed = context.get(key)
    if not isinstance(claimed, list):
        claimed = []
    number = allocate(claimed)
    claimed.append(number)
    return number


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
    # A role/account/campus command can *name* a results permission ("create
    # role X with permissions results.verify") — that is not a results run.
    if _has(tokens, "role", "permission", "permissions", "login", "account", "campus"):
        return None
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
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str],
    context: dict | None = None,
    **__,
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
    staff_no = _reserve_serial(
        context or {},
        "_claimed_staff_nos",
        lambda claimed: _next_staff_no(db, school_id, claimed=claimed),
    )
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
    r"^\s*" + _POLITE
    + r"(?:add|admit|enrol|enroll|register)\s+"
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
    arm_phrase = _arm_phrase(match.group("arm"))
    gender, raw_name = _extract_gender(tokens, raw_name)
    name = _clean_phrase(raw_name, drop={"student", "pupil", "child", "new"})
    # A write resolves the class only when the phrase names exactly one: "JSS 1"
    # with a JSS 1 A and a JSS 1 B on file must ask which, not pick the first.
    arm, arm_matches = _unique_arm(db, school_id, arm_phrase)
    class_note = _arm_note(db, school_id, arm_phrase, arm_matches)

    # An "enrol/enroll/register X in Y" for someone already on the roll is an
    # *enrolment*, not a second admission: the same person must not be created
    # twice. "add <name> to <class>" stays an admission (a school really can
    # have two pupils by the same name), which is why the verb decides.
    verb_match = re.match(
        r"^\s*" + _POLITE + r"(?P<verb>add|admit|enrol|enroll|register)\b",
        question,
        re.IGNORECASE,
    )
    verb = (verb_match.group("verb") if verb_match else "").lower()
    if verb in ("enrol", "enroll", "register") and name:
        existing = _resolve_student_by_phrase(db, school_id, name)
        if existing is not None:
            missing_enroll: list[str] = []
            if arm is None:
                missing_enroll.append("arm")
            params_enroll = {
                "student_id": str(existing.id),
                "student_name": existing.full_name,
                "admission_no": existing.admission_no,
                "arm_id": str(arm.id) if arm else None,
                "arm_name": arm.full_name if arm else _clause(arm_phrase),
            }
            detail_enroll = (
                f"Enrol {existing.full_name} ({existing.admission_no}) in {arm.full_name}."
                if arm is not None
                else f"Enrol {existing.full_name} ({existing.admission_no}) in a class."
            )
            return Proposal(
                code="enroll_student",
                title="Enrol a student",
                permissions=(STUDENTS_ENROLL,),
                detail=detail_enroll,
                params=params_enroll,
                missing=missing_enroll,
                notes=[class_note] if class_note else [],
            )

    words = [w for w in name.split() if w]
    first_name = " ".join(words[:-1]) if len(words) > 1 else (words[0] if words else "")
    last_name = words[-1] if len(words) > 1 else ""
    admission_no = _reserve_serial(
        context or {},
        "_claimed_admission_nos",
        lambda claimed: _next_admission_no(db, school_id, claimed=claimed),
    )

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
    if class_note:
        notes.append(class_note)
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
        r"^\s*" + _POLITE
        + r"(?:move|transfer|change|shift|promote|demote)\s+(?:the\s+)?(?P<name>.+?)"
        r"(?:\s+from\s+.+?)?\s+(?:to|into)\s+(?P<arm>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    name_phrase = _clause(match.group("name"))
    arm_phrase = _arm_phrase(match.group("arm"))
    # "Aisha Bello's class", "the student Aisha Bello" and friends all name the
    # pupil, not a class: strip the scaffolding before resolving.
    name_phrase = re.sub(r"\b(?:student|pupil|the)\b", " ", name_phrase, flags=re.IGNORECASE)
    name_phrase = re.sub(
        r"'s\s+(?:class|arm|section)\b", " ", name_phrase, flags=re.IGNORECASE
    )
    name_phrase = re.sub(
        r"\b(?:class|arm|section)\b\s*$", " ", name_phrase, flags=re.IGNORECASE
    )
    name_phrase = _clause(name_phrase).strip(" ,.")
    arm, arm_matches = _unique_arm(db, school_id, arm_phrase)
    class_note = _arm_note(db, school_id, arm_phrase, arm_matches)
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
        notes=[class_note] if class_note else [],
    )


# ---------------------------------------------------------------------------
# Detectors: students, academics, attendance, users, school setup, finance
# ---------------------------------------------------------------------------

_UPDATE_VERBS = {"rename", "set", "change", "update", "make"}


def _detect_update_school(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    """"rename the school to X" / "set the school email to Y"."""
    if not _has(tokens, "school") or not (tokens & _UPDATE_VERBS):
        return None
    if _has(
        tokens, "result", "results", "student", "staff", "teacher", "fee",
        "invoice", "payment", "role", "subject", "class", "arm", "campus",
    ):
        return None
    field = None
    for candidate, words in (
        ("name", ("name",)),
        ("short_name", ("shortname", "short")),
        ("phone", ("phone", "telephone")),
        ("email", ("email",)),
        ("address", ("address",)),
        ("website", ("website", "site")),
        ("currency", ("currency",)),
    ):
        if _has(tokens, *words):
            field = candidate
            break
    if field is None and "rename" in tokens:
        field = "name"
    if field is None:
        return None
    match = re.search(r"\b(?:to|as)\s+(?P<value>.+?)\s*$", question, re.IGNORECASE)
    value = _clean_phrase(match.group("value")) if match else ""
    label = {"short_name": "short name"}.get(field, field)
    missing = [] if value else ["school_name" if field == "name" else field]
    detail = (
        f"Set the school's {label} to {value}."
        if value
        else f"Set the school's {label}."
    )
    return Proposal(
        code="update_school",
        title="Update the school profile",
        permissions=(SCHOOL_MANAGE,),
        detail=detail,
        params={"field": field, "value": value},
        missing=missing,
    )


def _detect_add_campus(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "campus" not in tokens or not _is_create(tokens):
        return None
    rest = re.sub(
        r"\b(add|create|make|start|new|a|an|the|called|named|please|campus)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    name = _clause(rest).strip(" ,.")
    missing = [] if name else ["campus_name"]
    return Proposal(
        code="add_campus",
        title="Add a campus",
        permissions=(CAMPUS_MANAGE,),
        detail=f"Add campus {name}." if name else "Add a campus.",
        params={"name": name},
        missing=missing,
    )


def _detect_create_role(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    permissions: list[str] = []
    match = re.search(r"\bpermissions?\s+(?P<perms>.+?)\s*$", question, re.IGNORECASE)
    body = question
    if match:
        permissions = [
            p.strip()
            for p in re.split(r"\s+and\s+|\s*,\s*", match.group("perms"))
            if p.strip()
        ]
        body = question[: match.start()]
    # Only the command body names the role — the permission list may well
    # contain words like "results" or "subject", which must not disqualify it.
    body_tokens = _tokens(body)
    if "role" not in body_tokens or not _is_create(body_tokens):
        return None
    if _has(
        body_tokens, "result", "results", "subject", "session", "term", "class",
        "arm", "student", "staff", "teacher", "campus", "school", "fee",
        "invoice", "payment", "login", "account",
    ):
        return None
    name = _clean_phrase(
        re.sub(
            r"\b(add|create|make|start|new|a|an|the|called|named|role|with|please)\b",
            " ",
            body,
            flags=re.IGNORECASE,
        )
    )
    missing = [] if name else ["role_name"]
    if not name:
        detail = "Create a role."
    elif permissions:
        detail = f"Create role {name} with permissions {', '.join(permissions)}."
    else:
        detail = f"Create role {name} (no permissions yet — assign them after)."
    return Proposal(
        code="create_role",
        title="Create a role",
        permissions=(ROLES_MANAGE,),
        detail=detail,
        params={"name": name, "code": _role_code_for(name), "permissions": permissions},
        missing=missing,
    )


def _detect_create_staff_account(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | DirectReply | None:
    """"give Grace Ade a login" / "create a login for Grace Ade as teacher"."""
    if not _has(tokens, "login", "account", "credentials"):
        return None
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", question)
    email = email_match.group(0) if email_match else ""
    role = None
    role_match = re.search(
        r"\b(?:role|as)\s+(?P<role>[A-Za-z ]+?)\s*$", question, re.IGNORECASE
    )
    if role_match:
        role = _resolve_role_by_name(db, school_id, role_match.group("role").strip())
    body = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", " ", question, flags=re.IGNORECASE)
    body = re.sub(r"\b(?:role|as)\s+[A-Za-z ]+$", " ", body, flags=re.IGNORECASE)
    name = _clean_phrase(
        re.sub(
            r"\b(give|create|make|set|up|a|an|the|for|to|login|log|account|"
            r"credentials|with|email|password|please|staff|teacher|member)\b",
            " ",
            body,
            flags=re.IGNORECASE,
        )
    )
    staff = _resolve_staff_by_phrase(db, school_id, name) if name else None
    if staff is None and name:
        matches = _staff_ambiguity(db, school_id, name)
        if len(matches) > 1:
            listed = ", ".join(f"{m.full_name} ({m.staff_no})" for m in matches[:5])
            return DirectReply(
                text=(
                    f"Several staff match \"{name}\": {listed}. Rephrase with the "
                    "exact name or staff number and I'll add the login."
                ),
                payload={"intent": "create_staff_account", "ambiguous": True},
            )
    if staff is None:
        return Proposal(
            code="create_staff_account",
            title="Create a staff login",
            permissions=(USERS_MANAGE,),
            detail="Create a login for a staff member.",
            params={"staff_id": None, "staff_name": name, "email": email,
                    "role_id": None, "role_name": ""},
            missing=["staff"] + ([] if email else ["email"]),
        )
    if not email:
        email = staff.email or ""
    if role is None:
        role = _resolve_role_by_name(db, school_id, "teacher")
    missing: list[str] = []
    if not email:
        missing.append("email")
    if role is None:
        missing.append("role")
    params = {
        "staff_id": str(staff.id),
        "staff_name": staff.full_name,
        "staff_no": staff.staff_no,
        "email": email,
        "role_id": str(role.id) if role else None,
        "role_name": role.name if role else "",
    }
    detail = (
        f"Create a login for {staff.full_name} ({staff.staff_no}) with email "
        f"{email or '—'}" + (f" and role {role.name}." if role else ".")
    )
    return Proposal(
        code="create_staff_account",
        title="Create a staff login",
        permissions=(USERS_MANAGE,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_update_student(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    """Rename a pupil, or fix their gender."""
    match = re.match(
        r"^\s*rename\s+(?:the\s+)?(?:student\s+|pupil\s+)?(?P<name>.+?)\s+to\s+"
        r"(?P<new>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if match:
        student = _resolve_student_by_phrase(db, school_id, _clause(match.group("name")))
        if student is None:
            return None
        new_name = _clean_phrase(match.group("new"), drop={"student", "pupil"})
        words = [w for w in new_name.split() if w]
        first_name = " ".join(words[:-1]) if len(words) > 1 else (words[0] if words else "")
        last_name = words[-1] if len(words) > 1 else ""
        missing: list[str] = []
        if not first_name:
            missing.append("first_name")
        if not last_name:
            missing.append("last_name")
        return Proposal(
            code="update_student",
            title="Rename a student",
            permissions=(STUDENTS_EDIT,),
            detail=(
                f"Rename {student.full_name} ({student.admission_no}) to {new_name}."
                if new_name
                else f"Rename {student.full_name}."
            ),
            params={
                "student_id": str(student.id),
                "student_name": student.full_name,
                "admission_no": student.admission_no,
                "first_name": first_name,
                "last_name": last_name,
            },
            missing=missing,
        )
    match = re.match(
        r"^\s*(?:change|set|update)\s+(?:the\s+)?(?:student\s+|pupil\s+)?"
        r"(?P<name>.+?)(?:'s)?\s+gender\s+(?:to\s+)?(?P<gender>[a-z]+)\s*$",
        question,
        re.IGNORECASE,
    )
    if match:
        words = {"male": "male", "m": "male", "boy": "male",
                 "female": "female", "f": "female", "girl": "female"}
        gender = words.get(match.group("gender").strip().lower())
        if gender is None:
            return None
        student = _resolve_student_by_phrase(db, school_id, _clause(match.group("name")))
        if student is None:
            return None
        return Proposal(
            code="update_student",
            title="Update a student's gender",
            permissions=(STUDENTS_EDIT,),
            detail=(
                f"Set {student.full_name}'s ({student.admission_no}) gender to {gender}."
            ),
            params={
                "student_id": str(student.id),
                "student_name": student.full_name,
                "admission_no": student.admission_no,
                "gender": gender,
            },
        )
    return None


def _detect_remove_student(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | DirectReply | None:
    if not ({"remove", "delete", "expel", "withdraw"} & tokens):
        return None
    if not _has(tokens, "student", "pupil", "child"):
        return None
    match = re.match(
        r"^\s*(?:remove|delete|expel|withdraw)\s+(?:the\s+)?"
        r"(?:student|pupil|child)?\s*(?P<name>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    phrase = _clause(match.group("name"))
    student = _resolve_student_by_phrase(db, school_id, phrase)
    if student is None:
        matches = _student_ambiguity(db, school_id, phrase)
        if len(matches) > 1:
            listed = ", ".join(f"{s.full_name} ({s.admission_no})" for s in matches[:5])
            return DirectReply(
                text=(
                    f"Several students match \"{phrase}\": {listed}. Rephrase with "
                    "the exact name or admission number."
                ),
                payload={"intent": "remove_student", "ambiguous": True},
            )
        return DirectReply(
            text=f"I couldn't find a student called \"{phrase}\" in this school's records.",
            payload={"intent": "remove_student", "not_found": True},
        )
    return Proposal(
        code="remove_student",
        title="Remove a student",
        permissions=(STUDENTS_DELETE,),
        detail=(
            f"Remove {student.full_name} ({student.admission_no}) from the school's "
            "active student list. Their records are kept but hidden."
        ),
        params={
            "student_id": str(student.id),
            "student_name": student.full_name,
            "admission_no": student.admission_no,
        },
    )


def _detect_promote_class(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | DirectReply | None:
    if "promote" not in tokens:
        return None
    match = re.match(
        r"^\s*promote\s+(?P<src>.+?)\s+(?:to|into)\s+(?P<dst>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    src = resolve_arm_by_phrase(db, school_id, _clause(match.group("src")))
    dst = resolve_arm_by_phrase(db, school_id, _clause(match.group("dst")))
    if src is None or dst is None:
        return None  # a single pupil's class change — the change_class detector owns it
    if src.academic_session_id == dst.academic_session_id:
        return DirectReply(
            text=(
                f"{src.full_name} and {dst.full_name} are in the same session. "
                "To move one pupil, use 'move <name> to <class>'."
            ),
            payload={"intent": "promote_class", "same_session": True},
        )
    count = len(people_service.list_enrollments(db, school_id, src.id))
    return Proposal(
        code="promote_class",
        title="Promote a class",
        permissions=(STUDENTS_ENROLL,),
        detail=(
            f"Promote {count} student{'s' if count != 1 else ''} from {src.full_name} "
            f"to {dst.full_name} for the next session. Pupils without a seat in the "
            "target class are skipped."
        ),
        params={
            "from_arm_id": str(src.id),
            "from_arm_name": src.full_name,
            "to_arm_id": str(dst.id),
            "to_arm_name": dst.full_name,
            "from_session_id": str(src.academic_session_id),
            "to_session_id": str(dst.academic_session_id),
            "count": count,
        },
    )


def _detect_activate_session(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "session" not in tokens or not ({"activate", "open"} & tokens):
        return None
    rest = re.sub(
        r"\b(activate|open|the|please|session)\b", " ", question, flags=re.IGNORECASE
    )
    name = _clause(rest).strip(" ,.")
    session = resolve_session_by_phrase(db, school_id, name) if name else None
    missing = [] if session else ["session"]
    return Proposal(
        code="activate_session",
        title="Activate a session",
        permissions=(ACADEMICS_MANAGE,),
        detail=(
            f"Activate {session.name} as the current academic session."
            if session
            else "Activate an academic session."
        ),
        params={
            "session_id": str(session.id) if session else None,
            "session_name": session.name if session else name,
        },
        missing=missing,
    )


def _detect_activate_term(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "term" not in tokens or not ({"activate", "open"} & tokens):
        return None
    rest = re.sub(
        r"\b(activate|open|the|please|term)\b", " ", question, flags=re.IGNORECASE
    )
    name = _clause(rest).strip(" ,.")
    term = resolve_term_by_phrase(db, school_id, name) if name else None
    missing = [] if term else ["term"]
    return Proposal(
        code="activate_term",
        title="Activate a term",
        permissions=(ACADEMICS_MANAGE,),
        detail=(f"Activate {term.name} as the current term." if term else "Activate a term."),
        params={
            "term_id": str(term.id) if term else None,
            "term_name": term.name if term else name,
        },
        missing=missing,
    )


def _detect_close_term(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    if "term" not in tokens or not ({"close", "end", "finish"} & tokens):
        return None
    rest = re.sub(
        r"\b(close|end|finish|the|please|term)\b", " ", question, flags=re.IGNORECASE
    )
    name = _clause(rest).strip(" ,.")
    term = resolve_term_by_phrase(db, school_id, name) if name else None
    missing = [] if term else ["term"]
    return Proposal(
        code="close_term",
        title="Close a term",
        permissions=(ACADEMICS_MANAGE,),
        detail=(
            f"Close {term.name}. No further result changes will be allowed for it."
            if term
            else "Close a term."
        ),
        params={
            "term_id": str(term.id) if term else None,
            "term_name": term.name if term else name,
        },
        missing=missing,
    )


def _detect_add_offering(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    """"add Mathematics to JSS 1 A" / "offer Further Mathematics in JSS 1 A"."""
    if not (_is_create(tokens) or "offer" in tokens):
        return None
    if _has(
        tokens, "session", "term", "result", "results", "role", "staff", "teacher",
        "guardian", "campus", "fee", "invoice", "payment", "school", "student",
        "pupil", "login", "account",
    ):
        return None
    arm = find_arm_in_text(db, school_id, question)
    if arm is None:
        return None
    subject = _find_subject_in_text(db, school_id, question)
    if subject is None:
        return None
    already = any(
        o.subject_id == subject.id
        for o in academics_service.list_offerings(db, school_id, arm.id)
    )
    notes = (
        [f"{subject.name} is already offered in {arm.full_name} — nothing would change"]
        if already
        else []
    )
    return Proposal(
        code="add_offering",
        title="Add a subject to a class",
        permissions=(ACADEMICS_MANAGE,),
        detail=f"Add {subject.name} to {arm.full_name}'s subjects.",
        params={
            "arm_id": str(arm.id),
            "arm_name": arm.full_name,
            "subject_id": str(subject.id),
            "subject_name": subject.name,
        },
        notes=notes,
    )


def _detect_assign_teacher(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    """"assign Grace Ade to Mathematics in JSS 1 A"."""
    if "assign" not in tokens:
        return None
    if _has(tokens, "role", "permission", "permissions", "result", "results"):
        return None
    match = re.match(
        r"^\s*assign\s+(?P<teacher>.+?)\s+to\s+(?:teach\s+)?(?P<rest>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    rest = match.group("rest")
    arm = find_arm_in_text(db, school_id, rest)
    subject = _find_subject_in_text(db, school_id, rest)
    teacher_phrase = _clean_phrase(match.group("teacher"), drop={"teacher", "the"})
    teacher = _resolve_staff_by_phrase(db, school_id, teacher_phrase)
    missing: list[str] = []
    if teacher is None:
        missing.append("teacher")
    if subject is None:
        missing.append("subject")
    if arm is None:
        missing.append("arm")
    params = {
        "teacher_id": str(teacher.id) if teacher else None,
        "teacher_name": teacher.full_name if teacher else teacher_phrase,
        "subject_id": str(subject.id) if subject else None,
        "subject_name": subject.name if subject else "",
        "arm_id": str(arm.id) if arm else None,
        "arm_name": arm.full_name if arm else "",
    }
    detail = (
        f"Assign {teacher.full_name} to teach {subject.name} in {arm.full_name}."
        if not missing
        else "Assign a teacher to a subject and class."
    )
    return Proposal(
        code="assign_teacher",
        title="Assign a teacher",
        permissions=(ACADEMICS_MANAGE,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_add_guardian(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | DirectReply | None:
    """"add guardian Mary Bello for Aisha Bello"."""
    if not _has(tokens, "guardian", "parent") or not _is_create(tokens):
        return None
    match = re.match(
        r"^\s*(?:add|create|register)\s+(?:a\s+|an\s+|the\s+)?(?:guardian|parent)\s+"
        r"(?P<name>.+?)\s+(?:for|of)\s+(?P<student>.+?)\s*$",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw_name = match.group("name")
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw_name)
    phone_match = re.search(r"(\+?\d[\d\s-]{6,})", raw_name)
    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(1).strip() if phone_match else ""
    name = raw_name
    for pattern in (r"[\w.+-]+@[\w-]+\.[\w.-]+", r"\+?\d[\d\s-]{6,}", r"\b(?:phone|tel|email)\b"):
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)
    name = _clean_phrase(name, drop={"the", "and"})
    student = _resolve_student_by_phrase(db, school_id, _clause(match.group("student")))
    missing: list[str] = []
    if not name:
        missing.append("full_name")
    if student is None:
        missing.append("student")
    params = {
        "full_name": name,
        "phone": phone,
        "email": email,
        "relationship": "guardian",
        "student_id": str(student.id) if student else None,
        "student_name": student.full_name if student else _clause(match.group("student")),
    }
    detail = (
        f"Add {name} as {student.full_name}'s guardian"
        + (f" (phone {phone})" if phone else "")
        + (f" (email {email})" if email else "")
        + "."
        if name and student
        else "Add a guardian for a student."
    )
    return Proposal(
        code="add_guardian",
        title="Add a guardian",
        permissions=(STUDENTS_EDIT,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_mark_attendance(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    """"mark JSS 1 A present today", "mark Aisha Bello absent", "mark staff present"."""
    if not ({"mark", "record"} & tokens):
        return None
    status = next((v for k, v in _ATT_STATUS_WORDS.items() if k in tokens), None)
    if status is None:
        return None
    date = _parse_date(question) or datetime.now(timezone.utc).date().isoformat()
    staff_only = _has(tokens, "staff", "teachers") and not _has(
        tokens, "student", "students", "pupils", "class"
    )
    phrase = question
    for pattern in (
        r"\b(mark|record|attendance)\b",
        r"\b(present|absent|late|excused)\b",
        r"\b(today|yesterday|for|on|the|please|both)\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    ):
        phrase = re.sub(pattern, " ", phrase, flags=re.IGNORECASE)
    phrase = _clause(phrase).strip(" ,.")
    if staff_only:
        target = _resolve_staff_by_phrase(db, school_id, phrase)
        missing = [] if target else ["staff"]
        return Proposal(
            code="mark_attendance",
            title="Mark staff attendance",
            permissions=(ATTENDANCE_MARK,),
            detail=(
                f"Mark {target.full_name} as {status} for {date}."
                if target
                else "Mark a staff member's attendance."
            ),
            params={
                "scope": "staff",
                "staff_id": str(target.id) if target else None,
                "staff_name": target.full_name if target else phrase,
                "status": status,
                "date": date,
            },
            missing=missing,
        )
    student = _resolve_student_by_phrase(db, school_id, phrase) if phrase else None
    if student is not None:
        return Proposal(
            code="mark_attendance",
            title="Mark attendance",
            permissions=(ATTENDANCE_MARK,),
            detail=(
                f"Mark {student.full_name} ({student.admission_no}) as {status} "
                f"for {date}."
            ),
            params={
                "scope": "student",
                "student_id": str(student.id),
                "student_name": student.full_name,
                "status": status,
                "date": date,
            },
        )
    arm = resolve_arm_by_phrase(db, school_id, phrase) or find_arm_in_text(
        db, school_id, question
    )
    if arm is None:
        return None
    count = len(people_service.list_enrollments(db, school_id, arm.id))
    return Proposal(
        code="mark_attendance",
        title="Mark class attendance",
        permissions=(ATTENDANCE_MARK,),
        detail=(
            f"Mark all {count} student{'s' if count != 1 else ''} in {arm.full_name} "
            f"as {status} for {date}."
        ),
        params={
            "scope": "class",
            "arm_id": str(arm.id),
            "arm_name": arm.full_name,
            "status": status,
            "date": date,
            "count": count,
        },
    )


def _detect_create_fee_structure(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | None:
    """"create a fee structure called School Fees of 50000"."""
    if not _has(tokens, "fee", "fees") or not _is_create(tokens):
        return None
    if _has(tokens, "invoice", "invoices", "payment", "payments", "student", "pupil"):
        return None
    amount = _parse_amount(question)
    body = re.sub(
        r"\b(create|add|make|new|a|an|the|please|fee|fees|structure|called|named)\b",
        " ",
        question,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\b(?:of|at|amount|costing|worth|for|is)?\s*[0-9][0-9,]*(?:\.\d+)?\s*k?\b",
        " ",
        body,
        flags=re.IGNORECASE,
    )
    name = _clause(body).strip(" ,.")
    fee_type = next(
        (v for k, v in _FEE_TYPES.items() if k in tokens), "tuition"
    )
    arm = find_arm_in_text(db, school_id, question)
    missing: list[str] = []
    if not name:
        missing.append("fee_name")
    if amount is None:
        missing.append("amount")
    params = {
        "name": name,
        "amount": amount,
        "fee_type": fee_type,
        "arm_id": str(arm.id) if arm else None,
        "arm_name": arm.full_name if arm else "",
        "applicable_to": "specific_arm" if arm else "all",
    }
    if name and amount is not None:
        scope = f" for {arm.full_name}" if arm else " for the whole school"
        detail = f"Create the fee structure {name} of {amount:,.0f}{scope}."
    else:
        detail = "Create a fee structure."
    return Proposal(
        code="create_fee_structure",
        title="Create a fee structure",
        permissions=(FEES_CREATE,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_create_invoice(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | DirectReply | None:
    """"raise an invoice for Aisha Bello for School Fees"."""
    if not _has(tokens, "invoice", "invoices", "bill"):
        return None
    if not (_is_create(tokens) or ({"raise", "issue", "send"} & tokens)):
        return None
    student = _find_student_in_text(db, school_id, question)
    structure = _find_fee_structure_in_text(db, school_id, question)
    if structure is None:
        structures = fees_service.list_fee_structures(db, school_id)
        if len(structures) == 1:
            structure = structures[0]
    missing: list[str] = []
    if student is None:
        missing.append("student")
    if structure is None:
        missing.append("fee")
    params = {
        "student_id": str(student.id) if student else None,
        "student_name": student.full_name if student else "",
        "fee_structure_id": str(structure.id) if structure else None,
        "fee_name": structure.name if structure else "",
    }
    detail = (
        f"Raise an invoice for {student.full_name} for {structure.name}."
        if student and structure
        else "Raise an invoice for a student."
    )
    return Proposal(
        code="create_invoice",
        title="Raise an invoice",
        permissions=(FEES_CREATE,),
        detail=detail,
        params=params,
        missing=missing,
    )


def _detect_record_payment(
    db: Session, school_id: uuid.UUID, *, question: str, tokens: set[str], **__
) -> Proposal | DirectReply | None:
    """"record a payment of 50000 from Aisha Bello [for School Fees]"."""
    if not ({"payment", "paid", "collect", "collected", "receive", "received"} & tokens):
        return None
    if not ({"record", "collect", "collected", "receive", "received", "log", "payment", "paid"} & tokens):
        return None
    amount = _parse_amount(question)
    student = _find_student_in_text(db, school_id, question)
    structure = _find_fee_structure_in_text(db, school_id, question)
    method = next((v for k, v in _PAYMENT_METHODS.items() if k in tokens), "cash")
    missing: list[str] = []
    invoice = None
    if student is None:
        missing.append("student")
    else:
        invoices, _total = fees_service.list_invoices(
            db, school_id, student_id=student.id, status=None, limit=200
        )
        open_invoices = [
            inv for inv in invoices if inv.status not in ("paid", "write_off", "expired")
        ]
        if structure is not None:
            open_invoices = [
                inv for inv in open_invoices if inv.fee_structure_id == structure.id
            ]
        if len(open_invoices) == 1:
            invoice = open_invoices[0]
        elif not open_invoices:
            scope = f" for {structure.name}" if structure else ""
            return DirectReply(
                text=(
                    f"I couldn't find an unpaid invoice for {student.full_name}{scope}. "
                    "Raise the invoice first (say 'raise an invoice for "
                    f"{student.full_name}'), then record the payment."
                ),
                payload={"intent": "record_payment", "no_invoice": True},
            )
        else:
            missing.append("fee")
    if amount is None:
        missing.append("amount")
    params = {
        "invoice_id": str(invoice.id) if invoice else None,
        "student_id": str(student.id) if student else None,
        "student_name": student.full_name if student else "",
        "amount": amount,
        "payment_method": method,
        "fee_structure_id": str(structure.id) if structure else None,
        "fee_name": structure.name if structure else "",
    }
    if invoice is not None and amount is not None:
        detail = (
            f"Record a {method.replace('_', ' ')} payment of {amount:,.0f} from "
            f"{student.full_name} against invoice {invoice.reference_number}."
        )
    else:
        detail = "Record a fee payment."
    return Proposal(
        code="record_payment",
        title="Record a payment",
        permissions=(FEES_PAY,),
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
    _detect_create_role,
    _detect_create_staff_account,
    _detect_update_school,
    _detect_add_campus,
    _detect_create_fee_structure,
    _detect_create_invoice,
    _detect_record_payment,
    _detect_add_staff,
    _detect_update_student,
    _detect_activate_session,
    _detect_activate_term,
    _detect_close_term,
    _detect_assign_teacher,
    _detect_add_offering,
    _detect_add_guardian,
    _detect_promote_class,
    _detect_admit_student,
    _detect_change_class,
    _detect_remove_student,
    _detect_mark_attendance,
)


# Joins that separate two commands in one message: "add A to Nursery 1 and B to
# Nursery 2". Only conjunctions/punctuation — never a bare word — so a sentence
# that is not really a list is still read whole.
_BATCH_SPLIT_RE = re.compile(r"\s*(?:,|;|\band\b|\bthen\b|\balso\b)\s*", re.IGNORECASE)
_BATCH_HEAD_RE = re.compile(r"^\s*" + _POLITE + r"(?P<verb>[a-z]+)\b\s*", re.IGNORECASE)
# Verbs a command can open with. The message's leading verb carries across the
# conjunction ("add A to X and B to Y" means "add" twice), and a clause that
# names a verb of its own is read as that verb — so one message may mix kinds
# ("move A to X and create class Y").
_BATCH_VERBS = {
    "add", "admit", "enrol", "enroll", "register", "create", "make",
    "move", "transfer", "shift", "promote", "remove", "delete", "rename",
    "update", "mark", "assign", "record", "activate", "close",
    # The results pipeline: "submit results for X and publish results for Y".
    "publish", "release", "approve", "verify", "submit", "compile",
}


def _parse_single(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    tokens: set[str] | None = None,
    context: dict | None = None,
) -> Proposal | DirectReply | None:
    """Run the detector chain over one command sentence."""
    tokens = _tokens(question) if tokens is None else tokens
    for detector in _DETECTORS:
        out = detector(
            db, school_id, question=question, tokens=tokens, context=context or {}
        )
        if out is not None:
            return out
    return None


def _parse_clause(
    db: Session, school_id: uuid.UUID, *, part: str, verb: str, context: dict
) -> Proposal | DirectReply | None:
    """Parse one clause of a multi-command message.

    A clause may name a command verb of its own, and is then parsed as that
    command ("… and create subject Z"); otherwise the message's leading verb
    carries across the conjunction ("add A to X and B to Y").
    """
    lead = part.split(maxsplit=1)[0].lower() if part else ""
    if lead not in _BATCH_VERBS and verb:
        return _parse_single(db, school_id, question=f"{verb} {part}", context=context)
    parsed = _parse_single(db, school_id, question=part, context=context)
    if isinstance(parsed, Proposal):
        return parsed
    return _parse_single(db, school_id, question=f"{verb} {part}", context=context)


def _detect_batch(
    db: Session, school_id: uuid.UUID, *, question: str, context: dict
) -> list[Proposal] | None:
    """Two or more commands in one message, or ``None`` for a single command.

    "add Amina John in Nursery 1 and Hauwa Manuel in nursery 2" is two
    admissions — not one admission into a class literally called "Nursery 1 and
    Hauwa Manuel in nursery 2". Every clause has to parse into a command *of its
    own* before the message is read as a list; anything else falls back to the
    single parse, so a clause is never silently dropped. The clauses need not be
    the same kind of command — "add a pupil and create a subject" is two.
    """
    head = _BATCH_HEAD_RE.match(question)
    if head is None:
        return None
    verb = head.group("verb").lower()
    if verb not in _BATCH_VERBS:
        return None
    parts = [
        part.strip(" ,.;")
        for part in _BATCH_SPLIT_RE.split(question[head.end():])
        if part.strip(" ,.;")
    ]
    if len(parts) < 2:
        return None
    # Every clause is parsed before anything is written, so the generated
    # numbers each one reserves are tracked here — two admissions typed together
    # must not both be planned as the same admission number.
    parser_context = {
        **context,
        "_claimed_admission_nos": [],
        "_claimed_staff_nos": [],
    }
    proposals: list[Proposal] = []
    for part in parts:
        parsed = _parse_clause(
            db, school_id, part=part, verb=verb, context=parser_context
        )
        if not isinstance(parsed, Proposal):
            return None
        proposals.append(parsed)
    return proposals


def detect_action(
    db: Session,
    school_id: uuid.UUID,
    *,
    question: str,
    context: dict,
) -> list[Proposal] | Proposal | DirectReply | None:
    """Parse a chat message into an admin command, or ``None`` for a question.

    A list comes back when the message carries several commands at once (see
    :func:`_detect_batch`); the caller proposes them together and runs them in
    order once the user confirms.
    """
    # Strip the polite preamble once, here, so every detector sees the same
    # bare command shape ("create subject X", not "I want you to create
    # subject X"). The name-scraping detectors then don't have to know about it.
    question = _strip_polite(question)
    context = context or {}
    single = _parse_single(
        db, school_id, question=question, tokens=_tokens(question), context=context
    )
    batch = _detect_batch(db, school_id, question=question, context=context)
    if batch is not None:
        # A message that splits cleanly into several commands wins over reading
        # it as one — unless the one reading is a *complete, uncontaminated*
        # command in its own right, which is what a real list of values joined
        # by "and" looks like ("create role Bursar with permissions a and b").
        clean = (
            isinstance(single, Proposal)
            and not single.missing
            and not _swallowed_conjunction(single)
        )
        if not clean:
            return batch
    return single


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


# ---------------------------------------------------------------------------
# Batches — several commands given in one message
#
# The pending action slot holds one proposal, so a message that carries three
# admissions has to be run as a queue: the fields each one still needs are
# collected one item at a time (the same "still needed" prompt), and "confirm"
# then runs every item in order, each in its own SAVEPOINT so one failure does
# not unwind the others.
# ---------------------------------------------------------------------------
def batch_to_context(proposals: list[Proposal]) -> dict:
    return {"batch": [proposal.to_context() for proposal in proposals]}


def is_batch(raw: dict | None) -> bool:
    return bool(raw) and isinstance((raw or {}).get("batch"), list)


def batch_from_context(raw: dict) -> list[Proposal]:
    return [Proposal.from_context(item) for item in (raw.get("batch") or [])]


def _batch_needs(proposal: Proposal) -> str:
    return "; ".join(_FIELD_PROMPTS.get(m, m) for m in proposal.missing)


def render_batch(proposals: list[Proposal]) -> str:
    """The confirmation prompt for a whole message's worth of commands."""
    count = len(proposals)
    lines = [
        f"That message holds {count} commands — nothing runs until you confirm:",
    ]
    for i, proposal in enumerate(proposals, 1):
        needs = f" (still needs {_batch_needs(proposal)})" if proposal.missing else ""
        lines.append(f"{i}. {proposal.detail}{needs}")
        lines.extend(f"   Note: {note}." for note in proposal.notes)
    first_missing = next(
        (i for i, proposal in enumerate(proposals, 1) if proposal.missing), None
    )
    if first_missing is not None:
        lines.append(
            f"Start with item {first_missing}: I need "
            f"{_batch_needs(proposals[first_missing - 1])}."
        )
        lines.append('Reply with that, or say "cancel" to drop all of them.')
    else:
        lines.append(f'Reply "confirm" to run all {count}, or "cancel" to drop them.')
    return "\n".join(lines)


def batch_payload(
    proposals: list[Proposal],
    status: str,
    *,
    results: list[dict | None] | None = None,
) -> dict:
    """One action card for the whole batch: an item per command."""
    items = []
    for i, proposal in enumerate(proposals, 1):
        item: dict = {
            "n": i,
            "code": proposal.code,
            "title": proposal.title,
            "detail": proposal.detail,
            "missing": list(proposal.missing),
        }
        if results is not None and i - 1 < len(results) and results[i - 1]:
            item.update(results[i - 1])
            item["n"] = i
        items.append(item)
    count = len(proposals)
    if status == "cancelled":
        detail = f"Nothing was changed — all {count} commands were dropped."
    elif status == "denied":
        detail = f"Nothing was changed — none of the {count} commands ran."
    elif status == "done":
        detail = f"All {count} commands ran."
    elif status == "failed":
        detail = f"{count} commands ran — at least one did not go through."
    else:
        waiting = sum(1 for proposal in proposals if proposal.missing)
        detail = (
            f"{waiting} of {count} still need a detail before anything runs."
            if waiting
            else f"{count} commands are waiting for your \"confirm\"."
        )
    return {
        "intent": "batch",
        "action": {
            "code": "batch",
            "title": f"{count} commands at once",
            "status": status,
            "detail": detail,
            "missing": [],
            "items": items,
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


def _json_safe(value):
    """Coerce a value into something the audit log's JSONB column accepts.

    Money arrives from the database as ``Decimal`` and from the chat as
    ``float``; the JSON serializer only knows the latter. Since an audit row is
    a side effect of a command that has already succeeded, it must never be the
    thing that breaks the turn.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


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
            new=_json_safe(new) if new is not None else None,
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


def _execute_enroll(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    arm = academics_service.get_arm(db, school_id, _as_uuid(p["arm_id"]))
    enrollment = people_service.enroll_student(
        db,
        school_id,
        student_id=_as_uuid(p["student_id"]),
        arm_id=arm.id,
        session_id=arm.academic_session_id,
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="student_enrollment",
        entity_id=str(enrollment.id),
        new={"operation": "copilot_enroll_student", "student": p["student_name"],
             "class_arm": arm.full_name},
        details="Student enrolled via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Enrolled {p['student_name']} in {arm.full_name}.",
        {"student_id": p["student_id"], "admission_no": p.get("admission_no"),
         "class_arm": arm.full_name},
    )


def _execute_update_student(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    fields = {
        key: p[key]
        for key in ("first_name", "last_name", "gender")
        if p.get(key)
    }
    student = people_service.update_student(
        db, school_id, _as_uuid(p["student_id"]), **fields
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="student",
        entity_id=str(student.id),
        new={"operation": "copilot_update_student", "admission_no": student.admission_no,
             **fields},
        details="Student record updated via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Updated {student.full_name} ({student.admission_no}).",
        {"student_id": str(student.id), "full_name": student.full_name,
         "admission_no": student.admission_no},
    )


def _execute_remove_student(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    people_service.delete_student(db, school_id, _as_uuid(p["student_id"]))
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.DELETE.value, entity_type="student",
        entity_id=p["student_id"],
        new={"operation": "copilot_remove_student", "admission_no": p.get("admission_no"),
             "full_name": p.get("student_name")},
        details="Student removed via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Removed {p['student_name']} ({p.get('admission_no', '')}) from the "
        "active student list.",
        {"student_id": p["student_id"], "full_name": p.get("student_name")},
    )


def _execute_promote_class(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    result = people_service.promote_students(
        db,
        school_id,
        from_session_id=_as_uuid(p["from_session_id"]),
        to_session_id=_as_uuid(p["to_session_id"]),
        target_arms=[
            {"from_arm_id": _as_uuid(p["from_arm_id"]),
             "to_arm_id": _as_uuid(p["to_arm_id"])}
        ],
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="student_enrollment",
        entity_id=p["to_arm_id"],
        new={"operation": "copilot_promote_class", "from": p.get("from_arm_name"),
             "to": p.get("to_arm_name"), "promoted": result["promoted"],
             "skipped": len(result["skipped"])},
        details="Class promoted via the school copilot chat command",
    )
    skipped = len(result["skipped"])
    text = f"Done. Promoted {result['promoted']} student"
    text += "s" if result["promoted"] != 1 else ""
    text += f" from {p.get('from_arm_name')} to {p.get('to_arm_name')}."
    if skipped:
        text += f" {skipped} were skipped (no seat mapped in the target class)."
    return _done(proposal, text, {"promoted": result["promoted"], "skipped": skipped})


def _execute_activate_session(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    session = academics_service.activate_session(db, school_id, _as_uuid(p["session_id"]))
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="academic_session",
        entity_id=str(session.id),
        new={"operation": "copilot_activate_session", "name": session.name},
        details="Session activated via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. {session.name} is now the current academic session.",
        {"session_id": str(session.id), "name": session.name},
    )


def _execute_activate_term(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    term = academics_service.activate_term(db, school_id, _as_uuid(p["term_id"]))
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="term", entity_id=str(term.id),
        new={"operation": "copilot_activate_term", "name": term.name},
        details="Term activated via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. {term.name} is now the current term.",
        {"term_id": str(term.id), "name": term.name},
    )


def _execute_close_term(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    term = academics_service.close_term(db, school_id, _as_uuid(p["term_id"]))
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="term", entity_id=str(term.id),
        new={"operation": "copilot_close_term", "name": term.name, "status": term.status},
        details="Term closed via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Closed {term.name}. Results in it are now read-only.",
        {"term_id": str(term.id), "name": term.name, "status": term.status},
    )


def _execute_add_offering(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    offering = academics_service.add_offering(
        db, school_id, arm_id=_as_uuid(p["arm_id"]), subject_id=_as_uuid(p["subject_id"])
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="subject_offering",
        entity_id=str(offering.id),
        new={"operation": "copilot_add_offering", "subject": p.get("subject_name"),
             "class_arm": p.get("arm_name")},
        details="Subject added to a class via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. {p.get('subject_name')} is now offered in {p.get('arm_name')}.",
        {"offering_id": str(offering.id), "subject": p.get("subject_name"),
         "class": p.get("arm_name")},
    )


def _execute_assign_teacher(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    assignment = academics_service.assign_subject(
        db, school_id,
        arm_id=_as_uuid(p["arm_id"]),
        subject_id=_as_uuid(p["subject_id"]),
        teacher_id=_as_uuid(p["teacher_id"]),
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="subject_assignment",
        entity_id=str(assignment.id),
        new={"operation": "copilot_assign_teacher", "teacher": p.get("teacher_name"),
             "subject": p.get("subject_name"), "class_arm": p.get("arm_name")},
        details="Teacher assigned via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. {p.get('teacher_name')} now teaches {p.get('subject_name')} in "
        f"{p.get('arm_name')}.",
        {"assignment_id": str(assignment.id), "teacher": p.get("teacher_name"),
         "subject": p.get("subject_name"), "class": p.get("arm_name")},
    )


def _execute_add_guardian(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    guardian = people_service.create_guardian(
        db, school_id,
        full_name=p["full_name"],
        phone=p.get("phone") or None,
        email=p.get("email") or None,
    )
    people_service.link_guardian(
        db, school_id,
        student_id=_as_uuid(p["student_id"]),
        guardian_id=guardian.id,
        relationship=p.get("relationship") or "guardian",
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="guardian",
        entity_id=str(guardian.id),
        new={"operation": "copilot_add_guardian", "guardian": guardian.full_name,
             "student": p.get("student_name")},
        details="Guardian added via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Added {guardian.full_name} as {p.get('student_name')}'s guardian.",
        {"guardian_id": str(guardian.id), "name": guardian.full_name,
         "student": p.get("student_name")},
    )


def _execute_mark_attendance(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    """Mark one pupil, one staff member, or a whole class for the date."""
    p = proposal.params
    status = p["status"]
    date = p["date"]
    scope = p["scope"]
    if scope == "staff":
        attendance_service.record_staff_attendance(
            db, school_id=school_id, staff_id=_as_uuid(p["staff_id"]), campus_id=None,
            date=date, status=status, marked_by=actor_id,
        )
        marked, label = 1, p.get("staff_name") or "staff member"
    elif scope == "student":
        attendance_service.record_student_attendance(
            db, school_id=school_id, student_id=_as_uuid(p["student_id"]), campus_id=None,
            date=date, status=status, marked_by=actor_id,
        )
        marked, label = 1, p.get("student_name") or "student"
    else:
        rows = people_service.list_enrollments(db, school_id, _as_uuid(p["arm_id"]))
        for enrollment in rows:
            attendance_service.record_student_attendance(
                db, school_id=school_id, student_id=enrollment.student_id, campus_id=None,
                date=date, status=status, marked_by=actor_id,
            )
        marked, label = len(rows), p.get("arm_name") or "class"
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="attendance",
        entity_id=p.get("arm_id") or p.get("student_id") or p.get("staff_id"),
        new={"operation": "copilot_mark_attendance", "scope": scope, "status": status,
             "date": date, "marked": marked, "target": label},
        details="Attendance marked via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Marked {marked} '{status}' for {label} on {date}.",
        {"scope": scope, "status": status, "date": date, "marked": marked},
    )


def _execute_create_role(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    role = rbac_service.create_role(
        db, school_id, code=p["code"], name=p["name"], permissions=p.get("permissions") or []
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="role", entity_id=str(role.id),
        new={"operation": "copilot_create_role", "code": role.code, "name": role.name,
             "permissions": p.get("permissions") or []},
        details="Role created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Created role {role.name} ({role.code}).",
        {"role_id": str(role.id), "name": role.name, "code": role.code},
    )


def _execute_create_staff_account(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    password = _temporary_password()
    staff, role = people_service.create_staff_account(
        db, school_id, _as_uuid(p["staff_id"]),
        email=p["email"], password=password, role_id=_as_uuid(p["role_id"]),
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="staff_account",
        entity_id=str(staff.id),
        new={"operation": "copilot_create_staff_account", "staff": staff.full_name,
             "email": p["email"], "role": role.code},
        details="Staff login created via the school copilot chat command",
    )
    # The one-time password is shown once, exactly like the platform-admin flow;
    # it is never stored in the message payload's audit trail.
    return _done(
        proposal,
        f"Done. Created a login for {staff.full_name} with email {p['email']} and "
        f"role {role.name}. Temporary password: {password} — share it now and ask "
        "them to change it after signing in.",
        {"staff_id": str(staff.id), "full_name": staff.full_name,
         "email": p["email"], "role": role.name, "temporary_password": password},
    )


def _execute_update_school(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    school = db.get(School, school_id)
    if school is None:
        return _failed(proposal, "the school record could not be loaded")
    field = p["field"]
    setattr(school, field, p["value"])
    db.flush()
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.UPDATE.value, entity_type="school", entity_id=str(school.id),
        new={"operation": "copilot_update_school", "field": field, "value": p["value"]},
        details="School profile updated via the school copilot chat command",
    )
    label = {"short_name": "short name"}.get(field, field)
    return _done(
        proposal,
        f"Done. Set the school's {label} to {p['value']}.",
        {"field": field, "value": p["value"]},
    )


def _execute_add_campus(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    campus = Campus(school_id=school_id, name=p["name"], address=None)
    db.add(campus)
    db.flush()
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="campus", entity_id=str(campus.id),
        new={"operation": "copilot_add_campus", "name": campus.name},
        details="Campus added via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Added campus {campus.name}.",
        {"campus_id": str(campus.id), "name": campus.name},
    )


def _execute_create_fee_structure(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    data = FeeStructureIn(
        name=p["name"],
        fee_type=p.get("fee_type") or "tuition",
        amount=float(p["amount"]),
        applicable_to=p.get("applicable_to") or "all",
        class_arm_id=_as_uuid(p.get("arm_id")),
    )
    structure = fees_service.create_fee_structure(
        db, school_id, data=data, created_by=actor_id
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="fee_structure",
        entity_id=str(structure.id),
        new={"operation": "copilot_create_fee_structure", "name": structure.name,
             "amount": p["amount"], "fee_type": structure.fee_type},
        details="Fee structure created via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Created the fee structure {structure.name} of {float(p['amount']):,.0f}.",
        {"fee_structure_id": str(structure.id), "name": structure.name,
         "amount": float(structure.amount)},
    )


def _execute_create_invoice(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    current = academics_service.current_term(db, school_id)
    batch_number = (
        f"CHAT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )
    invoice = fees_service.create_invoice(
        db,
        school_id=school_id,
        student_id=_as_uuid(p["student_id"]),
        fee_structure_id=_as_uuid(p["fee_structure_id"]),
        term_id=current.id if current else None,
        batch_number=batch_number,
        issued_by=actor_id,
    )
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="invoice", entity_id=str(invoice.id),
        new={"operation": "copilot_create_invoice", "student": p.get("student_name"),
             "fee": p.get("fee_name"), "total": invoice.total_amount},
        details="Invoice raised via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Raised invoice {invoice.reference_number} for {p.get('student_name')} "
        f"for {p.get('fee_name')} — total {float(invoice.total_amount):,.0f}.",
        {"invoice_id": str(invoice.id), "reference_number": invoice.reference_number,
         "total": float(invoice.total_amount), "status": invoice.status},
    )


def _execute_record_payment(
    db: Session, school_id: uuid.UUID, proposal: Proposal, *, actor_id: uuid.UUID
) -> DirectReply:
    p = proposal.params
    payment = fees_service.record_payment(
        db,
        invoice_id=_as_uuid(p["invoice_id"]),
        student_id=_as_uuid(p["student_id"]),
        amount=float(p["amount"]),
        payment_method=p.get("payment_method") or "cash",
        school_id=school_id,
        recorded_by=actor_id,
    )
    invoice = fees_service.get_invoice(db, _as_uuid(p["invoice_id"]), school_id)
    _audit(
        db, school_id, actor_id=actor_id,
        action=AuditAction.CREATE.value, entity_type="payment",
        entity_id=str(payment.id),
        new={"operation": "copilot_record_payment", "student": p.get("student_name"),
             "amount": p["amount"], "method": p.get("payment_method"),
             "invoice": invoice.reference_number},
        details="Fee payment recorded via the school copilot chat command",
    )
    return _done(
        proposal,
        f"Done. Recorded {float(p['amount']):,.0f} from {p.get('student_name')} "
        f"(receipt {payment.receipt_number}); invoice {invoice.reference_number} is "
        f"now {invoice.status}.",
        {"payment_id": str(payment.id), "receipt_number": payment.receipt_number,
         "invoice_status": invoice.status, "amount": float(p["amount"])},
    )


_EXECUTORS = {
    "admit_student": _execute_admit,
    "enroll_student": _execute_enroll,
    "change_class": _execute_change_class,
    "update_student": _execute_update_student,
    "remove_student": _execute_remove_student,
    "promote_class": _execute_promote_class,
    "add_staff": _execute_add_staff,
    "create_subject": _execute_create_subject,
    "create_class_arm": _execute_create_arm,
    "create_session": _execute_create_session,
    "create_term": _execute_create_term,
    "activate_session": _execute_activate_session,
    "activate_term": _execute_activate_term,
    "close_term": _execute_close_term,
    "add_offering": _execute_add_offering,
    "assign_teacher": _execute_assign_teacher,
    "add_guardian": _execute_add_guardian,
    "mark_attendance": _execute_mark_attendance,
    "create_role": _execute_create_role,
    "create_staff_account": _execute_create_staff_account,
    "update_school": _execute_update_school,
    "add_campus": _execute_add_campus,
    "create_fee_structure": _execute_create_fee_structure,
    "create_invoice": _execute_create_invoice,
    "record_payment": _execute_record_payment,
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

_NAME_FIELDS = {
    "first_name", "last_name", "full_name", "subject_name", "arm_name",
    "session_name", "term_name", "campus_name", "role_name", "fee_name",
    "school_name", "short_name", "phone", "address", "website", "currency",
}


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
            # A reply is a write too: "JSS 1" when the school has a JSS 1 A and
            # a JSS 1 B stays unresolved, and the prompt (with its note listing
            # both) is asked again rather than one of them being guessed at.
            arm, _matches = _unique_arm(db, school_id, _arm_phrase(text))
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
        elif field_name == "amount":
            amount = _parse_amount(text)
            if amount is not None and amount > 0:
                proposal.params["amount"] = amount
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "fee":
            structure = _resolve_fee_structure_by_phrase(db, school_id, text)
            if structure is not None:
                proposal.params["fee_structure_id"] = str(structure.id)
                proposal.params["fee_name"] = structure.name
                # A payment that was only missing the fee can now pin its invoice.
                if proposal.code == "record_payment" and proposal.params.get("student_id"):
                    invoices, _total = fees_service.list_invoices(
                        db, school_id,
                        student_id=_as_uuid(proposal.params["student_id"]), limit=200,
                    )
                    open_invoices = [
                        inv for inv in invoices
                        if inv.status not in ("paid", "write_off", "expired")
                        and inv.fee_structure_id == structure.id
                    ]
                    if len(open_invoices) == 1:
                        proposal.params["invoice_id"] = str(open_invoices[0].id)
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "role":
            role = _resolve_role_by_name(db, school_id, text)
            if role is not None:
                proposal.params["role_id"] = str(role.id)
                proposal.params["role_name"] = role.name
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name in ("staff", "teacher"):
            member = _resolve_staff_by_phrase(db, school_id, text)
            if member is not None:
                proposal.params["staff_id"] = str(member.id)
                proposal.params["staff_name"] = member.full_name
                if field_name == "teacher":
                    proposal.params["teacher_id"] = str(member.id)
                    proposal.params["teacher_name"] = member.full_name
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "subject":
            subject = _resolve_subject_by_phrase(db, school_id, text)
            if subject is not None:
                proposal.params["subject_id"] = str(subject.id)
                proposal.params["subject_name"] = subject.name
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "email":
            match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
            if match:
                proposal.params["email"] = match.group(0)
                proposal.missing.remove(field_name)
                consumed = True
        elif field_name == "date":
            parsed = _parse_date(text)
            if parsed is not None:
                proposal.params["date"] = parsed
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
            elif field_name in ("campus_name", "fee_name", "role_name"):
                proposal.params["name"] = value
            elif field_name in (
                "school_name", "short_name", "phone", "address", "website", "currency"
            ):
                proposal.params["value"] = value
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
    if proposal.code == "enroll_student" and p.get("arm_name"):
        return f"Enrol {p.get('student_name')} in {p['arm_name']}."
    if proposal.code == "update_student" and (p.get("first_name") or p.get("gender")):
        if p.get("gender"):
            return f"Set {p.get('student_name')}'s gender to {p['gender']}."
        return f"Rename {p.get('student_name')} to {p.get('first_name')} {p.get('last_name')}."
    if proposal.code == "activate_session" and p.get("session_name"):
        return f"Activate {p['session_name']} as the current academic session."
    if proposal.code == "activate_term" and p.get("term_name"):
        return f"Activate {p['term_name']} as the current term."
    if proposal.code == "close_term" and p.get("term_name"):
        return f"Close {p['term_name']}."
    if proposal.code == "add_offering" and p.get("subject_name") and p.get("arm_name"):
        return f"Add {p['subject_name']} to {p['arm_name']}'s subjects."
    if proposal.code == "assign_teacher" and p.get("teacher_name") and p.get("subject_name") and p.get("arm_name"):
        return (
            f"Assign {p['teacher_name']} to teach {p['subject_name']} in {p['arm_name']}."
        )
    if proposal.code == "add_guardian" and p.get("full_name") and p.get("student_name"):
        return f"Add {p['full_name']} as {p['student_name']}'s guardian."
    if proposal.code == "mark_attendance" and p.get("status") and p.get("date"):
        if p.get("scope") == "staff" and p.get("staff_name"):
            return f"Mark {p['staff_name']} as {p['status']} for {p['date']}."
        if p.get("scope") == "class" and p.get("arm_name"):
            return (
                f"Mark all students in {p['arm_name']} as {p['status']} for {p['date']}."
            )
        if p.get("student_name"):
            return f"Mark {p['student_name']} as {p['status']} for {p['date']}."
    if proposal.code == "create_role" and p.get("name"):
        return f"Create role {p['name']}."
    if proposal.code == "create_staff_account" and p.get("staff_name") and p.get("email"):
        return (
            f"Create a login for {p['staff_name']} with email {p['email']} "
            f"(role {p.get('role_name') or 'teacher'})."
        )
    if proposal.code == "update_school" and p.get("value"):
        label = {"short_name": "short name"}.get(p.get("field"), p.get("field"))
        return f"Set the school's {label} to {p['value']}."
    if proposal.code == "add_campus" and p.get("name"):
        return f"Add campus {p['name']}."
    if proposal.code == "create_fee_structure" and p.get("name") and p.get("amount"):
        return f"Create the fee structure {p['name']} of {float(p['amount']):,.0f}."
    if proposal.code == "create_invoice" and p.get("student_name") and p.get("fee_name"):
        return f"Raise an invoice for {p['student_name']} for {p['fee_name']}."
    if proposal.code == "record_payment" and p.get("amount") and p.get("student_name"):
        return (
            f"Record a payment of {float(p['amount']):,.0f} from {p['student_name']}."
        )
    return proposal.detail


# ---------------------------------------------------------------------------
# Catalog — what the copilot can do, for help text and the UI
# ---------------------------------------------------------------------------
COMMAND_EXAMPLES: list[dict] = [
    # --- students & admissions ---
    {"code": "admit_student", "example": "add Genesis John to Nursery 1",
     "permissions": [STUDENTS_CREATE, STUDENTS_ENROLL]},
    {"code": "enroll_student", "example": "enrol Aisha Bello in Nursery 1",
     "permissions": [STUDENTS_ENROLL]},
    {"code": "change_class", "example": "move Genesis John to Nursery 2",
     "permissions": [STUDENTS_ENROLL]},
    {"code": "update_student", "example": "rename Aisha Bello to Aisha Okafor",
     "permissions": [STUDENTS_EDIT]},
    {"code": "remove_student", "example": "remove student Tolu Coker",
     "permissions": [STUDENTS_DELETE]},
    {"code": "promote_class", "example": "promote JSS 1 A to JSS 2 A",
     "permissions": [STUDENTS_ENROLL]},
    {"code": "add_guardian", "example": "add guardian Mary Bello for Aisha Bello",
     "permissions": [STUDENTS_EDIT]},
    {"code": "list_roster", "example": "list the students in Nursery 1",
     "permissions": ["students.view"]},
    # --- staff ---
    {"code": "add_staff", "example": "add teacher Grace Ade",
     "permissions": [STAFF_CREATE]},
    {"code": "create_staff_account", "example": "create a login for Grace Ade as teacher",
     "permissions": [USERS_MANAGE]},
    # --- academics ---
    {"code": "create_subject", "example": "create subject Further Mathematics",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "create_class_arm", "example": "create class Nursery 3",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "create_session", "example": "create session 2027/2028",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "create_term", "example": "create second term in 2025/2026",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "activate_session", "example": "activate session 2026/2027",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "activate_term", "example": "activate first term",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "close_term", "example": "close first term",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "add_offering", "example": "add Mathematics to JSS 1 A",
     "permissions": [ACADEMICS_MANAGE]},
    {"code": "assign_teacher", "example": "assign Grace Ade to Mathematics in JSS 1 A",
     "permissions": [ACADEMICS_MANAGE]},
    # --- attendance ---
    {"code": "mark_attendance", "example": "mark JSS 1 A present today",
     "permissions": [ATTENDANCE_MARK]},
    # --- results ---
    {"code": "submit_results", "example": "submit results for JSS 1 A",
     "permissions": [RESULTS_VERIFY]},
    {"code": "compile_results", "example": "compile results for JSS 1 A",
     "permissions": [RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH]},
    # --- users, roles & school setup ---
    {"code": "create_role", "example": "create role Bursar with permissions fees.view, fees.collect",
     "permissions": [ROLES_MANAGE]},
    {"code": "update_school", "example": "rename the school to Brightfield Academy",
     "permissions": [SCHOOL_MANAGE]},
    {"code": "add_campus", "example": "add campus Ikeja",
     "permissions": [CAMPUS_MANAGE]},
    # --- finance (accountant / owner permissions) ---
    {"code": "create_fee_structure", "example": "create a fee structure called School Fees of 50000",
     "permissions": [FEES_CREATE]},
    {"code": "create_invoice", "example": "raise an invoice for Aisha Bello for School Fees",
     "permissions": [FEES_CREATE]},
    {"code": "record_payment", "example": "record a payment of 50000 from Aisha Bello",
     "permissions": [FEES_PAY]},
]


def command_help() -> str:
    lines = [
        "I can also carry out administrative commands — I'll show you exactly "
        "what will change and wait for you to reply \"confirm\":",
    ]
    for item in COMMAND_EXAMPLES:
        lines.append(f"  • {item['example']}")
    lines.append(
        "Give me several at once, of the same kind or mixed, and I'll propose "
        "them together and run them in order — e.g. \"add Amina John to "
        "Nursery 1 and create subject Further Mathematics\"."
    )
    lines.append(
        "Commands are checked against your permissions, and every one I run is "
        "written to the audit log."
    )
    return "\n".join(lines)
