"""Accounting service layer: the ledger the school accountant keeps.

Design note — one source of truth per naira
-------------------------------------------
There is deliberately **no separate cash-ledger table**. The cashbook is a *read
model* computed from documents that already exist (fee payments in; paid
expenses and refunds out), and reconciliation state lives on those documents. A
parallel ledger would be a second place money is written down and would drift
from billing the first time a payment was edited.

Everything here is tenant-scoped by ``school_id`` and every lookup that resolves
an id re-checks ownership, so a cross-school id is a 404 rather than a leak.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    AcademicSession,
    CashAccount,
    ClassArm,
    CreditNote,
    Expense,
    ExpenseCategory,
    FeeStructure,
    Invoice,
    Payment,
    Refund,
    School,
    Student,
    StudentDiscount,
    StudentEnrollment,
    Term,
)
from ..schemas.accounting import (
    CashAccountIn,
    CreditNoteIn,
    DiscountIn,
    ExpenseCategoryIn,
    ExpenseIn,
    RefundIn,
)

_SENTINEL_UNPAID = ("draft", "sent", "partial")

# Aging bucket edges, in days past due.
_AGING_BUCKETS = (30, 60, 90)


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _f(value) -> float:
    return round(float(value or 0), 2)


def _today() -> date:
    return datetime.now(timezone.utc).date()


# ──────────────────────────────────────────────────────────────────────
# Cash accounts
# ──────────────────────────────────────────────────────────────────────


def _default_account(db: Session, school_id: uuid.UUID) -> CashAccount:
    """The account new money posts to, created on first use.

    Recording a fee payment must never fail because the school has not set up
    its bank accounts yet, so the first payment provisions a plain cash account.
    """
    account = db.scalar(
        select(CashAccount)
        .where(CashAccount.school_id == school_id, CashAccount.is_default.is_(True))
        .order_by(CashAccount.created_at)
    )
    if account is not None:
        return account
    account = db.scalar(
        select(CashAccount)
        .where(CashAccount.school_id == school_id)
        .order_by(CashAccount.created_at)
    )
    if account is not None:
        account.is_default = True
        db.flush()
        return account

    account = CashAccount(
        school_id=school_id,
        name="Cash",
        kind="cash",
        currency=_school_currency(db, school_id),
        opening_balance=Decimal("0"),
        is_active=True,
        is_default=True,
    )
    db.add(account)
    db.flush()
    return account


def _school_currency(db: Session, school_id: uuid.UUID) -> str:
    school = db.get(School, school_id)
    return (school.currency if school and school.currency else "NGN") or "NGN"


def get_cash_account(db: Session, account_id: uuid.UUID, school_id: uuid.UUID) -> CashAccount:
    account = db.get(CashAccount, account_id)
    if account is None or account.school_id != school_id:
        raise NotFoundError("Cash account not found")
    return account


def _account_movement(db: Session, school_id: uuid.UUID, account_id: uuid.UUID) -> tuple[float, float]:
    """(money in, money out) for one account, from the real documents."""
    in_total = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.school_id == school_id, Payment.cash_account_id == account_id
        )
    ) or 0
    out_expenses = db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.school_id == school_id,
            Expense.cash_account_id == account_id,
            Expense.status == "paid",
        )
    ) or 0
    out_refunds = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.school_id == school_id,
            Refund.cash_account_id == account_id,
            Refund.status == "paid",
        )
    ) or 0
    return _f(in_total), _f(_d(out_expenses) + _d(out_refunds))


def list_cash_accounts(
    db: Session, school_id: uuid.UUID, *, active_only: bool = False
) -> list[dict]:
    stmt = select(CashAccount).where(CashAccount.school_id == school_id)
    if active_only:
        stmt = stmt.where(CashAccount.is_active.is_(True))
    stmt = stmt.order_by(CashAccount.is_default.desc(), CashAccount.name)
    rows = []
    for account in db.scalars(stmt):
        money_in, money_out = _account_movement(db, school_id, account.id)
        rows.append(
            {
                "id": account.id,
                "name": account.name,
                "kind": account.kind,
                "bank_name": account.bank_name,
                "account_number": account.account_number,
                "currency": account.currency,
                "opening_balance": _f(account.opening_balance),
                "is_active": account.is_active,
                "is_default": account.is_default,
                "balance": _f(_d(account.opening_balance) + _d(money_in) - _d(money_out)),
            }
        )
    return rows


def create_cash_account(
    db: Session, school_id: uuid.UUID, *, data: CashAccountIn
) -> CashAccount:
    existing = db.scalar(
        select(CashAccount).where(
            CashAccount.school_id == school_id, CashAccount.name == data.name
        )
    )
    if existing:
        raise ValidationError("A cash account with this name already exists")

    account = CashAccount(
        school_id=school_id,
        name=data.name,
        kind=data.kind,
        bank_name=data.bank_name,
        account_number=data.account_number,
        currency=data.currency,
        opening_balance=_d(data.opening_balance),
        is_active=data.is_active,
        is_default=False,
    )
    db.add(account)
    db.flush()
    if data.is_default:
        _make_default(db, school_id, account)
    return account


def update_cash_account(
    db: Session, account_id: uuid.UUID, school_id: uuid.UUID, *, data: CashAccountIn
) -> CashAccount:
    account = get_cash_account(db, account_id, school_id)
    other = db.scalar(
        select(CashAccount).where(
            CashAccount.school_id == school_id,
            CashAccount.name == data.name,
            CashAccount.id != account_id,
        )
    )
    if other:
        raise ValidationError("Another cash account with this name already exists")

    account.name = data.name
    account.kind = data.kind
    account.bank_name = data.bank_name
    account.account_number = data.account_number
    account.currency = data.currency
    account.opening_balance = _d(data.opening_balance)
    account.is_active = data.is_active
    db.flush()
    if data.is_default:
        _make_default(db, school_id, account)
    return account


def _make_default(db: Session, school_id: uuid.UUID, account: CashAccount) -> None:
    for other in db.scalars(
        select(CashAccount).where(
            CashAccount.school_id == school_id, CashAccount.is_default.is_(True)
        )
    ):
        other.is_default = False
    account.is_default = True
    db.flush()


# ──────────────────────────────────────────────────────────────────────
# Expense categories
# ──────────────────────────────────────────────────────────────────────


def list_expense_categories(
    db: Session, school_id: uuid.UUID, *, active_only: bool = False
) -> list[ExpenseCategory]:
    stmt = select(ExpenseCategory).where(ExpenseCategory.school_id == school_id)
    if active_only:
        stmt = stmt.where(ExpenseCategory.is_active.is_(True))
    return list(db.scalars(stmt.order_by(ExpenseCategory.name)))


def get_expense_category(
    db: Session, category_id: uuid.UUID, school_id: uuid.UUID
) -> ExpenseCategory:
    category = db.get(ExpenseCategory, category_id)
    if category is None or category.school_id != school_id:
        raise NotFoundError("Expense category not found")
    return category


def create_expense_category(
    db: Session, school_id: uuid.UUID, *, data: ExpenseCategoryIn
) -> ExpenseCategory:
    existing = db.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.school_id == school_id, ExpenseCategory.name == data.name
        )
    )
    if existing:
        raise ValidationError("An expense category with this name already exists")
    category = ExpenseCategory(
        school_id=school_id,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(category)
    db.flush()
    return category


def update_expense_category(
    db: Session, category_id: uuid.UUID, school_id: uuid.UUID, *, data: ExpenseCategoryIn
) -> ExpenseCategory:
    category = get_expense_category(db, category_id, school_id)
    other = db.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.school_id == school_id,
            ExpenseCategory.name == data.name,
            ExpenseCategory.id != category_id,
        )
    )
    if other:
        raise ValidationError("Another expense category with this name already exists")
    category.name = data.name
    category.description = data.description
    category.is_active = data.is_active
    db.flush()
    return category


# ──────────────────────────────────────────────────────────────────────
# Expenses & petty cash
# ──────────────────────────────────────────────────────────────────────


def default_account(db: Session, school_id: uuid.UUID) -> CashAccount:
    """The cash/bank account new money posts to (provisioned on first use).

    Public entry point for the fees module, so collecting a payment can always
    attribute itself to an account.
    """
    return _default_account(db, school_id)


def expense_to_dict(db: Session, expense: Expense) -> dict:
    category = db.get(ExpenseCategory, expense.category_id) if expense.category_id else None
    account = db.get(CashAccount, expense.cash_account_id) if expense.cash_account_id else None
    return {
        "id": expense.id,
        "voucher_number": expense.voucher_number,
        "category_id": expense.category_id,
        "category_name": category.name if category else None,
        "description": expense.description,
        "payee": expense.payee,
        "amount": _f(expense.amount),
        "currency": expense.currency,
        "expense_date": expense.expense_date,
        "payment_method": expense.payment_method,
        "cash_account_id": expense.cash_account_id,
        "cash_account_name": account.name if account else None,
        "reference": expense.reference,
        "status": expense.status,
        "requires_approval": expense.requires_approval,
        "term_id": expense.term_id,
        "session_id": expense.session_id,
        "notes": expense.notes,
        "attachment_url": expense.attachment_url,
        "created_at": expense.created_at,
        "approved_at": expense.approved_at,
        "paid_at": expense.paid_at,
        "rejected_reason": expense.rejected_reason,
        "reconciled": expense.reconciled,
        "reconciled_at": expense.reconciled_at,
        "bank_reference": expense.bank_reference,
    }


def get_expense(db: Session, expense_id: uuid.UUID, school_id: uuid.UUID) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.school_id != school_id:
        raise NotFoundError("Expense not found")
    return expense


def create_expense(
    db: Session, school_id: uuid.UUID, *, data: ExpenseIn, recorded_by: uuid.UUID
) -> Expense:
    if data.category_id:
        get_expense_category(db, data.category_id, school_id)

    account_id = data.cash_account_id
    if account_id:
        get_cash_account(db, account_id, school_id)
    else:
        account_id = _default_account(db, school_id).id

    # A petty-cash purchase is money that has already left the box, so it posts
    # straight to "paid" — but only when it does not need an approver.
    if data.requires_approval:
        status = "draft"
    elif data.mark_paid:
        status = "paid"
    else:
        status = "draft"

    expense = Expense(
        school_id=school_id,
        voucher_number=f"PV-{school_id.hex[:6].upper()}-{uuid.uuid4().hex[:8].upper()}",
        category_id=data.category_id,
        description=data.description,
        payee=data.payee,
        amount=_d(data.amount),
        currency=data.currency,
        expense_date=data.expense_date,
        payment_method=data.payment_method,
        cash_account_id=account_id,
        reference=data.reference,
        status=status,
        requires_approval=data.requires_approval,
        term_id=data.term_id,
        session_id=data.session_id,
        notes=data.notes,
        attachment_url=data.attachment_url,
        recorded_by=recorded_by,
        paid_at=datetime.now(timezone.utc) if status == "paid" else None,
    )
    db.add(expense)
    db.flush()
    return expense


def list_expenses(
    db: Session,
    school_id: uuid.UUID,
    *,
    status: str | None = None,
    category_id: uuid.UUID | None = None,
    cash_account_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    stmt = select(Expense).where(Expense.school_id == school_id)
    if status:
        stmt = stmt.where(Expense.status == status)
    if category_id:
        stmt = stmt.where(Expense.category_id == category_id)
    if cash_account_id:
        stmt = stmt.where(Expense.cash_account_id == cash_account_id)
    if term_id:
        stmt = stmt.where(Expense.term_id == term_id)
    if date_from:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to:
        stmt = stmt.where(Expense.expense_date <= date_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    rows = [expense_to_dict(db, e) for e in db.scalars(stmt.offset(offset).limit(limit))]
    return rows, total


def update_expense(
    db: Session,
    expense_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    data: ExpenseIn,
) -> Expense:
    expense = get_expense(db, expense_id, school_id)
    if expense.status == "paid":
        raise ConflictError("A paid expense cannot be edited; void it instead")
    if data.category_id:
        get_expense_category(db, data.category_id, school_id)
    if data.cash_account_id:
        get_cash_account(db, data.cash_account_id, school_id)

    expense.description = data.description
    expense.payee = data.payee
    expense.amount = _d(data.amount)
    expense.currency = data.currency
    expense.expense_date = data.expense_date
    expense.payment_method = data.payment_method
    expense.category_id = data.category_id
    expense.cash_account_id = data.cash_account_id or expense.cash_account_id
    expense.reference = data.reference
    expense.term_id = data.term_id
    expense.session_id = data.session_id
    expense.notes = data.notes
    expense.attachment_url = data.attachment_url
    expense.requires_approval = data.requires_approval
    if expense.status == "rejected":
        # An edit is a re-submission: it goes back into the approval queue.
        expense.status = "draft"
        expense.rejected_reason = None
    db.flush()
    return expense


def approve_expense(
    db: Session, expense_id: uuid.UUID, school_id: uuid.UUID, *, approved_by: uuid.UUID
) -> Expense:
    expense = get_expense(db, expense_id, school_id)
    if expense.status == "paid":
        raise ConflictError("This expense has already been paid")
    if expense.status == "approved":
        raise ConflictError("This expense is already approved")
    expense.status = "approved"
    expense.approved_by = approved_by
    expense.approved_at = datetime.now(timezone.utc)
    expense.rejected_reason = None
    db.flush()
    return expense


def reject_expense(
    db: Session,
    expense_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    rejected_by: uuid.UUID,
    reason: str | None = None,
) -> Expense:
    expense = get_expense(db, expense_id, school_id)
    if expense.status == "paid":
        raise ConflictError("A paid expense cannot be rejected")
    expense.status = "rejected"
    expense.approved_by = rejected_by
    expense.approved_at = datetime.now(timezone.utc)
    expense.rejected_reason = reason
    db.flush()
    return expense


def pay_expense(
    db: Session, expense_id: uuid.UUID, school_id: uuid.UUID, *, paid_by: uuid.UUID
) -> Expense:
    """Mark an expense paid — the moment it becomes real money out."""
    expense = get_expense(db, expense_id, school_id)
    if expense.status == "paid":
        raise ConflictError("This expense is already paid")
    if expense.status == "rejected":
        raise ConflictError("A rejected expense cannot be paid; edit it first")
    if expense.requires_approval and expense.status != "approved":
        raise ConflictError("This expense needs approval before it can be paid")
    if not expense.cash_account_id:
        expense.cash_account_id = _default_account(db, school_id).id
    expense.status = "paid"
    expense.paid_at = datetime.now(timezone.utc)
    if expense.approved_by is None:
        expense.approved_by = paid_by
        expense.approved_at = expense.paid_at
    db.flush()
    return expense


def delete_expense(db: Session, expense_id: uuid.UUID, school_id: uuid.UUID) -> None:
    expense = get_expense(db, expense_id, school_id)
    if expense.status == "paid":
        raise ConflictError("A paid expense cannot be deleted; it is part of the books")
    db.delete(expense)
    db.flush()


# ──────────────────────────────────────────────────────────────────────
# Discounts / scholarships / waivers
# ──────────────────────────────────────────────────────────────────────

def _discount_to_dict(db: Session, discount: StudentDiscount) -> dict:
    student = db.get(Student, discount.student_id)
    fee = db.get(FeeStructure, discount.fee_structure_id) if discount.fee_structure_id else None
    row = {
        "id": discount.id,
        "student_id": discount.student_id,
        "student_name": student.full_name if student else None,
        "admission_no": student.admission_no if student else None,
        "name": discount.name,
        "kind": discount.kind,
        "percent": _f(discount.percent) if discount.percent is not None else None,
        "amount": _f(discount.amount) if discount.amount is not None else None,
        "fee_structure_id": discount.fee_structure_id,
        "fee_structure_name": fee.name if fee else None,
        "term_id": discount.term_id,
        "session_id": discount.session_id,
        "is_active": discount.is_active,
        "notes": discount.notes,
        "created_at": discount.created_at,
    }
    return row


def list_discounts(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID | None = None,
    active_only: bool = False,
) -> list[dict]:
    stmt = select(StudentDiscount).where(StudentDiscount.school_id == school_id)
    if student_id:
        stmt = stmt.where(StudentDiscount.student_id == student_id)
    if active_only:
        stmt = stmt.where(StudentDiscount.is_active.is_(True))
    stmt = stmt.order_by(StudentDiscount.created_at.desc())
    return [_discount_to_dict(db, d) for d in db.scalars(stmt)]


def get_discount(db: Session, discount_id: uuid.UUID, school_id: uuid.UUID) -> StudentDiscount:
    discount = db.get(StudentDiscount, discount_id)
    if discount is None or discount.school_id != school_id:
        raise NotFoundError("Discount not found")
    return discount


def _validate_student(db: Session, student_id: uuid.UUID, school_id: uuid.UUID) -> Student:
    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id or student.is_deleted:
        raise NotFoundError("Student not found")
    return student


def create_discount(
    db: Session,
    school_id: uuid.UUID,
    *,
    data: DiscountIn,
    approved_by: uuid.UUID,
) -> StudentDiscount:
    _validate_student(db, data.student_id, school_id)
    if data.fee_structure_id:
        fee = db.get(FeeStructure, data.fee_structure_id)
        if fee is None or fee.school_id != school_id:
            raise NotFoundError("Fee structure not found")

    discount = StudentDiscount(
        school_id=school_id,
        student_id=data.student_id,
        name=data.name,
        kind=data.kind,
        percent=_d(data.percent) if data.percent is not None else None,
        amount=_d(data.amount) if data.amount is not None else None,
        fee_structure_id=data.fee_structure_id,
        term_id=data.term_id,
        session_id=data.session_id,
        is_active=data.is_active,
        approved_by=approved_by,
        notes=data.notes,
    )
    db.add(discount)
    db.flush()
    return discount


def update_discount(
    db: Session, discount_id: uuid.UUID, school_id: uuid.UUID, *, data: DiscountIn
) -> StudentDiscount:
    discount = get_discount(db, discount_id, school_id)
    _validate_student(db, data.student_id, school_id)
    if data.fee_structure_id:
        fee = db.get(FeeStructure, data.fee_structure_id)
        if fee is None or fee.school_id != school_id:
            raise NotFoundError("Fee structure not found")
    discount.student_id = data.student_id
    discount.name = data.name
    discount.kind = data.kind
    discount.percent = _d(data.percent) if data.percent is not None else None
    discount.amount = _d(data.amount) if data.amount is not None else None
    discount.fee_structure_id = data.fee_structure_id
    discount.term_id = data.term_id
    discount.session_id = data.session_id
    discount.is_active = data.is_active
    discount.notes = data.notes
    db.flush()
    return discount


def delete_discount(db: Session, discount_id: uuid.UUID, school_id: uuid.UUID) -> None:
    discount = get_discount(db, discount_id, school_id)
    db.delete(discount)
    db.flush()


def discount_for(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    fee_structure_id: uuid.UUID | None,
    term_id: uuid.UUID | None,
    subtotal: Decimal,
) -> tuple[Decimal, list[StudentDiscount]]:
    """Total discount to apply to ``subtotal``, plus the discounts that caused it.

    A discount counts when it is active, belongs to the student, and either names
    no fee (applies to everything), names this fee, or was scoped to this term.
    Percentage and flat discounts stack, but the result is capped at the subtotal
    so a bill can never go negative.
    """
    stmt = select(StudentDiscount).where(
        StudentDiscount.school_id == school_id,
        StudentDiscount.student_id == student_id,
        StudentDiscount.is_active.is_(True),
    )
    applied: list[StudentDiscount] = []
    total = Decimal("0")
    for discount in db.scalars(stmt):
        if discount.fee_structure_id not in (None, fee_structure_id):
            continue
        if discount.term_id is not None and discount.term_id != term_id:
            continue
        if discount.percent is not None:
            total += (subtotal * _d(discount.percent) / Decimal("100")).quantize(Decimal("0.01"))
        elif discount.amount is not None:
            total += _d(discount.amount)
        applied.append(discount)
    total = min(total, subtotal)
    return total, applied


# ──────────────────────────────────────────────────────────────────────
# Credit notes
# ──────────────────────────────────────────────────────────────────────


def _credit_note_to_dict(db: Session, note: CreditNote) -> dict:
    student = db.get(Student, note.student_id)
    invoice = db.get(Invoice, note.invoice_id) if note.invoice_id else None
    return {
        "id": note.id,
        "note_number": note.note_number,
        "student_id": note.student_id,
        "student_name": student.full_name if student else None,
        "admission_no": student.admission_no if student else None,
        "invoice_id": note.invoice_id,
        "invoice_reference": invoice.reference_number if invoice else None,
        "amount": _f(note.amount),
        "reason": note.reason,
        "status": note.status,
        "issued_date": note.issued_date,
        "applied_invoice_id": note.applied_invoice_id,
        "applied_at": note.applied_at,
        "created_at": note.created_at,
    }


def list_credit_notes(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[dict]:
    stmt = select(CreditNote).where(CreditNote.school_id == school_id)
    if student_id:
        stmt = stmt.where(CreditNote.student_id == student_id)
    if status:
        stmt = stmt.where(CreditNote.status == status)
    stmt = stmt.order_by(CreditNote.created_at.desc())
    return [_credit_note_to_dict(db, n) for n in db.scalars(stmt)]


def get_credit_note(db: Session, note_id: uuid.UUID, school_id: uuid.UUID) -> CreditNote:
    note = db.get(CreditNote, note_id)
    if note is None or note.school_id != school_id:
        raise NotFoundError("Credit note not found")
    return note


def create_credit_note(
    db: Session, school_id: uuid.UUID, *, data: CreditNoteIn, issued_by: uuid.UUID
) -> CreditNote:
    _validate_student(db, data.student_id, school_id)
    if data.invoice_id:
        invoice = db.get(Invoice, data.invoice_id)
        if invoice is None or invoice.school_id != school_id:
            raise NotFoundError("Invoice not found")
        if invoice.student_id != data.student_id:
            raise ValidationError("The invoice belongs to a different student")

    note = CreditNote(
        school_id=school_id,
        note_number=f"CN-{school_id.hex[:6].upper()}-{uuid.uuid4().hex[:8].upper()}",
        student_id=data.student_id,
        invoice_id=data.invoice_id,
        amount=_d(data.amount),
        reason=data.reason,
        status="open",
        issued_by=issued_by,
        issued_date=_today().isoformat(),
    )
    db.add(note)
    db.flush()
    return note


def apply_credit_note(
    db: Session, note_id: uuid.UUID, school_id: uuid.UUID, *, invoice_id: uuid.UUID
) -> CreditNote:
    """Apply an open credit note to an invoice, reducing what is owed."""
    note = get_credit_note(db, note_id, school_id)
    if note.status != "open":
        raise ConflictError(f"This credit note is already {note.status}")

    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.school_id != school_id:
        raise NotFoundError("Invoice not found")
    if invoice.student_id != note.student_id:
        raise ValidationError("The invoice belongs to a different student")

    _apply_discount_to_invoice(db, invoice, _d(note.amount))
    note.status = "applied"
    note.applied_invoice_id = invoice.id
    note.applied_at = datetime.now(timezone.utc)
    db.flush()
    return note


def void_credit_note(db: Session, note_id: uuid.UUID, school_id: uuid.UUID) -> CreditNote:
    note = get_credit_note(db, note_id, school_id)
    if note.status == "applied":
        raise ConflictError("An applied credit note cannot be voided")
    note.status = "void"
    db.flush()
    return note


def _apply_discount_to_invoice(db: Session, invoice: Invoice, extra: Decimal) -> None:
    """Increase an invoice's discount and recompute its total + status.

    ``total = subtotal - discount + tax``, floored at zero so a credit note can
    never turn a bill into money the school owes.
    """
    discount = _d(invoice.discount_amount) + extra
    subtotal = _d(invoice.subtotal)
    discount = min(discount, subtotal)
    total = max(subtotal - discount + _d(invoice.tax_amount), Decimal("0"))
    invoice.discount_amount = discount
    invoice.total_amount = total
    _recalc_invoice_status(db, invoice)
    db.flush()


def _recalc_invoice_status(db: Session, invoice: Invoice) -> None:
    """Re-derive an invoice's paid/partial status from the payments on it."""
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice.id
        )
    ) or 0
    total = _d(invoice.total_amount)
    if total > 0 and _d(paid) >= total:
        invoice.status = "paid"
        if not invoice.paid_date:
            invoice.paid_date = _today().isoformat()
    elif _d(paid) > 0:
        invoice.status = "partial"
        invoice.paid_date = None
    elif invoice.status in ("paid", "partial"):
        invoice.status = "sent"
        invoice.paid_date = None


