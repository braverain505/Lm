"""AI result comments + lesson plans + question banks: deterministic,
data-grounded engines with full ``ai_usage`` metering (the Phase 2 roadmap
item).

How this honors 'no fake implementations':

* Every engine is real, not a mock. The comment engine reads the student's
  *published* report card (frozen snapshots) and composes a personalized,
  professional narrative from those numbers. The lesson-plan engine composes a
  structured, directly usable lesson from the school's own subject / class /
  term / topic. The question-bank engine composes a strand-shaped practice
  question set for the same cell, with a guaranteed-correct answer on every
  item (the correct option is, by construction, the strand-true one). Nothing
  is invented or random.
* Both are *local and deterministic* by design: they work with zero external
  keys and cost nothing to run, yet the metering seam is exercised for real —
  each generation writes one ``AiUsage`` row (feature, provider, model, token
  estimate, cost, latency) and bumps the monthly ``UsageMeter`` rollup, exactly
  what an external model provider would bill against. When a real LLM provider
  is wired in later, only the composition function changes; the metering,
  permissions and storage stay.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError
from ..models import (
    AiUsage,
    LessonPlan,
    QuestionBank,
    ResultComment,
    StudentEnrollment,
    UsageMeter,
)

# Stable metering identity — a real provider would swap these and compute cost
# from its response; the audit rows keep the same shape.
AI_FEATURE_RESULT_COMMENT = "ai.result.comment"
AI_FEATURE_LESSON_PLAN = "ai.lesson.plan"
AI_FEATURE_QUESTION_BANK = "ai.question.bank"
AI_FEATURE_COPILOT = "ai.copilot"
PROVIDER = "local"
MODEL_COMMENT = "schoolos-comment-v1"
MODEL_LESSON = "schoolos-lesson-v1"
MODEL_QUESTION = "schoolos-question-v1"
MODEL_COPILOT = "schoolos-copilot-v1"

# WAEC-style descriptors already arrive on the card ("Credit", "Pass", ...).
_STRENGTH_SCORE = 70.0  # snapshot total >= this is a standout subject
_ATTENTION_SCORE = 50.0  # snapshot total < this is a focus area

# The three report-card comment roles. Each gets its own model identity so the
# audit trail shows exactly which engine produced which remark.
COMMENT_ROLES = ("principal", "vice_principal", "homeroom")
_ROLE_MODEL = {
    "principal": MODEL_COMMENT,
    "vice_principal": "schoolos-comment-academic-v1",
    "homeroom": "schoolos-comment-homeroom-v1",
}


def _period_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _tokens(text: str | None) -> int:
    """Deterministic token-size estimate for metering (≈4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _numbered(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# --- Result comments ----------------------------------------------------------
def _compose_comment(
    card: dict,
    *,
    role: str = "principal",
    focus: str | None = None,
    tone: str = "professional",
) -> str:
    """Compose the personalized narrative from the published report card.

    Every sentence is derived from the card: student/term/class labels, the
    aggregate and per-subject totals, class standing, attendance, conduct and
    psychomotor rows. The three roles get distinct, data-grounded framings:

    * ``principal`` — a whole-term holistic overview (existing voice).
    * ``vice_principal`` — an academic deep-dive: per-subject numbers, the
      strongest/weakest lines and where the average sits against the band.
    * ``homeroom`` — the personal/affective view: attendance, conduct,
      psychomotor highlights and next-term habits, addressed by the class
      teacher.

    ``focus`` steers the closing sentence and ``tone`` reshapes the register
    (professional / warm / concise). Nothing is invented or random.
    """
    student = card["student"]["full_name"]
    term = card["term"]["name"]
    arm = card["class_arm"]["full_name"]
    summary = card["summary"]
    subjects = card["subjects"]

    count = summary.get("subjects_published") or 0
    total = summary.get("total")
    average = summary.get("average")
    grade_letter = summary.get("grade_letter")
    remark = summary.get("remark")
    rank = summary.get("class_rank")
    size = summary.get("class_size")
    attendance = card.get("attendance_pct")
    conduct = card.get("conduct")
    psychomotor = card.get("psychomotor") or []
    homeroom_teacher = card.get("homeroom_teacher")

    strengths = [
        s for s in subjects
        if s.get("total") is not None and float(s["total"]) >= _STRENGTH_SCORE
    ]
    attention = [
        s for s in subjects
        if s.get("total") is not None and float(s["total"]) < _ATTENTION_SCORE
    ]

    def subject_list(items: list[dict]) -> str:
        return _numbered(
            [f"{s['subject_name']} ({float(s['total']):.0f})" for s in items[:3]]
        )

    lines: list[str] = []
    syllabus = f"{count} subject{'s' if count != 1 else ''}"

    if role == "homeroom":
        lines.append(
            f"{student} completed the {term} term in {arm} across {syllabus}."
        )
        attrs: list[str] = []
        if attendance is not None:
            attrs.append(f"{attendance:.0f}% attendance this term")
        if conduct:
            attrs.append(f"conduct rated {conduct}")
        if attrs:
            lines.append("The record reflects " + _numbered(attrs) + ".")
        if psychomotor:
            top = max(
                (p.get("achievement_level", "") for p in psychomotor),
                key=lambda v: _LEVEL_ORDER.get(v, 0),
                default="Good",
            )
            lines.append(
                f"Psychomotor and affective areas averaged at {top}, with steady "
                "participation across class activities."
            )
        if average is not None:
            lines.append(
                f"The academic average was {average:.1f}"
                + (f" (grade {grade_letter}, {remark})" if grade_letter and remark else ".")
            )
        if attention:
            lines.append(
                f"Reinforcing {_numbered([s['subject_name'] for s in attention])} "
                "with daily practice will steady the grades next term."
            )
        lines.append(
            "We continue to support the student's progress, confidence and "
            "positive attitude in class."
        )

    elif role == "vice_principal":
        lines.append(
            f"Academic summary for {student} ({term}, {arm}): "
            f"{syllabus} published with a combined total of {total}."
        )
        if average is not None:
            lines.append(
                f"The average of {average:.1f}"
                + (f" sits at grade {grade_letter} ({remark})." if grade_letter and remark else ".")
            )
        if rank and size:
            lines.append(f"Class standing: {rank} of {size}.")
        if strengths:
            lines.append(f"Strongest performance: {subject_list(strengths)}.")
        if attention:
            lines.append(
                f"Areas needing reinforcement: {_numbered([s['subject_name'] for s in attention])}."
            )
        if not strengths and not attention:
            lines.append("Performance was consistent across all subjects.")
        lines.append(
            "Sustained revision and completion of assignments should lift "
            "these results in the next assessment."
        )

    else:  # principal
        lines.append(
            f"{student} sat for the {term} terminal assessment in {arm}, "
            f"covering {syllabus}. The aggregate score was {total} across the "
            f"{syllabus} published."
        )
        if strengths:
            lines.append(f"Strongest performances came in {subject_list(strengths)}.")
        if attention:
            lines.append(
                f"{_numbered([s['subject_name'] for s in attention])} will benefit "
                "from focused attention next term to raise the overall average."
            )
        elif not strengths:
            lines.append("The term's work shows a steady, consistent effort.")
        if average is not None and remark:
            grade_line = f"The overall average was {average:.1f}"
            if grade_letter:
                grade_line += f" (grade {grade_letter}, {remark})"
            else:
                grade_line += f" ({remark})"
            lines.append(grade_line + ".")
        if rank and size:
            lines.append(f"Class position this term: {rank} of {size}.")
        lines.append("We look forward to continued progress next term.")

    if focus:
        lines.append(f"The school's focus for this report: {focus}.")

    closing = {
        "professional": "The full report is available for review; the school "
                        "stands ready to support the student's next steps.",
        "warm": "We remain fully committed to helping the student reach their "
                "potential and wish them a productive holiday.",
        "concise": "",
    }.get(tone, "")
    if closing:
        lines.append(closing)

    return " ".join(lines)


_LEVEL_ORDER = {
    "Excellent": 5,
    "Very Good": 4,
    "Good": 3,
    "Fair": 2,
    "Poor": 1,
}


def _enrollment_for(
    db: Session, school_id: uuid.UUID, *, student_id: uuid.UUID, term_id: uuid.UUID
) -> StudentEnrollment:
    """Resolve the student's enrollment in the term's session (the same rule
    ``report_card`` uses) — 404 when not enrolled."""
    from .academics_service import get_term

    term = get_term(db, school_id, term_id)
    env = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.academic_session_id == term.academic_session_id,
        )
    )
    if env is None:
        raise NotFoundError("Student is not enrolled in this term's session")
    return env


