"""Student promotion tests: enroll in session A, promote into session B via an
explicit target-class mapping, verify history + isolation.
"""
from .conftest import active_school_id, register_school

BASE = "/api/students"
ACADEMICS = "/api/academics"


def _setup(client, school_id: str) -> dict:
    """Two sessions, one arm each, one enrolled student."""
    # Session 2025/2026 (current)
    s1 = client.post(
        f"{ACADEMICS}/sessions",
        json={"name": "2025/2026", "is_current": True},
        headers={"X-School-Id": school_id},
    ).json()
    # Arm JSS 1 A in session 1
    a1 = client.post(
        f"{ACADEMICS}/arms",
        json={"session_id": s1["id"], "name": "JSS 1 A"},
        headers={"X-School-Id": school_id},
    ).json()
    # Session 2026/2027
    s2 = client.post(
        f"{ACADEMICS}/sessions",
        json={"name": "2026/2027"},
        headers={"X-School-Id": school_id},
    ).json()
    # Arm JSS 2 A in session 2 (the promotion target)
    a2 = client.post(
        f"{ACADEMICS}/arms",
        json={"session_id": s2["id"], "name": "JSS 2 A"},
        headers={"X-School-Id": school_id},
    ).json()

    student = client.post(
        BASE,
        json={"admission_no": "STU-001", "first_name": "Ade", "last_name": "Bello", "gender": "male"},
        headers={"X-School-Id": school_id},
    ).json()
    enrollment = client.post(
        f"{BASE}/enrollments",
        json={"student_id": student["id"], "arm_id": a1["id"], "session_id": s1["id"]},
        headers={"X-School-Id": school_id},
    )
    assert enrollment.status_code == 201, enrollment.text

    return {"s1": s1, "s2": s2, "a1": a1, "a2": a2, "student": student}


def test_promote_student_to_next_session(client):
    register_school(client, name="Promo Academy", email="promo@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)

    r = client.post(
        f"{BASE}/promote",
        json={
            "from_session_id": fx["s1"]["id"],
            "to_session_id": fx["s2"]["id"],
            "target_arms": [{"from_arm_id": fx["a1"]["id"], "to_arm_id": fx["a2"]["id"]}],
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["promoted"] == 1
    assert body["skipped"] == []

    # History should show two rows: old (completed) + new (current, JSS 2 A).
    history = client.get(
        f"{BASE}/{fx['student']['id']}/enrollments",
        headers={"X-School-Id": school_id},
    )
    assert history.status_code == 200, history.text
    rows = history.json()
    assert len(rows) == 2
    current = next(r for r in rows if r["is_current"])
    assert current["arm_name"] == "JSS 2 A"
    old = next(r for r in rows if not r["is_current"])
    assert old["status"] == "completed"


def test_promote_skips_when_target_arm_missing(client):
    register_school(client, name="NoTarget Academy", email="notarget@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)

    # A second source class (JSS 1 B) with an enrolled student but no mapping.
    arm_b = client.post(
        f"{ACADEMICS}/arms",
        json={"session_id": fx["s1"]["id"], "name": "JSS 1 B"},
        headers={"X-School-Id": school_id},
    ).json()
    skipped_student = client.post(
        BASE,
        json={"admission_no": "STU-002", "first_name": "Chi", "last_name": "Nwosu", "gender": "female"},
        headers={"X-School-Id": school_id},
    ).json()
    r = client.post(
        f"{BASE}/enrollments",
        json={"student_id": skipped_student["id"], "arm_id": arm_b["id"], "session_id": fx["s1"]["id"]},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text

    # Only JSS 1 A maps to a target; JSS 1 B has none in the new session.
    r = client.post(
        f"{BASE}/promote",
        json={
            "from_session_id": fx["s1"]["id"],
            "to_session_id": fx["s2"]["id"],
            "target_arms": [{"from_arm_id": fx["a1"]["id"], "to_arm_id": fx["a2"]["id"]}],
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["promoted"] == 1
    assert skipped_student["id"] in body["skipped"]


def test_promote_restricted_to_student_ids(client):
    register_school(client, name="Selective Academy", email="sel@test.edu")
    school_id = active_school_id(client)
    fx = _setup(client, school_id)

    r = client.post(
        f"{BASE}/promote",
        json={
            "from_session_id": fx["s1"]["id"],
            "to_session_id": fx["s2"]["id"],
            "target_arms": [{"from_arm_id": fx["a1"]["id"], "to_arm_id": fx["a2"]["id"]}],
            "student_ids": [fx["student"]["id"]],
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["promoted"] == 1


def test_promote_cross_school_rejected(client):
    register_school(client, name="Isolation A", email="iso_a@test.edu")
    school_id_a = active_school_id(client)
    fx = _setup(client, school_id_a)

    register_school(client, name="Isolation B", email="iso_b@test.edu")
    school_id_b = active_school_id(client)

    # School B tries to promote School A's session -> 404 (not a member).
    r = client.post(
        f"{BASE}/promote",
        json={
            "from_session_id": fx["s1"]["id"],
            "to_session_id": fx["s2"]["id"],
            "target_arms": [{"from_arm_id": fx["a1"]["id"], "to_arm_id": fx["a2"]["id"]}],
        },
        headers={"X-School-Id": school_id_b},
    )
    assert r.status_code == 404, r.text