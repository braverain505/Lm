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
import re
import uuid

from sqlalchemy import select

from app.models import (
    AcademicSession,
    AuditLog,
    Campus,
    CopilotMessage,
    Guardian,
    Result,
    Role,
    School,
    Staff,
    Student,
    StudentEnrollment,
    Subject,
    Term,
    User,
)
from app.models.attendance import StudentAttendance
from app.models.enums import ResultStatus
from .conftest import (
    active_school_id,
    enable_premium,
    grant_permission,
    register_school,
)
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


def _add_session(client, sid, name, *, is_current=False):
    r = client.post(
        "/api/academics/sessions",
        json={"name": name, "is_current": is_current},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_subject(client, sid, name, code):
    r = client.post(
        "/api/academics/subjects",
        json={"name": name, "code": code},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_staff(client, sid, staff_no, full_name, membership_type="teaching"):
    r = client.post(
        "/api/staff",
        json={"staff_no": staff_no, "full_name": full_name,
              "membership_type": membership_type},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _student_by_admission(db, sid, admission_no):
    return db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.admission_no == admission_no
        )
    )


def _current_arm_of(db, sid, student):
    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.is_current.is_(True),
        )
    )
    return str(enrollment.class_arm_id)


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


# --- Natural phrasing resolves like the bare imperative -----------------------
# The reported bug: "I want you to add Genesis John to Nursery 2" was not read
# as a command at all, so it fell through to the LLM and got "I can't do that".


def test_polite_phrasing_is_recognized_as_a_command(client, db):
    sid, _w = _world(client, db, with_nursery=True)

    msg = _ask(
        client, sid, "I want you to add Godiya Markus to Nursery 1"
    )["message"]
    assert msg["intent"] == "admit_student"
    action = msg["answer_payload"]["action"]
    assert action["status"] == "pending"
    assert action["params"]["first_name"] == "Godiya"
    assert action["params"]["last_name"] == "Markus"
    assert action["params"]["arm_name"] == "Nursery 1"


def test_polite_phrasing_admits_end_to_end(client, db):
    sid, w = _world(client, db, with_nursery=True)
    conv = _ask(
        client, sid, "I want you to add Godiya Markus to Nursery 1"
    )["conversation"]["id"]

    _ask(client, sid, "male", conversation_id=conv)
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"

    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Godiya"
        )
    )
    assert student is not None
    assert student.last_name == "Markus"
    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.is_current.is_(True),
        )
    )
    assert enrollment is not None
    assert str(enrollment.class_arm_id) == w["nursery_arm_id"]