# ──────────────────────────────────────────────────────────────────────
# Refunds
# ──────────────────────────────────────────────────────────────────────


def _refund_to_dict(db: Session, refund: Refund) -> dict:
    student = db.get(Student, refund.student_id)
    return {
        "id": refund.id,
        "student_id": refund.student_id,
        "student_name": student.full_name if student else None,
        "admission_no": student.admission_no if student else None,
        "payment_id": refund.payment_id,
        "amount": _f(refund.amount),
        "currency": refund.currency,
        "method": refund.method,
        "reference": refund.reference,
        "reason": refund.reason,
        "status": refund.status,
        "cash_account_id": refund.cash_account_id,
        "refund_date": refund.refund_date,
        "reconciled": refund.reconciled,
        "created_at": refund.created_at,
        "approved_at": refund.approved_at,
    }


def list_refunds(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[dict]:
    stmt = select(Refund).where(Refund.school_id == school_id)
    if student_id:
        stmt = stmt.where(Refund.student_id == student_id)
    if status:
        stmt = stmt.where(Refund.status == status)
    stmt = stmt.order_by(Refund.created_at.desc())
    return [_refund_to_dict(db, r) for r in db.scalars(stmt)]


def get_refund(db: Session, refund_id: uuid.UUID, school_id: uuid.UUID) -> Refund:
    refund = db.get(Refund, refund_id)
    if refund is None or refund.school_id != school_id:
        raise NotFoundError("Refund not found")
    return refund


def _net_paid_by_student(db: Session, school_id: uuid.UUID, student_id: uuid.UUID) -> Decimal:
    """Payments received minus refunds already paid out — the refundable ceiling."""
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.school_id == school_id, Payment.student_id == student_id
        )
    ) or 0
    refunded = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.school_id == school_id,
            Refund.student_id == student_id,
            Refund.status.in_(("approved", "paid")),
        )
    ) or 0
    return _d(paid) - _d(refunded)


