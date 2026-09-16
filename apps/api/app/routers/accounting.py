"""Accounting API endpoints — the school Accountant's desk.

Every route here is gated by :func:`require_accountant`, which checks the
caller's **school-scoped role code** (``accountant``) *and* the relevant
accounting permission. Roles are per school, so an accountant acts on their own
school only; a bursar or an admin holding the same finance permissions still
cannot post to the books.

Exceptions, deliberately:

* Listing/provisioning accountant logins is a **school-admin** action
  (``users.manage``), because it is the office that hands out credentials, not
  the ledger itself.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from ..core.deps import DbSession, require_accountant, require_permission
from ..core.errors import ValidationError
from ..core.permissions import (
    ACCOUNTING_AMEND,
    ACCOUNTING_EXPENSES,
    ACCOUNTING_RECONCILE,
    ACCOUNTING_REPORTS,
    ACCOUNTING_VIEW,
    ROLE_ACCOUNTANT,
    USERS_MANAGE,
)
from ..models import Role
from ..schemas.accounting import (
    AccountingSummaryOut,
    AccountantCreateIn,
    AccountantOut,
    CashAccountIn,
    CashAccountOut,
    CashPositionOut,
    CashbookOut,
    CollectionReportOut,
    CreditNoteApplyIn,
    CreditNoteIn,
    CreditNoteOut,
    DebtorsOut,
    DiscountIn,
    DiscountOut,
    ExpenseCategoryIn,
    ExpenseCategoryOut,
    ExpenseIn,
    ExpenseOut,
    ExpenseRejectIn,
    IncomeExpenditureOut,
    ReconcileIn,
    RefundIn,
    RefundOut,
    RefundRejectIn,
)
from ..services import accounting_service as svc
from ..services import people_service


router = APIRouter(prefix="/accounting", tags=["accounting"])


# ──────────────────────────────────────────────────────────────────────
# Dashboard summary
# ──────────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=AccountingSummaryOut)
def accounting_summary(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    term_id: Optional[uuid.UUID] = Query(None),
):
    """Headline numbers for the accountant's dashboard."""
    return svc.summary(db, ctx.school.id, term_id=term_id)


# ──────────────────────────────────────────────────────────────────────
# Cash accounts
# ──────────────────────────────────────────────────────────────────────


@router.get("/accounts", response_model=list[CashAccountOut])
def list_cash_accounts(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    active_only: bool = Query(False),
):
    return svc.list_cash_accounts(db, ctx.school.id, active_only=active_only)


@router.post("/accounts", response_model=CashAccountOut, status_code=201)
def create_cash_account(
    payload: CashAccountIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_RECONCILE)),
):
    account = svc.create_cash_account(db, ctx.school.id, data=payload)
    db.commit()
    return _account_out(db, ctx.school.id, account.id)


@router.put("/accounts/{account_id}", response_model=CashAccountOut)
def update_cash_account(
    account_id: uuid.UUID,
    payload: CashAccountIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_RECONCILE)),
):
    svc.update_cash_account(db, account_id, ctx.school.id, data=payload)
    db.commit()
    return _account_out(db, ctx.school.id, account_id)


def _account_out(db, school_id, account_id):
    for row in svc.list_cash_accounts(db, school_id):
        if row["id"] == account_id:
            return CashAccountOut.model_validate(row)
    raise ValidationError("Cash account not found after save")


# ──────────────────────────────────────────────────────────────────────
# Expense categories
# ──────────────────────────────────────────────────────────────────────


@router.get("/categories", response_model=list[ExpenseCategoryOut])
def list_expense_categories(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    active_only: bool = Query(False),
):
    rows = svc.list_expense_categories(db, ctx.school.id, active_only=active_only)
    return [ExpenseCategoryOut.model_validate(row) for row in rows]


