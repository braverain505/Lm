"""School copilot admin commands: chat turns that change records.

Pinned behavior:

* A command is **never** a write on the turn it is typed: it comes back as a
  proposal naming exactly what will change, and nothing reaches the database
  until the user replies "confirm".
* A command never reaches the LLM — the model phrases answers, it does not
  execute. ``source`` is ``"command"`` and the provider is not called.
* Permissions are enforced per action against the caller's *real* set, not the
  ``ai.copilot`` gate that let them reach the endpoint: a principal may talk to
  the copilot and still be refused ``students.create``.
* A missing required field is asked for, not invented (the admission number is
  generated; the gender never is).
* Executions are journalled to ``audit_logs``.

The read side is covered too: the roster intent answers "who is in this class"
with real names, and follows the conversation's pinned class.
"""
import uuid

from sqlalchemy import select

from app.models import (
    AcademicSession,
    AuditLog,
    Result,
    Staff,
    Student,
    StudentEnrollment,
    Subject,
    Term,
)
from app.models.enums import ResultStatus
from .conftest import active_school_id, enable_premium, register_school
from .test_portal import _act, _add_components, _add_limited_user, _configure, _enter_all

COPILOT = "/api/copilot"


def _ask(client, sid, question, *, conversation_id=None, term_id=None, status=201):
    headers = {"X-School-Id": sid} if sid else {}
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    if term_id:
        body["term_id"] = term_id
    r = client.post(f"{COPILOT}/ask", json=body, headers=headers)
    assert r.status_code == status, r.text
    return r.json()


def _add_arm(client, sid, session_id, name):
    r = client.post(
        "/api/academics/arms",
        json={"session_id": session_id, "name": name},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _students(db, sid):
    return list(
        db.scalars(select(Student).where(Student.school_id == uuid.UUID(sid)))
    )


def _world(client, db, *, with_nursery=False):
    """The shared world plus (optionally) a Nursery 1 class."""
    register_school(client)
    sid = active_school_id(client)
    enable_premium(db, sid)
    w = _configure(client, sid, db)
    if with_nursery:
        w["nursery_arm_id"] = _add_arm(client, sid, w["session_id"], "Nursery 1")
    return sid, w


# --- Confirmation is mandatory ------------------------------------------------

def test_admit_proposes_and_writes_nothing(client, db):
    sid, w = _world(client, db, with_nursery=True)
    before = len(_students(db, sid))

    msg = _ask(client, sid, "Add Genesis John to Nursery 1")["message"]
    assert msg["intent"] == "admit_student"
    action = msg["answer_payload"]["action"]
    assert action["status"] == "pending"
    # The gender is never guessed — the proposal asks for it.
    assert action["missing"] == ["gender"]
    assert msg["answer_payload"]["source"] == "command"
    assert "Nursery 1" in msg["content"]
    assert "Genesis John" in msg["content"]
    # With a field missing it asks for that field instead of for a confirmation.
    assert "male" in msg["content"] and "female" in msg["content"]
    # Crucially: nothing was written.
    assert len(_students(db, sid)) == before


def test_confirm_admits_and_enrols_with_a_generated_number(client, db):
    sid, w = _world(client, db, with_nursery=True)
    conv = _ask(client, sid, "Add Genesis John to Nursery 1")["conversation"]["id"]

    # Supplying the missing gender re-renders the plan and still asks first.
    msg = _ask(client, sid, "male", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "pending"
    assert msg["answer_payload"]["action"]["missing"] == []

    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert "Done" in msg["content"]

    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Genesis"
        )
    )
    assert student is not None
    assert student.last_name == "John"
    assert student.gender == "male"
    assert student.admission_no.startswith("STU-")  # generated, never invented

    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.is_current.is_(True),
        )
    )
    assert enrollment is not None
    assert str(enrollment.class_arm_id) == w["nursery_arm_id"]