def create_refund(
    db: Session, school_id: uuid.UUID, *, data: RefundIn, requested_by: uuid.UUID
) -> Refund:
    _validate_student(db, data.student_id, school_id)
    if data.payment_id:
        payment = db.get(Payment, data.payment_id)
        if payment is None or payment.school_id != school_id:
            raise NotFoundError("Payment not found")

    account_id = data.cash_account_id
    if account_id:
        get_cash_account(db, account_id, school_id)

    # Never refund more than the student has actually paid and kept.
    ceiling = _net_paid_by_student(db, school_id, data.student_id)
    if _d(data.amount) > ceiling:
        raise ValidationError(
            "Refund exceeds the amount this student has paid",
            {"refundable": _f(ceiling)},
        )

    now = datetime.now(timezone.utc)
    refund = Refund(
        school_id=school_id,
        payment_id=data.payment_id,
        student_id=data.student_id,
        amount=_d(data.amount),
        currency=data.currency,
        method=data.method,
        reference=data.reference,
        reason=data.reason,
        status="paid" if data.mark_paid else "pending",
        cash_account_id=account_id or _default_account(db, school_id).id,
        requested_by=requested_by,
        approved_by=requested_by if data.mark_paid else None,
        refund_date=(data.refund_date or _today().isoformat()) if data.mark_paid else None,
    )
    db.add(refund)
    db.flush()
    return refund