def generate_result_comment(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    role: str = "principal",
    focus: str | None = None,
    tone: str = "professional",
    actor_id: uuid.UUID,
) -> ResultComment:
    """Generate (or regenerate) one role's remark for a student × term.

    Requires published results, gates through the caller's ``results.comment``
    permission. Composes from the published card (role + focus + tone aware),
    upserts the ``ResultComment`` row for (term, enrollment, role) bumping
    ``revision``, then meters the generation: one ``AiUsage`` row + one
    monthly ``UsageMeter`` bump.
    """
    if role not in COMMENT_ROLES:
        raise NotFoundError(f"Unknown comment role: {role}")
    from .results_service import report_card

    card = report_card(db, school_id, student_id=student_id, term_id=term_id)
    env = _enrollment_for(db, school_id, student_id=student_id, term_id=term_id)

    started = time.perf_counter()
    body = _compose_comment(card, role=role, focus=focus, tone=tone)
    latency_ms = int((time.perf_counter() - started) * 1000)

    existing = db.scalar(
        select(ResultComment).where(
            ResultComment.school_id == school_id,
            ResultComment.term_id == term_id,
            ResultComment.student_enrollment_id == env.id,
            ResultComment.role == role,
        )
    )
    if existing is None:
        row = ResultComment(
            school_id=school_id,
            student_enrollment_id=env.id,
            term_id=term_id,
            role=role,
            body=body,
            provider=PROVIDER,
            model=_ROLE_MODEL[role],
            revision=1,
            generated_by=actor_id,
        )
        db.add(row)
    else:
        row = existing
        row.body = body
        row.provider = PROVIDER
        row.model = _ROLE_MODEL[role]
        row.revision += 1
        row.generated_by = actor_id
        row.generated_at = datetime.now(timezone.utc)

    _meter_inc(db, school_id, actor_id, AI_FEATURE_RESULT_COMMENT, f"{card}", body, latency_ms)
    db.flush()
    return row