def test_contracted_politeness_moves_a_student(client, db):
    sid, w = _world(client, db, with_nursery=True)

    msg = _ask(
        client, sid, "I'd like you to move Aisha Bello to Nursery 1"
    )["message"]
    assert msg["intent"] == "change_class"
    assert msg["answer_payload"]["action"]["status"] == "pending"

    conv = _ask(
        client, sid, "I'd like you to move Aisha Bello to Nursery 1"
    )["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
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


def test_polite_phrasing_still_creates_academic_structure(client, db):
    sid, _w = _world(client, db)
    conv = _ask(
        client, sid, "I want you to create subject Further Mathematics"
    )["conversation"]["id"]
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"

    subject = db.scalar(
        select(Subject).where(
            Subject.school_id == uuid.UUID(sid), Subject.name == "Further Mathematics"
        )
    )
    assert subject is not None


# --- Deleting a chat from the history rail ------------------------------------


def test_delete_conversation_removes_the_thread_and_its_messages(client, db):
    sid, _w = _world(client, db)
    conv = _ask(client, sid, "how many students are enrolled?")["conversation"]["id"]

    r = client.delete(f"{COPILOT}/conversations/{conv}", headers={"X-School-Id": sid})
    assert r.status_code == 204, r.text

    # Gone from the thread endpoint (404) and from the rail.
    assert client.get(
        f"{COPILOT}/conversations/{conv}", headers={"X-School-Id": sid}
    ).status_code == 404
    convs = client.get(f"{COPILOT}/conversations", headers={"X-School-Id": sid}).json()
    assert all(c["id"] != conv for c in convs)
    # ...and its messages went with it.
    assert (
        db.scalars(
            select(CopilotMessage).where(CopilotMessage.conversation_id == uuid.UUID(conv))
        ).all()
        == []
    )


def test_delete_unknown_conversation_is_a_404(client, db):
    sid, _w = _world(client, db)
    r = client.delete(
        f"{COPILOT}/conversations/{uuid.uuid4()}", headers={"X-School-Id": sid}
    )
    assert r.status_code == 404


# ===========================================================================
# The wider administrative catalogue
# ===========================================================================


def _confirm(client, sid, first_message, *followups):
    """Send a command, supply any follow-up fields, confirm, and return the
    final assistant message."""
    conv = _ask(client, sid, first_message)["conversation"]["id"]
    last = None
    for value in followups:
        last = _ask(client, sid, value, conversation_id=conv)["message"]
    last = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    return last


# --- Students: the reported bug, plus the rest of the roster writes -----------


def test_move_student_with_from_clause_works(client, db):
    """The reported failure: "move a student to another class" must be read as
    a command. The from-clause phrasing is the one that silently fell through."""
    sid, w = _world(client, db, with_nursery=True)
    result = _ask(client, sid, "move Aisha Bello from JSS 1 A to Nursery 1")
    assert result["message"]["intent"] == "change_class"
    assert result["message"]["answer_payload"]["source"] == "command"
    msg = _ask(
        client, sid, "confirm", conversation_id=result["conversation"]["id"]
    )["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"
    student = _student_by_admission(db, sid, "STU-001")
    assert _current_arm_of(db, sid, student) == w["nursery_arm_id"]


def test_move_student_possessive_class_phrasing(client, db):
    sid, w = _world(client, db, with_nursery=True)
    result = _ask(client, sid, "change Aisha Bello's class to Nursery 1")
    assert result["message"]["intent"] == "change_class"
    msg = _ask(
        client, sid, "confirm", conversation_id=result["conversation"]["id"]
    )["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"
    student = _student_by_admission(db, sid, "STU-001")
    assert _current_arm_of(db, sid, student) == w["nursery_arm_id"]


def test_move_unknown_student_never_reaches_the_llm(client, db, monkeypatch):
    """An unrecognized pupil is an honest, deterministic reply — not the model."""
    sid, _w = _world(client, db)
    from app.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "test-key", raising=False)

    def _boom(*, system, user, temperature=0.3, max_tokens=2400):
        raise AssertionError("a command-shaped turn must not call the LLM")

    monkeypatch.setattr("app.services.copilot_service.complete_text", _boom)
    msg = _ask(client, sid, "move Nobody Atall to JSS 1 A")["message"]
    assert msg["answer_payload"]["source"] == "command"
    assert msg["answer_payload"].get("not_found") is True


def test_enrol_existing_student_does_not_create_a_duplicate(client, db):
    sid, w = _world(client, db, with_nursery=True)
    before = len(_students(db, sid))
    msg = _confirm(client, sid, "enrol Aisha Bello in Nursery 1")
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert len(_students(db, sid)) == before  # no second Aisha was created
    student = _student_by_admission(db, sid, "STU-001")
    assert _current_arm_of(db, sid, student) == w["nursery_arm_id"]


def test_remove_student_soft_deletes(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "remove student Tolu Coker")
    assert msg["answer_payload"]["action"]["status"] == "done"
    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Tolu"
        )
    )
    assert student.is_deleted is True


def test_rename_student(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "rename Aisha Bello to Aisha Okafor")
    assert msg["answer_payload"]["action"]["status"] == "done"
    student = _student_by_admission(db, sid, "STU-001")
    assert student.first_name == "Aisha"
    assert student.last_name == "Okafor"


def test_change_student_gender(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "change Aisha Bello's gender to male")
    assert msg["answer_payload"]["action"]["status"] == "done"
    student = _student_by_admission(db, sid, "STU-001")
    assert student.gender == "male"