def approve_refund(
    db: Session, refund_id: uuid.UUID, school_id: uuid.UUID, *, approved_by: uuid.UUID
) -> Refund:
    refund = get_refund(db, refund_id, school_id)
    if refund.status != "pending":
        raise ConflictError(f"This refund is already {refund.status}")
    refund.status = "approved"
    refund.approved_by = approved_by
    refund.approved_at = datetime.now(timezone.utc)
    db.flush()
    return refund


def reject_refund(
    db: Session,
    refund_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    rejected_by: uuid.UUID,
    reason: str | None = None,
) -> Refund:
    refund = get_refund(db, refund_id, school_id)
    if refund.status == "paid":
        raise ConflictError("A paid refund cannot be rejected")
    refund.status = "rejected"
    refund.approved_by = rejected_by
    refund.reason = reason or refund.reason
    db.flush()
    return refund


def pay_refund(
    db: Session,
    refund_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    paid_by: uuid.UUID,
    refund_date: str | None = None,
) -> Refund:
    refund = get_refund(db, refund_id, school_id)
    if refund.status == "paid":
        raise ConflictError("This refund is already paid")
    if refund.status == "rejected":
        raise ConflictError("A rejected refund cannot be paid")
    if refund.status == "pending":
        refund.approved_by = paid_by
        refund.approved_at = datetime.now(timezone.utc)
    if not refund.cash_account_id:
        refund.cash_account_id = _default_account(db, school_id).id
    refund.status = "paid"
    refund.refund_date = refund_date or _today().isoformat()
    db.flush()
    return refund


