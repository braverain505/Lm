"""Accounting-desk tests: the ledger the school Accountant alone keeps.

Exercised through the real HTTP API: expenses and petty cash (draft → approved →
paid), cash accounts and balances, the cashbook read model and its bank
reconciliation, discounts, credit notes, refunds, debtors aging, the reports and
the accountant-login provisioning.

Two rules get their own coverage because they are the point of the desk:

* the ledger is gated on the caller's *school-scoped role code* as well as the
  ``accounting.*`` permissions, so a bursar handed the very same permissions —
  or a school admin — still cannot post to the books;
* everything is tenant-scoped, so another school's accountant gets a neutral
  404 rather than someone else's books.
"""
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Permission, Role, RolePermission, SchoolMembership, User
from .conftest import active_school_id, register_school

BASE = "/api/accounting"
FEES = "/api/fees"
PEOPLE = "/api/students"


# --- Helpers ------------------------------------------------------------------
def _sign_in_as(
    client,
    db: Session,
    school_id: str,
    role_code: str,
    *,
    permissions: tuple[str, ...] = (),
) -> str:
    """Create a user holding ``role_code`` in this school and log the client in
    as them. ``permissions`` grants the role extra permission codes, which the
    role-gate tests use to prove that a permission set alone is not enough."""
    role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == role_code)
    )
    assert role is not None, f"{role_code} template role missing"
    if permissions:
        for code in permissions:
            permission = db.scalar(select(Permission).where(Permission.code == code))
            assert permission is not None, f"{code} missing from the permission catalog"
            granted = db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permission.id,
                )
            )
            if granted is None:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.flush()

    email = f"{role_code}-{uuid.uuid4().hex[:8]}@test.edu"
    user = User(
        email=email,
        password_hash=hash_password("Str0ng!Pass"),
        full_name=f"{role_code.title()} User",
    )
    db.add(user)
    db.flush()
    db.add(SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id))
    db.flush()

    r = client.post(
        "/api/auth/login", json={"email": email, "password": "Str0ng!Pass"}
    )
    assert r.status_code == 200, r.text
    return email


def _as_accountant(client, db: Session, school_id: str) -> str:
    """Log the client in as this school's Accountant — the ledger's only key."""
    return _sign_in_as(client, db, school_id, "accountant")


def _school(client, name: str, email: str) -> str:
    """Register a school; the client stays signed in as its admin (who can
    create students, and provision staff logins)."""
    register_school(client, name=name, email=email)
    return active_school_id(client)


def _headers(school_id: str) -> dict:
    return {"X-School-Id": school_id}