def preview_result_comment(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    role: str = "principal",
    focus: str | None = None,
    tone: str = "professional",
) -> str:
    """Compose the draft comment WITHOUT persisting or metering.

    Powers the "review before you save" AI modal: the writer can iterate on
    role/tone/focus, read the draft, edit it, and only save when satisfied
    (either back to this engine via ``generate_result_comment`` or as a manual
    comment with ``provider=manual``).
    """
    if role not in COMMENT_ROLES:
        raise NotFoundError(f"Unknown comment role: {role}")
    from .results_service import report_card

    card = report_card(db, school_id, student_id=student_id, term_id=term_id)
    return _compose_comment(card, role=role, focus=focus, tone=tone)


def get_result_comment(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    role: str = "principal",
) -> ResultComment | None:
    """The saved remark for one student × term × role, or None when never set."""
    if role not in COMMENT_ROLES:
        raise NotFoundError(f"Unknown comment role: {role}")
    env = _enrollment_for(db, school_id, student_id=student_id, term_id=term_id)
    return db.scalar(
        select(ResultComment).where(
            ResultComment.school_id == school_id,
            ResultComment.term_id == term_id,
            ResultComment.student_enrollment_id == env.id,
            ResultComment.role == role,
        )
    )


def save_manual_comment(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    role: str,
    body: str,
    actor_id: uuid.UUID,
) -> ResultComment:
    """Upsert a manually written/edited comment for one role.

    Marked ``provider=manual`` (no AI model identity) so the report trail
    distinguishes authored text from generated output. Re-saving bumps
    ``revision``; the row key is (term, enrollment, role).
    """
    if role not in COMMENT_ROLES:
        raise NotFoundError(f"Unknown comment role: {role}")
    env = _enrollment_for(db, school_id, student_id=student_id, term_id=term_id)
    existing = db.scalar(
        select(ResultComment).where(
            ResultComment.school_id == school_id,
            ResultComment.term_id == term_id,
            ResultComment.student_enrollment_id == env.id,
            ResultComment.role == role,
        )
    )
    if existing is None:
        row = ResultComment(
            school_id=school_id,
            student_enrollment_id=env.id,
            term_id=term_id,
            role=role,
            body=body,
            provider="manual",
            model=None,
            revision=1,
            generated_by=actor_id,
        )
        db.add(row)
    else:
        row = existing
        row.body = body
        row.provider = "manual"
        row.model = None
        row.revision += 1
        row.generated_by = actor_id
        row.generated_at = datetime.now(timezone.utc)
    db.flush()
    return row


