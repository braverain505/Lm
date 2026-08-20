"""Fees and billing API endpoints."""

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..core.deps import DbSession, require_permission
from ..core.errors import NotFoundError, ValidationError
from ..core.permissions import FEES_VIEW, FEES_CREATE, FEES_EDIT, FEES_PAY
from ..models import Payment
from ..schemas.fees import (
    FeeStructureIn,
    FeeStructureOut,
    InvoiceIn,
    InvoiceOut,
    PaymentIn,
    PaymentOut,
    PaymentStatusOut,
    ReceiptOut,
    StudentFeeBalanceOut,
)
from ..services.fees_service import (
    create_fee_structure,
    update_fee_structure,
    toggle_fee_structure_status,
    list_fee_structures,
    get_fee_structure,
    create_invoice,
    list_invoices,
    get_invoice,
    record_payment,
    get_student_fee_balance,
    list_payments,
    get_receipt,
    get_payment_status,
)


router = APIRouter(prefix="/fees", tags=["fees"])


# ──────────────────────────────────────────────────────────────────────
# Fee Structures
# ──────────────────────────────────────────────────────────────────────


@router.get("/structures", response_model=list[FeeStructureOut])
def list_fee_structures_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
    fee_type: Optional[str] = Query(None, description="Filter by fee type"),
    is_mandatory: Optional[bool] = Query(None),
    active_only: bool = Query(True),
):
    """List fee structures for the current school."""
    structures = list_fee_structures(
        db, ctx.school.id, fee_type=fee_type, is_mandatory=is_mandatory, active_only=active_only
    )
    return [FeeStructureOut.model_validate(s) for s in structures]


@router.post("/structures", response_model=FeeStructureOut, status_code=201)
def create_fee_structure_endpoint(
    payload: FeeStructureIn,
    db: DbSession,
    ctx=Depends(require_permission(FEES_CREATE)),
):
    """Create a new fee structure."""
    fs = create_fee_structure(db, school_id=ctx.school.id, data=payload, created_by=ctx.user.id)
    db.commit()
    return FeeStructureOut.model_validate(fs)


@router.put("/structures/{structure_id}", response_model=FeeStructureOut)
def update_fee_structure_endpoint(
    structure_id: uuid.UUID,
    payload: FeeStructureIn,
    db: DbSession,
    ctx=Depends(require_permission(FEES_EDIT)),
):
    """Update a fee structure."""
    fs = update_fee_structure(
        db, structure_id, ctx.school.id, data=payload, updated_by=ctx.user.id
    )
    db.commit()
    return FeeStructureOut.model_validate(fs)


@router.post("/structures/{structure_id}/toggle-status")
def toggle_fee_structure_status_endpoint(
    structure_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(FEES_EDIT)),
):
    """Toggle a fee structure active/inactive status."""
    fs = toggle_fee_structure_status(db, structure_id, ctx.school.id)
    db.commit()
    return {"id": str(fs.id), "is_active": fs.is_active, "name": fs.name}


# ──────────────────────────────────────────────────────────────────────
# Invoices
# ──────────────────────────────────────────────────────────────────────


@router.post("/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice_endpoint(
    payload: InvoiceIn,
    db: DbSession,
    ctx=Depends(require_permission(FEES_CREATE)),
):
    """Create a new invoice for a student."""
    invoice = create_invoice(
        db,
        school_id=ctx.school.id,
        student_id=payload.student_id,
        fee_structure_id=payload.fee_structure_id,
        term_id=payload.term_id,
        batch_number=payload.batch_number,
        issued_by=ctx.user.id,
    )
    db.commit()
    return InvoiceOut.model_validate(invoice)


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
    student_id: Optional[uuid.UUID] = Query(None, description="Filter by student"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List invoices for the current school."""
    invoices, total = list_invoices(
        db, ctx.school.id, student_id=student_id, status=status, limit=limit, offset=offset
    )
    return [InvoiceOut.model_validate(i) for i in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice_endpoint(
    invoice_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
):
    """Get a single invoice."""
    invoice = get_invoice(db, invoice_id, ctx.school.id)
    return InvoiceOut.model_validate(invoice)


# ──────────────────────────────────────────────────────────────────────
# Payments
# ──────────────────────────────────────────────────────────────────────


@router.post("/payments", response_model=PaymentOut, status_code=201)
def record_payment_endpoint(
    payload: PaymentIn,
    db: DbSession,
    ctx=Depends(require_permission(FEES_PAY)),
):
    """Record a payment against an invoice."""
    payment = record_payment(
        db,
        invoice_id=payload.invoice_id,
        student_id=payload.student_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        school_id=ctx.school.id,
        payment_reference=payload.payment_reference,
        transaction_id=payload.transaction_id,
        recorded_by=ctx.user.id,
    )
    db.commit()
    return PaymentOut.model_validate(payment)


@router.get("/payments", response_model=list[PaymentOut])
def list_payments_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
    student_id: Optional[uuid.UUID] = Query(None, description="Filter by student"),
    invoice_id: Optional[uuid.UUID] = Query(None, description="Filter by invoice"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List payment records for the current school."""
    payments, _ = list_payments(
        db, ctx.school.id, student_id=student_id, invoice_id=invoice_id,
        limit=limit, offset=offset,
    )
    return [PaymentOut.model_validate(p) for p in payments]


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment_endpoint(
    payment_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
):
    """Get a single payment record."""
    payment = db.get(Payment, payment_id)
    if payment is None or payment.school_id != ctx.school.id:
        raise NotFoundError("Payment not found")
    return PaymentOut.model_validate(payment)


@router.get("/payments/{payment_id}/receipt", response_model=ReceiptOut)
def get_payment_receipt_endpoint(
    payment_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
):
    """Printable receipt data for a recorded payment."""
    return get_receipt(db, ctx.school.id, payment_id)


# ──────────────────────────────────────────────────────────────────────
# Payment status (paid / not-paid tracking)
# ──────────────────────────────────────────────────────────────────────


@router.get("/status", response_model=PaymentStatusOut)
def get_payment_status_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
    term_id: Optional[uuid.UUID] = Query(None, description="Scope to a term"),
    arm_id: Optional[uuid.UUID] = Query(None, description="Scope to a class arm"),
):
    """Per-student payment status — who has paid and who has not."""
    return get_payment_status(
        db, ctx.school.id, term_id=term_id, arm_id=arm_id
    )


# ──────────────────────────────────────────────────────────────────────
# Student Fee Balance
# ──────────────────────────────────────────────────────────────────────


@router.get("/balances/{student_id}", response_model=StudentFeeBalanceOut)
def get_student_fee_balance_endpoint(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(FEES_VIEW)),
):
    """Get current fee balance for a student."""
    balance = get_student_fee_balance(db, student_id, ctx.school.id)
    return StudentFeeBalanceOut.model_validate(balance)