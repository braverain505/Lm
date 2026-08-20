"""Payroll service layer: salary structures, staff assignments, pay runs."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import Payslip, PayRun, Staff, SalaryStructure, StaffSalary
from ..schemas.payroll import SalaryStructureIn, StaffSalaryIn


def list_salary_structures(
    db: Session, school_id: uuid.UUID, *, active_only: bool = True
) -> list[SalaryStructure]:
    stmt = select(SalaryStructure).where(SalaryStructure.school_id == school_id)
    if active_only:
        stmt = stmt.where(SalaryStructure.is_active.is_(True))
    stmt = stmt.order_by(SalaryStructure.name)
    return list(db.scalars(stmt))


def get_salary_structure(
    db: Session, structure_id: uuid.UUID, school_id: uuid.UUID
) -> SalaryStructure:
    s = db.get(SalaryStructure, structure_id)
    if s is None or s.school_id != school_id:
        raise NotFoundError("Salary structure not found")
    return s


def create_salary_structure(
    db: Session, school_id: uuid.UUID, *, data: SalaryStructureIn
) -> SalaryStructure:
    existing = db.scalar(
        select(SalaryStructure).where(
            SalaryStructure.school_id == school_id,
            SalaryStructure.name == data.name,
        )
    )
    if existing:
        raise ValidationError("A salary structure with this name already exists")

    s = SalaryStructure(
        school_id=school_id,
        name=data.name,
        description=data.description,
        basic_salary=Decimal(str(data.basic_salary)),
        tax_percent=Decimal(str(data.tax_percent)),
        is_active=data.is_active,
    )
    db.add(s)
    db.flush()
    return s


def update_salary_structure(
    db: Session, structure_id: uuid.UUID, school_id: uuid.UUID, *, data: SalaryStructureIn
) -> SalaryStructure:
    s = get_salary_structure(db, structure_id, school_id)
    other = db.scalar(
        select(SalaryStructure).where(
            SalaryStructure.school_id == school_id,
            SalaryStructure.name == data.name,
            SalaryStructure.id != structure_id,
        )
    )
    if other:
        raise ValidationError("Another salary structure with this name already exists")

    s.name = data.name
    s.description = data.description
    s.basic_salary = Decimal(str(data.basic_salary))
    s.tax_percent = Decimal(str(data.tax_percent))
    s.is_active = data.is_active
    db.flush()
    return s


def toggle_salary_structure(
    db: Session, structure_id: uuid.UUID, school_id: uuid.UUID
) -> SalaryStructure:
    s = get_salary_structure(db, structure_id, school_id)
    s.is_active = not s.is_active
    db.flush()
    return s


def assign_staff_salary(
    db: Session, school_id: uuid.UUID, *, data: StaffSalaryIn
) -> StaffSalary:
    staff = db.get(Staff, data.staff_id)
    if staff is None or staff.school_id != school_id:
        raise NotFoundError("Staff member not found")
    get_salary_structure(db, data.structure_id, school_id)

    existing = db.scalar(
        select(StaffSalary).where(
            StaffSalary.school_id == school_id,
            StaffSalary.staff_id == data.staff_id,
        )
    )
    if existing:
        existing.structure_id = data.structure_id
        existing.effective_from = data.effective_from
        db.flush()
        return existing

    assignment = StaffSalary(
        school_id=school_id,
        staff_id=data.staff_id,
        structure_id=data.structure_id,
        effective_from=data.effective_from,
    )
    db.add(assignment)
    db.flush()
    return assignment


def list_staff_salaries(db: Session, school_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(StaffSalary, Staff, SalaryStructure)
        .join(Staff, Staff.id == StaffSalary.staff_id)
        .join(SalaryStructure, SalaryStructure.id == StaffSalary.structure_id)
        .where(StaffSalary.school_id == school_id)
        .order_by(Staff.full_name)
    )
    rows = []
    for assignment, staff, structure in db.execute(stmt).all():
        rows.append(
            {
                "id": assignment.id,
                "staff_id": assignment.staff_id,
                "structure_id": assignment.structure_id,
                "effective_from": assignment.effective_from,
                "staff_name": staff.full_name,
                "structure_name": structure.name,
            }
        )
    return rows


def create_pay_run(
    db: Session, school_id: uuid.UUID, *, month: str, created_by: uuid.UUID
) -> PayRun:
    existing = db.scalar(
        select(PayRun).where(PayRun.school_id == school_id, PayRun.month == month)
    )
    if existing:
        raise ConflictError(f"A pay run for {month} already exists")

    assignments = db.scalars(
        select(StaffSalary).where(StaffSalary.school_id == school_id)
    ).all()

    run = PayRun(school_id=school_id, month=month, status="draft", created_by=created_by)
    db.add(run)
    db.flush()

    total_gross = Decimal("0")
    total_tax = Decimal("0")
    total_net = Decimal("0")

    for assignment in assignments:
        structure = db.get(SalaryStructure, assignment.structure_id)
        if structure is None:
            continue
        gross = structure.basic_salary
        tax = (gross * structure.tax_percent / Decimal("100")).quantize(Decimal("0.01"))
        net = (gross - tax).quantize(Decimal("0.01"))
        db.add(
            Payslip(
                school_id=school_id,
                pay_run_id=run.id,
                staff_id=assignment.staff_id,
                structure_id=assignment.structure_id,
                gross=gross,
                tax=tax,
                net=net,
            )
        )
        total_gross += gross
        total_tax += tax
        total_net += net

    run.total_gross = total_gross
    run.total_tax = total_tax
    run.total_net = total_net
    db.flush()
    return run


def list_pay_runs(db: Session, school_id: uuid.UUID) -> list[PayRun]:
    stmt = (
        select(PayRun)
        .where(PayRun.school_id == school_id)
        .order_by(PayRun.month.desc())
    )
    return list(db.scalars(stmt))


def _payslips_to_dicts(db: Session, school_id: uuid.UUID, run: PayRun) -> list[dict]:
    rows = (
        select(Payslip, Staff)
        .join(Staff, Staff.id == Payslip.staff_id)
        .where(Payslip.school_id == school_id, Payslip.pay_run_id == run.id)
        .order_by(Staff.full_name)
    )
    return [
        {
            "id": p.id,
            "staff_id": p.staff_id,
            "staff_name": staff.full_name,
            "structure_id": p.structure_id,
            "gross": p.gross,
            "tax": p.tax,
            "net": p.net,
        }
        for p, staff in db.execute(rows).all()
    ]


def get_pay_run(db: Session, pay_run_id: uuid.UUID, school_id: uuid.UUID) -> dict:
    run = db.get(PayRun, pay_run_id)
    if run is None or run.school_id != school_id:
        raise NotFoundError("Pay run not found")
    data = {
        "id": run.id,
        "month": run.month,
        "status": run.status,
        "total_gross": run.total_gross,
        "total_tax": run.total_tax,
        "total_net": run.total_net,
        "paid_at": run.paid_at,
        "payslips": _payslips_to_dicts(db, school_id, run),
    }
    return data


def mark_pay_run_paid(db: Session, pay_run_id: uuid.UUID, school_id: uuid.UUID) -> PayRun:
    run = db.get(PayRun, pay_run_id)
    if run is None or run.school_id != school_id:
        raise NotFoundError("Pay run not found")
    if run.status == "paid":
        raise ConflictError("Pay run is already paid")
    run.status = "paid"
    run.paid_at = datetime.now(timezone.utc)
    db.flush()
    return run