"""Attendance tracking API endpoints."""

import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from ..core.deps import DbSession, require_permission
from ..core.errors import NotFoundError, ValidationError
from ..core.permissions import ATTENDANCE_MARK, ATTENDANCE_REPORT, ATTENDANCE_VIEW
from ..models import AcademicSession, Staff, Student
from ..schemas.attendance import (
    AttendanceRecordOut,
    AttendanceSummaryOut,
    StaffAttendanceIn,
    StaffAttendanceSummaryOut,
    StudentAttendanceIn,
)
from ..services.attendance_service import (
    get_staff_attendance,
    get_student_attendance,
    get_student_attendance_summary,
    log_attendance_action,
    record_staff_attendance,
    record_student_attendance,
)


router = APIRouter(prefix="/attendance", tags=["attendance"])


# ──────────────────────────────────────────────────────────────────────
# Mark attendance
# ──────────────────────────────────────────────────────────────────────


@router.post("/mark/student", response_model=AttendanceRecordOut, status_code=201)
def mark_student_attendance_endpoint(
    payload: StudentAttendanceIn,
    db: DbSession,
    ctx=Depends(require_permission(ATTENDANCE_MARK)),
):
    """Mark a student's attendance for a date (upsert on the same date)."""
    student = db.get(Student, payload.student_id)
    if student is None or student.school_id != ctx.school.id:
        raise NotFoundError("Student not found")

    record = record_student_attendance(
        db,
        school_id=ctx.school.id,
        student_id=payload.student_id,
        campus_id=None,
        date=payload.attendance_date.isoformat(),
        status=payload.status.value,
        marked_by=ctx.user.id,
        notes=payload.notes,
    )
    log_attendance_action(
        db,
        school_id=ctx.school.id,
        user_id=ctx.user.id,
        action="mark",
        entity_type="student_attendance",
        entity_id=payload.student_id,
        new_values={
            "status": payload.status.value,
            "date": payload.attendance_date.isoformat(),
        },
    )
    db.commit()
    return AttendanceRecordOut.model_validate(record)


@router.post("/mark/staff", response_model=AttendanceRecordOut, status_code=201)
def mark_staff_attendance_endpoint(
    payload: StaffAttendanceIn,
    db: DbSession,
    ctx=Depends(require_permission(ATTENDANCE_MARK)),
):
    """Mark a staff member's attendance for a date (upsert on the same date)."""
    staff = db.get(Staff, payload.staff_id)
    if staff is None or staff.school_id != ctx.school.id:
        raise NotFoundError("Staff member not found")

    record = record_staff_attendance(
        db,
        school_id=ctx.school.id,
        staff_id=payload.staff_id,
        campus_id=None,
        date=payload.attendance_date.isoformat(),
        status=payload.status.value,
        marked_by=ctx.user.id,
        notes=payload.notes,
    )
    log_attendance_action(
        db,
        school_id=ctx.school.id,
        user_id=ctx.user.id,
        action="mark",
        entity_type="staff_attendance",
        entity_id=payload.staff_id,
        new_values={
            "status": payload.status.value,
            "date": payload.attendance_date.isoformat(),
        },
    )
    db.commit()
    return AttendanceRecordOut.model_validate(record)


# ──────────────────────────────────────────────────────────────────────
# Student attendance queries
# ──────────────────────────────────────────────────────────────────────


@router.get("/student/{student_id}", response_model=list[AttendanceRecordOut])
def list_student_attendance_endpoint(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ATTENDANCE_VIEW)),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
):
    """List a student's attendance records, optional date range + status filter."""
    _require_student(db, ctx.school.id, student_id)
    records = get_student_attendance(
        db,
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )
    return [AttendanceRecordOut.model_validate(r) for r in records]


@router.get("/summary/{student_id}", response_model=AttendanceSummaryOut)
def get_student_attendance_summary_endpoint(
    student_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ATTENDANCE_REPORT)),
    academic_session_id: Optional[uuid.UUID] = Query(None, description="Academic session ID"),
):
    """Monthly attendance summary for a student."""
    _require_student(db, ctx.school.id, student_id)

    if academic_session_id is None:
        session = db.scalar(
            select(AcademicSession).where(
                AcademicSession.school_id == ctx.school.id,
                AcademicSession.is_current == True,
            )
        )
        if session is None:
            raise NotFoundError("No active academic session found")
        academic_session_id = session.id

    summary = get_student_attendance_summary(
        db,
        school_id=ctx.school.id,
        student_id=student_id,
        academic_session_id=academic_session_id,
    )
    return AttendanceSummaryOut.model_validate(summary)


# ──────────────────────────────────────────────────────────────────────
# Staff attendance queries
# ──────────────────────────────────────────────────────────────────────


@router.get("/staff/{staff_id}", response_model=list[AttendanceRecordOut])
def list_staff_attendance_endpoint(
    staff_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ATTENDANCE_VIEW)),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
):
    """List a staff member's attendance records."""
    _require_staff(db, ctx.school.id, staff_id)
    records = get_staff_attendance(
        db,
        staff_id=staff_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
    )
    return [AttendanceRecordOut.model_validate(r) for r in records]


@router.get("/staff/summary/{staff_id}", response_model=StaffAttendanceSummaryOut)
def get_staff_attendance_summary_endpoint(
    staff_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(ATTENDANCE_REPORT)),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Attendance summary for a staff member within a date range."""
    _require_staff(db, ctx.school.id, staff_id)
    records = get_staff_attendance(
        db,
        staff_id=staff_id,
        start_date=start_date,
        end_date=end_date,
    )

    total = len(records)
    counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
    for r in records:
        counts[r.status] = counts.get(r.status, 0) + 1

    return StaffAttendanceSummaryOut(
        staff_id=staff_id,
        total_days=total,
        present_days=counts["present"],
        absent_days=counts["absent"],
        late_days=counts["late"],
        excused_days=counts["excused"],
        percentage=round(counts["present"] / total * 100, 2) if total else 0.0,
    )


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _require_student(db: DbSession, school_id: uuid.UUID, student_id: uuid.UUID) -> None:
    student = db.get(Student, student_id)
    if student is None or student.school_id != school_id:
        raise NotFoundError("Student not found")


def _require_staff(db: DbSession, school_id: uuid.UUID, staff_id: uuid.UUID) -> None:
    staff = db.get(Staff, staff_id)
    if staff is None or staff.school_id != school_id:
        raise NotFoundError("Staff member not found")