@router.post("/categories", response_model=ExpenseCategoryOut, status_code=201)
def create_expense_category(
    payload: ExpenseCategoryIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    category = svc.create_expense_category(db, ctx.school.id, data=payload)
    db.commit()
    return ExpenseCategoryOut.model_validate(category)


@router.put("/categories/{category_id}", response_model=ExpenseCategoryOut)
def update_expense_category(
    category_id: uuid.UUID,
    payload: ExpenseCategoryIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    category = svc.update_expense_category(db, category_id, ctx.school.id, data=payload)
    db.commit()
    return ExpenseCategoryOut.model_validate(category)


# ──────────────────────────────────────────────────────────────────────
# Expenses & petty cash
# ──────────────────────────────────────────────────────────────────────


@router.get("/expenses")
def list_expenses(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    status: Optional[str] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    cash_account_id: Optional[uuid.UUID] = Query(None),
    term_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Cashbook-style expense list. Returns ``{items, total}``."""
    rows, total = svc.list_expenses(
        db,
        ctx.school.id,
        status=status,
        category_id=category_id,
        cash_account_id=cash_account_id,
        term_id=term_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {"items": [ExpenseOut.model_validate(row) for row in rows], "total": total}


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(
    payload: ExpenseIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    """Record an expense (draft, approved, or straight to paid for petty cash)."""
    expense = svc.create_expense(db, ctx.school.id, data=payload, recorded_by=ctx.user.id)
    db.commit()
    return _expense_out(db, ctx.school.id, expense.id)


@router.get("/expenses/{expense_id}", response_model=ExpenseOut)
def get_expense(
    expense_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
):
    svc.get_expense(db, expense_id, ctx.school.id)
    return _expense_out(db, ctx.school.id, expense_id)


def _expense_out(db, school_id, expense_id):
    return ExpenseOut.model_validate(
        svc.expense_to_dict(db, svc.get_expense(db, expense_id, school_id))
    )


@router.put("/expenses/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    svc.update_expense(db, expense_id, ctx.school.id, data=payload)
    db.commit()
    return _expense_out(db, ctx.school.id, expense_id)


@router.post("/expenses/{expense_id}/approve", response_model=ExpenseOut)
def approve_expense(
    expense_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    svc.approve_expense(db, expense_id, ctx.school.id, approved_by=ctx.user.id)
    db.commit()
    return _expense_out(db, ctx.school.id, expense_id)


@router.post("/expenses/{expense_id}/reject", response_model=ExpenseOut)
def reject_expense(
    expense_id: uuid.UUID,
    payload: ExpenseRejectIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    svc.reject_expense(
        db, expense_id, ctx.school.id, rejected_by=ctx.user.id, reason=payload.reason
    )
    db.commit()
    return _expense_out(db, ctx.school.id, expense_id)


@router.post("/expenses/{expense_id}/pay", response_model=ExpenseOut)
def pay_expense(
    expense_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    svc.pay_expense(db, expense_id, ctx.school.id, paid_by=ctx.user.id)
    db.commit()
    return _expense_out(db, ctx.school.id, expense_id)


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(
    expense_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_EXPENSES)),
):
    svc.delete_expense(db, expense_id, ctx.school.id)
    db.commit()


# ──────────────────────────────────────────────────────────────────────
# Cashbook & bank reconciliation
# ──────────────────────────────────────────────────────────────────────


@router.get("/cashbook", response_model=CashbookOut)
def get_cashbook(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    cash_account_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    only_unreconciled: bool = Query(False),
):
    """The cashbook for a window, derived from payments, expenses and refunds."""
    return svc.get_cashbook(
        db,
        ctx.school.id,
        cash_account_id=cash_account_id,
        date_from=date_from,
        date_to=date_to,
        only_unreconciled=only_unreconciled,
    )


@router.post("/reconcile")
def reconcile_cashbook_entry(
    payload: ReconcileIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_RECONCILE)),
):
    """Tick (or un-tick) a cashbook entry against a bank statement."""
    result = svc.set_reconciled(
        db,
        ctx.school.id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        reconciled=payload.reconciled,
        bank_reference=payload.bank_reference,
    )
    db.commit()
    return result


# ──────────────────────────────────────────────────────────────────────
# Discounts / scholarships / waivers
# ──────────────────────────────────────────────────────────────────────


@router.get("/discounts", response_model=list[DiscountOut])
def list_discounts(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    student_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(False),
):
    rows = svc.list_discounts(
        db, ctx.school.id, student_id=student_id, active_only=active_only
    )
    return [DiscountOut.model_validate(row) for row in rows]


@router.post("/discounts", response_model=DiscountOut, status_code=201)
def create_discount(
    payload: DiscountIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    discount = svc.create_discount(
        db, ctx.school.id, data=payload, approved_by=ctx.user.id
    )
    db.commit()
    return _discount_out(db, ctx.school.id, discount.id)


@router.put("/discounts/{discount_id}", response_model=DiscountOut)
def update_discount(
    discount_id: uuid.UUID,
    payload: DiscountIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    svc.update_discount(db, discount_id, ctx.school.id, data=payload)
    db.commit()
    return _discount_out(db, ctx.school.id, discount_id)


def _discount_out(db, school_id, discount_id):
    rows = svc.list_discounts(db, school_id)
    for row in rows:
        if row["id"] == discount_id:
            return DiscountOut.model_validate(row)
    raise ValidationError("Discount not found after save")


@router.delete("/discounts/{discount_id}", status_code=204)
def delete_discount(
    discount_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    svc.delete_discount(db, discount_id, ctx.school.id)
    db.commit()


# ──────────────────────────────────────────────────────────────────────
# Credit notes
# ──────────────────────────────────────────────────────────────────────


@router.get("/credit-notes", response_model=list[CreditNoteOut])
def list_credit_notes(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    student_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
):
    rows = svc.list_credit_notes(db, ctx.school.id, student_id=student_id, status=status)
    return [CreditNoteOut.model_validate(row) for row in rows]


@router.post("/credit-notes", response_model=CreditNoteOut, status_code=201)
def create_credit_note(
    payload: CreditNoteIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    note = svc.create_credit_note(
        db, ctx.school.id, data=payload, issued_by=ctx.user.id
    )
    db.commit()
    return _credit_note_out(db, ctx.school.id, note.id)


@router.post("/credit-notes/{note_id}/apply", response_model=CreditNoteOut)
def apply_credit_note(
    note_id: uuid.UUID,
    payload: CreditNoteApplyIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    svc.apply_credit_note(db, note_id, ctx.school.id, invoice_id=payload.invoice_id)
    db.commit()
    return _credit_note_out(db, ctx.school.id, note_id)


@router.post("/credit-notes/{note_id}/void", response_model=CreditNoteOut)
def void_credit_note(
    note_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    svc.void_credit_note(db, note_id, ctx.school.id)
    db.commit()
    return _credit_note_out(db, ctx.school.id, note_id)


def _credit_note_out(db, school_id, note_id):
    svc.get_credit_note(db, note_id, school_id)
    for row in svc.list_credit_notes(db, school_id):
        if row["id"] == note_id:
            return CreditNoteOut.model_validate(row)
    raise ValidationError("Credit note not found after save")


# ──────────────────────────────────────────────────────────────────────
# Refunds
# ──────────────────────────────────────────────────────────────────────


@router.get("/refunds", response_model=list[RefundOut])
def list_refunds(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    student_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
):
    rows = svc.list_refunds(db, ctx.school.id, student_id=student_id, status=status)
    return [RefundOut.model_validate(row) for row in rows]


@router.post("/refunds", response_model=RefundOut, status_code=201)
def create_refund(
    payload: RefundIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    refund = svc.create_refund(
        db, ctx.school.id, data=payload, requested_by=ctx.user.id
    )
    db.commit()
    return _refund_out(db, ctx.school.id, refund.id)


@router.post("/refunds/{refund_id}/approve", response_model=RefundOut)
def approve_refund(
    refund_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    svc.approve_refund(db, refund_id, ctx.school.id, approved_by=ctx.user.id)
    db.commit()
    return _refund_out(db, ctx.school.id, refund_id)


@router.post("/refunds/{refund_id}/reject", response_model=RefundOut)
def reject_refund(
    refund_id: uuid.UUID,
    payload: RefundRejectIn,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
):
    svc.reject_refund(
        db, refund_id, ctx.school.id, rejected_by=ctx.user.id, reason=payload.reason
    )
    db.commit()
    return _refund_out(db, ctx.school.id, refund_id)


@router.post("/refunds/{refund_id}/pay", response_model=RefundOut)
def pay_refund(
    refund_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_AMEND)),
    refund_date: Optional[str] = Query(None),
):
    svc.pay_refund(db, refund_id, ctx.school.id, paid_by=ctx.user.id, refund_date=refund_date)
    db.commit()
    return _refund_out(db, ctx.school.id, refund_id)


def _refund_out(db, school_id, refund_id):
    svc.get_refund(db, refund_id, school_id)
    for row in svc.list_refunds(db, school_id):
        if row["id"] == refund_id:
            return RefundOut.model_validate(row)
    raise ValidationError("Refund not found after save")


# ──────────────────────────────────────────────────────────────────────
# Debtors
# ──────────────────────────────────────────────────────────────────────


@router.get("/debtors", response_model=DebtorsOut)
def get_debtors(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
    term_id: Optional[uuid.UUID] = Query(None),
    arm_id: Optional[uuid.UUID] = Query(None),
):
    """Outstanding fees with aging buckets, for chasing who owes what."""
    return svc.get_debtors(db, ctx.school.id, term_id=term_id, arm_id=arm_id)


# ──────────────────────────────────────────────────────────────────────
# Reports
# ──────────────────────────────────────────────────────────────────────


@router.get("/reports/income-expenditure", response_model=IncomeExpenditureOut)
def income_expenditure_report(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_REPORTS)),
    term_id: Optional[uuid.UUID] = Query(None),
    session_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    return svc.income_expenditure(
        db,
        ctx.school.id,
        term_id=term_id,
        session_id=session_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/reports/collection", response_model=CollectionReportOut)
def collection_report(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_REPORTS)),
    term_id: Optional[uuid.UUID] = Query(None),
    session_id: Optional[uuid.UUID] = Query(None),
):
    return svc.collection_report(
        db, ctx.school.id, term_id=term_id, session_id=session_id
    )


@router.get("/reports/cash-position", response_model=CashPositionOut)
def cash_position_report(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_REPORTS)),
):
    return svc.cash_position(db, ctx.school.id)


# ──────────────────────────────────────────────────────────────────────
# Accountant logins (own credentials, per school)
# ──────────────────────────────────────────────────────────────────────


@router.get("/accountants", response_model=list[AccountantOut])
def list_accountants(
    db: DbSession,
    ctx=Depends(require_accountant(ACCOUNTING_VIEW)),
):
    """Who holds the Accountant role in this school."""
    return [AccountantOut.model_validate(row) for row in svc.list_accountants(db, ctx.school.id, ROLE_ACCOUNTANT)]


@router.post("/accountants", response_model=AccountantOut, status_code=201)
def create_accountant(
    payload: AccountantCreateIn,
    db: DbSession,
    ctx=Depends(require_permission(USERS_MANAGE)),
):
    """Give a school accountant their own login (staff record + membership).

    A school-admin action (``users.manage``), not a ledger one: the office that
    hands out credentials is not the same as the office that keeps the books.
    The resulting membership carries the **Accountant** role for *this* school,
    so the accountant signs in with their own email and sees only this school.
    """
    role = db.scalar(
        select(Role).where(Role.school_id == ctx.school.id, Role.code == ROLE_ACCOUNTANT)
    )
    if role is None:
        raise ValidationError(
            "This school has no Accountant role; re-run the role setup first."
        )

    staff = people_service.create_staff(
        db,
        ctx.school.id,
        staff_no=payload.staff_no or f"ACC-{uuid.uuid4().hex[:6].upper()}",
        full_name=payload.full_name,
        membership_type="non_teaching",
        phone=payload.phone,
        email=str(payload.email),
        joined_date=date.today(),
    )
    staff, role = people_service.create_staff_account(
        db,
        ctx.school.id,
        staff.id,
        email=str(payload.email),
        password=payload.password,
        role_id=role.id,
    )
    db.commit()
    return AccountantOut(
        user_id=staff.user_id,
        staff_id=staff.id,
        email=staff.user.email if staff.user else str(payload.email).strip().lower(),
        full_name=staff.full_name,
        school_id=ctx.school.id,
        role_code=role.code,
        role_name=role.name,
        has_login=True,
    )
