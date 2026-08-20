"""Timetable tests: slot template, deterministic generation with no teacher
double-booking, validation, weekly view, tenant isolation, and permission gates.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/timetable"
ACAD = "/api/academics"
STAFF = "/api/staff"


def _school(client, name: str, email: str) -> str:
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _create_world(client, school_id: str) -> dict:
    """Session + 2 subjects + offerings + arm + teacher + assignments."""
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2026/2027", "is_current": True},
        headers={"X-School-Id": school_id},
    )
    session_id = r.json()["id"]

    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": session_id, "name": "JSS 1 A"},
        headers={"X-School-Id": school_id},
    )
    arm_id = r.json()["id"]

    subjects = []
    for name, code in [("Mathematics", "MTH"), ("English", "ENG")]:
        r = client.post(
            f"{ACAD}/subjects",
            json={"name": name, "code": code},
            headers={"X-School-Id": school_id},
        )
        subject = r.json()
        subjects.append(subject)
        r = client.post(
            f"{ACAD}/offerings",
            json={"arm_id": arm_id, "subject_id": subject["id"]},
            headers={"X-School-Id": school_id},
        )
        assert r.status_code == 201, r.text

    r = client.post(
        STAFF,
        json={"staff_no": "T-001", "full_name": "Miss Teach", "membership_type": "teaching"},
        headers={"X-School-Id": school_id},
    )
    teacher_id = r.json()["id"]

    for subject in subjects:
        r = client.post(
            f"{ACAD}/assignments",
            json={"arm_id": arm_id, "subject_id": subject["id"], "teacher_id": teacher_id},
            headers={"X-School-Id": school_id},
        )
        assert r.status_code == 201, r.text

    return {
        "session_id": session_id,
        "arm_id": arm_id,
        "teacher_id": teacher_id,
        "subjects": subjects,
    }


# --- Slots -----------------------------------------------------------------------------
def test_time_slots_template(client):
    school_id = _school(client, "Slot School", "sl@test.edu")
    r = client.get(f"{BASE}/time-slots", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    slots = r.json()
    assert len(slots) == 8
    assert slots[0]["start"] == "08:00:00"
    assert slots[0]["label"].startswith("Period 1")


# --- Generation ------------------------------------------------------------------------
def test_generate_is_deterministic_and_conflict_free(client):
    school_id = _school(client, "Gen School", "gn@test.edu")
    world = _create_world(client, school_id)

    r = client.post(
        f"{BASE}/generate",
        json={"academic_session_id": world["session_id"], "include_rooms": False},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    entries = body["entries"]
    # 2 subjects × 2 periods each for the single arm.
    assert len(entries) == 4
    assert body["message"].startswith("Generated 4 entries")

    for subject in world["subjects"]:
        subj_entries = [e for e in entries if e["subject_id"] == subject["id"]]
        assert len(subj_entries) == 2

    # Teacher is never double-booked in the same (day, period).
    seen: dict[tuple, int] = {}
    for e in entries:
        assert e["teacher_id"] == world["teacher_id"]
        assert e["teacher_name"] == "Miss Teach"
        key = (e["day_of_week"], e["period_start"])
        assert key not in seen, f"teacher double-booked at {key}"
        seen[key] = 1

    # Same input → same output (deterministic).
    r2 = client.post(
        f"{BASE}/generate",
        json={"academic_session_id": world["session_id"], "include_rooms": False},
        headers={"X-School-Id": school_id},
    )
    assert [e["id"] for e in r2.json()["entries"]] == [e["id"] for e in entries]


def test_generate_warns_when_subject_has_no_teacher(client):
    school_id = _school(client, "Warn School", "wn@test.edu")
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2027/2028", "is_current": False},
        headers={"X-School-Id": school_id},
    )
    session_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/arms",
        json={"session_id": session_id, "name": "JSS 2 B"},
        headers={"X-School-Id": school_id},
    )
    arm_id = r.json()["id"]
    r = client.post(
        f"{ACAD}/subjects", json={"name": "Physics", "code": "PHY"}, headers={"X-School-Id": school_id}
    )
    subject_id = r.json()["id"]
    client.post(
        f"{ACAD}/offerings",
        json={"arm_id": arm_id, "subject_id": subject_id},
        headers={"X-School-Id": school_id},
    )

    r = client.post(
        f"{BASE}/generate",
        json={"academic_session_id": session_id, "include_rooms": False},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert any("No teacher assigned" in w for w in r.json()["warnings"])
    assert all(e["teacher_id"] is None for e in r.json()["entries"])


# --- Weekly view -----------------------------------------------------------------------
def test_weekly_schedule_for_arm(client):
    school_id = _school(client, "Week School", "wk@test.edu")
    world = _create_world(client, school_id)

    r = client.get(
        f"{BASE}/week/{world['arm_id']}", headers={"X-School-Id": school_id}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["academic_session_id"] == world["session_id"]
    assert len(body["days"]) == 5
    assert body["total_entries"] == 4
    assert sum(d["total_periods"] for d in body["days"]) == 4
    assert all(d["day_name"] == name for d, name in zip(body["days"], ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))


# --- Validation ------------------------------------------------------------------------
def test_validate_detects_teacher_double_booking(client):
    school_id = _school(client, "Val School", "vl@test.edu")
    world = _create_world(client, school_id)
    subject_id = world["subjects"][0]["id"]

    conflict_entries = [
        {
            "class_arm_id": world["arm_id"],
            "class_arm_name": "JSS 1A",
            "subject_id": subject_id,
            "subject_name": "Mathematics",
            "teacher_id": world["teacher_id"],
            "teacher_name": "Miss Teach",
            "day_of_week": 0,
            "period_start": "08:00:00",
            "period_end": "08:35:00",
        },
        {
            "class_arm_id": world["arm_id"],
            "class_arm_name": "JSS 1A",
            "subject_id": subject_id,
            "subject_name": "Mathematics",
            "teacher_id": world["teacher_id"],
            "teacher_name": "Miss Teach",
            "day_of_week": 0,
            "period_start": "08:05:00",
            "period_end": "08:40:00",
        },
    ]
    r = client.post(
        f"{BASE}/validate", json={"entries": conflict_entries}, headers={"X-School-Id": school_id}
    )
    assert r.status_code == 200
    assert r.json()["is_valid"] is False
    assert any(c["type"] == "teacher_double_booking" for c in r.json()["conflicts"])


def test_validate_accepts_generated_schedule(client):
    school_id = _school(client, "OK School", "ok@test.edu")
    world = _create_world(client, school_id)

    r = client.post(
        f"{BASE}/generate",
        json={"academic_session_id": world["session_id"], "include_rooms": False},
        headers={"X-School-Id": school_id},
    )
    entries = r.json()["entries"]

    r = client.post(f"{BASE}/validate", json={"entries": entries}, headers={"X-School-Id": school_id})
    assert r.status_code == 200
    assert r.json()["is_valid"] is True
    assert r.json()["conflicts"] == []


# --- Tenant isolation ------------------------------------------------------------------
def test_cross_school_timetable_isolation(client):
    school_a = _school(client, "Isol A", "ta@test.edu")
    world = _create_world(client, school_a)

    register_school(client, name="Isol B", email="tb@test.edu")
    school_b = active_school_id(client)

    # Weekly view of school A's arm from school B.
    r = client.get(f"{BASE}/week/{world['arm_id']}", headers={"X-School-Id": school_b})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    # Generate against school A's session from school B.
    r = client.post(
        f"{BASE}/generate",
        json={"academic_session_id": world["session_id"], "include_rooms": False},
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404


# --- Permission gates ------------------------------------------------------------------
def _role_membership(db: Session, school_id: uuid.UUID, role_code: str, email: str) -> tuple[str, uuid.UUID]:
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == role_code))
    assert role is not None
    user = User(email=email, password_hash=hash_password("Str0ng!Pass"), full_name="Restricted")
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_timetable_requires_permission(client, db: Session):
    register_school(client, name="Perm School", email="pt@test.edu")
    school_id = active_school_id(client)
    world = _create_world(client, school_id)

    # Accountant has no timetable permissions at all.
    token, _ = _role_membership(db, school_id, "accountant", "acct@test.edu")
    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/time-slots", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    # Teacher can view but not manage (generate).
    token, _ = _role_membership(db, school_id, "teacher", "tt@test.edu")
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/time-slots", headers=headers)
    assert r.status_code == 200

    r = client.post(
        f"{BASE}/generate",
        json={"academic_session_id": world["session_id"], "include_rooms": False},
        headers=headers,
    )
    assert r.status_code == 403
