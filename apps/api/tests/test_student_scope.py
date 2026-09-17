"""A teacher's view of the school stops at the classes they teach.

The student roster, a single profile, a class roster and a student's guardians
are all bounded by the caller's ``SubjectAssignment``. A pupil in a class the
caller does not teach is a neutral 404 — the same answer the tenancy layer gives
for another school's rows — so nothing is revealed either way.

Offices that genuinely need every pupil (school admins, principal, VPs, the exam
office, admission officer, secretary, librarian) keep the whole roster, because
they hold a roster-wide capability: see ``ROSTER_WIDE_PERMISSIONS``.
"""
from .conftest import active_school_id, register_school
from .test_staff_accounts import _add_staff, _create_account

ACAD = "/api/academics"
STUDENTS = "/api/students"


def _world(client, sid: str) -> dict:
    """Two class arms, one subject, and one student enrolled in each arm."""
    headers = {"X-School-Id": sid}
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    r = client.post(
        f"{ACAD}/terms",
        json={"session_id": session_id, "term_no": 1, "name": "First Term"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    term_id = r.json()["id"]
    # Results work needs an activated session + term; the roster does not, but
    # keeping the world consistent means these helpers stay reusable.
    assert client.post(f"{ACAD}/sessions/{session_id}/activate", headers=headers).status_code == 200
    assert client.post(f"{ACAD}/terms/{term_id}/activate", headers=headers).status_code == 200

    arms = {}
    for name in ("JSS 1 A", "JSS 1 B"):
        r = client.post(
            f"{ACAD}/arms",
            json={"session_id": session_id, "name": name},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        arms[name] = r.json()["id"]

    r = client.post(
        f"{ACAD}/subjects",
        json={"name": "Mathematics", "code": "MTH"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    subject_id = r.json()["id"]

    for arm_id in arms.values():
        r = client.post(
            f"{ACAD}/offerings",
            json={"arm_id": arm_id, "subject_id": subject_id},
            headers=headers,
        )
        assert r.status_code == 201, r.text

    students = {}
    for arm_name, (admission_no, first, last) in {
        "JSS 1 A": ("A-001", "Ada", "Alpha"),
        "JSS 1 B": ("B-001", "Bob", "Beta"),
    }.items():
        r = client.post(
            f"{STUDENTS}",
            json={
                "admission_no": admission_no,
                "first_name": first,
                "last_name": last,
                "gender": "female",
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        student_id = r.json()["id"]
        r = client.post(
            f"{STUDENTS}/enrollments",
            json={"student_id": student_id, "arm_id": arms[arm_name], "session_id": session_id},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        students[arm_name] = student_id

    return {
        "session_id": session_id,
        "term_id": term_id,
        "arms": arms,
        "subject_id": subject_id,
        "students": students,
    }


def _teacher(client, sid: str, *, staff_no: str, role_code: str, email: str) -> dict:
    staff = _add_staff(client, sid, staff_no=staff_no)
    r = _create_account(client, sid, staff["id"], email=email, role_code=role_code)
    assert r.status_code == 201, r.text
    return staff


def _login(client, email: str, password: str = "Str0ng!Pass") -> None:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def test_teacher_roster_stops_at_their_own_classes(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    headers = {"X-School-Id": sid}
    arm_a, arm_b = w["arms"]["JSS 1 A"], w["arms"]["JSS 1 B"]
    student_a, student_b = w["students"]["JSS 1 A"], w["students"]["JSS 1 B"]

    # The admin (school super_admin) sees everyone, before and after.
    r = client.get(STUDENTS, headers=headers)
    assert r.status_code == 200 and len(r.json()) == 2, r.text

    staff = _teacher(
        client, sid, staff_no="T101", role_code="teacher", email="maths@test.edu"
    )
    _login(client, "maths@test.edu")

    # Not assigned to anything yet: a teacher's roster is empty, not the school.
    r = client.get(STUDENTS, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == []

    # The admin assigns Mathematics in JSS 1 A only.
    _login(client, "admin@test.edu")
    r = client.post(
        f"{ACAD}/assignments",
        json={"arm_id": arm_a, "subject_id": w["subject_id"], "teacher_id": staff["id"]},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    _login(client, "maths@test.edu")

    # The roster is now exactly their own class.
    r = client.get(STUDENTS, headers=headers)
    assert r.status_code == 200, r.text
    assert [s["id"] for s in r.json()] == [student_a]

    # Asking for another class explicitly returns nothing, rather than its pupils.
    r = client.get(f"{STUDENTS}?arm_id={arm_b}", headers=headers)
    assert r.status_code == 200 and r.json() == [], r.text

    # Their own class still works, both ways round.
    r = client.get(f"{STUDENTS}?arm_id={arm_a}", headers=headers)
    assert r.status_code == 200 and [s["id"] for s in r.json()] == [student_a], r.text
    r = client.get(f"{STUDENTS}/arms/{arm_a}/enrollments", headers=headers)
    assert r.status_code == 200 and len(r.json()) == 1, r.text

    # A pupil outside their classes is a neutral 404, everywhere a student is read.
    for url in (
        f"{STUDENTS}/{student_b}",
        f"{STUDENTS}/{student_b}/enrollments",
        f"{STUDENTS}/{student_b}/guardians",
        f"{STUDENTS}/arms/{arm_b}/enrollments",
    ):
        r = client.get(url, headers=headers)
        assert r.status_code == 404, (url, r.status_code, r.text)
        assert r.json()["error"]["code"] == "ERR_NOT_FOUND", url

    # Their own pupil's profile and history stay readable.
    assert client.get(f"{STUDENTS}/{student_a}", headers=headers).status_code == 200
    assert client.get(f"{STUDENTS}/{student_a}/enrollments", headers=headers).status_code == 200
    assert client.get(f"{STUDENTS}/{student_a}/guardians", headers=headers).status_code == 200


def test_homeroom_teacher_is_scoped_and_offices_are_not(client, db):
    register_school(client)
    sid = active_school_id(client)
    w = _world(client, sid)
    headers = {"X-School-Id": sid}
    arm_a = w["arms"]["JSS 1 A"]
    student_a = w["students"]["JSS 1 A"]

    _teacher(
        client, sid, staff_no="T102", role_code="homeroom_teacher", email="hr@test.edu"
    )
    _teacher(
        client, sid, staff_no="T103", role_code="secretary", email="sec@test.edu"
    )

    # A homeroom teacher with no assignment teaches nothing → empty roster.
    _login(client, "hr@test.edu")
    r = client.get(STUDENTS, headers=headers)
    assert r.status_code == 200 and r.json() == [], r.text

    # The secretary runs the front office: the whole roster, unscoped.
    _login(client, "sec@test.edu")
    r = client.get(STUDENTS, headers=headers)
    assert r.status_code == 200 and len(r.json()) == 2, r.text

    # And so does everyone else whose work spans the school.
    for staff_no, role_code, email in (
        ("T104", "exam_officer", "exam-scope@test.edu"),
        ("T105", "principal", "principal2@test.edu"),
    ):
        _login(client, "admin@test.edu")
        _teacher(client, sid, staff_no=staff_no, role_code=role_code, email=email)
        _login(client, email)
        r = client.get(STUDENTS, headers=headers)
        assert r.status_code == 200 and len(r.json()) == 2, (role_code, r.text)

    # Sanity: the assigned arm is visible to the homeroom teacher once assigned.
    _login(client, "admin@test.edu")
    staff_hr = client.get("/api/staff", headers=headers).json()
    hr_id = next(s["id"] for s in staff_hr if s["staff_no"] == "T102")
    r = client.post(
        f"{ACAD}/assignments",
        json={"arm_id": arm_a, "subject_id": w["subject_id"], "teacher_id": hr_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    _login(client, "hr@test.edu")
    r = client.get(STUDENTS, headers=headers)
    assert r.status_code == 200 and [s["id"] for s in r.json()] == [student_a], r.text
