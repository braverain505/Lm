"""Fees, invoices, and payments schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, validator


# ──────────────────────────────────────────────────────────────────────
# FeeStructure
# ──────────────────────────────────────────────────────────────────────


class FeeStructureIn(BaseModel):
    """Input for creating/updating a fee structure."""

    name: str = Field(..., min_length=1, max_length=120, description="Fee structure name")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    fee_type: str = Field(..., description="Type of fee: tuition, boarding, activity, examination, etc.")
    amount: float = Field(..., gt=0, description="Fee amount")
    currency: str = Field("NGN", max_length=3, description="Currency code (ISO 4217)")
    billing_frequency: str = Field("term", max_length=20, description="term|month|year|one_time")
    applicable_to: Optional[str] = Field(
        None, max_length=40, description="'all', 'specific_class', or 'specific_arm'"
    )
    class_arm_id: Optional[uuid.UUID] = Field(
        None, description="Required if applicable_to is class-scoped"
    )
    effective_from: Optional[str] = Field(
        None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD"
    )
    effective_to: Optional[str] = Field(
        None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD"
    )
    is_mandatory: bool = Field(True, description="Whether this fee is mandatory")
    allow_override: bool = Field(False, description="Whether school can override amount")

    @validator("class_arm_id")
    def require_class_arm_if_class_scoped(cls, v, values):
        applicable = values.data.get("applicable_to") if hasattr(values, "data") else getattr(values, "applicable_to", None)
        if applicable in ("specific_class", "specific_arm") and v is None:
            raise ValueError("class_arm_id is required when applicable_to is class-scoped")
        return v


class FeeStructureOut(BaseModel):
    """Output schema for fee structure."""

    id: uuid.UUID
    name: str
    description: Optional[str]
    fee_type: str
    amount: float
    currency: str
    billing_frequency: str
    applicable_to: Optional[str]
    class_arm_id: Optional[uuid.UUID]
    effective_from: Optional[str]
    effective_to: Optional[str]
    is_mandatory: bool
    allow_override: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────
# Invoice
# ──────────────────────────────────────────────────────────────────────


class InvoiceIn(BaseModel):
    """Input for creating an invoice."""

    student_id: uuid.UUID = Field(..., description="Student to invoice")
    fee_structure_id: uuid.UUID = Field(..., description="Fee structure to invoice")
    term_id: Optional[uuid.UUID] = Field(None, description="Academic term")
    batch_number: str = Field(..., min_length=1, description="Batch reference number")


class InvoiceOut(BaseModel):
    """Output schema for invoice."""

    id: uuid.UUID
    student_id: uuid.UUID
    fee_structure_id: uuid.UUID
    term_id: Optional[uuid.UUID]
    batch_number: str
    reference_number: str
    subtotal: float
    discount_amount: float
    tax_amount: float
    total_amount: float
    status: str
    issue_date: date
    due_date: date
    paid_date: Optional[date]
    payment_method: Optional[str]
    transaction_id: Optional[str]
    payment_reference: Optional[str]
    notes: Optional[str]
    student: Optional["StudentOut"] = None

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────
# Payment
# ──────────────────────────────────────────────────────────────────────


class PaymentIn(BaseModel):
    """Input for recording a payment."""

    invoice_id: uuid.UUID = Field(..., description="Invoice to record payment against")
    student_id: Optional[uuid.UUID] = Field(
        None, description="Student the payment is for (defaults to the invoice's student)"
    )
    amount: float = Field(..., gt=0, description="Payment amount")
    payment_method: str = Field(
        ..., description="cash|card|bank_transfer|paystack|flutterwave|pos|other"
    )
    payment_reference: Optional[str] = Field(None, max_length=100)
    transaction_id: Optional[str] = Field(None, max_length=100)


class PaymentOut(BaseModel):
    """Output schema for payment."""

    id: uuid.UUID
    invoice_id: uuid.UUID
    student_id: Optional[uuid.UUID]
    amount: float
    payment_method: str
    payment_reference: Optional[str]
    transaction_id: Optional[str]
    receipt_number: Optional[str]
    payment_date: date

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────
# Student Fee Balance
# ──────────────────────────────────────────────────────────────────────


class StudentFeeBalanceOut(BaseModel):
    """Output schema for student fee balance."""

    id: uuid.UUID
    student_id: uuid.UUID
    school_id: uuid.UUID
    total_owed: float
    total_paid: float
    total_unpaid: float
    current_invoice_total: float
    current_invoice_due: Optional[date]
    period_start: date
    period_end: date
    calculated_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────────────────────────────
# Payment receipt
# ──────────────────────────────────────────────────────────────────────


class ReceiptPaymentLine(BaseModel):
    """One payment line shown on a receipt."""

    receipt_number: Optional[str]
    amount: float
    payment_method: str
    payment_date: Optional[date]


class ReceiptSchool(BaseModel):
    name: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    logo_url: Optional[str]
    currency: str


class ReceiptStudent(BaseModel):
    id: uuid.UUID
    admission_no: str
    full_name: str


class ReceiptOut(BaseModel):
    """Printable receipt for a recorded payment."""

    receipt_number: Optional[str]
    payment_date: Optional[date]
    payment_method: str
    payment_reference: Optional[str]
    transaction_id: Optional[str]
    amount_paid: float
    invoice_total: float
    paid_total: float
    balance_due: float
    invoice_status: str
    invoice_reference: str
    invoice_issue_date: Optional[date]
    invoice_due_date: Optional[date]
    fee_structure_name: Optional[str]
    term_id: Optional[uuid.UUID]
    school: ReceiptSchool
    student: ReceiptStudent
    invoice_payments: list[ReceiptPaymentLine]


# ──────────────────────────────────────────────────────────────────────
# Payment status (paid / not-paid tracking)
# ──────────────────────────────────────────────────────────────────────


class PaymentStatusRow(BaseModel):
    student_id: uuid.UUID
    admission_no: str
    full_name: str
    arm_name: Optional[str]
    invoiced: float
    paid: float
    balance: float
    status: str  # "paid" | "partial" | "unpaid"


class PaymentStatusOut(BaseModel):
    summary: dict[str, int]
    students: list[PaymentStatusRow]


# ──────────────────────────────────────────────────────────────────────
# Helper schemas
# ──────────────────────────────────────────────────────────────────────


class StudentOut(BaseModel):
    """Minimal student info for invoice output."""

    id: uuid.UUID
    admission_no: str
    first_name: str
    last_name: str
    full_name: str

    class Config:
        from_attributes = True