def test_promote_a_class_into_the_next_session(client, db):
    sid, w = _world(client, db)
    next_session = _add_session(client, sid, "2026/2027")
    target_arm = _add_arm(client, sid, next_session, "JSS 2 A")

    msg = _confirm(client, sid, "promote JSS 1 A to JSS 2 A")
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert msg["answer_payload"]["action"]["result"]["promoted"] == 3

    current = db.scalars(
        select(StudentEnrollment).where(
            StudentEnrollment.school_id == uuid.UUID(sid),
            StudentEnrollment.is_current.is_(True),
        )
    ).all()
    assert {str(e.class_arm_id) for e in current} == {target_arm}


def test_add_guardian_for_a_student(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "add guardian Mary Bello for Aisha Bello")
    assert msg["answer_payload"]["action"]["status"] == "done"
    guardian = db.scalar(
        select(Guardian).where(
            Guardian.school_id == uuid.UUID(sid), Guardian.full_name == "Mary Bello"
        )
    )
    assert guardian is not None


# --- Academic structure -------------------------------------------------------


def test_activate_and_close_a_term(client, db):
    sid, w = _world(client, db)
    r = client.post(
        "/api/academics/terms",
        json={"session_id": w["session_id"], "term_no": 2, "name": "Second Term"},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    second = r.json()["id"]

    msg = _confirm(client, sid, "activate second term")
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert db.get(Term, uuid.UUID(second)).status == "open"

    msg = _confirm(client, sid, "close second term")
    assert msg["answer_payload"]["action"]["status"] == "done"
    db.expire_all()
    assert db.get(Term, uuid.UUID(second)).status == "closed"


def test_activate_a_session(client, db):
    sid, _w = _world(client, db)
    next_session = _add_session(client, sid, "2027/2028")
    msg = _confirm(client, sid, "activate session 2027/2028")
    assert msg["answer_payload"]["action"]["status"] == "done"
    db.expire_all()
    assert db.get(AcademicSession, uuid.UUID(next_session)).is_current is True


def test_add_subject_to_a_class(client, db):
    sid, w = _world(client, db)
    subject_id = _add_subject(client, sid, "English Language", "ENG")
    msg = _confirm(client, sid, "add English Language to JSS 1 A")
    assert msg["answer_payload"]["action"]["status"] == "done"
    offerings = client.get(
        f"/api/academics/arms/{w['arm_id']}/offerings", headers={"X-School-Id": sid}
    ).json()
    assert subject_id in {o["subject_id"] for o in offerings}


def test_assign_a_teacher_to_subject_and_class(client, db):
    sid, w = _world(client, db)
    _add_staff(client, sid, "STF-001", "Grace Ade")
    msg = _confirm(client, sid, "assign Grace Ade to Mathematics in JSS 1 A")
    assert msg["answer_payload"]["action"]["status"] == "done"
    assignments = client.get(
        f"/api/academics/arms/{w['arm_id']}/assignments", headers={"X-School-Id": sid}
    ).json()
    assert len(assignments) == 1


# --- Attendance ---------------------------------------------------------------


def test_mark_a_whole_class_present(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "mark JSS 1 A present today")
    assert msg["answer_payload"]["action"]["status"] == "done"
    rows = db.scalars(
        select(StudentAttendance).where(StudentAttendance.school_id == uuid.UUID(sid))
    ).all()
    assert len(rows) == 3
    assert {r.status for r in rows} == {"present"}


def test_mark_one_student_absent(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "mark Aisha Bello absent today")
    assert msg["answer_payload"]["action"]["status"] == "done"
    rows = db.scalars(
        select(StudentAttendance).where(StudentAttendance.school_id == uuid.UUID(sid))
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "absent"


# --- Users, roles & school setup ---------------------------------------------


def test_create_a_role_with_permissions(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(
        client, sid,
        "create role Exam Assistant with permissions results.view, results.verify",
    )
    assert msg["answer_payload"]["action"]["status"] == "done"
    role = db.scalar(
        select(Role).where(
            Role.school_id == uuid.UUID(sid), Role.name == "Exam Assistant"
        )
    )
    assert role is not None
    assert role.code == "exam_assistant"


def test_create_a_staff_login_and_show_the_password_once(client, db):
    sid, _w = _world(client, db)
    _add_staff(client, sid, "STF-001", "Grace Ade")
    # The email is not on the staff record, so the copilot asks for it first.
    conv = _ask(client, sid, "create a login for Grace Ade as teacher")["conversation"]["id"]
    msg = _ask(client, sid, "grace.ade@school.example", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "pending"
    assert msg["answer_payload"]["action"]["missing"] == []
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done"
    assert "Temporary password" in msg["content"]
    assert db.scalar(
        select(User).where(User.email == "grace.ade@school.example")
    ) is not None


def test_rename_the_school(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "rename the school to Brightfield Academy")
    assert msg["answer_payload"]["action"]["status"] == "done"
    db.expire_all()
    assert db.get(School, uuid.UUID(sid)).name == "Brightfield Academy"


def test_add_a_campus(client, db):
    sid, _w = _world(client, db)
    msg = _confirm(client, sid, "add campus Ikeja")
    assert msg["answer_payload"]["action"]["status"] == "done"
    # A school is seeded with a "Main Campus" at registration, so assert on the
    # campus the command named rather than on whichever row comes back first.
    campus = db.scalar(
        select(Campus).where(
            Campus.school_id == uuid.UUID(sid), Campus.name == "Ikeja"
        )
    )
    assert campus is not None


# --- Finance ------------------------------------------------------------------


def test_fee_structure_invoice_and_payment_through_chat(client, db):
    sid, _w = _world(client, db)
    grant_permission(db, sid, "fees.create")
    grant_permission(db, sid, "fees.pay")

    msg = _confirm(client, sid, "create a fee structure called School Fees of 50000")
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]

    msg = _confirm(client, sid, "raise an invoice for Aisha Bello for School Fees")
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]

    msg = _confirm(client, sid, "record a payment of 50000 from Aisha Bello")
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]
    assert msg["answer_payload"]["action"]["result"]["invoice_status"] == "paid"


def test_payment_without_an_invoice_is_an_honest_refusal(client, db):
    sid, _w = _world(client, db)
    grant_permission(db, sid, "fees.pay")
    msg = _ask(client, sid, "record a payment of 50000 from Aisha Bello")["message"]
    assert msg["answer_payload"].get("no_invoice") is True
    assert "couldn't find an unpaid invoice" in msg["content"]


def test_finance_is_denied_to_a_school_admin_without_the_permission(client, db):
    """The founding admin template withholds finance codes by design."""
    sid, _w = _world(client, db)
    msg = _ask(client, sid, "create a fee structure called School Fees of 50000")["message"]
    assert msg["answer_payload"]["action"]["status"] == "denied"
    assert "fees.create" in msg["answer_payload"]["action"]["permissions"]


# --- Per-action permission checks still hold for the new commands -------------


def test_principal_cannot_mark_attendance(client, db):
    sid, _w = _world(client, db)
    user = _add_limited_user(db, sid, "principal")
    client.post(
        "/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"}
    )
    msg = _ask(client, sid, "mark JSS 1 A present today")["message"]
    assert msg["answer_payload"]["action"]["status"] == "denied"
    assert "attendance.mark" in msg["answer_payload"]["action"]["permissions"]
    # ...but the same principal can still read.
    assert _ask(client, sid, "how many students are enrolled?")["message"]["intent"] == (
        "school_overview"
    )


