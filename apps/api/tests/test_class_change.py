"""Bulk class-change tests: move one or many students into another class of the
same session (a manual promote/demote), and check the skip rules.
"""
from .conftest import active_school_id, register_school

BASE = "/api/students"
ACADEMICS = "/api/academics"


def _setup(client, school_id: str) -> dict:
    """One session with two classes and two enrolled pupils."""
    session = client.post(
        f"{ACADEMICS}/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": school_id},
    ).json()
    basic1 = client.post(
        f"{ACADEMICS}/arms",
        json={"session_id": session["id"], "name": "Basic 1"},
        headers={"X-School-Id": school_id},
    ).json()
    basic2 = client.post(
        f"{ACADEMICS}/arms",
        json={"session_id": session["id"], "name": "Basic 2"},
        headers={"X-School-Id": school_id},
    ).json()

    students = []
    for number, name in ((1, "Ade"), (2, "Bisi")):
        student = client.post(
            BASE,
            json={
                "admission_no": f"STU-00{number}",
                "first_name": name,
                "last_name": "Bello",
                "gender": "male",
            },
            headers={"X-School-Id": school_id},
        ).json()
        enrolled = client.post(
            f"{BASE}/enrollments",
            json={
                "student_id": student["id"],
                "arm_id": basic1["id"],
                "session_id": session["id"],
            },
            headers={"X-School-Id": school_id},
        )
        assert enrolled.status_code == 201, enrolled.text
        students.append(student)

    return {"session": session, "basic1": basic1, "basic2": basic2, "students": students}


def _current_arm(client, school_id: str, student_id: str) -> str:
    rows = client.get(
        f"{BASE}/{student_id}/enrollments", headers={"X-School-Id": school_id}
    ).json()
    return next(row for row in rows if row["is_current"])["arm_name"]


def test_bulk_change_moves_selected_students(client):
    register_school(client, name="Change Academy", email="change@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)

    r = client.post(
        f"{BASE}/class-change",
        json={
            "student_ids": [s["id"] for s in fx["students"]],
            "session_id": fx["session"]["id"],
            "target_arm_id": fx["basic2"]["id"],
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"moved": 2, "skipped": []}
    for student in fx["students"]:
        assert _current_arm(client, school_id, student["id"]) == "Basic 2"


def test_single_student_change_is_the_same_endpoint(client):
    register_school(client, name="Single Academy", email="single@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)
    student, other = fx["students"]

    r = client.post(
        f"{BASE}/class-change",
        json={
            "student_ids": [student["id"]],
            "session_id": fx["session"]["id"],
            "target_arm_id": fx["basic2"]["id"],
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"moved": 1, "skipped": []}
    assert _current_arm(client, school_id, student["id"]) == "Basic 2"
    # The pupil who was not selected stays where they were.
    assert _current_arm(client, school_id, other["id"]) == "Basic 1"


def test_students_already_in_target_are_skipped(client):
    register_school(client, name="Skip Academy", email="skip@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)

    payload = {
        "student_ids": [s["id"] for s in fx["students"]],
        "session_id": fx["session"]["id"],
        "target_arm_id": fx["basic2"]["id"],
    }
    first = client.post(
        f"{BASE}/class-change", json=payload, headers={"X-School-Id": school_id}
    )
    assert first.status_code == 200, first.text

    again = client.post(
        f"{BASE}/class-change", json=payload, headers={"X-School-Id": school_id}
    )
    assert again.status_code == 200, again.text
    body = again.json()
    assert body["moved"] == 0
    assert sorted(body["skipped"]) == sorted(s["id"] for s in fx["students"])


def test_target_class_from_another_session_is_rejected(client):
    register_school(client, name="Session Academy", email="session@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)
    other_session = client.post(
        f"{ACADEMICS}/sessions",
        json={"name": "2026/2027"},
        headers={"X-School-Id": school_id},
    ).json()
    other_arm = client.post(
        f"{ACADEMICS}/arms",
        json={"session_id": other_session["id"], "name": "Basic 2"},
        headers={"X-School-Id": school_id},
    ).json()

    r = client.post(
        f"{BASE}/class-change",
        json={
            "student_ids": [fx["students"][0]["id"]],
            "session_id": fx["session"]["id"],
            "target_arm_id": other_arm["id"],
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422, r.text
