"""Accounting schemas: expenses, cash accounts, discounts, credit notes,
refunds, the cashbook read model, and the accountant's reports."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

_DATE = r"^\d{4}-\d{2}-\d{2}$"

ExpenseStatus = Literal["draft", "approved", "paid", "rejected"]
RefundStatus = Literal["pending", "approved", "paid", "rejected"]
CreditNoteStatus = Literal["open", "applied", "void"]
CashAccountKind = Literal["bank", "cash", "petty_cash"]
DiscountKind = Literal[
    "discount", "scholarship", "bursary", "staff_child", "sibling", "waiver"
]


# ──────────────────────────────────────────────────────────────────────
# Expense categories
# ──────────────────────────────────────────────────────────────────────


class ExpenseCategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = True


class ExpenseCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    is_active: bool


# ──────────────────────────────────────────────────────────────────────
# Cash accounts
# ──────────────────────────────────────────────────────────────────────


class CashAccountIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: CashAccountKind = "bank"
    bank_name: Optional[str] = Field(None, max_length=160)
    account_number: Optional[str] = Field(None, max_length=40)
    currency: str = Field("NGN", max_length=3)
    opening_balance: float = Field(0, ge=0)
    is_active: bool = True
    is_default: bool = False


class CashAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    bank_name: Optional[str]
    account_number: Optional[str]
    currency: str
    opening_balance: float
    is_active: bool
    is_default: bool
    # Computed for the account list: opening balance + everything posted in - out.
    balance: Optional[float] = None


# ──────────────────────────────────────────────────────────────────────
# Expenses & petty cash
# ──────────────────────────────────────────────────────────────────────


class ExpenseIn(BaseModel):
    description: str = Field(..., min_length=1, max_length=300)
    amount: float = Field(..., gt=0)
    expense_date: str = Field(..., pattern=_DATE)
    payment_method: str = Field(..., max_length=30)
    category_id: Optional[uuid.UUID] = None
    cash_account_id: Optional[uuid.UUID] = None
    payee: Optional[str] = Field(None, max_length=160)
    reference: Optional[str] = Field(None, max_length=100)
    currency: str = Field("NGN", max_length=3)
    term_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    attachment_url: Optional[str] = None
    requires_approval: bool = False
    # Post straight to "paid" in one step (petty cash). Ignored when the expense
    # requires approval — an approver must clear it first.
    mark_paid: bool = False


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    voucher_number: str
    category_id: Optional[uuid.UUID]
    category_name: Optional[str] = None
    description: str
    payee: Optional[str]
    amount: float
    currency: str
    expense_date: str
    payment_method: str
    cash_account_id: Optional[uuid.UUID]
    cash_account_name: Optional[str] = None
    reference: Optional[str]
    status: str
    requires_approval: bool
    term_id: Optional[uuid.UUID]
    session_id: Optional[uuid.UUID]
    notes: Optional[str]
    attachment_url: Optional[str]
    created_at: datetime
    approved_at: Optional[datetime]
    paid_at: Optional[datetime]
    rejected_reason: Optional[str]
    reconciled: bool
    reconciled_at: Optional[datetime]
    bank_reference: Optional[str]


class ExpenseRejectIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


# ──────────────────────────────────────────────────────────────────────
# Cashbook + bank reconciliation
# ──────────────────────────────────────────────────────────────────────


class CashbookLine(BaseModel):
    """One money movement in the cashbook (derived from a real document)."""

    source_type: str  # "payment" | "expense" | "refund" | "opening"
    source_id: Optional[uuid.UUID]
    direction: str  # "in" | "out"
    entry_date: Optional[str]
    description: str
    reference: Optional[str]
    amount: float
    cash_account_id: Optional[uuid.UUID]
    cash_account_name: Optional[str]
    reconciled: bool
    bank_reference: Optional[str]


class CashbookOut(BaseModel):
    lines: list[CashbookLine]
    total_in: float
    total_out: float
    net: float
    opening: float
    closing: float
    reconciled_count: int
    unreconciled_count: int


class ReconcileIn(BaseModel):
    """Mark a cashbook document as matched (or not) to a bank statement line."""

    source_type: Literal["payment", "expense", "refund"]
    source_id: uuid.UUID
    reconciled: bool = True
    bank_reference: Optional[str] = Field(None, max_length=100)


# ──────────────────────────────────────────────────────────────────────
# Discounts / scholarships / waivers
# ──────────────────────────────────────────────────────────────────────


class DiscountIn(BaseModel):
    student_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=120)
    kind: DiscountKind = "discount"
    percent: Optional[float] = Field(None, gt=0, le=100)
    amount: Optional[float] = Field(None, gt=0)
    fee_structure_id: Optional[uuid.UUID] = None
    term_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    is_active: bool = True

    @model_validator(mode="after")
    def _exactly_one_of_percent_or_amount(self):
        # Mirrors the DB check constraint, so the caller gets a clear 422 naming
        # the field instead of an integrity error from Postgres.
        if (self.percent is None) == (self.amount is None):
            raise ValueError("Provide exactly one of percent or amount")
        return self


class DiscountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    student_name: Optional[str] = None
    admission_no: Optional[str] = None
    name: str
    kind: str
    percent: Optional[float]
    amount: Optional[float]
    fee_structure_id: Optional[uuid.UUID]
    fee_structure_name: Optional[str] = None
    term_id: Optional[uuid.UUID]
    session_id: Optional[uuid.UUID]
    is_active: bool
    notes: Optional[str]
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────
# Credit notes
# ──────────────────────────────────────────────────────────────────────


class CreditNoteIn(BaseModel):
    student_id: uuid.UUID
    amount: float = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=500)
    invoice_id: Optional[uuid.UUID] = None


class CreditNoteApplyIn(BaseModel):
    invoice_id: uuid.UUID


class CreditNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    note_number: str
    student_id: uuid.UUID
    student_name: Optional[str] = None
    admission_no: Optional[str] = None
    invoice_id: Optional[uuid.UUID]
    invoice_reference: Optional[str] = None
    amount: float
    reason: Optional[str]
    status: str
    issued_date: str
    applied_invoice_id: Optional[uuid.UUID]
    applied_at: Optional[datetime]
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────
# Refunds
# ──────────────────────────────────────────────────────────────────────


class RefundIn(BaseModel):
    student_id: uuid.UUID
    amount: float = Field(..., gt=0)
    method: str = Field(..., max_length=30)
    payment_id: Optional[uuid.UUID] = None
    reference: Optional[str] = Field(None, max_length=100)
    reason: Optional[str] = Field(None, max_length=500)
    currency: str = Field("NGN", max_length=3)
    cash_account_id: Optional[uuid.UUID] = None
    refund_date: Optional[str] = Field(None, pattern=_DATE)
    # Record an already-completed refund in one step.
    mark_paid: bool = False


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    student_name: Optional[str] = None
    admission_no: Optional[str] = None
    payment_id: Optional[uuid.UUID]
    amount: float
    currency: str
    method: str
    reference: Optional[str]
    reason: Optional[str]
    status: str
    cash_account_id: Optional[uuid.UUID]
    refund_date: Optional[str]
    reconciled: bool
    created_at: datetime
    approved_at: Optional[datetime] = None


class RefundRejectIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


# ──────────────────────────────────────────────────────────────────────
# Debtors (aging)
# ──────────────────────────────────────────────────────────────────────


class DebtorRow(BaseModel):
    student_id: uuid.UUID
    admission_no: str
    full_name: str
    arm_name: Optional[str]
    # Primary guardian, so the accountant can send a fee reminder straight away.
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[str] = None
    invoiced: float
    paid: float
    balance: float
    # Aging buckets by how far past the invoice due date the balance sits.
    current: float      # not yet due
    days_1_30: float
    days_31_60: float
    days_61_90: float
    days_90_plus: float
    oldest_due_date: Optional[str]
    invoice_count: int


class DebtorsOut(BaseModel):
    currency: str
    rows: list[DebtorRow]
    total_outstanding: float
    buckets: dict[str, float]
    student_count: int


# ──────────────────────────────────────────────────────────────────────
# Reports
# ──────────────────────────────────────────────────────────────────────


class IncomeExpenditureOut(BaseModel):
    """Income & expenditure statement for a term/session window."""

    period_label: str
    currency: str
    term_id: Optional[uuid.UUID]
    session_id: Optional[uuid.UUID]
    # Income
    fee_collections: float
    other_income: float
    total_income: float
    # Expenditure
    expenses_by_category: list[dict]
    total_expenditure: float
    # Result
    surplus: float
    surplus_label: str  # "surplus" | "deficit"


class CollectionReportRow(BaseModel):
    arm_id: Optional[uuid.UUID]
    arm_name: Optional[str]
    students: int
    invoiced: float
    collected: float
    outstanding: float
    collection_rate: float  # 0-100


class CollectionReportOut(BaseModel):
    currency: str
    rows: list[CollectionReportRow]
    total_invoiced: float
    total_collected: float
    total_outstanding: float
    collection_rate: float


class CashPositionRow(BaseModel):
    cash_account_id: uuid.UUID
    name: str
    kind: str
    opening_balance: float
    total_in: float
    total_out: float
    balance: float
    unreconciled_amount: float


class CashPositionOut(BaseModel):
    currency: str
    rows: list[CashPositionRow]
    total_balance: float
    total_unreconciled: float


# ──────────────────────────────────────────────────────────────────────
# Dashboard summary
# ──────────────────────────────────────────────────────────────────────


class AccountingSummaryOut(BaseModel):
    currency: str
    # Outstanding student fees (the accountant's headline number).
    outstanding_fees: float
    collected_this_term: float
    expenses_this_term: float
    surplus_this_term: float
    # Operational counters
    pending_expense_approvals: int
    pending_refunds: int
    open_credit_notes: int
    unreconciled_cashbook_entries: int
    cash_position: float
    debtors_over_90_days: float


# ──────────────────────────────────────────────────────────────────────
# Accountant accounts (own login details, per school)
# ──────────────────────────────────────────────────────────────────────


class AccountantCreateIn(BaseModel):
    """Provision a login for a school accountant.

    Creates the staff record, the global user, and the *school-scoped*
    membership carrying the Accountant role — so the accountant signs in with
    their own credentials and can act on this school only.
    """

    full_name: str = Field(..., min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    phone: Optional[str] = Field(None, max_length=40)
    staff_no: Optional[str] = Field(None, max_length=40)


class AccountantOut(BaseModel):
    user_id: uuid.UUID
    staff_id: Optional[uuid.UUID]
    email: str
    full_name: str
    school_id: uuid.UUID
    role_code: str
    role_name: str
    has_login: bool
