"""Accounting: the ledger a school accountant keeps *beyond* fee billing.

Fee billing (``fees.py``) answers "what does a student owe and what have they
paid". Accounting answers the rest of the bursar's desk:

* **Expenses & petty cash** — the money going out (running costs, salaries paid
  outside payroll, stationery, fuel), each posted to a cash/bank account.
* **Cash accounts** — the bank accounts, cash boxes and petty-cash floats the
  money sits in, so the cashbook can be kept per account.
* **Discounts / scholarships / waivers** — standing reductions on a student's
  fees (staff child, sibling, bursary) applied when an invoice is generated.
* **Credit notes** — a formal reduction issued against a raised invoice (e.g.
  the school over-billed, or a student withdrew mid-term).
* **Refunds** — money actually paid back out to a guardian.

Rather than keeping a second, parallel set of money rows that can silently drift
from billing, the cashbook is a *read model* over the documents that already
exist (fee payments in, expenses/refunds out), and each document carries its own
reconciliation marks. There is exactly one place each naira is written down.

Dates are ISO ``YYYY-MM-DD`` strings to match the convention already used
throughout the finance module (``fees.py``); money is ``Numeric(12, 2)``.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class ExpenseCategory(TenantScopedBase, Base):
    """A school's own chart of expense accounts ("Fuel", "Stationery", ...)."""

    __tablename__ = "expense_categories"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_expense_category_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"ExpenseCategory(id={self.id}, name={self.name})"


class CashAccount(TenantScopedBase, Base):
    """A bank account, cash box or petty-cash float the school keeps money in."""

    __tablename__ = "cash_accounts"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_cash_account_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # "bank" | "cash" | "petty_cash"
    kind: Mapped[str] = mapped_column(String(16), default="bank", nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(160))
    account_number: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    opening_balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # The float that new money posts to when the collector does not pick one, so
    # recording a payment never fails for want of an account.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"CashAccount(id={self.id}, name={self.name}, kind={self.kind})"


class Expense(TenantScopedBase, Base):
    """A payment out of the school, with a small approval trail.

    Lifecycle: ``draft`` -> ``approved`` -> ``paid`` (or ``rejected``). Only a
    ``paid`` expense is money that actually left, so only it appears as an
    outflow in the cashbook and in the income & expenditure statement.
    """

    __tablename__ = "expenses"

    voucher_number: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    payee: Mapped[str | None] = mapped_column(String(160))

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")

    expense_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    # "cash" | "bank_transfer" | "card" | "pos" | "cheque" | "other"
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    cash_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cash_accounts.id", ondelete="SET NULL"), nullable=True
    )
    reference: Mapped[str | None] = mapped_column(String(100))

    # "draft" | "approved" | "paid" | "rejected"
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text)
    # Text: attachments are stored as Base64 data URLs, matching photos elsewhere
    # (Render's free tier has ephemeral disk, so file-backed URLs would vanish).
    attachment_url: Mapped[str | None] = mapped_column(Text)

    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_reason: Mapped[str | None] = mapped_column(Text)

    # Bank reconciliation marks (see the cashbook read model in the service).
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bank_reference: Mapped[str | None] = mapped_column(String(100))

    def __repr__(self) -> str:
        return (
            f"Expense(id={self.id}, voucher={self.voucher_number}, "
            f"amount={self.amount}, status={self.status})"
        )


class StudentDiscount(TenantScopedBase, Base):
    """A standing reduction on a student's fees.

    Either a percentage *or* a flat amount — never both (enforced by a check
    constraint), so the intent is never ambiguous. ``fee_structure_id`` scopes it
    to one fee; ``None`` means every fee the student is charged.
    """

    __tablename__ = "student_discounts"
    __table_args__ = (
        CheckConstraint(
            "(percent IS NOT NULL AND amount IS NULL) "
            "OR (percent IS NULL AND amount IS NOT NULL)",
            name="ck_discount_percent_xor_amount",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # "discount" | "scholarship" | "bursary" | "staff_child" | "sibling" | "waiver"
    kind: Mapped[str] = mapped_column(String(24), default="discount", nullable=False)

    percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))

    fee_structure_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="SET NULL"), nullable=True
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"StudentDiscount(id={self.id}, student={self.student_id}, name={self.name})"


class CreditNote(TenantScopedBase, Base):
    """A formal reduction issued against an already-raised invoice.

    Kept ``open`` until it is applied to a specific invoice, at which point it
    increases that invoice's discount and the note becomes ``applied``. A note is
    never deleted — a voided one is marked ``void`` so the trail survives.
    """

    __tablename__ = "credit_notes"

    note_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)

    # "open" | "applied" | "void"
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)

    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_date: Mapped[str] = mapped_column(String(10), nullable=False)

    applied_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"CreditNote(id={self.id}, number={self.note_number}, "
            f"amount={self.amount}, status={self.status})"
        )


class Refund(TenantScopedBase, Base):
    """Money paid back out to a guardian (overpayment, withdrawal, credit)."""

    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    # "cash" | "bank_transfer" | "card" | "cheque" | "other"
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)

    # "pending" | "approved" | "paid" | "rejected"
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    cash_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cash_accounts.id", ondelete="SET NULL"), nullable=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_date: Mapped[str | None] = mapped_column(String(10))

    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bank_reference: Mapped[str | None] = mapped_column(String(100))

    def __repr__(self) -> str:
        return (
            f"Refund(id={self.id}, student={self.student_id}, "
            f"amount={self.amount}, status={self.status})"
        )


__all__ = [
    "CashAccount",
    "CreditNote",
    "Expense",
    "ExpenseCategory",
    "Refund",
    "StudentDiscount",
]