# ===========================================================================
# Several commands in one message, and classes the copilot must not guess at
# ===========================================================================


def test_two_admissions_in_one_message_are_proposed_together(client, db):
    """The reported message: "Add Amina John in Nursery 1 and Hauwa Manuel in
    nursery 2". It is two admissions — it used to be read as one admission into
    a class called "Nursery 1 and Hauwa Manuel in nursery 2", or fall through
    to the LLM, which answered "I don't have any information about adding
    students"."""
    sid, w = _world(client, db, with_nursery=True)
    nursery_2 = _add_arm(client, sid, w["session_id"], "Nursery 2")
    before = len(_students(db, sid))

    first = _ask(
        client, sid, "Add Amina John in Nursery 1 and Hauwa Manuel in nursery 2"
    )
    msg = first["message"]
    assert msg["answer_payload"]["source"] == "command"
    action = msg["answer_payload"]["action"]
    assert action["code"] == "batch"
    assert action["status"] == "pending"
    assert len(action["items"]) == 2
    assert "Amina John" in action["items"][0]["detail"]
    assert "Hauwa Manuel" in action["items"][1]["detail"]
    # Both classes resolved exactly, so neither is reported as ambiguous.
    assert "fits more than one class" not in msg["content"]
    # Nothing is written before the confirmation, batch or not.
    assert len(_students(db, sid)) == before
    conv = first["conversation"]["id"]

    # One missing field at a time: the batch walks its own items in order.
    msg = _ask(client, sid, "male", conversation_id=conv)["message"]
    items = msg["answer_payload"]["action"]["items"]
    assert items[0]["missing"] == []
    assert items[1]["missing"] == ["gender"]
    assert "item 2" in msg["content"]

    msg = _ask(client, sid, "female", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["items"][1]["missing"] == []
    assert "confirm" in msg["content"]

    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]
    assert "(1)" in msg["content"] and "(2)" in msg["content"]

    amina = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Amina"
        )
    )
    hawa = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Hauwa"
        )
    )
    assert amina is not None and hawa is not None
    assert amina.gender == "male" and hawa.gender == "female"
    assert amina.last_name == "John" and hawa.last_name == "Manuel"
    assert _current_arm_of(db, sid, amina) == w["nursery_arm_id"]
    assert _current_arm_of(db, sid, hawa) == nursery_2
    assert len(_students(db, sid)) == before + 2


