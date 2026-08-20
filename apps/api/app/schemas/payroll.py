"""Payroll schemas: salary structures, staff assignments, pay runs, payslips."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SalaryStructureIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    basic_salary: float = Field(..., gt=0)
    tax_percent: float = Field(0, ge=0, le=100)
    is_active: bool = Field(True)


class SalaryStructureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    basic_salary: float
    tax_percent: float
    is_active: bool
    created_at: datetime


class StaffSalaryIn(BaseModel):
    staff_id: uuid.UUID = Field(...)
    structure_id: uuid.UUID = Field(...)
    effective_from: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class StaffSalaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staff_id: uuid.UUID
    structure_id: uuid.UUID
    effective_from: Optional[str]
    staff_name: Optional[str] = None
    structure_name: Optional[str] = None


class PayRunCreate(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")


class PayslipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staff_id: uuid.UUID
    staff_name: Optional[str] = None
    structure_id: Optional[uuid.UUID]
    gross: float
    tax: float
    net: float


class PayRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    month: str
    status: str
    total_gross: float
    total_tax: float
    total_net: float
    paid_at: Optional[datetime]


class PayRunDetailOut(PayRunOut):
    payslips: list[PayslipOut] = Field(default_factory=list)
