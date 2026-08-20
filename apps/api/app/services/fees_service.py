"""Fees, payments, invoices, and billing service layer."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    ClassArm,
    School,
    Student,
    StudentEnrollment,
    FeeStructure,
    Invoice,
    Payment,
    StudentFeeBalance,
    Term,
)
from ..models.fees import FeeStructure as FeeStructureModel
from ..schemas.fees import (
    FeeStructureIn,
    InvoiceIn,
    PaymentIn,
)


def _validate_scope_targets(db: Session, school_id: uuid.UUID, data: FeeStructureIn) -> None:
    """A class-scoped fee ('specific_class'/'specific_arm') must point at an arm
    that actually belongs to the school — otherwise a cross-school reference
    leaks."""
    if data.applicable_to in ("specific_class", "specific_arm"):
        if data.class_arm_id is None:
            raise ValidationError("class_arm_id is required for class-scoped fees")
        arm = db.get(ClassArm, data.class_arm_id)
        if arm is None or arm.school_id != school_id:
            raise NotFoundError("Class not found")


# ──────────────────────────────────────────────────────────────────────
# FeeStructure
# ──────────────────────────────────────────────────────────────────────


def list_fee_structures(
    db: Session,
    school_id: uuid.UUID,
    *,
    fee_type: str | None = None,
    is_mandatory: bool | None = None,
    active_only: bool = True,
) -> list[FeeStructureModel]:
    """List fee structures for a school."""
    stmt = select(FeeStructureModel).where(FeeStructureModel.school_id == school_id)
    if fee_type:
        stmt = stmt.where(FeeStructureModel.fee_type == fee_type)
    if is_mandatory is not None:
        stmt = stmt.where(FeeStructureModel.is_mandatory == is_mandatory)
    if active_only:
        stmt = stmt.where(FeeStructureModel.is_active.is_(True))
    stmt = stmt.order_by(FeeStructureModel.name)
    return list(db.scalars(stmt))


def get_fee_structure(
    db: Session, fee_structure_id: uuid.UUID, school_id: uuid.UUID
) -> FeeStructureModel:
    """Get a single fee structure, verifying school ownership."""
    fs = db.get(FeeStructureModel, fee_structure_id)
    if fs is None or fs.school_id != school_id:
        raise NotFoundError("Fee structure not found")
    return fs


def create_fee_structure(
    db: Session,
    school_id: uuid.UUID,
    *,
    data: FeeStructureIn,
    created_by: uuid.UUID,
) -> FeeStructureModel:
    """Create a new fee structure."""
    # Check for duplicate name within school
    existing = db.scalar(
        select(FeeStructureModel).where(
            FeeStructureModel.school_id == school_id,
            FeeStructureModel.name == data.name,
        )
    )
    if existing:
        raise ValidationError("A fee structure with this name already exists")

    _validate_scope_targets(db, school_id, data)

    fs = FeeStructureModel(
        school_id=school_id,
        name=data.name,
        description=data.description,
        fee_type=data.fee_type,
        amount=Decimal(str(data.amount)),
        currency=data.currency,
        billing_frequency=data.billing_frequency,
        applicable_to=data.applicable_to,
        class_arm_id=(
            data.class_arm_id if data.applicable_to in ("specific_class", "specific_arm") else None
        ),
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        is_mandatory=data.is_mandatory,
        allow_override=data.allow_override,
        is_active=True,
    )
    db.add(fs)
    db.flush()
    return fs


def update_fee_structure(
    db: Session,
    fee_structure_id: uuid.UUID,
    school_id: uuid.UUID,
    *,
    data: FeeStructureIn,
    updated_by: uuid.UUID,
) -> FeeStructureModel:
    """Update a fee structure."""
    fs = get_fee_structure(db, fee_structure_id, school_id)
    # Prevent name clash
    other = db.scalar(
        select(FeeStructureModel).where(
            FeeStructureModel.school_id == school_id,
            FeeStructureModel.name == data.name,
            FeeStructureModel.id != fee_structure_id,
        )
    )
    if other:
        raise ValidationError("Another fee structure with this name already exists")

    _validate_scope_targets(db, school_id, data)

    fs.name = data.name
    fs.description = data.description
    fs.fee_type = data.fee_type
    fs.amount = Decimal(str(data.amount))
    fs.currency = data.currency
    fs.billing_frequency = data.billing_frequency
    fs.applicable_to = data.applicable_to
    fs.class_arm_id = (
        data.class_arm_id if data.applicable_to in ("specific_class", "specific_arm") else None
    )
    fs.effective_from = data.effective_from
    fs.effective_to = data.effective_to
    fs.is_mandatory = data.is_mandatory
    fs.allow_override = data.allow_override
    db.flush()
    return fs


def toggle_fee_structure_status(
    db: Session, fee_structure_id: uuid.UUID, school_id: uuid.UUID
) -> FeeStructureModel:
    """Toggle active/inactive status."""
    fs = get_fee_structure(db, fee_structure_id, school_id)
    fs.is_active = not fs.is_active
    db.flush()
    return fs


# ──────────────────────────────────────────────────────────────────────
# Invoice
# ──────────────────────────────────────────────────────────────────────


def create_invoice(
    db: Session,
    *,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    fee_structure_id: uuid.UUID,
    term_id: uuid.UUID | None,
    batch_number: str,
    issued_by: uuid.UUID,
) -> Invoice:
    """Create a new invoice for a student."""
    # Verify student belongs to school
    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id:
        raise NotFoundError("Student not found")

    # Verify fee structure belongs to school
    fee_structure = get_fee_structure(db, fee_structure_id, school_id)

    # Check if student already has an invoice for this fee structure + term
    existing = db.scalar(
        select(Invoice).where(
            Invoice.student_id == student_id,
            Invoice.fee_structure_id == fee_structure_id,
            Invoice.term_id == term_id,
            Invoice.school_id == school_id,
        )
    )
    if existing:
        # Return existing draft or send existing
        if existing.status in ("draft", "sent"):
            # Update due date and send
            from datetime import datetime as dt_mod
            base_date = dt_mod.now().date()
            due = base_date + timedelta(days=_due_days(fee_structure.billing_frequency))
            existing.due_date = due.isoformat()
            existing.status = "sent"
            existing.issue_date = base_date.isoformat()
            db.flush()
            return existing
        return existing

    # Calculate amounts
    subtotal = float(fee_structure.amount)
    discount_amount = Decimal("0")
    tax_amount = Decimal("0")
    total_amount = subtotal + float(discount_amount) + float(tax_amount)

    # Generate batch/reference numbers
    import uuid as uuid_mod
    ref = f"INV-{school_id.hex[:8].upper()}-{student_id.hex[:8].upper()}-{uuid_mod.uuid4().hex[:6].upper()}"

    now = datetime.now().date()
    due = now + timedelta(days=_due_days(fee_structure.billing_frequency))

    invoice = Invoice(
        school_id=school_id,
        student_id=student_id,
        fee_structure_id=fee_structure_id,
        term_id=term_id,
        batch_number=batch_number,
        reference_number=ref,
        subtotal=subtotal,
        discount_amount=float(discount_amount),
        tax_amount=float(tax_amount),
        total_amount=total_amount,
        status="draft",
        issue_date=now.isoformat(),
        due_date=due.isoformat(),
    )
    db.add(invoice)
    db.flush()
    return invoice


def _due_days(frequency: str) -> int:
    """Return due days from now based on billing frequency."""
    mapping = {"term": 30, "month": 30, "year": 365, "one_time": 14}
    return mapping.get(frequency, 30)


def list_invoices(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Invoice], int]:
    """List invoices for a school."""
    stmt = select(Invoice).where(Invoice.school_id == school_id)
    if student_id:
        stmt = stmt.where(Invoice.student_id == student_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.issue_date.desc())
    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0
    invoices = db.scalars(
        stmt.offset(offset).limit(limit)
    ).all()
    return invoices, total


def get_invoice(
    db: Session, invoice_id: uuid.UUID, school_id: uuid.UUID
) -> Invoice:
    """Get a single invoice, verifying school ownership."""
    inv = db.get(Invoice, invoice_id)
    if inv is None or inv.school_id != school_id:
        raise NotFoundError("Invoice not found")
    return inv


def record_payment(
    db: Session,
    *,
    invoice_id: uuid.UUID,
    student_id: uuid.UUID,
    amount: float,
    payment_method: str,
    school_id: uuid.UUID,
    payment_reference: str | None = None,
    transaction_id: str | None = None,
    recorded_by: uuid.UUID,
) -> Payment:
    """Record a payment against an invoice, updating the invoice status."""
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.school_id != school_id:
        raise NotFoundError("Invoice not found")

    if student_id is None:
        student_id = invoice.student_id

    # Verify the student belongs to the same school as the invoice.
    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id:
        raise NotFoundError("Student not found")

    # Check if invoice already has enough payments
    existing_total = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .select_from(Payment)
        .where(Payment.invoice_id == invoice_id)
    )

    new_total = float(existing_total) + amount
    total_amount = float(invoice.total_amount)

    # Determine status
    if new_total >= total_amount:
        status = "paid"
    elif new_total > 0:
        status = "partial"
    else:
        status = invoice.status  # keep existing

    payment = Payment(
        school_id=school_id,
        invoice_id=invoice_id,
        student_id=student_id,
        amount=Decimal(str(amount)),
        payment_method=payment_method,
        payment_reference=payment_reference,
        transaction_id=transaction_id,
        payment_date=datetime.utcnow().strftime("%Y-%m-%d"),
        receipt_number=f"RCP-{school_id.hex[:6].upper()}-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(payment)

    # Update invoice status
    invoice.status = status
    if status == "paid":
        invoice.paid_date = datetime.utcnow().strftime("%Y-%m-%d")

    db.flush()
    return payment


def list_payments(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Payment], int]:
    """List payment records for a school, newest first."""
    stmt = select(Payment).where(Payment.school_id == school_id)
    if student_id:
        stmt = stmt.where(Payment.student_id == student_id)
    if invoice_id:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    stmt = stmt.order_by(Payment.payment_date.desc(), Payment.created_at.desc())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    payments = db.scalars(stmt.offset(offset).limit(limit)).all()
    return payments, total


def get_receipt(
    db: Session, school_id: uuid.UUID, payment_id: uuid.UUID
) -> dict:
    """Assemble the full printable receipt payload for a payment."""
    payment = db.get(Payment, payment_id)
    if payment is None or payment.school_id != school_id:
        raise NotFoundError("Payment not found")

    invoice = db.get(Invoice, payment.invoice_id)
    if invoice is None or invoice.school_id != school_id:
        raise NotFoundError("Invoice not found")

    student = db.get(Student, payment.student_id)
    if student is None:
        student = db.get(Student, invoice.student_id)
    if student is None or student.school_id != school_id:
        raise NotFoundError("Student not found")

    fee_structure = db.get(FeeStructure, invoice.fee_structure_id)
    school = db.get(School, school_id)

    # All payments recorded against this invoice (for the paid/balance view).
    invoice_payments = list(
        db.scalars(
            select(Payment)
            .where(Payment.invoice_id == invoice.id, Payment.school_id == school_id)
            .order_by(Payment.payment_date)
        )
    )
    paid_total = float(
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .select_from(Payment)
            .where(Payment.invoice_id == invoice.id)
        )
        or 0
    )
    invoice_total = float(invoice.total_amount)
    balance = round(max(invoice_total - paid_total, 0.0), 2)

    return {
        "receipt_number": payment.receipt_number,
        "payment_date": payment.payment_date,
        "payment_method": payment.payment_method,
        "payment_reference": payment.payment_reference,
        "transaction_id": payment.transaction_id,
        "amount_paid": float(payment.amount),
        "invoice_total": invoice_total,
        "paid_total": round(paid_total, 2),
        "balance_due": balance,
        "invoice_status": invoice.status,
        "invoice_reference": invoice.reference_number,
        "invoice_issue_date": invoice.issue_date,
        "invoice_due_date": invoice.due_date,
        "fee_structure_name": fee_structure.name if fee_structure else None,
        "term_id": str(invoice.term_id) if invoice.term_id else None,
        "school": {
            "name": school.name if school else None,
            "address": school.address if school else None,
            "phone": school.phone if school else None,
            "email": school.email if school else None,
            "logo_url": school.logo_url if school else None,
            "currency": school.currency if school else "NGN",
        },
        "student": {
            "id": str(student.id),
            "admission_no": student.admission_no,
            "full_name": student.full_name,
        },
        "invoice_payments": [
            {
                "receipt_number": p.receipt_number,
                "amount": float(p.amount),
                "payment_method": p.payment_method,
                "payment_date": p.payment_date,
            }
            for p in invoice_payments
        ],
    }


def get_payment_status(
    db: Session,
    school_id: uuid.UUID,
    *,
    term_id: uuid.UUID | None = None,
    arm_id: uuid.UUID | None = None,
) -> dict:
    """Per-student payment status — who has paid and who has not.

    If ``term_id`` is given, only invoices for that term are considered;
    otherwise the student's whole history counts. ``arm_id`` narrows to the
    students enrolled in a specific class arm (current enrollment).
    """
    # Invoices in scope.
    inv_stmt = select(Invoice).where(Invoice.school_id == school_id)
    if term_id:
        inv_stmt = inv_stmt.where(Invoice.term_id == term_id)
    invoices = list(db.scalars(inv_stmt))

    student_ids = {inv.student_id for inv in invoices}
    paid_by = {s: 0.0 for s in student_ids}
    if invoices:
        rows = db.execute(
            select(Payment.student_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.school_id == school_id, Payment.invoice_id.in_([i.id for i in invoices]))
            .group_by(Payment.student_id)
        ).all()
        for sid, amt in rows:
            if sid is not None:
                paid_by[sid] = float(amt)

    # Student roster: everyone in scope (the whole school, the given arm, or
    # the term's session) — plus anyone with invoices in scope — so the
    # tracking table always shows who has paid and who has not.
    roster: dict[uuid.UUID, Student] = {}
    if student_ids:
        roster = {s.id: s for s in db.scalars(select(Student).where(Student.id.in_(student_ids)))}
    enrolled_students: list[Student] = []
    if arm_id:
        arm = db.get(ClassArm, arm_id)
        if arm is None or arm.school_id != school_id:
            raise NotFoundError("Class arm not found")
        enrolled_students = list(
            db.scalars(
                select(Student)
                .join(StudentEnrollment, StudentEnrollment.student_id == Student.id)
                .where(
                    StudentEnrollment.class_arm_id == arm_id,
                    StudentEnrollment.is_current.is_(True),
                )
            )
        )
    elif term_id:
        term = db.get(Term, term_id)
        if term is not None and term.school_id == school_id:
            enrolled_students = list(
                db.scalars(
                    select(Student)
                    .join(StudentEnrollment, StudentEnrollment.student_id == Student.id)
                    .where(
                        StudentEnrollment.academic_session_id == term.academic_session_id,
                        StudentEnrollment.is_current.is_(True),
                    )
                )
            )
    else:
        enrolled_students = list(
            db.scalars(
                select(Student).where(Student.school_id == school_id)
            )
        )
    for s in enrolled_students:
        roster.setdefault(s.id, s)

    invoiced_by: dict[uuid.UUID, float] = {}
    for inv in invoices:
        invoiced_by[inv.student_id] = invoiced_by.get(inv.student_id, 0.0) + float(inv.total_amount)

    status_counts = {"paid": 0, "partial": 0, "unpaid": 0}
    students: list[dict] = []
    for student in roster.values():
        invoiced = round(invoiced_by.get(student.id, 0.0), 2)
        paid = round(paid_by.get(student.id, 0.0), 2)
        balance = round(max(invoiced - paid, 0.0), 2)
        if invoiced > 0 and balance == 0:
            status = "paid"
        elif paid > 0:
            status = "partial"
        else:
            status = "unpaid"
        status_counts[status] += 1

        arm_name = None
        if arm_id:
            arm_name = arm.full_name
        else:
            enrollment = db.scalar(
                select(StudentEnrollment)
                .where(
                    StudentEnrollment.student_id == student.id,
                    StudentEnrollment.is_current.is_(True),
                )
                .order_by(StudentEnrollment.enrolled_at.desc())
            )
            if enrollment:
                arm_row = db.get(ClassArm, enrollment.class_arm_id)
                arm_name = arm_row.full_name if arm_row else None

        students.append(
            {
                "student_id": str(student.id),
                "admission_no": student.admission_no,
                "full_name": student.full_name,
                "arm_name": arm_name,
                "invoiced": invoiced,
                "paid": paid,
                "balance": balance,
                "status": status,
            }
        )

    students.sort(key=lambda r: (r["status"] != "unpaid", r["full_name"].lower()))
    return {"summary": status_counts, "students": students}


def get_student_fee_balance(
    db: Session, student_id: uuid.UUID, school_id: uuid.UUID
) -> StudentFeeBalance:
    """Calculate current fee balance for a student."""
    from ..models.fees import StudentFeeBalance as BalanceModel

    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id:
        raise NotFoundError("Student not found")

    # Get total unpaid invoices
    total_owed = db.scalar(
        select(func.coalesce(func.sum(Invoice.total_amount), 0))
        .select_from(Invoice)
        .where(
            Invoice.student_id == student_id,
            Invoice.school_id == school_id,
            Invoice.status.notin_(["paid", "write_off", "expired"]),
        )
    ) or 0

    total_paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .select_from(Payment)
        .where(
            Payment.student_id == student_id,
            Payment.school_id == school_id,
            Payment.invoice_id.in_(
                select(Invoice.id).where(Invoice.student_id == student_id)
            ),
        )
    ) or 0

    total_owed = float(total_owed)
    total_paid = float(total_paid)
    total_unpaid = round(max(total_owed - total_paid, 0.0), 2)

    # Current unpaid invoice
    current_invoice = db.scalar(
        select(Invoice)
        .where(
            Invoice.student_id == student_id,
            Invoice.school_id == school_id,
            Invoice.status.in_(["draft", "sent", "partial"]),
        )
        .order_by(Invoice.due_date.asc())
        .limit(1)
    )

    current_invoice_total = float(current_invoice.total_amount) if current_invoice else 0
    current_invoice_due = None
    if current_invoice and current_invoice.due_date:
        current_invoice_due = current_invoice.due_date[:10]

    # Calculate period (current term/month)
    # For simplicity, use current month
    from datetime import datetime as dt_mod
    now = dt_mod.now()
    period_start = now.replace(day=1).strftime("%Y-%m-%d")
    period_end = (now.replace(day=1) + timedelta(days=32)).replace(day=1).strftime(
        "%Y-%m-%d"
    )

    # Check if record exists
    existing = db.scalar(
        select(BalanceModel).where(
            BalanceModel.student_id == student_id,
            BalanceModel.period_start == period_start,
        )
    )

    if existing:
        existing.total_owed = round(total_owed, 2)
        existing.total_paid = round(total_paid, 2)
        existing.total_unpaid = total_unpaid
        existing.current_invoice_total = current_invoice_total
        existing.current_invoice_due = current_invoice_due
        existing.calculated_at = now.strftime("%Y-%m-%d")
        db.flush()
        return existing

    balance = BalanceModel(
        student_id=student_id,
        school_id=school_id,
        total_owed=round(total_owed, 2),
        total_paid=round(total_paid, 2),
        total_unpaid=total_unpaid,
        current_invoice_total=current_invoice_total,
        current_invoice_due=current_invoice_due,
        period_start=period_start,
        period_end=period_end,
        calculated_at=now.strftime("%Y-%m-%d"),
    )
    db.add(balance)
    db.flush()
    return balance


# ──────────────────────────────────────────────────────────────────────
# Audit
# ──────────────────────────────────────────────────────────────────────


def log_fee_action(
    db: Session,
    *,
    school_id: uuid.UUID,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip: str | None = None,
) -> None:
    """Log a fee-related action to the audit trail."""
    from ..models.crosscut import AuditLog

    audit = AuditLog(
        school_id=school_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old=old_values,
        new=new_values,
        ip=ip,
    )
    db.add(audit)
    db.flush()