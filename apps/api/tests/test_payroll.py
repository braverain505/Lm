"""Payroll tests: salary structures, staff assignments, pay runs, payslips,
tenant isolation, and the permission gate — exercised through the HTTP API.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/payroll"
STAFF = "/api/staff"


def _as_accountant(client, db: Session, school_id: str) -> None:
    """Create an accountant user for the school and log the client in as them.

    Payroll is finance — only the Accountant role carries payroll permissions,
    so these tests run as an accountant after creating staff as the admin.
    """
    role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == "accountant")
    )
    assert role is not None, "accountant template role missing"
    user = User(
        email=f"acc-{uuid.uuid4().hex[:8]}@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Accountant",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    r = client.post(
        "/api/auth/login", json={"email": user.email, "password": "Str0ng!Pass"}
    )
    assert r.status_code == 200, r.text


def _school(client, name: str, email: str) -> str:
    """Register a school; the client stays logged in as the school admin, who
    can create staff (the accountant cannot). Call ``_as_accountant`` before
    any payroll operations."""
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _create_staff(client, school_id: str, staff_no: str, full_name: str) -> dict:
    r = client.post(
        STAFF,
        json={"staff_no": staff_no, "full_name": full_name, "membership_type": "teaching"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_structure(
    client, school_id: str, name: str, basic: float = 5000.0, tax: float = 10.0
) -> dict:
    r = client.post(
        f"{BASE}/structures",
        json={"name": name, "basic_salary": basic, "tax_percent": tax},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _assign_salary(client, school_id: str, staff_id: str, structure_id: str) -> dict:
    r = client.post(
        f"{BASE}/assignments",
        json={"staff_id": staff_id, "structure_id": structure_id, "effective_from": "2026-01-01"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_run(client, school_id: str, month: str) -> dict:
    r = client.post(
        f"{BASE}/runs",
        json={"month": month},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- Salary structures --------------------------------------------------------
def test_create_list_and_filter_structures(client, db):
    school_id = _school(client, "Pay School", "pay@test.edu")
    _as_accountant(client, db, school_id)
    _create_structure(client, school_id, "Teacher", basic=60000.0, tax=10.0)
    _create_structure(client, school_id, "Admin", basic=40000.0, tax=5.0)

    r = client.get(f"{BASE}/structures", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert {s["name"] for s in body} == {"Teacher", "Admin"}
    assert all(s["is_active"] is True for s in body)

    # Inactive structures are hidden by default.
    _create_structure(client, school_id, "Off Role", basic=10000.0)
    r = client.post(
        f"{BASE}/structures/{body[0]['id']}/toggle-status",
        headers={"X-School-Id": school_id},
    )
    assert r.json()["is_active"] is False
    r = client.get(f"{BASE}/structures", headers={"X-School-Id": school_id})
    assert len(r.json()) == 2

    r = client.get(f"{BASE}/structures?active_only=false", headers={"X-School-Id": school_id})
    assert len(r.json()) == 3


def test_duplicate_structure_name_rejected(client, db):
    school_id = _school(client, "DupPay School", "duppay@test.edu")
    _as_accountant(client, db, school_id)
    _create_structure(client, school_id, "Teacher")
    r = client.post(
        f"{BASE}/structures",
        json={"name": "Teacher", "basic_salary": 50000.0},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"
    assert "already exists" in r.json()["error"]["message"]


def test_update_structure(client, db):
    school_id = _school(client, "UpdPay School", "updpay@test.edu")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, "Teacher", basic=60000.0, tax=10.0)

    r = client.put(
        f"{BASE}/structures/{structure['id']}",
        json={"name": "Senior Teacher", "basic_salary": 70000.0, "tax_percent": 12.0},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Senior Teacher"
    assert r.json()["basic_salary"] == 70000.0
    assert r.json()["tax_percent"] == 12.0


# --- Staff salary assignments -------------------------------------------------
def test_assign_and_reassign_staff_salary(client, db):
    school_id = _school(client, "Assign School", "assign@test.edu")
    staff = _create_staff(client, school_id, "PAY-001", "Tunde Musa")
    _as_accountant(client, db, school_id)
    s1 = _create_structure(client, school_id, "Teacher", basic=60000.0)
    s2 = _create_structure(client, school_id, "Senior Teacher", basic=80000.0)

    assignment = _assign_salary(client, school_id, staff["id"], s1["id"])
    assert assignment["staff_name"] == "Tunde Musa"
    assert assignment["structure_name"] == "Teacher"

    # Re-assigning to a new structure updates the same row (still one assignment).
    r = client.post(
        f"{BASE}/assignments",
        json={"staff_id": staff["id"], "structure_id": s2["id"]},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201
    assert r.json()["id"] == assignment["id"]
    assert r.json()["structure_name"] == "Senior Teacher"

    r = client.get(f"{BASE}/assignments", headers={"X-School-Id": school_id})
    assert len(r.json()) == 1


def test_assign_salary_to_cross_school_staff_rejected(client, db):
    school_a = _school(client, "CrossA School", "crossa@test.edu")
    _create_staff(client, school_a, "CA-001", "Alice K")
    register_school(client, name="CrossB School", email="crossb@test.edu")
    school_b = active_school_id(client)
    _as_accountant(client, db, school_b)
    structure = _create_structure(client, school_b, "Teacher", basic=60000.0)

    r = client.post(
        f"{BASE}/assignments",
        json={"staff_id": str(uuid.uuid4()), "structure_id": structure["id"]},
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Pay runs + payslips --------------------------------------------------------
def test_pay_run_computes_gross_tax_net(client, db):
    school_id = _school(client, "Run School", "run@test.edu")
    s1 = _create_staff(client, school_id, "RUN-001", "Ade K")
    s2 = _create_staff(client, school_id, "RUN-002", "Bola J")
    _as_accountant(client, db, school_id)
    t = _create_structure(client, school_id, "Teacher", basic=60000.0, tax=10.0)
    admin = _create_structure(client, school_id, "Admin", basic=40000.0, tax=5.0)
    _assign_salary(client, school_id, s1["id"], t["id"])
    _assign_salary(client, school_id, s2["id"], admin["id"])

    run = _create_run(client, school_id, "2026-01")
    assert run["status"] == "draft"
    assert run["month"] == "2026-01"

    # Teacher: 60000 gross, 6000 tax, 54000 net. Admin: 40000, 2000, 38000.
    assert run["total_gross"] == 100000.0
    assert run["total_tax"] == 8000.0
    assert run["total_net"] == 92000.0

    payslips = {p["staff_name"]: p for p in run["payslips"]}
    assert payslips["Ade K"]["gross"] == 60000.0
    assert payslips["Ade K"]["tax"] == 6000.0
    assert payslips["Ade K"]["net"] == 54000.0
    assert payslips["Bola J"]["gross"] == 40000.0
    assert payslips["Bola J"]["net"] == 38000.0


def test_pay_run_duplicate_month_rejected(client, db):
    school_id = _school(client, "DupRun School", "duprun@test.edu")
    _as_accountant(client, db, school_id)
    _create_run(client, school_id, "2026-02")
    r = client.post(
        f"{BASE}/runs",
        json={"month": "2026-02"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"


def test_mark_pay_run_paid(client, db):
    school_id = _school(client, "Paid School", "paid@test.edu")
    staff = _create_staff(client, school_id, "PAID-001", "Kay E")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, "Teacher", basic=50000.0)
    _assign_salary(client, school_id, staff["id"], structure["id"])
    run = _create_run(client, school_id, "2026-03")

    r = client.post(
        f"{BASE}/runs/{run['id']}/mark-paid",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "paid"
    assert r.json()["paid_at"] is not None

    r = client.post(
        f"{BASE}/runs/{run['id']}/mark-paid",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 409


def test_list_runs_ordered_by_month_desc(client, db):
    school_id = _school(client, "ListRun School", "listrun@test.edu")
    _as_accountant(client, db, school_id)
    _create_run(client, school_id, "2026-01")
    _create_run(client, school_id, "2026-02")

    r = client.get(f"{BASE}/runs", headers={"X-School-Id": school_id})
    months = [x["month"] for x in r.json()]
    assert months == ["2026-02", "2026-01"]


# --- Tenant isolation ------------------------------------------------------------
def test_cross_school_payroll_isolation(client, db):
    school_a = _school(client, "IsolPay A", "ipay@test.edu")
    staff = _create_staff(client, school_a, "IPA-001", "Sam U")
    _as_accountant(client, db, school_a)
    structure = _create_structure(client, school_a, "Teacher", basic=60000.0)
    _assign_salary(client, school_a, staff["id"], structure["id"])
    run = _create_run(client, school_a, "2026-01")

    register_school(client, name="IsolPay B", email="ipayb@test.edu")
    school_b = active_school_id(client)
    _as_accountant(client, db, school_b)

    r = client.get(f"{BASE}/runs/{run['id']}", headers={"X-School-Id": school_b})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    r = client.post(
        f"{BASE}/structures/{structure['id']}/toggle-status",
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404

    r = client.get(f"{BASE}/structures", headers={"X-School-Id": school_b})
    assert r.json() == []
    r = client.get(f"{BASE}/runs", headers={"X-School-Id": school_b})
    assert r.json() == []

    r = client.post(
        f"{BASE}/runs/{run['id']}/mark-paid",
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404


# --- Permission gate ---------------------------------------------------------------
def _teacher_membership(db: Session, school_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == "teacher"))
    assert role is not None
    user = User(
        email="pay-teacher@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Miss P",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_payroll_requires_permission(client, db: Session):
    register_school(client, name="PayPerm School", email="payperm@test.edu")
    school_id = active_school_id(client)
    token, _ = _teacher_membership(db, school_id)  # teacher has no payroll perms

    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/structures", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(
        f"{BASE}/structures",
        json={"name": "Teacher", "basic_salary": 60000.0},
        headers=headers,
    )
    assert r.status_code == 403

    r = client.post(
        f"{BASE}/runs",
        json={"month": "2026-01"},
        headers=headers,
    )
    assert r.status_code == 403
