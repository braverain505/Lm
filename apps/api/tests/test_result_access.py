"""Access control around results: the Exam Office owns report cards, a teacher
owns only their own scoresheets.

A teacher holds ``results.view`` so the Results page works, but a report card
renders every subject a student takes, which is not a teacher's document. The
report-card endpoints therefore demand ``results.report_card`` — carried by the
Exam Officer, Principal and VP Academics templates, never by Teacher.

Separately, ``results.view`` alone must not open another teacher's score grid:
the assigned-teacher gate is enforced on reads too, not just writes.
"""
import uuid

from .conftest import active_school_id, register_school
from .test_results import (
    BASE,
    _act,
    _add_components,
    _configure,
    _enter_all,
    _enter_and_publish,
    _first_student_id,
)
from .test_staff_accounts import _add_staff, _create_account


def _login(client, email: str, password: str = "Str0ng!Pass"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def _permissions(client) -> set[str]:
    r = client.get("/api/auth/me")
    assert r.status_code == 200, r.text
    memberships = r.json()["memberships"]
    assert len(memberships) == 1
    return set(memberships[0]["permissions"])


def _make_staff_user(client, sid: str, *, staff_no: str, role_code: str, email: str) -> dict:
    """A staff record plus a login account carrying the given template role."""
    staff = _add_staff(client, sid, staff_no=staff_no)
    r = _create_account(client, sid, staff["id"], email=email, role_code=role_code)
    assert r.status_code == 201, r.text
    assert r.json()["role_code"] == role_code
    return staff


def test_school_admin_can_view_but_cannot_enter_scores(client):
    """The owner template keeps results.view and loses results.enter.

    A school admin may open any score grid (a supervisor bypasses the
    assigned-teacher gate) but the write endpoint refuses them — entering marks
    is the class teacher's job.
    """
    register_school(client)
    sid = active_school_id(client)
    perms = _permissions(client)
    assert "results.view" in perms  # grids stay viewable
    assert "results.enter" not in perms  # but not editable

    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": str(uuid.uuid4()),
            "subject_id": str(uuid.uuid4()),
            "term_id": str(uuid.uuid4()),
            "entries": [],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


# --- Report cards belong to the Exam Office ------------------------------------
def test_teacher_cannot_reach_any_report_card_endpoint(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    _add_components(client, sid, w["term_id"])
    _make_staff_user(client, sid, staff_no="T001", role_code="teacher", email="teach@test.edu")

    _login(client, "teach@test.edu")
    perms = _permissions(client)
    assert "results.view" in perms  # the Results page must still work
    assert "results.report_card" not in perms

    student_id = _first_student_id(db, w["arm_id"])
    headers = {"X-School-Id": sid}
    endpoints = [
        f"{BASE}/report-index?arm_id={w['arm_id']}&term_id={w['term_id']}",
        f"{BASE}/report-card?student_id={student_id}&term_id={w['term_id']}",
        f"{BASE}/report-cards?arm_id={w['arm_id']}&term_id={w['term_id']}",
        f"{BASE}/broadsheet?arm_id={w['arm_id']}&term_id={w['term_id']}",
        f"{BASE}/best-in-subjects?arm_id={w['arm_id']}&term_id={w['term_id']}",
        f"{BASE}/cumulative?student_id={student_id}&session_id={w['session_id']}",
    ]
    for url in endpoints:
        r = client.get(url, headers=headers)
        assert r.status_code == 403, (url, r.status_code, r.text)
        assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED", url


def test_exam_officer_can_render_published_report_cards(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _make_staff_user(
        client, sid, staff_no="T002", role_code="exam_officer", email="exam@test.edu"
    )
    # The admin publishes the cell while still signed in as the school admin.
    _enter_and_publish(client, sid, w, comps)

    _login(client, "exam@test.edu")
    perms = _permissions(client)
    assert "results.report_card" in perms

    student_id = _first_student_id(db, w["arm_id"])
    headers = {"X-School-Id": sid}

    r = client.get(
        f"{BASE}/report-index",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert all(row["subjects_published"] == 1 for row in r.json())

    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": student_id, "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["subjects_published"] == 1

    r = client.get(
        f"{BASE}/report-cards",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 3

    r = client.get(
        f"{BASE}/broadsheet",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_principal_and_vp_academics_carry_the_report_card_permission(client, db):
    """The template, not the individual: whoever holds these roles can print."""
    register_school(client)
    sid = active_school_id(client)
    for staff_no, role_code, email in (
        ("T003", "principal", "principal@test.edu"),
        ("T004", "vp_academics", "vp@test.edu"),
    ):
        _make_staff_user(
            client, sid, staff_no=staff_no, role_code=role_code, email=email
        )
    _login(client, "principal@test.edu")
    assert "results.report_card" in _permissions(client)
    _login(client, "vp@test.edu")
    assert "results.report_card" in _permissions(client)


def test_head_teacher_and_secretary_lose_report_cards(client, db):
    """Academic leadership that is not the exam office keeps results.view only."""
    register_school(client)
    sid = active_school_id(client)
    for staff_no, role_code, email in (
        ("T005", "head_teacher", "head@test.edu"),
        ("T006", "secretary", "sec@test.edu"),
    ):
        _make_staff_user(client, sid, staff_no=staff_no, role_code=role_code, email=email)
    for email in ("head@test.edu", "sec@test.edu"):
        _login(client, email)
        perms = _permissions(client)
        assert "results.view" in perms
        # Both may look at results; neither may render a report card.
        assert "results.report_card" not in perms


# --- The Exam Office owns the whole pipeline ------------------------------------
def test_exam_officer_can_compile_to_a_published_report_card(client, db):
    """Verify + approve + publish in one action, then print what it produced.

    Teachers enter the marks; the exam office finalizes them. Report cards render
    *published* results, so before ``results.approve`` was on the role the office
    could only print cards somebody else had signed off.
    """
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _make_staff_user(
        client, sid, staff_no="T009", role_code="exam_officer", email="exam3@test.edu"
    )

    # The admin (a score-entry role) enters the marks.
    _enter_all(client, sid, w, comps, score=70)

    _login(client, "exam3@test.edu")
    headers = {"X-School-Id": sid}
    r = client.post(
        f"{BASE}/compile",
        json={"arm_id": w["arm_id"], "subject_id": w["subject_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["published"] == 3

    r = client.get(
        f"{BASE}/report-card",
        params={"student_id": _first_student_id(db, w["arm_id"]), "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    card = r.json()
    assert card["summary"]["subjects_published"] == 1
    # 70 on every component, so the frozen snapshot is 70.
    assert card["subjects"][0]["total"] == 70.0


def test_exam_officer_verifies_approves_and_publishes_stepwise(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _make_staff_user(
        client, sid, staff_no="T010", role_code="exam_officer", email="exam4@test.edu"
    )

    # A score-entry role submits; the exam office takes it from there.
    _enter_all(client, sid, w, comps)
    assert _act(client, sid, w, "submit").status_code == 200

    _login(client, "exam4@test.edu")
    r = _act(client, sid, w, "verify")
    assert r.status_code == 200 and r.json()["verified"] == 3, r.text
    r = _act(client, sid, w, "approve")
    assert r.status_code == 200 and r.json()["approved"] == 3, r.text
    r = _act(client, sid, w, "publish")
    assert r.status_code == 200 and r.json()["published"] == 3, r.text


def test_exam_officer_cannot_enter_or_submit_scores(client, db):
    """The office finalizes; entering marks stays with the teacher."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    comps = _add_components(client, sid, w["term_id"])
    _make_staff_user(
        client, sid, staff_no="T011", role_code="exam_officer", email="exam5@test.edu"
    )
    _login(client, "exam5@test.edu")

    r = client.put(
        f"{BASE}/scorecard",
        json={
            "arm_id": w["arm_id"],
            "subject_id": w["subject_id"],
            "term_id": w["term_id"],
            "entries": [
                {
                    "student_enrollment_id": w["enrollment_ids"][0],
                    "scores": [
                        {"assessment_component_id": comps[c], "score": 10}
                        for c in ("CA1", "CA2", "Exam")
                    ],
                }
            ],
        },
        headers={"X-School-Id": sid},
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"


# --- A teacher reads only their own score grids ---------------------------------
def test_teacher_scoresheet_restricted_to_assigned_class(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    _add_components(client, sid, w["term_id"])
    staff = _make_staff_user(
        client, sid, staff_no="T007", role_code="teacher", email="owner@test.edu"
    )

    headers = {"X-School-Id": sid}
    grid = {"arm_id": w["arm_id"], "subject_id": w["subject_id"], "term_id": w["term_id"]}

    _login(client, "owner@test.edu")

    # Not assigned yet: the grid is refused and the readiness board is empty,
    # even though the arm x subject genuinely exists in the school.
    r = client.get(f"{BASE}/scorecard", params=grid, headers=headers)
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "ERR_ASSIGNMENT"

    r = client.get(
        f"{BASE}/readiness",
        params={"term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json() == []

    r = client.get(
        f"{BASE}/workbench",
        params={"term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json() == []

    # The admin assigns this teacher to the class x subject.
    _login(client, "admin@test.edu")
    r = client.post(
        "/api/academics/assignments",
        json={"arm_id": w["arm_id"], "subject_id": w["subject_id"], "teacher_id": staff["id"]},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    _login(client, "owner@test.edu")
    r = client.get(f"{BASE}/scorecard", params=grid, headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["students"]) == 3

    r = client.get(
        f"{BASE}/readiness",
        params={"term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["arm_id"] == w["arm_id"]
    assert rows[0]["subject_id"] == w["subject_id"]

    # Report cards stay shut even for the assigned teacher.
    r = client.get(
        f"{BASE}/report-index",
        params={"arm_id": w["arm_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 403


def test_supervisor_sees_the_whole_school(client, db):
    """A workflow permission (verify/approve/publish) lifts the assignment gate."""
    register_school(client)
    sid = active_school_id(client)
    w = _configure(client, sid, db)
    _add_components(client, sid, w["term_id"])
    _make_staff_user(
        client, sid, staff_no="T008", role_code="vp_academics", email="vp2@test.edu"
    )

    _login(client, "vp2@test.edu")
    headers = {"X-School-Id": sid}

    r = client.get(
        f"{BASE}/scorecard",
        params={"arm_id": w["arm_id"], "subject_id": w["subject_id"], "term_id": w["term_id"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r = client.get(f"{BASE}/readiness", params={"term_id": w["term_id"]}, headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1