def test_the_reported_two_commands_in_one_message_both_run(client, db):
    """The reported message: "Add James Madison in Nursery 2 and Michael Klint
    in JSS 1".

    The instance the report came from ran an older build whose *only* reading of
    that sentence was the single parse, which swallowed the second command into
    the class phrase ("Nursery 2 and Michael Klint in JSS 1") and asked for the
    first pupil's gender — Michael was never seen. Both clauses must be planned
    here, in their own classes, and run together."""
    sid, w = _world(client, db, with_nursery=True)
    # The shared world ships "JSS 1 A"; add the reporting school's Nursery 2.
    nursery_2 = _add_arm(client, sid, w["session_id"], "Nursery 2")
    before = len(_students(db, sid))

    first = _ask(
        client, sid, "Add James Madison in Nursery 2 and Michael Klint in JSS 1"
    )
    msg = first["message"]
    action = msg["answer_payload"]["action"]
    assert action["code"] == "batch"
    assert len(action["items"]) == 2
    assert "James Madison" in action["items"][0]["detail"]
    assert "Nursery 2" in action["items"][0]["detail"]
    assert "Michael Klint" in action["items"][1]["detail"]
    # A bare "JSS 1" resolves to the one class that fits it, and the second
    # command is named rather than folded into the first pupil's class.
    assert "JSS 1" in action["items"][1]["detail"]
    assert "no class called" not in msg["content"]
    # Two admissions typed together must not be planned as the same number, and
    # neither clause may be folded into the other's class.
    numbers = []
    for item in action["items"]:
        match = re.search(r"STU-[0-9]+-[0-9]+", item["detail"])
        assert match is not None, item
        numbers.append(match.group(0))
    assert len(set(numbers)) == 2, numbers
    assert len(_students(db, sid)) == before
    conv = first["conversation"]["id"]

    msg = _ask(client, sid, "male", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["items"][1]["missing"] == ["gender"]
    msg = _ask(client, sid, "female", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["items"][1]["missing"] == []

    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]

    james = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "James"
        )
    )
    michael = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Michael"
        )
    )
    assert james is not None and michael is not None
    assert _current_arm_of(db, sid, james) == nursery_2
    assert _current_arm_of(db, sid, michael) == w["arm_id"]
    assert len(_students(db, sid)) == before + 2


