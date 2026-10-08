"""Academic-structure delete tests.

Deleting a session, term or class is the undo for one created by mistake, so the
behaviour pinned here is deliberately asymmetric: an empty record disappears
cleanly, while one that is in use (active, has results/components, or has
students enrolled) is refused with a 409 rather than silently cascading real
school data away.
"""
import uuid

from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Term
from .conftest import active_school_id, register_school
from .test_portal import _add_limited_user
from .test_results import ACAD, _add_components, _configure, _enter_all


def _create_session(client, sid: str, name: str = "2026/2027") -> str:
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": name, "is_current": False},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_term(client, sid: str, session_id: str, term_no: int, name: str) -> str:
    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": session_id, "term_no": term_no, "name": name},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_arm(client, sid: str, session_id: str, name: str) -> str:
    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": session_id, "name": name},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_student(client, sid: str, admission_no: str) -> str:
    r = client.post(
        "/api/students",
        json={
            "admission_no": admission_no,
            "first_name": "Ada",
            "last_name": "One",
            "gender": "female",
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _enroll(client, sid: str, student_id: str, arm_id: str, session_id: str) -> str:
    r = client.post(
        "/api/students/enrollments",
        json={"student_id": student_id, "arm_id": arm_id, "session_id": session_id},
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- Classes -----------------------------------------------------------------
def test_delete_unused_class_removes_its_offerings(client, db):
    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    arm_id = _create_arm(client, sid, session_id, "JSS 1 A")

    r = client.post(
        f"{ACAD}/subjects",
        json={"name": "Mathematics", "code": "MTH"},
        headers={"X-School-Id": sid},
    )
    subject_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/offerings",
        json={"arm_id": arm_id, "subject_id": subject_id},
        headers={"X-School-Id": sid},
    )
    offering_id = r.json()["id"]

    r = client.delete(f"{ACAD}/arms/{arm_id}", headers={"X-School-Id": sid})
    assert r.status_code == 204, r.text

    r = client.get(f"{ACAD}/sessions/{session_id}/arms", headers={"X-School-Id": sid})
    assert r.json() == []
    # The class's offering went with it instead of being orphaned.
    from app.models import SubjectOffering

    assert db.scalar(select(SubjectOffering.id).where(SubjectOffering.id == uuid.UUID(offering_id))) is None


def test_delete_class_with_enrolled_students_is_refused(client, db):
    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    arm_id = _create_arm(client, sid, session_id, "JSS 1 A")
    student_id = _create_student(client, sid, "STU-001")
    _enroll(client, sid, student_id, arm_id, session_id)

    r = client.delete(f"{ACAD}/arms/{arm_id}", headers={"X-School-Id": sid})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"
    assert "students enrolled" in r.json()["error"]["message"]

    # Still there — a refused delete changes nothing.
    r = client.get(f"{ACAD}/sessions/{session_id}/arms", headers={"X-School-Id": sid})
    assert [a["id"] for a in r.json()] == [arm_id]


def test_delete_missing_class_returns_404(client, db):
    register_school(client)
    sid = active_school_id(client)
    r = client.delete(f"{ACAD}/arms/{uuid.uuid4()}", headers={"X-School-Id": sid})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Terms -------------------------------------------------------------------
def test_delete_unused_term(client, db):
    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    term_id = _create_term(client, sid, session_id, 1, "First Term")

    r = client.delete(f"{ACAD}/terms/{term_id}", headers={"X-School-Id": sid})
    assert r.status_code == 204, r.text

    r = client.get(f"{ACAD}/sessions/{session_id}/terms", headers={"X-School-Id": sid})
    assert r.json() == []


def test_delete_active_term_is_refused(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)  # First Term activated (open)

    r = client.delete(f"{ACAD}/terms/{w['term_id']}", headers={"X-School-Id": sid})
    assert r.status_code == 409
    assert "active term" in r.json()["error"]["message"]


def test_delete_closed_term_with_components_is_refused(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    _add_components(client, sid, w["term_id"])

    # Close it so the active-term guard no longer masks the in-use guard.
    r = client.post(f"{ACAD}/terms/{w['term_id']}/close", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text

    r = client.delete(f"{ACAD}/terms/{w['term_id']}", headers={"X-School-Id": sid})
    assert r.status_code == 409
    assert "assessment components" in r.json()["error"]["message"]


def test_delete_closed_term_with_results_is_refused(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _enter_all(client, sid, w, comps)

    r = client.post(f"{ACAD}/terms/{w['term_id']}/close", headers={"X-School-Id": sid})
    assert r.status_code == 200, r.text

    r = client.delete(f"{ACAD}/terms/{w['term_id']}", headers={"X-School-Id": sid})
    assert r.status_code == 409
    assert "results recorded" in r.json()["error"]["message"]


# --- Sessions ----------------------------------------------------------------
def test_delete_active_session_is_refused(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)  # session activated (open)

    r = client.delete(f"{ACAD}/sessions/{w['session_id']}", headers={"X-School-Id": sid})
    assert r.status_code == 409
    assert "active session" in r.json()["error"]["message"]


def test_delete_session_with_enrolled_students_is_refused(client, db):
    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    arm_id = _create_arm(client, sid, session_id, "JSS 1 A")
    student_id = _create_student(client, sid, "STU-002")
    _enroll(client, sid, student_id, arm_id, session_id)

    r = client.delete(f"{ACAD}/sessions/{session_id}", headers={"X-School-Id": sid})
    assert r.status_code == 409
    assert "students enrolled" in r.json()["error"]["message"]


def test_delete_unused_session_removes_its_terms_and_classes(client, db):
    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    term_id = _create_term(client, sid, session_id, 1, "First Term")
    arm_id = _create_arm(client, sid, session_id, "JSS 1 A")

    r = client.delete(f"{ACAD}/sessions/{session_id}", headers={"X-School-Id": sid})
    assert r.status_code == 204, r.text

    # Query columns rather than entities so the identity map can't return a
    # stale object for a row a core DELETE removed.
    from app.models import AcademicSession, ClassArm

    assert db.scalar(select(AcademicSession.id).where(AcademicSession.id == uuid.UUID(session_id))) is None
    assert db.scalar(select(Term.id).where(Term.id == uuid.UUID(term_id))) is None
    assert db.scalar(select(ClassArm.id).where(ClassArm.id == uuid.UUID(arm_id))) is None

    r = client.get(f"{ACAD}/sessions", headers={"X-School-Id": sid})
    assert [s["id"] for s in r.json()] == []


# --- Permission gate ---------------------------------------------------------
def test_deletes_require_academic_manage(client, db):
    register_school(client)
    sid = active_school_id(client)
    session_id = _create_session(client, sid)
    term_id = _create_term(client, sid, session_id, 1, "First Term")
    arm_id = _create_arm(client, sid, session_id, "JSS 1 A")

    user = _add_limited_user(db, sid, "teacher")  # teachers cannot manage academics
    client.cookies.clear()
    headers = {"X-School-Id": sid, "Authorization": f"Bearer {create_access_token(str(user.id))}"}

    for path in (
        f"{ACAD}/sessions/{session_id}",
        f"{ACAD}/terms/{term_id}",
        f"{ACAD}/arms/{arm_id}",
    ):
        r = client.delete(path, headers=headers)
        assert r.status_code == 403, r.text
        assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"