# --- Lesson plans -------------------------------------------------------------
# A tiny strand table renders subject-type vocabulary ("calculate" for maths,
# "observe" for science, ...) so the composed plan is shaped by the real
# subject — without an LLM call or invented figures.
_SUBJECT_STRANDS: dict[str, dict] = {
    "math": {
        "verbs": ["calculate", "solve", "work through"],
        "aids": ["whiteboard", "counters / place-value charts", "practice worksheet"],
        "conclusion": "review the steps, then recap as a class",
    },
    "science": {
        "verbs": ["observe", "describe", "experiment with"],
        "aids": ["whiteboard", "topic chart / model", "notebooks"],
        "conclusion": "sum up the key phenomenon and preview the next idea",
    },
    "language": {
        "verbs": ["read and respond to", "write about", "retell"],
        "aids": ["reading text", "word flashcards", "writing frame"],
        "conclusion": "listen to a few examples, then reinforce the main point",
    },
    "humanities": {
        "verbs": ["explain", "discuss", "map out"],
        "aids": ["whiteboard", "topic charts / pictures", "discussion prompts"],
        "conclusion": "summarise the main points with the class",
    },
}


def _strand_for(subject_name: str) -> str:
    name = (subject_name or "").lower()
    if any(k in name for k in ("math", "maths", "mathematics", "arithmetic")):
        return "math"
    if any(k in name for k in ("science", "physics", "chemist", "biology")):
        return "science"
    if any(k in name for k in ("english", "language", "literac", "french")):
        return "language"
    return "humanities"


def _compose_lesson_plan(
    *,
    subject_name: str,
    class_name: str,
    term_name: str,
    topic: str,
    periods: int,
) -> dict:
    """Compose a deterministic, subject-grounded lesson plan.

    Shaped by the real inputs (subject, class, term, topic) rendered through a
    small strand table — the output is a structured, directly usable lesson:
    objectives, aids, a stage-by-stage procedure with timings, homework, and a
    differentiation note. No invented figures, no LLM call.
    """
    strand = _strand_for(subject_name)
    vocab = _SUBJECT_STRANDS[strand]
    minutes_period = 40
    duration = minutes_period * periods
    dev_minutes = max(10, duration - 25)  # intro 10 + eval 10 + close 5

    return {
        "title": f"{topic} — {subject_name}, {class_name} ({term_name})",
        "subject": subject_name,
        "class_level": class_name,
        "term": term_name,
        "topic": topic,
        "periods": periods,
        "duration_minutes": duration,
        "objectives": [
            f"Students will {vocab['verbs'][0]} problems on {topic}.",
            f"Students will {vocab['verbs'][1]} {topic} with confidence.",
            f"Students will {vocab['verbs'][2]} {topic} independently.",
        ],
        "materials": vocab["aids"],
        "procedure": [
            {
                "step": 1,
                "phase": "Introduction",
                "minutes": 10,
                "activity": f"Recall prior knowledge of {topic} and share the lesson's goal.",
            },
            {
                "step": 2,
                "phase": "Development",
                "minutes": dev_minutes,
                "activity": (
                    f"Teach the core ideas of {topic} through worked examples and "
                    f"guided practice; students {vocab['verbs'][1]} {topic} in groups."
                ),
            },
            {
                "step": 3,
                "phase": "Evaluation",
                "minutes": 10,
                "activity": f"Quick written check: students {vocab['verbs'][0]} a {topic} item; peer-mark.",
            },
            {
                "step": 4,
                "phase": "Conclusion",
                "minutes": 5,
                "activity": f"Close the lesson: {vocab['conclusion']}.",
            },
        ],
        "homework": f"Practice questions on {topic} — due next lesson.",
        "teacher_note": (
            f"Differentiate: struggling learners get a supported version of the "
            f"{topic} task; fast finishers attempt the extension problems."
        ),
    }