def _create_student(client, school_id: str, admission_no: str) -> dict:
    r = client.post(
        PEOPLE,
        json={
            "admission_no": admission_no,
            "first_name": "Ade",
            "last_name": "Bello",
            "gender": "male",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_structure(client, school_id: str, amount: float = 1000.0) -> dict:
    r = client.post(
        f"{FEES}/structures",
        json={
            "name": f"Tuition {uuid.uuid4().hex[:4]}",
            "fee_type": "tuition",
            "amount": amount,
            "currency": "NGN",
            "billing_frequency": "term",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_invoice(client, school_id: str, student_id: str, structure_id: str) -> dict:
    r = client.post(
        f"{FEES}/invoices",
        json={
            "student_id": student_id,
            "fee_structure_id": structure_id,
            "batch_number": f"B-{uuid.uuid4().hex[:6].upper()}",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _collect(client, school_id: str, invoice_id: str, amount: float) -> dict:
    """Record a fee payment — the income side of the cashbook."""
    r = client.post(
        f"{FEES}/payments",
        json={"invoice_id": invoice_id, "amount": amount, "payment_method": "cash"},
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _expense(client, school_id: str, amount: float = 100.0, **extra) -> dict:
    payload = {
        "description": "Generator diesel",
        "amount": amount,
        "expense_date": date.today().isoformat(),
        "payment_method": "cash",
        **extra,
    }
    r = client.post(f"{BASE}/expenses", json=payload, headers=_headers(school_id))
    assert r.status_code == 201, r.text
    return r.json()


def _book_fees(client, school_id: str, student_id: str) -> dict:
    """Raise a structure + invoice for an existing student. Fees are the
    Accountant's to create, so call this after ``_as_accountant``."""
    structure = _create_structure(client, school_id)
    invoice = _create_invoice(client, school_id, student_id, structure["id"])
    return {"structure": structure, "invoice": invoice}


# --- The desk is the Accountant's alone ----------------------------------------
def test_school_admin_cannot_touch_the_ledger(client, db: Session):
    """The general school admin holds no finance code at all, so every ledger
    route refuses them before the service is reached."""
    register_school(client, name="Admin Lock School", email="al@test.edu")
    school_id = active_school_id(client)

    for method, path in (
        ("GET", f"{BASE}/summary"),
        ("GET", f"{BASE}/expenses"),
        ("GET", f"{BASE}/cashbook"),
        ("GET", f"{BASE}/debtors"),
        ("GET", f"{BASE}/discounts"),
        ("GET", f"{BASE}/refunds"),
        ("GET", f"{BASE}/reports/income-expenditure"),
        ("GET", f"{BASE}/reports/collection"),
        ("GET", f"{BASE}/reports/cash-position"),
    ):
        r = client.request(method, path, headers=_headers(school_id))
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
        assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"

    r = client.post(
        f"{BASE}/expenses",
        json={
            "description": "Fees for nothing",
            "amount": 10.0,
            "expense_date": date.today().isoformat(),
            "payment_method": "cash",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 403


def test_bursar_with_every_accounting_permission_is_still_refused(client, db: Session):
    """The gate is the *role*, not the permission set: hand the bursar all five
    accounting codes and the books still stay shut."""
    school_id = _school(client, "Role Gate School", "rg@test.edu")
    _sign_in_as(
        client,
        db,
        school_id,
        "bursar",
        permissions=(
            "accounting.view",
            "accounting.expenses",
            "accounting.amend",
            "accounting.reconcile",
            "accounting.reports",
        ),
    )

    r = client.get(f"{BASE}/summary", headers=_headers(school_id))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ERR_PERMISSION_DENIED"
    assert "Accountant" in r.json()["error"]["message"]

    r = client.get(f"{BASE}/cashbook", headers=_headers(school_id))
    assert r.status_code == 403

    r = client.post(
        f"{BASE}/expenses",
        json={
            "description": "Petty cash",
            "amount": 5.0,
            "expense_date": date.today().isoformat(),
            "payment_method": "cash",
            "mark_paid": True,
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 403


def test_accountant_summary_starts_clean(client, db: Session):
    """A brand-new school's books are empty, not invented."""
    school_id = _school(client, "Clean Books School", "cb@test.edu")
    _as_accountant(client, db, school_id)

    r = client.get(f"{BASE}/summary", headers=_headers(school_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outstanding_fees"] == 0.0
    assert body["collected_this_term"] == 0.0
    assert body["expenses_this_term"] == 0.0
    assert body["surplus_this_term"] == 0.0
    assert body["pending_expense_approvals"] == 0
    assert body["pending_refunds"] == 0
    assert body["open_credit_notes"] == 0
    assert body["debtors_over_90_days"] == 0.0
    assert body["currency"]


# --- Expenses & petty cash ------------------------------------------------------
def test_expense_needs_approval_before_it_can_be_paid(client, db: Session):
    school_id = _school(client, "Approval School", "ap@test.edu")
    _as_accountant(client, db, school_id)

    expense = _expense(client, school_id, 250.0, requires_approval=True, payee="NNPC")
    assert expense["status"] == "draft"
    assert expense["requires_approval"] is True
    assert expense["voucher_number"].startswith("PV-")
    assert expense["paid_at"] is None

    # A draft that needs approval cannot jump straight to paid.
    r = client.post(f"{BASE}/expenses/{expense['id']}/pay", headers=_headers(school_id))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"

    r = client.post(
        f"{BASE}/expenses/{expense['id']}/approve", headers=_headers(school_id)
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["approved_at"] is not None

    # Approving twice is a conflict, not a silent no-op.
    r = client.post(
        f"{BASE}/expenses/{expense['id']}/approve", headers=_headers(school_id)
    )
    assert r.status_code == 409

    r = client.post(f"{BASE}/expenses/{expense['id']}/pay", headers=_headers(school_id))
    assert r.status_code == 200
    paid = r.json()
    assert paid["status"] == "paid"
    assert paid["paid_at"] is not None

    # A paid voucher is part of the books: it can no longer be edited or dropped.
    r = client.put(
        f"{BASE}/expenses/{expense['id']}",
        json={
            "description": "Trying to rewrite history",
            "amount": 1.0,
            "expense_date": date.today().isoformat(),
            "payment_method": "cash",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 409
    r = client.delete(f"{BASE}/expenses/{expense['id']}", headers=_headers(school_id))
    assert r.status_code == 409

    # The outflow is visible in the cashbook.
    r = client.get(f"{BASE}/cashbook", headers=_headers(school_id))
    assert r.status_code == 200
    cashbook = r.json()
    assert cashbook["total_out"] == 250.0
    assert cashbook["net"] == -250.0
    assert any(
        line["source_type"] == "expense" and line["source_id"] == expense["id"]
        for line in cashbook["lines"]
    )


def test_petty_cash_posts_straight_to_paid(client, db: Session):
    """Money that has already left the box needs no second step."""
    school_id = _school(client, "Petty Cash School", "pc@test.edu")
    _as_accountant(client, db, school_id)

    expense = _expense(client, school_id, 40.0, mark_paid=True)
    assert expense["status"] == "paid"
    assert expense["paid_at"] is not None

    r = client.get(f"{BASE}/expenses?status=paid", headers=_headers(school_id))
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["id"] == expense["id"]

    r = client.get(f"{BASE}/expenses?status=draft", headers=_headers(school_id))
    assert r.json()["total"] == 0


def test_rejected_expense_goes_back_to_draft_when_edited(client, db: Session):
    school_id = _school(client, "Reject School", "rj@test.edu")
    _as_accountant(client, db, school_id)

    expense = _expense(client, school_id, 90.0, requires_approval=True)
    r = client.post(
        f"{BASE}/expenses/{expense['id']}/reject",
        json={"reason": "No receipt attached"},
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejected_reason"] == "No receipt attached"

    # A rejected expense cannot be paid...
    r = client.post(f"{BASE}/expenses/{expense['id']}/pay", headers=_headers(school_id))
    assert r.status_code == 409

    # ...but editing it resubmits it, clearing the reason.
    r = client.put(
        f"{BASE}/expenses/{expense['id']}",
        json={
            "description": "Generator diesel (receipt attached)",
            "amount": 95.0,
            "expense_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
            "requires_approval": True,
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "draft"
    assert r.json()["rejected_reason"] is None
    assert r.json()["amount"] == 95.0


def test_expense_categories_are_scoped_and_linked(client, db: Session):
    school_id = _school(client, "Category School", "ct@test.edu")
    _as_accountant(client, db, school_id)

    r = client.post(
        f"{BASE}/categories",
        json={"name": "Utilities"},
        headers=_headers(school_id),
    )
    assert r.status_code == 201
    category = r.json()
    assert category["is_active"] is True

    r = client.put(
        f"{BASE}/categories/{category['id']}",
        json={"name": "Utilities & Power", "is_active": True},
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Utilities & Power"

    expense = _expense(client, school_id, 60.0, category_id=category["id"])
    assert expense["category_name"] == "Utilities & Power"

    r = client.get(f"{BASE}/categories?active_only=true", headers=_headers(school_id))
    assert [c["name"] for c in r.json()] == ["Utilities & Power"]

    # A category from another school is never accepted.
    r = client.post(
        f"{BASE}/expenses",
        json={
            "description": "Foreign category",
            "amount": 10.0,
            "expense_date": date.today().isoformat(),
            "payment_method": "cash",
            "category_id": str(uuid.uuid4()),
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Cash accounts, cashbook & reconciliation -----------------------------------
def test_cash_account_balance_follows_the_money(client, db: Session):
    school_id = _school(client, "Account School", "ca@test.edu")
    _as_accountant(client, db, school_id)

    r = client.post(
        f"{BASE}/accounts",
        json={
            "name": "Main Bank",
            "kind": "bank",
            "bank_name": "Zenith",
            "opening_balance": 5000.0,
            "is_default": True,
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    account = r.json()
    assert account["balance"] == 5000.0

    _expense(client, school_id, 1200.0, cash_account_id=account["id"], mark_paid=True)

    r = client.get(f"{BASE}/accounts", headers=_headers(school_id))
    assert r.status_code == 200
    row = next(a for a in r.json() if a["id"] == account["id"])
    assert row["balance"] == 3800.0

    # Closing an account keeps it (and its history) but hides it from the
    # active-only listing.
    r = client.put(
        f"{BASE}/accounts/{account['id']}",
        json={"name": "Main Bank", "kind": "bank", "opening_balance": 5000.0, "is_active": False},
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    r = client.get(f"{BASE}/accounts?active_only=true", headers=_headers(school_id))
    assert all(a["id"] != account["id"] for a in r.json())


def test_cashbook_reconciles_against_the_bank(client, db: Session):
    school_id = _school(client, "Reconcile School", "rc@test.edu")
    student = _create_student(client, school_id, "RC-001")
    _as_accountant(client, db, school_id)
    booking = _book_fees(client, school_id, student["id"])
    payment = _collect(client, school_id, booking["invoice"]["id"], 400.0)

    r = client.get(f"{BASE}/cashbook", headers=_headers(school_id))
    cashbook = r.json()
    assert cashbook["total_in"] == 400.0
    assert cashbook["unreconciled_count"] == 1
    assert cashbook["reconciled_count"] == 0
    assert cashbook["opening"] == 0.0
    assert cashbook["closing"] == 400.0

    # Tick it off against a bank statement line.
    r = client.post(
        f"{BASE}/reconcile",
        json={
            "source_type": "payment",
            "source_id": payment["id"],
            "reconciled": True,
            "bank_reference": "ZEN-0001",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 200, r.text
    assert r.json()["reconciled"] is True
    assert r.json()["bank_reference"] == "ZEN-0001"
    assert r.json()["reconciled_at"] is not None

    r = client.get(f"{BASE}/cashbook?only_unreconciled=true", headers=_headers(school_id))
    assert r.json()["unreconciled_count"] == 0
    assert r.json()["lines"] == []

    # Un-ticking it puts it back in the queue.
    r = client.post(
        f"{BASE}/reconcile",
        json={"source_type": "payment", "source_id": payment["id"], "reconciled": False},
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["reconciled"] is False
    assert r.json()["reconciled_at"] is None

    # An unknown entry type is a payload error; someone else's entry is a 404.
    r = client.post(
        f"{BASE}/reconcile",
        json={
            "source_type": "invoice",
            "source_id": booking["invoice"]["id"],
            "reconciled": True,
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 422
    r = client.post(
        f"{BASE}/reconcile",
        json={"source_type": "payment", "source_id": str(uuid.uuid4()), "reconciled": True},
        headers=_headers(school_id),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"


# --- Discounts, credit notes & refunds ------------------------------------------
def test_discount_accepts_exactly_one_of_percent_or_amount(client, db: Session):
    school_id = _school(client, "Discount School", "dc@test.edu")
    student = _create_student(client, school_id, "DSC-001")
    _as_accountant(client, db, school_id)

    both = client.post(
        f"{BASE}/discounts",
        json={"student_id": student["id"], "name": "Two ways", "percent": 10.0, "amount": 500.0},
        headers=_headers(school_id),
    )
    assert both.status_code == 422
    neither = client.post(
        f"{BASE}/discounts",
        json={"student_id": student["id"], "name": "No way"},
        headers=_headers(school_id),
    )
    assert neither.status_code == 422
    assert neither.json()["error"]["code"] == "ERR_VALIDATION"

    r = client.post(
        f"{BASE}/discounts",
        json={"student_id": student["id"], "name": "Sibling waiver", "kind": "sibling", "percent": 15.0},
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    discount = r.json()
    assert discount["kind"] == "sibling"
    assert discount["percent"] == 15.0
    assert discount["amount"] is None
    assert discount["admission_no"] == "DSC-001"

    r = client.get(
        f"{BASE}/discounts?student_id={student['id']}&active_only=true",
        headers=_headers(school_id),
    )
    assert [d["id"] for d in r.json()] == [discount["id"]]

    r = client.put(
        f"{BASE}/discounts/{discount['id']}",
        json={"student_id": student["id"], "name": "Full scholarship", "kind": "scholarship", "percent": 100.0},
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Full scholarship"

    r = client.delete(f"{BASE}/discounts/{discount['id']}", headers=_headers(school_id))
    assert r.status_code == 204
    r = client.get(f"{BASE}/discounts", headers=_headers(school_id))
    assert r.json() == []


def test_credit_note_applies_once_and_reduces_the_invoice(client, db: Session):
    school_id = _school(client, "Credit Note School", "cn@test.edu")
    student = _create_student(client, school_id, "CN-001")
    other = _create_student(client, school_id, "CN-OTHER")
    _as_accountant(client, db, school_id)
    booking = _book_fees(client, school_id, student["id"])
    invoice = booking["invoice"]

    r = client.post(
        f"{BASE}/credit-notes",
        json={"student_id": student["id"], "amount": 300.0, "reason": "Overpaid"},
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["status"] == "open"
    assert note["note_number"].startswith("CN-")

    r = client.post(
        f"{BASE}/credit-notes/{note['id']}/apply",
        json={"invoice_id": invoice["id"]},
        headers=_headers(school_id),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "applied"
    assert r.json()["applied_invoice_id"] == invoice["id"]

    r = client.get(f"{FEES}/invoices/{invoice['id']}", headers=_headers(school_id))
    assert r.json()["total_amount"] == 700.0

    # One application only, and an applied note can never be voided.
    r = client.post(
        f"{BASE}/credit-notes/{note['id']}/apply",
        json={"invoice_id": invoice["id"]},
        headers=_headers(school_id),
    )
    assert r.status_code == 409
    r = client.post(f"{BASE}/credit-notes/{note['id']}/void", headers=_headers(school_id))
    assert r.status_code == 409

    r = client.post(
        f"{BASE}/credit-notes",
        json={"student_id": student["id"], "amount": 50.0},
        headers=_headers(school_id),
    )
    spare = r.json()
    r = client.post(f"{BASE}/credit-notes/{spare['id']}/void", headers=_headers(school_id))
    assert r.status_code == 200
    assert r.json()["status"] == "void"

    # A note for one student can never be applied to another student's invoice.
    other_invoice = _create_invoice(
        client, school_id, other["id"], booking["structure"]["id"]
    )
    r = client.post(
        f"{BASE}/credit-notes",
        json={"student_id": student["id"], "amount": 10.0},
        headers=_headers(school_id),
    )
    stray = r.json()
    r = client.post(
        f"{BASE}/credit-notes/{stray['id']}/apply",
        json={"invoice_id": other_invoice["id"]},
        headers=_headers(school_id),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ERR_VALIDATION"


def test_refund_ceiling_lifecycle_and_rejection(client, db: Session):
    school_id = _school(client, "Refund School", "rf@test.edu")
    student = _create_student(client, school_id, "RFD-001")
    _as_accountant(client, db, school_id)
    structure = _create_structure(client, school_id, amount=1000.0)
    invoice = _create_invoice(client, school_id, student["id"], structure["id"])
    payment = _collect(client, school_id, invoice["id"], 400.0)

    # Never refund more than the student paid and kept.
    r = client.post(
        f"{BASE}/refunds",
        json={"student_id": student["id"], "amount": 500.0, "method": "bank_transfer"},
        headers=_headers(school_id),
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "ERR_VALIDATION"
    assert body["error"]["details"]["refundable"] == 400.0

    r = client.post(
        f"{BASE}/refunds",
        json={
            "student_id": student["id"],
            "amount": 100.0,
            "method": "bank_transfer",
            "payment_id": payment["id"],
            "reason": "Duplicate payment",
        },
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    refund = r.json()
    assert refund["status"] == "pending"
    assert refund["refund_date"] is None

    r = client.post(f"{BASE}/refunds/{refund['id']}/approve", headers=_headers(school_id))
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    r = client.post(f"{BASE}/refunds/{refund['id']}/approve", headers=_headers(school_id))
    assert r.status_code == 409

    r = client.post(f"{BASE}/refunds/{refund['id']}/pay", headers=_headers(school_id))
    assert r.status_code == 200
    paid = r.json()
    assert paid["status"] == "paid"
    assert paid["refund_date"]
    assert paid["reconciled"] is False

    # A paid refund is done: it cannot be rejected afterwards.
    r = client.post(
        f"{BASE}/refunds/{refund['id']}/reject",
        json={"reason": "Changed my mind"},
        headers=_headers(school_id),
    )
    assert r.status_code == 409

    # A pending refund can be rejected, and a rejected one cannot be paid.
    r = client.post(
        f"{BASE}/refunds",
        json={"student_id": student["id"], "amount": 50.0, "method": "cash"},
        headers=_headers(school_id),
    )
    second = r.json()
    assert second["status"] == "pending"
    r = client.post(
        f"{BASE}/refunds/{second['id']}/reject",
        json={"reason": "Not a duplicate"},
        headers=_headers(school_id),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    r = client.post(f"{BASE}/refunds/{second['id']}/pay", headers=_headers(school_id))
    assert r.status_code == 409


# --- Debtors, reports & the dashboard -------------------------------------------
def test_debtors_aging_reports_and_dashboard_agree(client, db: Session):
    """One set of books, three views: the aging list, the reports and the
    accountant's headline numbers must all tell the same story."""
    school_id = _school(client, "Reports School", "rp@test.edu")
    student = _create_student(client, school_id, "RPT-001")
    _as_accountant(client, db, school_id)

    structure = _create_structure(client, school_id, amount=1000.0)
    invoice = _create_invoice(client, school_id, student["id"], structure["id"])
    _collect(client, school_id, invoice["id"], 250.0)
    expenses = client.post(
        f"{BASE}/categories", json={"name": "Repairs"}, headers=_headers(school_id)
    ).json()
    _expense(
        client,
        school_id,
        100.0,
        category_id=expenses["id"],
        mark_paid=True,
    )

    # Debtors: invoiced 1000, paid 250, so 750 still owed.
    r = client.get(f"{BASE}/debtors", headers=_headers(school_id))
    assert r.status_code == 200, r.text
    debtors = r.json()
    assert debtors["student_count"] == 1
    assert debtors["total_outstanding"] == 750.0
    row = debtors["rows"][0]
    assert row["admission_no"] == "RPT-001"
    assert row["invoiced"] == 1000.0
    assert row["paid"] == 250.0
    assert row["balance"] == 750.0
    assert row["invoice_count"] == 1
    assert sum(debtors["buckets"].values()) == 750.0

    # Income & expenditure over an explicit window: 250 in, 100 spent.
    today = date.today().isoformat()
    r = client.get(
        f"{BASE}/reports/income-expenditure?date_from={today}&date_to={today}",
        headers=_headers(school_id),
    )
    assert r.status_code == 200, r.text
    statement = r.json()
    assert statement["fee_collections"] == 250.0
    assert statement["other_income"] == 0.0
    assert statement["total_income"] == 250.0
    assert statement["total_expenditure"] == 100.0
    assert statement["surplus"] == 150.0
    assert statement["surplus_label"] == "surplus"
    assert statement["expenses_by_category"] == [
        {"category": "Repairs", "amount": 100.0}
    ]

    # Collection report: how much of what was billed actually came in.
    r = client.get(f"{BASE}/reports/collection", headers=_headers(school_id))
    assert r.status_code == 200, r.text
    collection = r.json()
    assert collection["total_invoiced"] == 1000.0
    assert collection["total_collected"] == 250.0
    assert collection["total_outstanding"] == 750.0
    assert collection["collection_rate"] == 25.0

    # Cash position: 250 collected − 100 paid out.
    r = client.get(f"{BASE}/reports/cash-position", headers=_headers(school_id))
    assert r.status_code == 200, r.text
    position = r.json()
    assert position["total_balance"] == 150.0
    # Both movements are still unmatched, so the unreconciled figure sums the
    # money in *and* the money out (250 + 100).
    assert position["total_unreconciled"] == 350.0
    assert sum(row["unreconciled_amount"] for row in position["rows"]) == 350.0

    # Dashboard headline numbers line up with the views above.
    r = client.get(f"{BASE}/summary", headers=_headers(school_id))
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["outstanding_fees"] == 750.0
    assert summary["collected_this_term"] == 250.0
    assert summary["expenses_this_term"] == 100.0
    assert summary["surplus_this_term"] == 150.0
    assert summary["cash_position"] == 150.0
    assert summary["pending_expense_approvals"] == 0
    assert summary["pending_refunds"] == 0
    assert summary["open_credit_notes"] == 0
    # The collection and the paid voucher are both still un-ticked.
    assert summary["unreconciled_cashbook_entries"] == 2


def test_dashboard_counts_what_is_still_in_the_queue(client, db: Session):
    school_id = _school(client, "Queue School", "qu@test.edu")
    student = _create_student(client, school_id, "Q-001")
    _as_accountant(client, db, school_id)

    _expense(client, school_id, 30.0, requires_approval=True)
    _expense(client, school_id, 20.0, mark_paid=True)
    r = client.post(
        f"{BASE}/refunds",
        json={"student_id": student["id"], "amount": 1.0, "method": "cash"},
        headers=_headers(school_id),
    )
    # A refund cannot exceed what the student paid, so nothing is added.
    assert r.status_code == 422

    r = client.post(
        f"{BASE}/credit-notes",
        json={"student_id": student["id"], "amount": 25.0},
        headers=_headers(school_id),
    )
    assert r.status_code == 201

    r = client.get(f"{BASE}/summary", headers=_headers(school_id))
    summary = r.json()
    assert summary["pending_expense_approvals"] == 1
    assert summary["open_credit_notes"] == 1
    assert summary["expenses_this_term"] == 20.0


# --- Provisioning an accountant login -------------------------------------------
def test_admin_provisions_an_accountant_who_can_keep_the_books(client, db: Session):
    """Handing out the credentials is the office's job (``users.manage``);
    keeping the books is the Accountant's."""
    school_id = _school(client, "Provision School", "pv@test.edu")
    email = f"bursar-{uuid.uuid4().hex[:8]}@test.edu"

    r = client.post(
        f"{BASE}/accountants",
        json={"full_name": "Ada Bursar", "email": email, "password": "Str0ng!Pass"},
        headers=_headers(school_id),
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"] == email
    assert created["role_code"] == "accountant"
    assert created["has_login"] is True
    assert created["staff_id"]

    # The roster itself is the desk's own view, not the admin's.
    r = client.get(f"{BASE}/accountants", headers=_headers(school_id))
    assert r.status_code == 403

    # The new accountant signs in with their own email and password.
    r = client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Pass"})
    assert r.status_code == 200, r.text
    r = client.get(f"{BASE}/summary", headers=_headers(school_id))
    assert r.status_code == 200
    r = client.get(f"{BASE}/accountants", headers=_headers(school_id))
    assert r.status_code == 200
    assert [a["email"] for a in r.json()] == [email]

    # A login can only belong to one person.
    r = client.post(
        f"{BASE}/accountants",
        json={"full_name": "Copy Cat", "email": email, "password": "Str0ng!Pass"},
        headers={"X-School-Id": school_id, "Authorization": ""},
    )
    # The client is signed in as the accountant now, who cannot provision.
    assert r.status_code in (403, 409)

    register_school(client, name="Second Office School", email="so@test.edu")
    other_school = active_school_id(client)
    r = client.post(
        f"{BASE}/accountants",
        json={"full_name": "Copy Cat", "email": email, "password": "Str0ng!Pass"},
        headers=_headers(other_school),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ERR_CONFLICT"


# --- Tenant isolation -----------------------------------------------------------
def test_another_schools_books_are_invisible(client, db: Session):
    school_a = _school(client, "Books A", "a@test.edu")
    student = _create_student(client, school_a, "ISO-001")
    _as_accountant(client, db, school_a)
    expense = _expense(client, school_a, 75.0, requires_approval=True)
    r = client.post(
        f"{BASE}/discounts",
        json={"student_id": student["id"], "name": "Waiver", "percent": 5.0},
        headers=_headers(school_a),
    )
    assert r.status_code == 201
    discount = r.json()

    # School B's accountant owns their own books only.
    school_b = _school(client, "Books B", "b@test.edu")
    _as_accountant(client, db, school_b)

    r = client.get(f"{BASE}/expenses/{expense['id']}", headers=_headers(school_b))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ERR_NOT_FOUND"

    r = client.post(
        f"{BASE}/expenses/{expense['id']}/approve", headers=_headers(school_b)
    )
    assert r.status_code == 404

    r = client.post(
        f"{BASE}/reconcile",
        json={"source_type": "expense", "source_id": expense["id"], "reconciled": True},
        headers=_headers(school_b),
    )
    assert r.status_code == 404

    r = client.delete(f"{BASE}/discounts/{discount['id']}", headers=_headers(school_b))
    assert r.status_code == 404

    # ...and their listings start empty rather than leaking the other school.
    r = client.get(f"{BASE}/expenses", headers=_headers(school_b))
    assert r.json()["total"] == 0
    r = client.get(f"{BASE}/debtors", headers=_headers(school_b))
    assert r.json()["student_count"] == 0