# ──────────────────────────────────────────────────────────────────────
# Cashbook (read model) + bank reconciliation
# ──────────────────────────────────────────────────────────────────────


def get_cashbook(
    db: Session,
    school_id: uuid.UUID,
    *,
    cash_account_id: uuid.UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    only_unreconciled: bool = False,
) -> dict:
    """The cashbook over a date window, derived from real documents.

    Fee payments are money in; paid expenses and paid refunds are money out. Each
    line keeps a pointer back to the document that produced it so reconciliation
    writes to the original row rather than to a shadow ledger.
    """
    default_account = _default_account(db, school_id)
    accounts = {
        a.id: a for a in db.scalars(select(CashAccount).where(CashAccount.school_id == school_id))
    }

    def account_of(account_id: uuid.UUID | None) -> CashAccount | None:
        # Unattributed money is shown against the default account so it never
        # silently drops out of the cashbook.
        return accounts.get(account_id) if account_id else default_account

    lines: list[dict] = []

    # Opening balances (one synthetic line per account holding a float).
    for account in accounts.values():
        if cash_account_id and account.id != cash_account_id:
            continue
        if _d(account.opening_balance) == 0:
            continue
        opened = account.created_at.date().isoformat() if account.created_at else None
        lines.append(
            {
                "source_type": "opening",
                "source_id": None,
                "direction": "in",
                "entry_date": opened,
                "description": f"Opening balance — {account.name}",
                "reference": None,
                "amount": _f(account.opening_balance),
                "cash_account_id": account.id,
                "cash_account_name": account.name,
                "reconciled": True,
                "bank_reference": None,
                "_sort": (opened or "", 0),
            }
        )

    # Money in: fee payments.
    pay_stmt = select(Payment).where(Payment.school_id == school_id)
    if date_from:
        pay_stmt = pay_stmt.where(Payment.payment_date >= date_from)
    if date_to:
        pay_stmt = pay_stmt.where(Payment.payment_date <= date_to)
    for payment in db.scalars(pay_stmt):
        account = account_of(payment.cash_account_id)
        if cash_account_id and (account is None or account.id != cash_account_id):
            continue
        student = db.get(Student, payment.student_id) if payment.student_id else None
        lines.append(
            {
                "source_type": "payment",
                "source_id": payment.id,
                "direction": "in",
                "entry_date": payment.payment_date,
                "description": (
                    f"Fee payment — {student.full_name}" if student else "Fee payment"
                ),
                "reference": payment.receipt_number or payment.payment_reference,
                "amount": _f(payment.amount),
                "cash_account_id": account.id if account else None,
                "cash_account_name": account.name if account else None,
                "reconciled": bool(payment.reconciled),
                "bank_reference": payment.bank_reference,
                "_sort": (payment.payment_date or "", 1),
            }
        )

    # Money out: paid expenses.
    exp_stmt = select(Expense).where(Expense.school_id == school_id, Expense.status == "paid")
    if date_from:
        exp_stmt = exp_stmt.where(Expense.expense_date >= date_from)
    if date_to:
        exp_stmt = exp_stmt.where(Expense.expense_date <= date_to)
    for expense in db.scalars(exp_stmt):
        account = account_of(expense.cash_account_id)
        if cash_account_id and (account is None or account.id != cash_account_id):
            continue
        lines.append(
            {
                "source_type": "expense",
                "source_id": expense.id,
                "direction": "out",
                "entry_date": expense.expense_date,
                "description": expense.description,
                "reference": expense.voucher_number,
                "amount": _f(expense.amount),
                "cash_account_id": account.id if account else None,
                "cash_account_name": account.name if account else None,
                "reconciled": bool(expense.reconciled),
                "bank_reference": expense.bank_reference,
                "_sort": (expense.expense_date or "", 2),
            }
        )

    # Money out: paid refunds.
    ref_stmt = select(Refund).where(Refund.school_id == school_id, Refund.status == "paid")
    if date_from:
        ref_stmt = ref_stmt.where(Refund.refund_date >= date_from)
    if date_to:
        ref_stmt = ref_stmt.where(Refund.refund_date <= date_to)
    for refund in db.scalars(ref_stmt):
        account = account_of(refund.cash_account_id)
        if cash_account_id and (account is None or account.id != cash_account_id):
            continue
        student = db.get(Student, refund.student_id) if refund.student_id else None
        lines.append(
            {
                "source_type": "refund",
                "source_id": refund.id,
                "direction": "out",
                "entry_date": refund.refund_date,
                "description": (
                    f"Refund — {student.full_name}" if student else "Refund"
                ),
                "reference": refund.reference,
                "amount": _f(refund.amount),
                "cash_account_id": account.id if account else None,
                "cash_account_name": account.name if account else None,
                "reconciled": bool(refund.reconciled),
                "bank_reference": refund.bank_reference,
                "_sort": (refund.refund_date or "", 3),
            }
        )

    lines.sort(key=lambda line: line["_sort"])
    if only_unreconciled:
        lines = [line for line in lines if not line["reconciled"]]

    total_in = _f(sum(_d(line["amount"]) for line in lines if line["direction"] == "in"))
    total_out = _f(sum(_d(line["amount"]) for line in lines if line["direction"] == "out"))

    opening = _f(
        sum(
            _d(account.opening_balance)
            for account in accounts.values()
            if (not cash_account_id or account.id == cash_account_id)
        )
    )
    reconciled_count = sum(1 for line in lines if line["reconciled"])
    unreconciled_count = len(lines) - reconciled_count
    for line in lines:
        line.pop("_sort", None)

    return {
        "lines": lines,
        "total_in": total_in,
        "total_out": total_out,
        "net": _f(_d(total_in) - _d(total_out)),
        "opening": opening,
        "closing": _f(_d(opening) + _d(total_in) - _d(total_out)),
        "reconciled_count": reconciled_count,
        "unreconciled_count": unreconciled_count,
    }


