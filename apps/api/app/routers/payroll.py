"""Payroll API endpoints: salary structures, assignments, pay runs, payslips."""

import uuid

from fastapi import APIRouter, Depends

from ..core.deps import DbSession, require_permission
from ..core.permissions import PAYROLL_VIEW, PAYROLL_MANAGE
from ..schemas.payroll import (
    PayRunCreate,
    PayRunDetailOut,
    PayRunOut,
    PayslipOut,
    SalaryStructureIn,
    SalaryStructureOut,
    StaffSalaryIn,
    StaffSalaryOut,
)
from ..services.payroll_service import (
    assign_staff_salary,
    create_pay_run,
    create_salary_structure,
    get_pay_run,
    list_pay_runs,
    list_salary_structures,
    list_staff_salaries,
    mark_pay_run_paid,
    toggle_salary_structure,
    update_salary_structure,
)


router = APIRouter(prefix="/payroll", tags=["payroll"])


# ──────────────────────────────────────────────────────────────────────
# Salary Structures
# ──────────────────────────────────────────────────────────────────────


@router.get("/structures", response_model=list[SalaryStructureOut])
def list_structures_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_VIEW)),
    active_only: bool = True,
):
    structures = list_salary_structures(db, ctx.school.id, active_only=active_only)
    return [SalaryStructureOut.model_validate(s) for s in structures]


@router.post("/structures", response_model=SalaryStructureOut, status_code=201)
def create_structure_endpoint(
    payload: SalaryStructureIn,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_MANAGE)),
):
    structure = create_salary_structure(db, ctx.school.id, data=payload)
    db.commit()
    return SalaryStructureOut.model_validate(structure)


@router.put("/structures/{structure_id}", response_model=SalaryStructureOut)
def update_structure_endpoint(
    structure_id: uuid.UUID,
    payload: SalaryStructureIn,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_MANAGE)),
):
    structure = update_salary_structure(db, structure_id, ctx.school.id, data=payload)
    db.commit()
    return SalaryStructureOut.model_validate(structure)


@router.post("/structures/{structure_id}/toggle-status")
def toggle_structure_status_endpoint(
    structure_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_MANAGE)),
):
    structure = toggle_salary_structure(db, structure_id, ctx.school.id)
    db.commit()
    return {"id": str(structure.id), "name": structure.name, "is_active": structure.is_active}


# ──────────────────────────────────────────────────────────────────────
# Staff Salary Assignments
# ──────────────────────────────────────────────────────────────────────


@router.get("/assignments", response_model=list[StaffSalaryOut])
def list_assignments_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_VIEW)),
):
    return list_staff_salaries(db, ctx.school.id)


@router.post("/assignments", response_model=StaffSalaryOut, status_code=201)
def assign_salary_endpoint(
    payload: StaffSalaryIn,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_MANAGE)),
):
    assignment = assign_staff_salary(db, ctx.school.id, data=payload)
    db.commit()
    for row in list_staff_salaries(db, ctx.school.id):
        if row["staff_id"] == assignment.staff_id:
            return StaffSalaryOut.model_validate(row)
    raise RuntimeError("assignment not found after upsert")


# ──────────────────────────────────────────────────────────────────────
# Pay Runs & Payslips
# ──────────────────────────────────────────────────────────────────────


@router.get("/runs", response_model=list[PayRunOut])
def list_runs_endpoint(
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_VIEW)),
):
    return [PayRunOut.model_validate(r) for r in list_pay_runs(db, ctx.school.id)]


@router.post("/runs", response_model=PayRunDetailOut, status_code=201)
def create_run_endpoint(
    payload: PayRunCreate,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_MANAGE)),
):
    run = create_pay_run(db, ctx.school.id, month=payload.month, created_by=ctx.user.id)
    db.commit()
    return PayRunDetailOut.model_validate(get_pay_run(db, run.id, ctx.school.id))


@router.get("/runs/{pay_run_id}", response_model=PayRunDetailOut)
def get_run_endpoint(
    pay_run_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_VIEW)),
):
    return PayRunDetailOut.model_validate(get_pay_run(db, pay_run_id, ctx.school.id))


@router.post("/runs/{pay_run_id}/mark-paid", response_model=PayRunDetailOut)
def mark_run_paid_endpoint(
    pay_run_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(PAYROLL_MANAGE)),
):
    run = mark_pay_run_paid(db, pay_run_id, ctx.school.id)
    db.commit()
    return PayRunDetailOut.model_validate(get_pay_run(db, run.id, ctx.school.id))
