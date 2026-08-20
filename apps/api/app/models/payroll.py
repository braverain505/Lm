"""Payroll: salary structures, staff assignments, pay runs, and payslips."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class SalaryStructure(TenantScopedBase, Base):
    """A named salary template: monthly basic pay plus a tax rate."""

    __tablename__ = "salary_structures"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    def __repr__(self) -> str:
        return f"SalaryStructure(id={self.id}, name={self.name})"


class StaffSalary(TenantScopedBase, Base):
    """A staff member's current pay assignment.

    One row per staff member; re-assigning updates the row (keeping it simple
    and auditable via created/updated timestamps).
    """

    __tablename__ = "staff_salaries"

    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), index=True, nullable=False
    )
    structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    effective_from: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD

    __table_args__ = (
        UniqueConstraint("school_id", "staff_id", name="uq_staff_salary_school_staff"),
    )

    def __repr__(self) -> str:
        return f"StaffSalary(staff={self.staff_id}, structure={self.structure_id})"


class PayRun(TenantScopedBase, Base):
    """A monthly payroll run over all assigned staff, with a status lifecycle."""

    __tablename__ = "pay_runs"

    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | paid
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("school_id", "month", name="uq_pay_run_school_month"),
    )

    def __repr__(self) -> str:
        return f"PayRun(id={self.id}, month={self.month}, status={self.status})"


class Payslip(TenantScopedBase, Base):
    """One staff member's line within a pay run, with computed gross/tax/net."""

    __tablename__ = "payslips"

    pay_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pay_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="SET NULL"), nullable=True
    )
    gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("pay_run_id", "staff_id", name="uq_payslip_run_staff"),
    )

    def __repr__(self) -> str:
        return f"Payslip(run={self.pay_run_id}, staff={self.staff_id}, net={self.net})"


__all__ = ["SalaryStructure", "StaffSalary", "PayRun", "Payslip"]
