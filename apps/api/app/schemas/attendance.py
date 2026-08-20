"""Attendance tracking schemas."""

from datetime import date as dt_date
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field
from ..models.enums import AttendanceStatus


class StudentAttendanceIn(BaseModel):
    """Input for marking student attendance."""

    student_id: UUID = Field(..., description="Student ID")
    attendance_date: dt_date = Field(..., description="Attendance date (YYYY-MM-DD)")
    status: AttendanceStatus = Field(
        ..., description="Attendance status: present/absent/late/excused"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class StaffAttendanceIn(BaseModel):
    """Input for marking staff attendance."""

    staff_id: UUID = Field(..., description="Staff/teacher ID")
    attendance_date: dt_date = Field(..., description="Attendance date (YYYY-MM-DD)")
    status: AttendanceStatus = Field(
        ..., description="Attendance status: present/absent/late/excused"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class AttendanceSummaryOut(BaseModel):
    """Output schema for monthly attendance summary."""

    student_id: UUID = Field(..., description="Student ID")
    academic_session_id: UUID = Field(..., description="Academic session ID")
    month: str = Field(..., description="Month in YYYY-MM format")
    total_days: int = Field(default=0, description="Total school days in month")
    present_days: int = Field(default=0, description="Days present")
    absent_days: int = Field(default=0, description="Days absent")
    late_days: int = Field(default=0, description="Days late")
    excused_days: int = Field(default=0, description="Days excused")
    percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Attendance percentage"
    )

    class Config:
        from_attributes = True


class AttendanceRecordOut(BaseModel):
    """A single marking of attendance (student or staff)."""

    id: UUID = Field(..., description="Record ID")
    date: str = Field(..., description="Attendance date (YYYY-MM-DD)")
    status: str = Field(..., description="present/absent/late/excused")
    notes: Optional[str] = Field(None, description="Optional notes")
    marked_by: UUID = Field(..., description="ID of the user who marked it")

    class Config:
        from_attributes = True


class StaffAttendanceSummaryOut(BaseModel):
    """Output schema for staff attendance within a date range."""

    staff_id: UUID = Field(..., description="Staff ID")
    total_days: int = Field(..., description="Total days in range")
    present_days: int = Field(..., description="Days present")
    absent_days: int = Field(..., description="Days absent")
    late_days: int = Field(..., description="Days late")
    excused_days: int = Field(..., description="Days excused")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Attendance percentage")


class StudentOut(BaseModel):
    """Minimal student info for output."""

    id: UUID = Field(..., description="Student ID")
    admission_no: str = Field(..., description="Admission number")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    full_name: str = Field(..., description="Full name")

    class Config:
        from_attributes = True


class TeacherOut(BaseModel):
    """Minimal teacher/staff info for output."""

    id: UUID = Field(..., description="Staff ID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    full_name: str = Field(..., description="Full name")

    class Config:
        from_attributes = True