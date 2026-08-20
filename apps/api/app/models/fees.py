"""Fees, payments, invoices, and billing."""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase
from .enums import PaymentStatus, PaymentMethod, InvoiceStatus


class FeeStructure(TenantScopedBase, Base):
    """A fee structure defines what fees a student can be charged and how."""

    __tablename__ = "fee_structures"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # school_id is inherited from TenantScopedBase

    # How the fee is charged
    fee_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # "tuition", "boarding", "activity", "examination", etc.

    # Pricing
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")

    # Billing configuration
    billing_frequency: Mapped[str] = mapped_column(
        String(20), default="term"
    )  # "term", "month", "year", "one_time"

    # Which students/Classes this applies to
    applicable_to: Mapped[str | None] = mapped_column(
        String(40)
    )  # "all", "specific_class", "specific_arm"
    class_arm_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_arms.id", ondelete="SET NULL"), nullable=True
    )

    # Timing
    effective_from: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # YYYY-MM-DD
    effective_to: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # Whether this fee is mandatory
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)

    # Whether the fee structure is currently active (draft/deactivated ones are
    # excluded from invoicing by default)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Per-school overrides allowed
    allow_override: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="fee_structure", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"FeeStructure(id={self.id}, name={self.name}, amount={self.amount})"


class Invoice(TenantScopedBase, Base):
    """An invoice generated from a fee structure for a student."""

    __tablename__ = "invoices"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fee_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="SET NULL"), index=True
    )

    # Billing info
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True
    )
    batch_number: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Amounts
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
    )  # "draft", "sent", "paid", "partial", "write_off", "expired"

    # Timing
    issue_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    paid_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Payment info
    payment_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="invoices")
    fee_structure: Mapped["FeeStructure"] = relationship(
        back_populates="invoices"
    )

    def __repr__(self) -> str:
        return f"Invoice(id={self.id}, student={self.student_id}, total={self.total_amount}, status={self.status})"


class Payment(TenantScopedBase, Base):
    """A payment record received against an invoice."""

    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )

    # Payment details
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # "cash", "card", "transfer", "paystack", "flutterwave", "bank_transfer"
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timing
    payment_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    receipt_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Related records (optional)
    # Could link to a bank transfer, check, etc.

    def __repr__(self) -> str:
        return f"Payment(id={self.id}, invoice={self.invoice_id}, amount={self.amount}, method={self.payment_method})"


class StudentFeeBalance(TenantScopedBase, Base):
    """A denormalized view of a student's current fee balance — used for UI display."""

    __tablename__ = "student_fee_balances"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Balance breakdown
    total_owed: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_paid: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_unpaid: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Current invoice
    current_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    current_invoice_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    current_invoice_due: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Period
    period_start: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    period_end: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Timing
    calculated_at: Mapped[str | None] = mapped_column(String(10), nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "period_start", name="uq_balance_student_period"),
    )

    def __repr__(self) -> str:
        return f"StudentFeeBalance(student={self.student_id}, owed={self.total_owed}, paid={self.total_paid})"


__all__ = ["FeeStructure", "Invoice", "Payment", "StudentFeeBalance"]