def test_cancel_changes_nothing(client, db):
    sid, w = _world(client, db, with_nursery=True)
    before = len(_students(db, sid))
    conv = _ask(client, sid, "Add Genesis John to Nursery 1")["conversation"]["id"]

    msg = _ask(client, sid, "cancel", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "cancelled"
    assert "Cancelled" in msg["content"]
    assert len(_students(db, sid)) == before

    # A later "confirm" has nothing to confirm — it is treated as a question.
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert (msg["answer_payload"].get("action") or {}).get("status") != "done"
    assert len(_students(db, sid)) == before


def test_unknown_class_is_asked_for_not_invented(client, db):
    sid, _w = _world(client, db)

    msg = _ask(client, sid, "Add Genesis John to Nowhere 9")["message"]
    assert msg["intent"] == "admit_student"
    assert "arm" in msg["answer_payload"]["action"]["missing"]
    assert len(_students(db, sid)) == 3


def test_unrelated_question_drops_a_complete_proposal(client, db):
    sid, w = _world(client, db, with_nursery=True)
    conv = _ask(client, sid, "move Aisha Bello to Nursery 1")["conversation"]["id"]

    # A different question is answered, and the proposal is dropped with it.
    msg = _ask(
        client, sid, "how many students are enrolled?", conversation_id=conv
    )["message"]
    assert msg["intent"] == "school_overview"
    assert msg["answer_payload"]["students"] == 3

    # A late "confirm" must not carry out the abandoned move.
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert (msg["answer_payload"].get("action") or {}).get("status") != "done"
    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Aisha"
        )
    )
    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.is_current.is_(True),
        )
    )
    assert str(enrollment.class_arm_id) == w["arm_id"]  # still JSS 1 A


def test_new_command_replaces_a_half_specified_one(client, db):
    sid, _w = _world(client, db, with_nursery=True)
    conv = _ask(client, sid, "add Genesis John to Nursery 1")["conversation"]["id"]

    msg = _ask(client, sid, "add Ada Inyang to JSS 1 A", conversation_id=conv)["message"]
    assert msg["intent"] == "admit_student"
    action = msg["answer_payload"]["action"]
    assert action["status"] == "pending"
    assert action["params"]["last_name"] == "Inyang"
    assert action["params"]["arm_name"] == "JSS 1 A"


def test_half_specified_command_keeps_asking_and_offers_cancel(client, db):
    sid, _w = _world(client, db, with_nursery=True)
    conv = _ask(client, sid, "add Genesis John to Nursery 1")["conversation"]["id"]

    msg = _ask(
        client, sid, "how many students are enrolled?", conversation_id=conv
    )["message"]
    # Still on the admission, and it says how to get out of that.
    assert msg["answer_payload"]["action"]["status"] == "pending"
    assert "cancel" in msg["content"]
    assert len(_students(db, sid)) == 3


# --- Permissions are per action, not just the copilot gate ---------------------

def test_principal_can_ask_but_cannot_admit(client, db):
    sid, _w = _world(client, db, with_nursery=True)
    user = _add_limited_user(db, sid, "principal")
    client.post(
        "/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"}
    )

    msg = _ask(client, sid, "Add Genesis John to Nursery 1")["message"]
    assert msg["answer_payload"]["action"]["status"] == "denied"
    assert "permission" in msg["content"]
    assert "students.create" in msg["answer_payload"]["action"]["permissions"]
    # No write, and no partial state: the three seated pupils are all there is.
    assert len(_students(db, sid)) == 3
    # ...and a read question still works for that same principal.
    assert _ask(client, sid, "how many students are enrolled?")["message"]["intent"] == (
        "school_overview"
    )


# --- The read side: who is in the class ---------------------------------------

def test_roster_lists_real_names(client, db):
    sid, _w = _world(client, db)

    msg = _ask(client, sid, "who is in JSS 1A?")["message"]
    assert msg["intent"] == "class_roster"
    payload = msg["answer_payload"]
    assert payload["class"] == "JSS 1 A"
    assert payload["count"] == 3
    names = {s["full_name"] for s in payload["students"]}
    assert names == {"Aisha Bello", "David Okafor", "Tolu Coker"}
    assert "Aisha Bello" in msg["content"]


def test_roster_follows_the_conversation_class(client, db):
    """The reported bug: "give me the names" after a class question."""
    sid, _w = _world(client, db)
    conv = _ask(client, sid, "how many students are in JSS 1A?")["conversation"]["id"]

    msg = _ask(client, sid, "Give me the names", conversation_id=conv)["message"]
    assert msg["intent"] == "class_roster"
    assert msg["answer_payload"]["class"] == "JSS 1 A"
    assert msg["answer_payload"]["count"] == 3


def test_roster_does_not_shadow_performance_questions(client, db):
    """\"who scored highest?\" is a marks question, not a class list."""
    sid, w = _world(client, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)
    for step in ("submit", "verify", "approve", "publish"):
        assert _act(client, sid, w, step).status_code == 200, step

    msg = _ask(
        client, sid, "who scored highest in Mathematics?", term_id=w["term_id"]
    )["message"]
    assert msg["intent"] == "top_performers"


# --- Academic structure --------------------------------------------------------

