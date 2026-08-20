"""Attendance tracking service layer."""

import calendar
import uuid
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..models import School, Student, Staff
from ..models.attendance import StudentAttendance, StaffAttendance, AttendanceSummary
from ..models.enums import AttendanceStatus


# ──────────────────────────────────────────────────────────────────────
# StudentAttendance
# ──────────────────────────────────────────────────────────────────────


def record_student_attendance(
    db: Session,
    *,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    campus_id: uuid.UUID | None,
    date: str,
    status: str,
    marked_by: uuid.UUID,
    notes: str | None = None,
) -> StudentAttendance:
    """Record daily attendance for a student."""
    try:
        AttendanceStatus(status)
    except ValueError:
        raise ValidationError(f"Invalid attendance status: {status}")

    existing = db.scalar(
        select(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.date == date,
        )
    )
    if existing:
        # Update existing record
        existing.status = status
        existing.campus_id = campus_id
        existing.marked_by = marked_by
        existing.notes = notes
        db.flush()
        return existing

    attendance = StudentAttendance(
        school_id=school_id,
        student_id=student_id,
        campus_id=campus_id,
        date=date,
        status=status,
        marked_by=marked_by,
        notes=notes,
    )
    db.add(attendance)
    db.flush()
    return attendance


def get_student_attendance(
    db: Session,
    student_id: uuid.UUID,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> List[StudentAttendance]:
    """Get attendance records for a student within a date range."""
    stmt = select(StudentAttendance).where(StudentAttendance.student_id == student_id)
    if start_date:
        # Simple string comparison for YYYY-MM-DD format
        stmt = stmt.where(StudentAttendance.date >= start_date)
    if end_date:
        stmt = stmt.where(StudentAttendance.date <= end_date)
    if status:
        stmt = stmt.where(StudentAttendance.status == status)
    stmt = stmt.order_by(StudentAttendance.date.desc())
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def get_student_attendance_summary(
    db: Session,
    *,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    academic_session_id: uuid.UUID,
) -> AttendanceSummary:
    """Get or create monthly attendance summary for a student."""
    # Try to find existing summary for current month
    from datetime import datetime as dt_mod
    now = dt_mod.now()
    month = now.strftime("%Y-%m")

    existing = db.scalar(
        select(AttendanceSummary).where(
            AttendanceSummary.student_id == student_id,
            AttendanceSummary.academic_session_id == academic_session_id,
            AttendanceSummary.month == month,
        )
    )

    if existing:
        return existing

    # Calculate summary from attendance records
    month_start = f"{now.year}-{now.month:02d}-01"
    month_end = f"{now.year}-{now.month:02d}-{calendar.monthrange(now.year, now.month)[1]:02d}"

    total_days = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.date >= month_start,
            StudentAttendance.date <= month_end,
        )
    ) or 0

    present_days = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.status == AttendanceStatus.PRESENT.value,
            StudentAttendance.date >= month_start,
            StudentAttendance.date <= month_end,
        )
    ) or 0

    absent_days = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.status == AttendanceStatus.ABSENT.value,
            StudentAttendance.date >= month_start,
            StudentAttendance.date <= month_end,
        )
    ) or 0

    late_days = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.status == AttendanceStatus.LATE.value,
            StudentAttendance.date >= month_start,
            StudentAttendance.date <= month_end,
        )
    ) or 0

    excused_days = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.status == AttendanceStatus.EXCUSED.value,
            StudentAttendance.date >= month_start,
            StudentAttendance.date <= month_end,
        )
    ) or 0

    percentage = (present_days / total_days * 100) if total_days > 0 else 0.0

    summary = AttendanceSummary(
        school_id=school_id,
        student_id=student_id,
        academic_session_id=academic_session_id,
        month=month,
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        late_days=late_days,
        excused_days=excused_days,
        percentage=round(percentage, 2),
    )
    db.add(summary)
    db.flush()
    return summary


# ──────────────────────────────────────────────────────────────────────
# StaffAttendance
# ──────────────────────────────────────────────────────────────────────


def record_staff_attendance(
    db: Session,
    *,
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    campus_id: uuid.UUID | None,
    date: str,
    status: str,
    marked_by: uuid.UUID,
    notes: str | None = None,
) -> StaffAttendance:
    """Record daily attendance for staff/teacher."""
    try:
        AttendanceStatus(status)
    except ValueError:
        raise ValidationError(f"Invalid attendance status: {status}")

    existing = db.scalar(
        select(StaffAttendance).where(
            StaffAttendance.staff_id == staff_id,
            StaffAttendance.date == date,
        )
    )
    if existing:
        existing.status = status
        existing.campus_id = campus_id
        existing.marked_by = marked_by
        existing.notes = notes
        db.flush()
        return existing

    attendance = StaffAttendance(
        school_id=school_id,
        staff_id=staff_id,
        campus_id=campus_id,
        date=date,
        status=status,
        marked_by=marked_by,
        notes=notes,
    )
    db.add(attendance)
    db.flush()
    return attendance


def get_staff_attendance(
    db: Session,
    staff_id: uuid.UUID,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> List[StaffAttendance]:
    """Get attendance records for staff within a date range."""
    stmt = select(StaffAttendance).where(StaffAttendance.staff_id == staff_id)
    if start_date:
        stmt = stmt.where(StaffAttendance.date >= start_date)
    if end_date:
        stmt = stmt.where(StaffAttendance.date <= end_date)
    if status:
        stmt = stmt.where(StaffAttendance.status == status)
    stmt = stmt.order_by(StaffAttendance.date.desc())
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


# ──────────────────────────────────────────────────────────────────────
# Audit
# ──────────────────────────────────────────────────────────────────────


def log_attendance_action(
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
    """Log an attendance-related action to the audit trail."""
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