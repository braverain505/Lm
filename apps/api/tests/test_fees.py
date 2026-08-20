"""Fees/billing tests: fee structures, invoices, payments, balances, tenant
isolation, and the permission gate — exercised through the real HTTP API.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import Role, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/fees"
PEOPLE = "/api/students"


def _as_accountant(client, db: Session, school_id: str) -> None:
    """Create an accountant user for the school and log the client in as them.

    Finance is the Accountant's domain — the school-admin (super_admin) role no
    longer carries any fee permissions, so fee tests run as an accountant.
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
    can create students (the accountant cannot). Call ``_as_accountant`` before
    any fee operations."""
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _create_student(client, school_id: str, admission_no: str) -> dict:
    r = client.post(
        PEOPLE,
        json={
            "admission_no": admission_no,
            "first_name": "Ade",
            "last_name": "Bello",
            "gender": "male",
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_structure(
    client, school_id: str, name: str, amount: float = 1000.0, **extra
) -> dict:
    payload = {
        "name": name,
        "fee_type": "tuition",
        "amount": amount,
        "currency": "NGN",
        "billing_frequency": "term",
        **extra,
    }
    r = client.post(
        f"{BASE}/structures", json=payload, headers={"X-School-Id": school_id}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_invoice(client, school_id: str, student_id: str, structure_id: str) -> dict:
    r = client.post(
        f"{BASE}/invoices",
        json={
            "student_id": student_id,
            "fee_structure_id": structure_id,
            "batch_number": f"B-{uuid.uuid4().hex[:6].upper()}",
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _record_payment(client, school_id: str, invoice_id: str, amount: float) -> dict:
    r = client.post(
        f"{BASE}/payments",
        json={"invoice_id": invoice_id, "amount": amount, "payment_method": "cash"},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- Fee structures -------------------------------------------------------------
def test_create_list_and_filter_fee_structures(client, db):
    school_id = _school(client, "Fees School", "fs@test.edu")
    _as_accountant(client, db, school_id)
    _create_structure(client, school_id, "Tuition", amount=5000.0, is_mandatory=True)
    _create_structure(client, school_id, "Exam Fee", amount=2000.0, fee_type="examination")

    r = client.get(f"{BASE}/structures", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert {s["name"] for s in body} == {"Exam Fee", "Tuition"}
    assert all(s["is_active"] is True for s in body)

    # Filter by fee type.
    r = client.get(f"{BASE}/structures?fee_type=examination", headers={"X-School-Id": school_id})
    assert [s["name"] for s in r.json()] == ["Exam Fee"]

    # Inactive structures are hidden by default.
    r = client.get(f"{BASE}/structures?active_only=false", headers={"X-School-Id": school_id})
    assert len(r.json()) == 2


def test_duplicate_fee_structure_name_rejected(client, db):
    school_id = _school(client, "Dup School", "dup@test.edu")
    _as_accountant(client, db, school_id)
    _create_structure(client, school_id, "Tuition")
    r = client.post(
        f"{BASE}/structures",
        json={"name": "Tuition", "fee_type": "tuition", "amount": 5000.0},
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"
    assert "already exists" in r.json()["error"]["message"]


def test_update_and_toggle_fee_structure(client, db):
    school_id = _school(client, "Toggle School", "tg@test.edu")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, "Boarding", amount=8000.0)

    r = client.put(
        f"{BASE}/structures/{structure['id']}",
        json={
            "name": "Boarding 2026",
            "fee_type": "boarding",
            "amount": 8500.0,
            "billing_frequency": "term",
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Boarding 2026"
    assert r.json()["amount"] == 8500.0

    r = client.post(
        f"{BASE}/structures/{structure['id']}/toggle-status",
        headers={"X-School-Id": school_id},
    )
    assert r.json()["is_active"] is False

    r = client.get(f"{BASE}/structures", headers={"X-School-Id": school_id})
    assert r.json() == []


def test_specific_class_fee_requires_owned_arm(client, db):
    school_id = _school(client, "Scope School", "sc@test.edu")
    _as_accountant(client, db, school_id)
    r = client.post(
        f"{BASE}/structures",
        json={
            "name": "Lab Fee",
            "fee_type": "activity",
            "amount": 1500.0,
            "applicable_to": "specific_class",
            "class_arm_id": str(uuid.uuid4()),
        },
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Invoices + payments ----------------------------------------------------------
def test_invoice_lifecycle_full_and_partial_payment(client, db):
    school_id = _school(client, "Invoice School", "inv@test.edu")
    student = _create_student(client, school_id, "INV-001")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, "Tuition", amount=1000.0)

    invoice = _create_invoice(client, school_id, student["id"], structure["id"])
    assert invoice["total_amount"] == 1000.0
    assert invoice["subtotal"] == 1000.0
    assert invoice["status"] == "draft"
    assert invoice["reference_number"].startswith("INV-")

    # Partial payment → invoice becomes partial.
    _record_payment(client, school_id, invoice["id"], 400.0)
    r = client.get(f"{BASE}/invoices/{invoice['id']}", headers={"X-School-Id": school_id})
    assert r.json()["status"] == "partial"

    # Remaining payment → paid.
    _record_payment(client, school_id, invoice["id"], 600.0)
    r = client.get(f"{BASE}/invoices/{invoice['id']}", headers={"X-School-Id": school_id})
    paid = r.json()
    assert paid["status"] == "paid"
    assert paid["paid_date"] is not None


def test_list_invoices_filters_by_student_and_status(client, db):
    school_id = _school(client, "List School", "lst@test.edu")
    s1 = _create_student(client, school_id, "L-001")
    s2 = _create_student(client, school_id, "L-002")
    _as_accountant(client, db, school_id)
    fs = _create_structure(client, school_id, "Tuition", amount=1000.0)
    _create_invoice(client, school_id, s1["id"], fs["id"])
    _create_invoice(client, school_id, s2["id"], fs["id"])

    r = client.get(
        f"{BASE}/invoices?student_id={s1['id']}", headers={"X-School-Id": school_id}
    )
    assert len(r.json()) == 1
    assert r.json()[0]["student_id"] == s1["id"]

    r = client.get(f"{BASE}/invoices?status=draft", headers={"X-School-Id": school_id})
    assert len(r.json()) == 2


def test_invoice_for_cross_school_student_rejected(client, db):
    school_a = _school(client, "A School", "a@test.edu")
    _create_student(client, school_a, "A-001")
    register_school(client, name="B School", email="b@test.edu")
    school_b = active_school_id(client)
    _as_accountant(client, db, school_b)
    fs = _create_structure(client, school_b, "Tuition", amount=1000.0)

    # Student belongs to school A, invoice created in school B's context.
    r = client.post(
        f"{BASE}/invoices",
        json={
            "student_id": str(uuid.uuid4()),
            "fee_structure_id": fs["id"],
            "batch_number": "B-X",
        },
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


def test_balance_tracks_owed_paid_and_unpaid(client, db):
    school_id = _school(client, "Bal School", "bal@test.edu")
    student = _create_student(client, school_id, "B-001")
    _as_accountant(client, db, school_id)
    fs = _create_structure(client, school_id, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_id, student["id"], fs["id"])

    r = client.get(f"{BASE}/balances/{student['id']}", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    balance = r.json()
    assert balance["total_owed"] == 1000.0
    assert balance["total_paid"] == 0.0
    assert balance["total_unpaid"] == 1000.0
    assert balance["current_invoice_total"] == 1000.0

    _record_payment(client, school_id, invoice["id"], 400.0)
    r = client.get(f"{BASE}/balances/{student['id']}", headers={"X-School-Id": school_id})
    assert r.json()["total_paid"] == 400.0
    assert r.json()["total_unpaid"] == 600.0

    _record_payment(client, school_id, invoice["id"], 600.0)
    r = client.get(f"{BASE}/balances/{student['id']}", headers={"X-School-Id": school_id})
    assert r.json()["total_owed"] == 0.0
    assert r.json()["total_unpaid"] == 0.0
    assert r.json()["current_invoice_total"] == 0.0


# --- Tenant isolation --------------------------------------------------------------
def test_cross_school_read_isolation(client, db):
    school_a = _school(client, "Isol A", "ia@test.edu")
    student = _create_student(client, school_a, "I-001")
    _as_accountant(client, db, school_a)
    fs = _create_structure(client, school_a, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_a, student["id"], fs["id"])
    payment = _record_payment(client, school_a, invoice["id"], 1000.0)

    register_school(client, name="Isol B", email="ib@test.edu")
    school_b = active_school_id(client)
    _as_accountant(client, db, school_b)

    for path in (
        f"{BASE}/invoices/{invoice['id']}",
        f"{BASE}/payments/{payment['id']}",
    ):
        r = client.get(path, headers={"X-School-Id": school_b})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    # Toggling school A's structure from school B's context is also a 404.
    r = client.post(
        f"{BASE}/structures/{fs['id']}/toggle-status",
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404

    r = client.get(f"{BASE}/structures", headers={"X-School-Id": school_b})
    assert r.json() == []


def test_balance_cross_school_isolation(client, db):
    """The fee-balance endpoint must not leak another tenant's student data."""
    school_a = _school(client, "Bal A", "ba@test.edu")
    student = _create_student(client, school_a, "B-001")
    _as_accountant(client, db, school_a)
    fs = _create_structure(client, school_a, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_a, student["id"], fs["id"])
    _record_payment(client, school_a, invoice["id"], 1000.0)

    # School A can read its own student's balance.
    r = client.get(
        f"{BASE}/balances/{student['id']}", headers={"X-School-Id": school_a}
    )
    assert r.status_code == 200
    assert r.json()["total_paid"] == 1000.0

    register_school(client, name="Bal B", email="bb@test.edu")
    school_b = active_school_id(client)
    _as_accountant(client, db, school_b)

    # School B must not be able to resolve school A's student.
    r = client.get(
        f"{BASE}/balances/{student['id']}", headers={"X-School-Id": school_b}
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    # Unknown student id from the calling school is also a 404 (neutral).
    r = client.get(
        f"{BASE}/balances/{uuid.uuid4()}", headers={"X-School-Id": school_b}
    )
    assert r.status_code == 404


# --- Permission gate ----------------------------------------------------------------
def _teacher_membership(db: Session, school_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    role = db.scalar(select(Role).where(Role.school_id == school_id, Role.code == "teacher"))
    assert role is not None
    user = User(
        email="teacher@test.edu",
        password_hash=hash_password("Str0ng!Pass"),
        full_name="Miss T",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()
    return create_access_token(str(user.id)), user.id


def test_fees_require_permission(client, db: Session):
    register_school(client, name="Perm School", email="pf@test.edu")
    school_id = active_school_id(client)
    token, _ = _teacher_membership(db, school_id)  # teacher has no fees perms

    client.cookies.clear()
    headers = {"X-School-Id": school_id, "Authorization": f"Bearer {token}"}

    r = client.get(f"{BASE}/structures", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(
        f"{BASE}/structures",
        json={"name": "Tuition", "fee_type": "tuition", "amount": 1000.0},
        headers=headers,
    )
    assert r.status_code == 403


# --- Accounting is Accountant-only -------------------------------------------------
def test_school_admin_cannot_access_fees(client, db: Session):
    """The general school admin must not see or touch any accounting."""
    register_school(client, name="Admin Lock School", email="al@test.edu")
    school_id = active_school_id(client)  # still logged in as super_admin

    for method, path in (
        ("GET", f"{BASE}/structures"),
        ("POST", f"{BASE}/structures"),
        ("GET", f"{BASE}/status"),
        ("GET", f"{BASE}/payments"),
    ):
        r = client.request(
            method, path,
            headers={"X-School-Id": school_id},
            json={"name": "X", "fee_type": "tuition", "amount": 1.0} if method == "POST" else None,
        )
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"


def test_accountant_can_use_fees(client, db: Session):
    """The accountant role carries every finance permission."""
    school_id = _school(client, "Acc School", "ac@test.edu")
    student = _create_student(client, school_id, "ACC-001")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_id, student["id"], structure["id"])
    payment = _record_payment(client, school_id, invoice["id"], 1000.0)
    assert payment["receipt_number"].startswith("RCP-")


# --- Payment receipts --------------------------------------------------------------
def test_payment_receipt_endpoint(client, db: Session):
    school_id = _school(client, "Receipt School", "rc@test.edu")
    student = _create_student(client, school_id, "RC-001")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_id, student["id"], structure["id"])
    _record_payment(client, school_id, invoice["id"], 400.0)
    payment = _record_payment(client, school_id, invoice["id"], 600.0)

    r = client.get(
        f"{BASE}/payments/{payment['id']}/receipt",
        headers={"X-School-Id": school_id},
    )
    assert r.status_code == 200, r.text
    receipt = r.json()
    assert receipt["receipt_number"] == payment["receipt_number"]
    assert receipt["amount_paid"] == 600.0
    assert receipt["paid_total"] == 1000.0
    assert receipt["balance_due"] == 0.0
    assert receipt["invoice_status"] == "paid"
    assert receipt["invoice_reference"] == invoice["reference_number"]
    assert receipt["student"]["admission_no"] == "RC-001"
    assert receipt["student"]["full_name"].startswith("Ade")
    assert receipt["school"]["name"] == "Receipt School"
    assert len(receipt["invoice_payments"]) == 2
    assert all(p["receipt_number"] for p in receipt["invoice_payments"])


def test_payment_receipt_cross_school_isolated(client, db: Session):
    school_a = _school(client, "Rcpt A", "ra@test.edu")
    student = _create_student(client, school_a, "RA-001")
    _as_accountant(client, db, school_a)
    fs = _create_structure(client, school_a, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_a, student["id"], fs["id"])
    payment = _record_payment(client, school_a, invoice["id"], 500.0)

    register_school(client, name="Rcpt B", email="rb@test.edu")
    school_b = active_school_id(client)
    _as_accountant(client, db, school_b)

    r = client.get(
        f"{BASE}/payments/{payment['id']}/receipt",
        headers={"X-School-Id": school_b},
    )
    assert r.status_code == 404


# --- Paid / not-paid tracking ------------------------------------------------------
def test_payment_status_tracks_paid_and_unpaid(client, db: Session):
    school_id = _school(client, "Track School", "tr@test.edu")
    s1 = _create_student(client, school_id, "TR-001")
    s2 = _create_student(client, school_id, "TR-002")
    _as_accountant(client, db, school_id)
    fs = _create_structure(client, school_id, "Tuition", amount=1000.0)

    # Only s1 is invoiced; s2 has no invoice at all.
    inv1 = _create_invoice(client, school_id, s1["id"], fs["id"])
    _record_payment(client, school_id, inv1["id"], 600.0)

    r = client.get(f"{BASE}/status", headers={"X-School-Id": school_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["paid"] == 0
    assert body["summary"]["unpaid"] == 1
    assert body["summary"]["partial"] == 1

    by_no = {row["admission_no"]: row for row in body["students"]}
    assert by_no["TR-001"]["status"] == "partial"
    assert by_no["TR-001"]["paid"] == 600.0
    assert by_no["TR-001"]["balance"] == 400.0
    assert by_no["TR-002"]["status"] == "unpaid"
    assert by_no["TR-002"]["balance"] == 0.0

    # Paying the balance clears s1.
    _record_payment(client, school_id, inv1["id"], 400.0)
    r = client.get(f"{BASE}/status", headers={"X-School-Id": school_id})
    body = r.json()
    assert body["summary"]["paid"] == 1
    assert body["summary"]["partial"] == 0
    by_no = {row["admission_no"]: row for row in body["students"]}
    assert by_no["TR-001"]["status"] == "paid"
    assert by_no["TR-001"]["balance"] == 0.0


def test_list_payments_endpoint(client, db: Session):
    school_id = _school(client, "List Pay School", "lp@test.edu")
    student = _create_student(client, school_id, "LP-001")
    _as_accountant(client, db, school_id)
    fs = _create_structure(client, school_id, "Tuition", amount=1000.0)
    invoice = _create_invoice(client, school_id, student["id"], fs["id"])
    p1 = _record_payment(client, school_id, invoice["id"], 400.0)
    p2 = _record_payment(client, school_id, invoice["id"], 600.0)

    r = client.get(f"{BASE}/payments", headers={"X-School-Id": school_id})
    assert r.status_code == 200
    assert len(r.json()) == 2

    r = client.get(
        f"{BASE}/payments?student_id={student['id']}",
        headers={"X-School-Id": school_id},
    )
    assert len(r.json()) == 2

    r = client.get(
        f"{BASE}/payments?invoice_id={invoice['id']}",
        headers={"X-School-Id": school_id},
    )
    assert {p["id"] for p in r.json()} == {p1["id"], p2["id"]}
