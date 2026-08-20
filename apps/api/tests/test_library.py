"""Library tests: books, borrowings, returns, tenant isolation, and the
permission gate — exercised through the real HTTP API.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/library"
STUDENTS = "/api/students"
STAFF = "/api/staff"


def _school(client, name: str, email: str) -> str:
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _create_book(client, school_id: str, title: str, copies: int = 2, **extra) -> dict:
    payload = {"title": title, "author": "Author A", "total_copies": copies, **extra}
    r = client.post(
        f"{BASE}/books", json=payload, headers={"X-School-Id": school_id}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_student(client, school_id: str, admission_no: str) -> dict:
    r = client.post(
        STUDENTS,
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


def _create_staff(client, school_id: str, staff_no: str, full_name: str) -> dict:
    r = client.post(
        STAFF,
        json={"staff_no": staff_no, "full_name": full_name, "membership_type": "teaching"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _check_out(
    client, school_id: str, book_id: str, *, student_id: str = None, staff_id: str = None,
    due="2026-09-01",
) -> dict:
    payload = {"book_id": book_id, "borrower_type": "student" if student_id else "staff", "due_on": due}
    if student_id:
        payload["student_id"] = student_id
    else:
        payload["staff_id"] = staff_id
    r = client.post(
        f"{BASE}/borrowings", json=payload, headers={"X-School-Id": school_id}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _return(client, school_id: str, borrowing_id: str) -> dict:
    r = client.post(
        f"{BASE}/borrowings/{borrowing_id}/return",
        json={},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


# --- Books ---------------------------------------------------------------------
def test_create_list_and_get_books(client):
    school_id = _school(client, "Lib School", "lib@test.edu")
    _create_book(client, school_id, "Physics 101", copies=5)
    _create_book(client, school_id, "Chemistry 101", copies=3)

    r = client.get(f"{BASE}/books", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    assert {b["title"] for b in r.json()} == {"Physics 101", "Chemistry 101"}
    assert all(b["available_copies"] == b["total_copies"] for b in r.json())


def test_duplicate_isbn_rejected(client):
    school_id = _school(client, "ISBN School", "isbn@test.edu")
    _create_book(client, school_id, "Book One", isbn="978-1-111")
    r = client.post(
        f"{BASE}/books",
        json={"title": "Book Two", "isbn": "978-1-111"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


def test_update_book_keeps_available_count(client):
    school_id = _school(client, "UpdBook School", "updbook@test.edu")
    book = _create_book(client, school_id, "Novel", copies=3)
    student = _create_student(client, school_id, "LB-001")
    _check_out(client, school_id, book["id"], student_id=student["id"])
    # 1 of 3 on loan → 2 available.

    r = client.put(
        f"{BASE}/books/{book['id']}",
        json={"title": "Novel 2026", "author": "Author A", "total_copies": 5},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["total_copies"] == 5
    assert r.json()["available_copies"] == 4


def test_reducing_copies_below_on_loan_rejected(client):
    school_id = _school(client, "Reduce School", "reduce@test.edu")
    book = _create_book(client, school_id, "Textbook", copies=3)
    student = _create_student(client, school_id, "LB-002")
    _check_out(client, school_id, book["id"], student_id=student["id"])
    _check_out(client, school_id, book["id"], student_id=student["id"])
    # 2 on loan, 1 available → cannot drop below 2 copies.

    r = client.put(
        f"{BASE}/books/{book['id']}",
        json={"title": "Textbook", "author": "Author A", "total_copies": 1},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert "on loan" in r.json()["error"]["message"]


# --- Borrowings -----------------------------------------------------------------
def test_checkout_decrements_available_and_blocks_zero_copies(client):
    school_id = _school(client, "Checkout School", "co@test.edu")
    book = _create_book(client, school_id, "Novel", copies=1)
    student = _create_student(client, school_id, "LB-003")

    borrowing = _check_out(client, school_id, book["id"], student_id=student["id"])
    assert borrowing["status"] == "borrowed"
    assert borrowing["book_title"] == "Novel"
    assert borrowing["borrower_name"] == "Ada Obi"

    r = client.get(f"{BASE}/books/{book['id']}", headers={"X-School-Id": school_id})
    assert r.json()["available_copies"] == 0

    r = client.post(
        f"{BASE}/borrowings",
        json={"book_id": book["id"], "borrower_type": "student", "student_id": student["id"], "due_on": "2026-09-01"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert "available" in r.json()["error"]["message"]


def test_return_increments_available_and_marks_status(client):
    school_id = _school(client, "Return School", "ret@test.edu")
    book = _create_book(client, school_id, "Novel", copies=1)
    staff = _create_staff(client, school_id, "LB-ST1", "Tunde Musa")
    borrowing = _check_out(client, school_id, book["id"], staff_id=staff["id"])

    result = _return(client, school_id, borrowing["id"])
    assert result["status"] == "returned"
    assert result["returned_on"] is not None

    r = client.get(f"{BASE}/books/{book['id']}", headers={"X-School-Id": school_id})
    assert r.json()["available_copies"] == 1

    r = client.post(
        f"{BASE}/borrowings/{borrowing['id']}/return",
        json={},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 409


def test_borrowing_foreign_borrower_rejected(client):
    school_id = _school(client, "Foreign School", "foreign@test.edu")
    book = _create_book(client, school_id, "Novel", copies=1)
    r = client.post(
        f"{BASE}/borrowings",
        json={"book_id": book["id"], "borrower_type": "student", "student_id": str(uuid.uuid4()), "due_on": "2026-09-01"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_list_borrowings_filters_overdue(client):
    school_id = _school(client, "Overdue School", "overdue@test.edu")
    book = _create_book(client, school_id, "Novel", copies=2)
    student = _create_student(client, school_id, "LB-004")
    _check_out(client, school_id, book["id"], student_id=student["id"], due="2020-01-01")

    r = client.get(f"{BASE}/borrowings?overdue=true", headers={"X-School-Id": school_id})
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "borrowed"

    r = client.get(f"{BASE}/borrowings?status=returned", headers={"X-School-Id": school_id})
    assert r.json() == []


# --- Tenant isolation -----------------------------------------------------------
def test_cross_school_library_isolation(client):
    school_a = _school(client, "IsolLib A", "ilib@test.edu")
    book = _create_book(client, school_a, "Novel", copies=1)
    student = _create_student(client, school_a, "LB-005")
    borrowing = _check_out(client, school_a, book["id"], student_id=student["id"])

    register_school(client, name="IsolLib B", email="ilibb@test.edu")
    school_b = active_school_id(client)

    r = client.get(f"{BASE}/books/{book['id']}", headers={"X-School-Id": school_b})
    assert r.status_code == 404
    r = client.get(f"{BASE}/books", headers={"X-School-Id": school_b})
    assert r.json() == []

    r = client.post(
        f"{BASE}/borrowings/{borrowing['id']}/return",
        json={},
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404


# --- Permission gate ------------------------------------------------------------
def _teacher_membership(db: Session, school_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == "teacher"))
    assert role is not None
    user = User(
        email="lib-teacher@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Miss L",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_library_requires_permission(client, db: Session):
    register_school(client, name="LibPerm School", email="libperm@test.edu")
    school_id = active_school_id(client)
    token, _ = _teacher_membership(db, school_id)  # teacher has no library perms

    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/books", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(
        f"{BASE}/books",
        json={"title": "Hack", "total_copies": 1},
        headers=headers,
    )
    assert r.status_code == 403

    r = client.post(
        f"{BASE}/borrowings",
        json={"book_id": str(uuid.uuid4()), "borrower_type": "student", "due_on": "2026-09-01"},
        headers=headers,
    )
    assert r.status_code == 403