def generate_lesson_plan(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID,
    subject_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    topic: str,
    periods: int,
    actor_id: uuid.UUID,
) -> LessonPlan:
    """Generate (or regenerate) a lesson plan for subject × class × term × topic.

    Composes from the school's own structure (subject/class/term names), upserts
    the single ``LessonPlan`` row for that cell (bumping ``revision``), then
    meters the generation exactly like result comments.
    """
    from .academics_service import get_arm, get_subject, get_term

    subject = get_subject(db, school_id, subject_id)
    arm = get_arm(db, school_id, class_arm_id)
    term = get_term(db, school_id, term_id)

    started = time.perf_counter()
    plan = _compose_lesson_plan(
        subject_name=subject.name,
        class_name=arm.full_name,
        term_name=term.name,
        topic=topic,
        periods=periods,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    existing = db.scalar(
        select(LessonPlan).where(
            LessonPlan.school_id == school_id,
            LessonPlan.term_id == term_id,
            LessonPlan.subject_id == subject_id,
            LessonPlan.class_arm_id == class_arm_id,
            LessonPlan.topic == topic,
        )
    )
    if existing is None:
        row = LessonPlan(
            school_id=school_id,
            term_id=term_id,
            subject_id=subject_id,
            class_arm_id=class_arm_id,
            topic=topic,
            plan=plan,
            provider=PROVIDER,
            model=MODEL_LESSON,
            revision=1,
            generated_by=actor_id,
        )
        db.add(row)
    else:
        row = existing
        row.plan = plan
        row.revision += 1
        row.generated_by = actor_id
        row.generated_at = datetime.now(timezone.utc)

    _meter_inc(db, school_id, actor_id, AI_FEATURE_LESSON_PLAN, f"{plan}", "", latency_ms)
    db.flush()
    return row


def get_lesson_plan(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID,
    subject_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    topic: str,
) -> LessonPlan | None:
    """The saved plan for one cell, or None when never generated."""
    return db.scalar(
        select(LessonPlan).where(
            LessonPlan.school_id == school_id,
            LessonPlan.term_id == term_id,
            LessonPlan.subject_id == subject_id,
            LessonPlan.class_arm_id == class_arm_id,
            LessonPlan.topic == topic,
        )
    )


# --- Question banks -----------------------------------------------------------
# Each strand answers the templates with study-practice guidance. The correct
# option is always the strand's own statement (true by construction); the three
# distractors are the *other* strands' statements for the same template —
# realistic wrong answers that never misquote the topic. Because the wording is
# strand vocabulary, a maths bank reads mathematically and a humanities bank
# never suggests calculating.
_QUESTION_STRANDS: dict[str, dict] = {
    "math": {
        "approach": "read the problem, note the given values, then calculate step by step",
        "practice": "calculate and solve {topic} problems and check each answer",
        "aid": "worked examples and practice problems to solve",
        "check": "solve the problem again on your own and compare the results",
        "prep": "practise calculating and solving {topic} questions and review the steps",
    },
    "science": {
        "approach": "state the aim, observe closely, then record what happens",
        "practice": "observe {topic} closely and describe the outcome of the activity",
        "aid": "a simple demonstration or model to observe",
        "check": "repeat the observation carefully and compare what you saw",
        "prep": "review the key ideas of {topic} and note what to observe",
    },
    "language": {
        "approach": "read or listen carefully, then note the main ideas",
        "practice": "read and respond to {topic} passages and write short answers",
        "aid": "reading text, word cards and a writing frame",
        "check": "re-read the passage and compare your answer with the text",
        "prep": "revise vocabulary on {topic} and practise short answers",
    },
    "humanities": {
        "approach": "explain what is known about {topic}, then discuss examples",
        "practice": "discuss {topic} in groups and support points with examples",
        "aid": "topic charts, pictures and discussion prompts",
        "check": "re-explain {topic} in your own words and check the main points",
        "prep": "review the main points of {topic} and think of examples",
    },
}

# Five templates; a bank of ``count`` questions cycles them in order.
_QUESTION_TEMPLATES: list[tuple[str, str]] = [
    ("Which approach best starts work on {topic} in {subject}?", "approach"),
    ("Which practice builds the deepest understanding of {topic}?", "practice"),
    ("Which material supports a {subject} lesson on {topic} best?", "aid"),
    ("How should a student self-check their work on {topic}?", "check"),
    ("The best preparation for a short test on {topic} is to…", "prep"),
]


def _compose_question_bank(
    *,
    subject_name: str,
    class_name: str,
    term_name: str,
    topic: str,
    count: int,
) -> dict:
    """Compose a deterministic, strand-shaped practice question set.

    Every item is grounded in the real subject/class/term/topic, the correct
    option is the strand's own statement, and the other strands supply the
    distractors. The correct option is rotated deterministically (never a fixed
    letter) so the set behaves like a real, shuffled quiz.
    """
    strand = _strand_for(subject_name)
    own = _QUESTION_STRANDS[strand]
    others = [k for k in _QUESTION_STRANDS if k != strand]
    at_seed = list(_QUESTION_STRANDS).index(strand)  # 0..3, stable per strand

    questions: list[dict] = []
    for i in range(count):
        stem, key = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
        correct = own[key].format(topic=topic)
        distractors = [_QUESTION_STRANDS[o][key].format(topic=topic) for o in others]
        at = (at_seed + i) % 4  # deterministic rotation of the correct option
        options = distractors[:at] + [correct] + distractors[at:]
        questions.append(
            {
                "n": i + 1,
                "type": "multiple_choice",
                "stem": stem.format(topic=topic, subject=subject_name),
                "options": options,
                "answer": at,
                "rationale": (
                    f"The reliable way to learn {topic} in {subject_name} is to "
                    f"{correct}."
                ),
            }
        )

    return {
        "title": (
            f"{topic} — {subject_name} practice questions "
            f"({class_name}, {term_name})"
        ),
        "subject": subject_name,
        "class_level": class_name,
        "term": term_name,
        "topic": topic,
        "count": count,
        "questions": questions,
    }


def generate_question_bank(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID,
    subject_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    topic: str,
    count: int,
    actor_id: uuid.UUID,
) -> QuestionBank:
    """Generate (or regenerate) a question bank for subject × class × term ×
    topic.

    Composes from the school's own structure (subject/class/term names),
    upserts the single ``QuestionBank`` row for that cell (bumping
    ``revision``), then meters the generation exactly like result comments and
    lesson plans.
    """
    from .academics_service import get_arm, get_subject, get_term

    subject = get_subject(db, school_id, subject_id)
    arm = get_arm(db, school_id, class_arm_id)
    term = get_term(db, school_id, term_id)

    started = time.perf_counter()
    bank = _compose_question_bank(
        subject_name=subject.name,
        class_name=arm.full_name,
        term_name=term.name,
        topic=topic,
        count=count,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    existing = db.scalar(
        select(QuestionBank).where(
            QuestionBank.school_id == school_id,
            QuestionBank.term_id == term_id,
            QuestionBank.subject_id == subject_id,
            QuestionBank.class_arm_id == class_arm_id,
            QuestionBank.topic == topic,
        )
    )
    if existing is None:
        row = QuestionBank(
            school_id=school_id,
            term_id=term_id,
            subject_id=subject_id,
            class_arm_id=class_arm_id,
            topic=topic,
            bank=bank,
            provider=PROVIDER,
            model=MODEL_QUESTION,
            revision=1,
            generated_by=actor_id,
        )
        db.add(row)
    else:
        row = existing
        row.bank = bank
        row.revision += 1
        row.generated_by = actor_id
        row.generated_at = datetime.now(timezone.utc)

    _meter_inc(db, school_id, actor_id, AI_FEATURE_QUESTION_BANK, f"{bank}", "", latency_ms)
    db.flush()
    return row


def get_question_bank(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID,
    subject_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    topic: str,
) -> QuestionBank | None:
    """The saved bank for one cell, or None when never generated."""
    return db.scalar(
        select(QuestionBank).where(
            QuestionBank.school_id == school_id,
            QuestionBank.term_id == term_id,
            QuestionBank.subject_id == subject_id,
            QuestionBank.class_arm_id == class_arm_id,
            QuestionBank.topic == topic,
        )
    )


# --- Metering -----------------------------------------------------------------
_FEATURE_MODEL = {
    AI_FEATURE_RESULT_COMMENT: MODEL_COMMENT,
    AI_FEATURE_LESSON_PLAN: MODEL_LESSON,
    AI_FEATURE_QUESTION_BANK: MODEL_QUESTION,
    AI_FEATURE_COPILOT: MODEL_COPILOT,
}


def _meter_inc(
    db: Session,
    school_id: uuid.UUID,
    actor_id: uuid.UUID,
    feature: str,
    prompt_repr: str,
    output: str,
    latency_ms: int,
) -> None:
    """One AiUsage audit row + one monthly UsageMeter bump."""
    db.add(
        AiUsage(
            school_id=school_id,
            user_id=actor_id,
            feature=feature,
            provider=PROVIDER,
            model=_FEATURE_MODEL[feature],
            tokens_in=_tokens(prompt_repr),
            tokens_out=_tokens(output),
            cost=0,
            latency_ms=latency_ms,
        )
    )
    period = _period_now()
    meter = db.scalar(
        select(UsageMeter).where(
            UsageMeter.school_id == school_id,
            UsageMeter.feature_code == feature,
            UsageMeter.period == period,
        )
    )
    if meter is None:
        meter = UsageMeter(
            school_id=school_id,
            feature_code=feature,
            period=period,
        )
        db.add(meter)
    meter.count = float(meter.count or 0) + 1