def set_reconciled(
    db: Session,
    school_id: uuid.UUID,
    *,
    source_type: str,
    source_id: uuid.UUID,
    reconciled: bool,
    bank_reference: str | None = None,
) -> dict:
    """Mark one cashbook document matched (or unmatched) to a bank statement."""
    model = {"payment": Payment, "expense": Expense, "refund": Refund}.get(source_type)
    if model is None:
        raise ValidationError("Unknown cashbook entry type")

    row = db.get(model, source_id)
    if row is None or row.school_id != school_id:
        raise NotFoundError("Cashbook entry not found")

    row.reconciled = reconciled
    now = datetime.now(timezone.utc)
    row.reconciled_at = now if reconciled else None
    if bank_reference is not None:
        row.bank_reference = bank_reference
    db.flush()
    return {
        "source_type": source_type,
        "source_id": row.id,
        "reconciled": row.reconciled,
        "bank_reference": row.bank_reference,
        "reconciled_at": row.reconciled_at,
    }


# ──────────────────────────────────────────────────────────────────────
# Windows (term / session / explicit dates)
# ──────────────────────────────────────────────────────────────────────


def resolve_window(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Resolve a reporting window. Terms/sessions fall back to the current one."""
    label = "All time"
    start: date | None = None
    end: date | None = None
    resolved_term: uuid.UUID | None = None
    resolved_session: uuid.UUID | None = None

    term: Term | None = None
    if term_id:
        term = db.get(Term, term_id)
        if term is None or term.school_id != school_id:
            raise NotFoundError("Term not found")
    elif session_id:
        session = db.get(AcademicSession, session_id)
        if session is None or session.school_id != school_id:
            raise NotFoundError("Session not found")
        resolved_session = session.id
        label = session.name
        start, end = session.start_date, session.end_date
    else:
        term = db.scalar(
            select(Term).where(Term.school_id == school_id, Term.is_current.is_(True))
        )

    if term is not None:
        resolved_term = term.id
        resolved_session = term.academic_session_id
        label = term.name
        start, end = term.start_date, term.end_date
        session = db.get(AcademicSession, term.academic_session_id)
        if session is not None:
            label = f"{session.name} · {term.name}"

    if date_from:
        start = date.fromisoformat(date_from)
    if date_to:
        end = date.fromisoformat(date_to)
    if (date_from or date_to) and term is None and resolved_session is None:
        left = start.isoformat() if start else "start"
        right = end.isoformat() if end else "today"
        label = f"{left} → {right}"

    return {
        "label": label,
        "start": start,
        "end": end,
        "term_id": resolved_term,
        "session_id": resolved_session,
    }


# ──────────────────────────────────────────────────────────────────────
# Debtors (aging)
# ──────────────────────────────────────────────────────────────────────


def get_debtors(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID | None = None,
    arm_id: uuid.UUID | None = None,
) -> dict:
    """Outstanding student fees with aging buckets by days past the due date.

    Only invoices that are not settled count (draft/sent/partial); an invoice
    marked paid, written off or expired is not a debtor.
    """
    inv_stmt = select(Invoice).where(
        Invoice.school_id == school_id, Invoice.status.in_(_SENTINEL_UNPAID)
    )
    if term_id:
        inv_stmt = inv_stmt.where(Invoice.term_id == term_id)
    invoices = list(db.scalars(inv_stmt))

    if arm_id:
        arm = db.get(ClassArm, arm_id)
        if arm is None or arm.school_id != school_id:
            raise NotFoundError("Class arm not found")

    paid_by_invoice: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    if invoices:
        rows = db.execute(
            select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.school_id == school_id, Payment.invoice_id.in_([i.id for i in invoices]))
            .group_by(Payment.invoice_id)
        ).all()
        for invoice_id, amount in rows:
            if invoice_id is not None:
                paid_by_invoice[invoice_id] = _d(amount)

    today = _today()
    buckets = {"current": 0.0, "1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
    per_student: dict[uuid.UUID, dict] = {}

    for invoice in invoices:
        paid = paid_by_invoice.get(invoice.id, Decimal("0"))
        balance = max(_d(invoice.total_amount) - paid, Decimal("0"))
        if balance <= 0:
            continue

        entry = per_student.setdefault(
            invoice.student_id,
            {
                "student_id": invoice.student_id,
                "invoiced": Decimal("0"),
                "paid": Decimal("0"),
                "balance": Decimal("0"),
                "current": Decimal("0"),
                "days_1_30": Decimal("0"),
                "days_31_60": Decimal("0"),
                "days_61_90": Decimal("0"),
                "days_90_plus": Decimal("0"),
                "oldest_due_date": None,
                "invoice_count": 0,
            },
        )
        entry["invoiced"] += _d(invoice.total_amount)
        entry["paid"] += paid
        entry["balance"] += balance
        entry["invoice_count"] += 1
        due = invoice.due_date
        if due and (entry["oldest_due_date"] is None or due < entry["oldest_due_date"]):
            entry["oldest_due_date"] = due

        # Bucket by how far past due the balance sits.
        if not due or due >= today.isoformat():
            bucket = "current"
        else:
            days_past = (today - date.fromisoformat(due)).days
            if days_past <= _AGING_BUCKETS[0]:
                bucket = "1_30"
            elif days_past <= _AGING_BUCKETS[1]:
                bucket = "31_60"
            elif days_past <= _AGING_BUCKETS[2]:
                bucket = "61_90"
            else:
                bucket = "90_plus"
        entry[bucket] += balance
        buckets[bucket] += float(balance)

    # One query for the primary guardian of every debtor, rather than a lookup
    # per student (this list is the "chase these parents" screen).
    guardian_by_student = _guardian_contacts(db, set(per_student.keys()))

    rows: list[dict] = []
    for entry in per_student.values():
        student = db.get(Student, entry["student_id"])
        if student is None or student.school_id != school_id:
            continue
        arm_name = _current_arm_name(db, student.id)
        contact = guardian_by_student.get(student.id, (None, None, None))
        if arm_id:
            enrollment = db.scalar(
                select(StudentEnrollment).where(
                    StudentEnrollment.student_id == student.id,
                    StudentEnrollment.is_current.is_(True),
                )
            )
            if enrollment is None or enrollment.class_arm_id != arm_id:
                continue
        rows.append(
            {
                "student_id": student.id,
                "admission_no": student.admission_no,
                "full_name": student.full_name,
                "arm_name": arm_name,
                "guardian_name": contact[0],
                "guardian_phone": contact[1],
                "guardian_email": contact[2],
                "invoiced": _f(entry["invoiced"]),
                "paid": _f(entry["paid"]),
                "balance": _f(entry["balance"]),
                "current": _f(entry["current"]),
                "days_1_30": _f(entry["days_1_30"]),
                "days_31_60": _f(entry["days_31_60"]),
                "days_61_90": _f(entry["days_61_90"]),
                "days_90_plus": _f(entry["days_90_plus"]),
                "oldest_due_date": entry["oldest_due_date"],
                "invoice_count": entry["invoice_count"],
            }
        )

    rows.sort(key=lambda row: row["balance"], reverse=True)
    return {
        "currency": _school_currency(db, school_id),
        "rows": rows,
        "total_outstanding": _f(sum(_d(row["balance"]) for row in rows)),
        "buckets": {key: _f(value) for key, value in buckets.items()},
        "student_count": len(rows),
    }


def _guardian_contacts(
    db: Session, student_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[str | None, str | None, str | None]]:
    """Primary guardian (name, phone, email) per student — one query."""
    from ..models import Guardian, StudentGuardian

    if not student_ids:
        return {}
    rows = db.execute(
        select(Guardian, StudentGuardian)
        .join(StudentGuardian, StudentGuardian.guardian_id == Guardian.id)
        .where(StudentGuardian.student_id.in_(student_ids))
        .order_by(StudentGuardian.is_primary.desc())
    ).all()
    contacts: dict[uuid.UUID, tuple[str | None, str | None, str | None]] = {}
    for guardian, link in rows:
        # is_primary is ordered first, so the first row for a student wins.
        contacts.setdefault(
            link.student_id, (guardian.full_name, guardian.phone, guardian.email)
        )
    return contacts


def _current_arm_name(db: Session, student_id: uuid.UUID) -> str | None:
    enrollment = db.scalar(
        select(StudentEnrollment)
        .where(
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.is_current.is_(True),
        )
        .order_by(StudentEnrollment.enrolled_at.desc())
    )
    if enrollment is None:
        return None
    arm = db.get(ClassArm, enrollment.class_arm_id)
    return arm.full_name if arm else None


# ──────────────────────────────────────────────────────────────────────
# Reports
# ──────────────────────────────────────────────────────────────────────


def _fee_collections(
    db: Session, school_id: uuid.UUID, start: date | None, end: date | None
) -> float:
    # Dates are ISO YYYY-MM-DD strings throughout the finance module, so the
    # window comparison is a plain lexicographic one — done in SQL, not in Python.
    stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.school_id == school_id
    )
    if start:
        stmt = stmt.where(Payment.payment_date >= start.isoformat())
    if end:
        stmt = stmt.where(Payment.payment_date <= end.isoformat())
    return _f(db.scalar(stmt) or 0)


def _paid_expenses(
    db: Session, school_id: uuid.UUID, start: date | None, end: date | None
) -> list[Expense]:
    stmt = select(Expense).where(Expense.school_id == school_id, Expense.status == "paid")
    if start:
        stmt = stmt.where(Expense.expense_date >= start.isoformat())
    if end:
        stmt = stmt.where(Expense.expense_date <= end.isoformat())
    return list(db.scalars(stmt))


def income_expenditure(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Income & expenditure statement for the window.

    Income is fees actually collected (a school's ledger is cash-based). Expenses
    count only once paid, grouped by category. ``other_income`` stays zero until
    the school records non-fee income, rather than inventing a number.
    """
    window = resolve_window(
        db,
        school_id,
        term_id=term_id,
        session_id=session_id,
        date_from=date_from,
        date_to=date_to,
    )
    start, end = window["start"], window["end"]

    fee_collections = _fee_collections(db, school_id, start, end)

    by_category: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for expense in _paid_expenses(db, school_id, start, end):
        category = (
            db.get(ExpenseCategory, expense.category_id) if expense.category_id else None
        )
        label = category.name if category else "Uncategorised"
        by_category[label] += _d(expense.amount)

    total_expenditure = sum(by_category.values(), Decimal("0"))
    total_income = _d(fee_collections)
    surplus = total_income - total_expenditure

    return {
        "period_label": window["label"],
        "currency": _school_currency(db, school_id),
        "term_id": window["term_id"],
        "session_id": window["session_id"],
        "fee_collections": _f(fee_collections),
        "other_income": 0.0,
        "total_income": _f(total_income),
        "expenses_by_category": [
            {"category": name, "amount": _f(amount)}
            for name, amount in sorted(
                by_category.items(), key=lambda item: item[1], reverse=True
            )
        ],
        "total_expenditure": _f(total_expenditure),
        "surplus": _f(surplus),
        "surplus_label": "surplus" if surplus >= 0 else "deficit",
    }


def collection_report(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
) -> dict:
    """Fee collection by class arm: invoiced vs collected vs outstanding."""
    window = resolve_window(db, school_id, term_id=term_id, session_id=session_id)
    inv_stmt = select(Invoice).where(Invoice.school_id == school_id)
    if window["term_id"]:
        inv_stmt = inv_stmt.where(Invoice.term_id == window["term_id"])
    elif window["session_id"]:
        inv_stmt = inv_stmt.where(Invoice.session_id == window["session_id"])
    invoices = list(db.scalars(inv_stmt))

    paid_by_invoice: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    if invoices:
        rows = db.execute(
            select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.school_id == school_id, Payment.invoice_id.in_([i.id for i in invoices]))
            .group_by(Payment.invoice_id)
        ).all()
        for invoice_id, amount in rows:
            if invoice_id is not None:
                paid_by_invoice[invoice_id] = _d(amount)

    groups: dict[uuid.UUID | None, dict] = {}
    for invoice in invoices:
        arm_name = _current_arm_name(db, invoice.student_id)
        arm = db.scalar(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.student_id == invoice.student_id,
                StudentEnrollment.is_current.is_(True),
            )
            .order_by(StudentEnrollment.enrolled_at.desc())
        )
        arm_id = arm.class_arm_id if arm else None
        arm_label = arm_name or "Unassigned"

        group = groups.setdefault(
            arm_id,
            {
                "arm_id": arm_id,
                "arm_name": arm_label,
                "students": set(),
                "invoiced": Decimal("0"),
                "collected": Decimal("0"),
            },
        )
        group["students"].add(invoice.student_id)
        group["invoiced"] += _d(invoice.total_amount)
        group["collected"] += paid_by_invoice.get(invoice.id, Decimal("0"))

    rows_out: list[dict] = []
    for group in groups.values():
        invoiced = group["invoiced"]
        collected = group["collected"]
        outstanding = max(invoiced - collected, Decimal("0"))
        rate = float(collected / invoiced * 100) if invoiced > 0 else 0.0
        rows_out.append(
            {
                "arm_id": group["arm_id"],
                "arm_name": group["arm_name"],
                "students": len(group["students"]),
                "invoiced": _f(invoiced),
                "collected": _f(collected),
                "outstanding": _f(outstanding),
                "collection_rate": round(rate, 1),
            }
        )

    rows_out.sort(key=lambda row: row["invoiced"], reverse=True)
    total_invoiced = sum(_d(row["invoiced"]) for row in rows_out)
    total_collected = sum(_d(row["collected"]) for row in rows_out)
    total_outstanding = sum(_d(row["outstanding"]) for row in rows_out)
    overall_rate = (
        float(total_collected / total_invoiced * 100) if total_invoiced > 0 else 0.0
    )
    return {
        "currency": _school_currency(db, school_id),
        "rows": rows_out,
        "total_invoiced": _f(total_invoiced),
        "total_collected": _f(total_collected),
        "total_outstanding": _f(total_outstanding),
        "collection_rate": round(overall_rate, 1),
    }