def test_a_batch_does_not_silently_drop_a_target(client, db):
    """Every clause of the message stays visible, even the one that cannot be
    resolved yet."""
    sid, _w = _world(client, db, with_nursery=True)
    msg = _ask(
        client, sid, "add Amina John in Nursery 1 and Hauwa Manuel in Nursery 9"
    )["message"]
    action = msg["answer_payload"]["action"]
    assert action["code"] == "batch"
    assert len(action["items"]) == 2
    assert "arm" in action["items"][1]["missing"]
    assert "Nursery 9" in msg["content"]


def test_a_value_list_is_not_mistaken_for_a_second_command(client, db):
    """"create role Transport Lead with permissions fees.view and fees.collect" is
    one command whose value list happens to be joined by "and" — not two
    commands."""
    sid, _w = _world(client, db)
    msg = _confirm(
        client, sid,
        "create role Transport Lead with permissions fees.view and fees.collect",
    )
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]
    # Read as one command, not as a batch of two.
    assert msg["answer_payload"]["action"]["code"] == "create_role"
    role = db.scalar(
        select(Role).where(
            Role.school_id == uuid.UUID(sid), Role.name == "Transport Lead"
        )
    )
    assert role is not None


def test_an_intent_preamble_before_the_verb_is_understood(client, db):
    """"I wanted to say you should add …" is still a command."""
    sid, _w = _world(client, db, with_nursery=True)
    msg = _ask(
        client, sid, "I wanted to say you should add Genesis John to Nursery 1"
    )["message"]
    assert msg["answer_payload"]["source"] == "command"
    assert msg["intent"] == "admit_student"
    assert "Nursery 1" in msg["content"]


def test_a_bare_level_resolves_when_only_one_class_matches(client, db):
    """"Add Amina Manuel in JSS 1" — the school's only JSS 1 is "JSS 1 A"."""
    sid, _w = _world(client, db)
    msg = _ask(client, sid, "Add Amina Manuel in JSS 1")["message"]
    action = msg["answer_payload"]["action"]
    assert action["status"] == "pending"
    assert action["missing"] == ["gender"]
    assert action["params"]["arm_name"] == "JSS 1 A"
    # A resolved class must not be described as ambiguous.
    assert "fits more than one class" not in msg["content"]


def test_an_ambiguous_level_asks_which_class_instead_of_guessing(client, db):
    """With a JSS 1 A and a JSS 1 B on file, "JSS 1" asks — it does not admit
    the pupil into whichever class happens to sort first."""
    sid, w = _world(client, db)
    jss_1b = _add_arm(client, sid, w["session_id"], "JSS 1 B")
    first = _ask(client, sid, "add Ada Inyang to JSS 1")
    action = first["message"]["answer_payload"]["action"]
    assert "arm" in action["missing"]
    assert "JSS 1 A" in first["message"]["content"]
    assert "JSS 1 B" in first["message"]["content"]

    conv = first["conversation"]["id"]
    msg = _ask(client, sid, "JSS 1 B", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["params"]["arm_name"] == "JSS 1 B"
    _ask(client, sid, "female", conversation_id=conv)
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]
    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Ada"
        )
    )
    assert _current_arm_of(db, sid, student) == jss_1b


def test_an_unknown_class_is_named_and_the_real_classes_listed(client, db):
    """"Still needed: arm" was a misleading way to say "I don't have a class
    called that". Name the class that was not found and list the real ones."""
    sid, _w = _world(client, db, with_nursery=True)
    msg = _ask(client, sid, "Add Amina Manuel in Nursery 9")["message"]
    action = msg["answer_payload"]["action"]
    assert "arm" in action["missing"]
    assert "Nursery 9" in msg["content"]
    assert "Nursery 1" in msg["content"]
    assert "JSS 1 A" in msg["content"]