def test_create_subject_via_chat(client, db):
    sid, _w = _world(client, db)
    conv = _ask(client, sid, "create subject Further Mathematics")["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"

    subject = db.scalar(
        select(Subject).where(
            Subject.school_id == uuid.UUID(sid), Subject.name == "Further Mathematics"
        )
    )
    assert subject is not None
    assert subject.code  # auto-derived


def test_create_session_and_class(client, db):
    sid, _w = _world(client, db)
    conv = _ask(client, sid, "create session 2027/2028")["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert db.scalar(
        select(AcademicSession).where(
            AcademicSession.school_id == uuid.UUID(sid),
            AcademicSession.name == "2027/2028",
        )
    ) is not None


def test_a_command_that_conflicts_reports_it_instead_of_crashing(client, db):
    """A duplicate is an honest refusal: the savepoint unwinds and the turn
    still commits with the reason, rather than 500ing the chat."""
    sid, w = _world(client, db)
    before = len(
        db.scalars(
            select(Term).where(Term.academic_session_id == uuid.UUID(w["session_id"]))
        ).all()
    )
    conv = _ask(client, sid, "create first term")["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]

    assert msg["answer_payload"]["action"]["status"] == "failed"
    assert "already exists" in msg["content"]
    after = db.scalars(
        select(Term).where(Term.academic_session_id == uuid.UUID(w["session_id"]))
    ).all()
    assert len(after) == before


def test_add_staff_via_chat(client, db):
    sid, _w = _world(client, db)
    conv = _ask(client, sid, "add teacher Grace Ade")["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"

    staff = db.scalar(
        select(Staff).where(
            Staff.school_id == uuid.UUID(sid), Staff.full_name == "Grace Ade"
        )
    )
    assert staff is not None
    assert staff.membership_type == "teaching"


def test_move_student_to_another_class(client, db):
    sid, w = _world(client, db, with_nursery=True)

    result = _ask(client, sid, "move Aisha Bello to Nursery 1")
    assert result["message"]["intent"] == "change_class"
    msg = _ask(
        client, sid, "confirm", conversation_id=result["conversation"]["id"]
    )["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"

    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Aisha"
        )
    )
    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.is_current.is_(True),
        )
    )
    assert str(enrollment.class_arm_id) == w["nursery_arm_id"]


def test_move_unknown_student_is_honest(client, db):
    sid, _w = _world(client, db)
    msg = _ask(client, sid, "move Nobody Atall to Nursery 1")["message"]
    assert msg["intent"] == "change_class"
    assert msg["answer_payload"].get("not_found") is True
    assert "couldn't find" in msg["content"]


# --- Results pipeline ----------------------------------------------------------

def test_publish_results_via_chat(client, db):
    sid, w = _world(client, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)
    for step in ("submit", "verify", "approve"):
        assert _act(client, sid, w, step).status_code == 200, step

    conv = _ask(client, sid, "publish results for JSS 1 A")["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert msg["answer_payload"]["action"]["result"]["totals"]["published"] == 3

    statuses = set(
        db.scalars(
            select(Result.status).where(Result.school_id == uuid.UUID(sid))
        )
    )
    assert statuses == {ResultStatus.PUBLISHED.value}

    # ...and the copilot can now quote them, because publish froze the snapshots.
    msg = _ask(
        client, sid, "how did JSS 1A do overall this term?", term_id=w["term_id"]
    )["message"]
    assert msg["intent"] == "term_summary"
    assert msg["answer_payload"]["class_average"] == 60.0


# --- Audit + the LLM boundary --------------------------------------------------

def test_executed_command_is_audited(client, db):
    sid, _w = _world(client, db, with_nursery=True)
    conv = _ask(client, sid, "Add Genesis John to Nursery 1")["conversation"]["id"]
    _ask(client, sid, "female", conversation_id=conv)
    _ask(client, sid, "confirm", conversation_id=conv)

    audit = db.scalar(
        select(AuditLog).where(
            AuditLog.school_id == uuid.UUID(sid), AuditLog.entity_type == "student"
        )
    )
    assert audit is not None
    assert audit.action == "create"
    assert "copilot" in (audit.details or "").lower()


def test_command_turn_never_calls_the_llm(client, db, monkeypatch):
    sid, _w = _world(client, db, with_nursery=True)
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "test-key", raising=False)
    calls: list[dict] = []

    def _fake(*, system, user, temperature=0.3, max_tokens=2400):
        calls.append({"user": user})
        raise AssertionError("the LLM must not be used for a command")

    monkeypatch.setattr("app.services.copilot_service.complete_text", _fake)

    msg = _ask(client, sid, "Add Genesis John to Nursery 1")["message"]
    assert msg["answer_payload"]["action"]["status"] == "pending"
    assert msg["answer_payload"]["source"] == "command"
    assert calls == []