def cash_position(db: Session, school_id: uuid.UUID) -> dict:
    """How much is in each cash/bank account, and how much is still unmatched."""
    rows: list[dict] = []
    for account in db.scalars(select(CashAccount).where(CashAccount.school_id == school_id)):
        money_in, money_out = _account_movement(db, school_id, account.id)

        unreconciled = Decimal("0")
        for model in (Payment, Expense, Refund):
            amount_sum = db.scalar(
                select(func.coalesce(func.sum(model.amount), 0)).where(
                    model.school_id == school_id,
                    model.cash_account_id == account.id,
                    model.reconciled.is_(False),
                )
            ) or 0
            unreconciled += _d(amount_sum)

        rows.append(
            {
                "cash_account_id": account.id,
                "name": account.name,
                "kind": account.kind,
                "opening_balance": _f(account.opening_balance),
                "total_in": money_in,
                "total_out": money_out,
                "balance": _f(_d(account.opening_balance) + _d(money_in) - _d(money_out)),
                "unreconciled_amount": _f(unreconciled),
            }
        )

    rows.sort(key=lambda row: row["balance"], reverse=True)
    return {
        "currency": _school_currency(db, school_id),
        "rows": rows,
        "total_balance": _f(sum(_d(row["balance"]) for row in rows)),
        "total_unreconciled": _f(sum(_d(row["unreconciled_amount"]) for row in rows)),
    }