def test_a_mixed_message_runs_commands_of_different_kinds(client, db):
    """A message may carry commands of different kinds: an admission and a
    subject. Both are proposed together, then run one after the other."""
    sid, w = _world(client, db, with_nursery=True)
    before = len(_students(db, sid))

    first = _ask(
        client, sid,
        "add Amina John to Nursery 1 and create subject Further Mathematics",
    )
    msg = first["message"]
    assert msg["answer_payload"]["source"] == "command"
    action = msg["answer_payload"]["action"]
    assert action["code"] == "batch"
    assert action["status"] == "pending"
    assert [item["code"] for item in action["items"]] == [
        "admit_student",
        "create_subject",
    ]
    # Neither half ran before the confirmation.
    assert len(_students(db, sid)) == before
    assert db.scalar(
        select(Subject).where(
            Subject.school_id == uuid.UUID(sid),
            Subject.name == "Further Mathematics",
        )
    ) is None
    conv = first["conversation"]["id"]

    # The admission is the item missing a field, so it is asked for first.
    msg = _ask(client, sid, "female", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["items"][0]["missing"] == []

    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]

    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Amina"
        )
    )
    assert student is not None and student.gender == "female"
    assert _current_arm_of(db, sid, student) == w["nursery_arm_id"]
    subject = db.scalar(
        select(Subject).where(
            Subject.school_id == uuid.UUID(sid),
            Subject.name == "Further Mathematics",
        )
    )
    assert subject is not None


def test_a_mixed_message_can_span_students_and_staff(client, db):
    """"add Amina John to Nursery 1 and add teacher Grace Ade" — the carried
    verb means a pupil in one clause and a staff member in the next, and both
    writes still land."""
    sid, _w = _world(client, db, with_nursery=True)
    before = len(_students(db, sid))

    first = _ask(
        client, sid, "add Amina John to Nursery 1 and add teacher Grace Ade"
    )
    action = first["message"]["answer_payload"]["action"]
    assert action["code"] == "batch"
    assert [item["code"] for item in action["items"]] == [
        "admit_student",
        "add_staff",
    ]
    assert len(_students(db, sid)) == before

    conv = first["conversation"]["id"]
    _ask(client, sid, "female", conversation_id=conv)
    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]

    assert db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Amina"
        )
    ) is not None
    assert db.scalar(
        select(Staff).where(
            Staff.school_id == uuid.UUID(sid), Staff.full_name == "Grace Ade"
        )
    ) is not None


def test_three_commands_of_three_kinds_in_one_prompt(client, db):
    """One prompt, three different tasks: admit a pupil, create a subject and
    add a teacher. All three are proposed, then run in order."""
    sid, w = _world(client, db, with_nursery=True)
    before = len(_students(db, sid))

    prompt = (
        "add Amina John to Nursery 1 and create subject Further Mathematics "
        "and add teacher Grace Ade"
    )
    first = _ask(client, sid, prompt)
    action = first["message"]["answer_payload"]["action"]
    assert action["code"] == "batch"
    assert len(action["items"]) == 3
    assert [item["code"] for item in action["items"]] == [
        "admit_student",
        "create_subject",
        "add_staff",
    ]
    # Nothing is written until the confirmation.
    assert len(_students(db, sid)) == before

    conv = first["conversation"]["id"]
    msg = _ask(client, sid, "male", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["items"][0]["missing"] == []

    msg = _ask(client, sid, "confirm", conversation_id=conv)["message"]
    assert msg["answer_payload"]["action"]["status"] == "done", msg["content"]
    assert "(1)" in msg["content"]
    assert "(2)" in msg["content"]
    assert "(3)" in msg["content"]

    student = db.scalar(
        select(Student).where(
            Student.school_id == uuid.UUID(sid), Student.first_name == "Amina"
        )
    )
    assert student is not None and student.gender == "male"
    assert _current_arm_of(db, sid, student) == w["nursery_arm_id"]
    assert db.scalar(
        select(Subject).where(
            Subject.school_id == uuid.UUID(sid),
            Subject.name == "Further Mathematics",
        )
    ) is not None
    staff = db.scalar(
        select(Staff).where(
            Staff.school_id == uuid.UUID(sid), Staff.full_name == "Grace Ade"
        )
    )
    assert staff is not None and staff.staff_no.startswith("STF-")
