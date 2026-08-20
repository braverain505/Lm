"""Attendance tests: student/staff marking (upsert), list filters, summaries,
tenant isolation, and the permission gate — through the real HTTP API.
"""
import calendar
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/attendance"
PEOPLE = "/api/students"
STAFF = "/api/staff"
ACAD = "/api/academics"


def _school(client, name: str, email: str) -> str:
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _create_student(client, school_id: str, admission_no: str) -> dict:
    r = client.post(
        PEOPLE,
        json={
            "admission_no": admission_no,
            "first_name": "Ada",
            "last_name": "Obi",
            "gender": "female",
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_staff(client, school_id: str, staff_no: str, full_name: str = "Mr T") -> dict:
    r = client.post(
        STAFF,
        json={"staff_no": staff_no, "full_name": full_name, "membership_type": "teaching"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _mark_student(client, school_id: str, student_id: str, day: str, status: str) -> dict:
    r = client.post(
        f"{BASE}/mark/student",
        json={"student_id": student_id, "attendance_date": day, "status": status},
        headers={"X-School-Id": school_id},
    )
    return r


def _mark_staff(client, school_id: str, staff_id: str, day: str, status: str) -> dict:
    r = client.post(
        f"{BASE}/mark/staff",
        json={"staff_id": staff_id, "attendance_date": day, "status": status},
        headers={"X-School-Id": school_id},
    )
    return r


def _in_month_dates() -> tuple[str, str]:
    """Two distinct dates within the current month (for summary counting)."""
    today = date.today()
    first = date(today.year, today.month, 1)
    last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    return first.isoformat(), last.isoformat()


def _create_current_session(client, school_id: str) -> str:
    r = client.post(
        f"{ACAD}/sessions",
        json={"name": "2026/2027", "is_current": True},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- Marking ------------------------------------------------------------------------
def test_mark_student_attendance_upserts_on_same_day(client):
    school_id = _school(client, "Att School", "att@test.edu")
    student = _create_student(client, school_id, "A-001")
    day = date.today().isoformat()

    r = _mark_student(client, school_id, student["id"], day, "present")
    assert r.status_code == 201, r.text
    record_id = r.json()["id"]

    # Same student + date → upsert, not a new row.
    r = _mark_student(client, school_id, student["id"], day, "late")
    assert r.status_code == 201, r.text
    assert r.json()["id"] == record_id
    assert r.json()["status"] == "late"

    r = client.get(f"{BASE}/student/{student['id']}", headers={"X-School-Id": school_id})
    records = r.json()
    assert len(records) == 1
    assert records[0]["status"] == "late"


def test_mark_staff_attendance_and_summary(client):
    school_id = _school(client, "Staff Att", "sat@test.edu")
    staff = _create_staff(client, school_id, "S-001")
    d1, d2 = _in_month_dates()

    r = _mark_staff(client, school_id, staff["id"], d1, "present")
    assert r.status_code == 201, r.text
    r = _mark_staff(client, school_id, staff["id"], d2, "late")
    assert r.status_code == 201, r.text

    r = client.get(f"{BASE}/staff/{staff['id']}", headers={"X-School-Id": school_id})
    assert len(r.json()) == 2

    r = client.get(f"{BASE}/staff/summary/{staff['id']}", headers={"X-School-Id": school_id})
    summary = r.json()
    assert summary["total_days"] == 2
    assert summary["present_days"] == 1
    assert summary["late_days"] == 1
    assert summary["percentage"] == 50.0


def test_attendance_date_range_and_status_filters(client):
    school_id = _school(client, "Filter Att", "fat@test.edu")
    student = _create_student(client, school_id, "F-001")
    d1, d2 = _in_month_dates()
    _mark_student(client, school_id, student["id"], d1, "present")
    _mark_student(client, school_id, student["id"], d2, "absent")

    r = client.get(f"{BASE}/student/{student['id']}?status=absent", headers={"X-School-Id": school_id})
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "absent"

    r = client.get(
        f"{BASE}/student/{student['id']}?start_date={d1}&end_date={d1}",
        headers={"X-School-Id": school_id},
    )
    assert len(r.json()) == 1


def test_invalid_attendance_status_rejected(client):
    school_id = _school(client, "Bad Att", "bat@test.edu")
    student = _create_student(client, school_id, "BA-001")
    r = _mark_student(client, school_id, student["id"], date.today().isoformat(), "probably")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


# --- Summary -------------------------------------------------------------------------
def test_student_attendance_summary_counts_month(client):
    school_id = _school(client, "Sum School", "sum@test.edu")
    student = _create_student(client, school_id, "S-001")
    session_id = _create_current_session(client, school_id)
    d1, d2 = _in_month_dates()

    _mark_student(client, school_id, student["id"], d1, "present")
    _mark_student(client, school_id, student["id"], d2, "absent")

    r = client.get(f"{BASE}/summary/{student['id']}", headers={"X-School-Id": school_id})
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["academic_session_id"] == session_id
    assert summary["total_days"] == 2
    assert summary["present_days"] == 1
    assert summary["absent_days"] == 1
    assert summary["percentage"] == 50.0


def test_student_summary_requires_current_session(client):
    school_id = _school(client, "NoSum School", "nos@test.edu")
    student = _create_student(client, school_id, "NS-001")
    r = client.get(f"{BASE}/summary/{student['id']}", headers={"X-School-Id": school_id})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Tenant isolation ----------------------------------------------------------------
def test_cross_school_attendance_isolation(client):
    school_a = _school(client, "Isol A", "aa@test.edu")
    student = _create_student(client, school_a, "IA-001")
    staff = _create_staff(client, school_a, "IS-001")
    _mark_student(client, school_a, student["id"], date.today().isoformat(), "present")

    register_school(client, name="Isol B", email="ab@test.edu")
    school_b = active_school_id(client)

    # Can't read school A's student from school B.
    r = client.get(f"{BASE}/student/{student['id']}", headers={"X-School-Id": school_b})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    # Can't mark school A's student/staff from school B.
    r = _mark_student(client, school_b, student["id"], date.today().isoformat(), "present")
    assert r.status_code == 404
    r = _mark_staff(client, school_b, staff["id"], date.today().isoformat(), "present")
    assert r.status_code == 404

    # School B's own list is empty.
    r = client.get(f"{BASE}/student/{student['id']}", headers={"X-School-Id": school_a})
    assert len(r.json()) == 1


# --- Permission gate -----------------------------------------------------------------
def _accountant_membership(db: Session, school_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    """Accountant role: no attendance permissions."""
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == "accountant"))
    assert role is not None
    user = User(
        email="accountant@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Mrs A",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_attendance_requires_permission(client, db: Session):
    register_school(client, name="Perm School", email="pa@test.edu")
    school_id = active_school_id(client)
    student = _create_student(client, school_id, "P-001")
    token, _ = _accountant_membership(db, school_id)

    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/student/{student['id']}", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(
        f"{BASE}/mark/student",
        json={"student_id": student["id"], "attendance_date": "2026-08-13", "status": "present"},
        headers=headers,
    )
    assert r.status_code == 403