def summary(
    db: Session, school_id: uuid.UUID, *, term_id: uuid.UUID | None = None
) -> dict:
    """The accountant's dashboard: headline numbers for the current term."""
    window = resolve_window(db, school_id, term_id=term_id)
    start, end = window["start"], window["end"]

    # Outstanding: every unsettled invoice, less what has been paid on it.
    outstanding = Decimal("0")
    invoices = db.scalars(
        select(Invoice).where(Invoice.school_id == school_id, Invoice.status.in_(_SENTINEL_UNPAID))
    )
    for invoice in invoices:
        paid = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice.id
            )
        ) or 0
        outstanding += max(_d(invoice.total_amount) - _d(paid), Decimal("0"))

    collected = _d(_fee_collections(db, school_id, start, end))
    expenses = sum(
        (_d(expense.amount) for expense in _paid_expenses(db, school_id, start, end)),
        Decimal("0"),
    )

    debtors = get_debtors(db, school_id, term_id=window["term_id"])
    position = cash_position(db, school_id)

    pending_approvals = db.scalar(
        select(func.count()).select_from(Expense).where(
            Expense.school_id == school_id,
            Expense.requires_approval.is_(True),
            Expense.status.in_(("draft", "approved")),
        )
    ) or 0
    pending_refunds = db.scalar(
        select(func.count()).select_from(Refund).where(
            Refund.school_id == school_id, Refund.status == "pending"
        )
    ) or 0
    open_notes = db.scalar(
        select(func.count()).select_from(CreditNote).where(
            CreditNote.school_id == school_id, CreditNote.status == "open"
        )
    ) or 0

    return {
        "currency": _school_currency(db, school_id),
        "outstanding_fees": _f(outstanding),
        "collected_this_term": _f(collected),
        "expenses_this_term": _f(expenses),
        "surplus_this_term": _f(collected - expenses),
        "pending_expense_approvals": int(pending_approvals),
        "pending_refunds": int(pending_refunds),
        "open_credit_notes": int(open_notes),
        "unreconciled_cashbook_entries": int(
            get_cashbook(db, school_id, only_unreconciled=True)["unreconciled_count"]
        ),
        "cash_position": position["total_balance"],
        "debtors_over_90_days": debtors["buckets"].get("90_plus", 0.0),
    }


# ──────────────────────────────────────────────────────────────────────
# Provisioning an accountant (own login, per school)
# ──────────────────────────────────────────────────────────────────────


def list_accountants(db: Session, school_id: uuid.UUID, role_code: str) -> list[dict]:
    """Every member of this school holding the Accountant role."""
    from ..models import Role, SchoolMembership, User

    role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == role_code)
    )
    if role is None:
        return []
    rows = db.execute(
        select(SchoolMembership, User)
        .join(User, User.id == SchoolMembership.user_id)
        .where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.role_id == role.id,
        )
        .order_by(User.full_name)
    ).all()

    from ..models import Staff

    out = []
    for membership, user in rows:
        staff = db.scalar(select(Staff).where(Staff.user_id == user.id, Staff.school_id == school_id))
        out.append(
            {
                "user_id": user.id,
                "staff_id": staff.id if staff else None,
                "email": user.email,
                "full_name": user.full_name,
                "school_id": school_id,
                "role_code": role.code,
                "role_name": role.name,
                "has_login": user.status == "active",
            }
        )
    return out
