"""Attendance tracking for students and staff."""

import uuid
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase
from .enums import AttendanceStatus


class StudentAttendance(TenantScopedBase, Base):
    """Daily attendance record for a student."""

    __tablename__ = "student_attendance"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    campus_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "present", "absent", "late", "excused"
    marked_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"StudentAttendance(student={self.student_id}, date={self.date}, status={self.status})"


class StaffAttendance(TenantScopedBase, Base):
    """Daily attendance record for staff/teachers."""

    __tablename__ = "staff_attendance"

    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), index=True, nullable=False
    )
    campus_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # "present", "absent", "late", "excused"
    marked_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"StaffAttendance(staff={self.staff_id}, date={self.date}, status={self.status})"


class AttendanceSummary(TenantScopedBase, Base):
    """Monthly attendance summary for a student."""

    __tablename__ = "attendance_summaries"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    total_days: Mapped[int] = mapped_column(Integer, default=0)
    present_days: Mapped[int] = mapped_column(Integer, default=0)
    absent_days: Mapped[int] = mapped_column(Integer, default=0)
    late_days: Mapped[int] = mapped_column(Integer, default=0)
    excused_days: Mapped[int] = mapped_column(Integer, default=0)
    percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)

    __table_args__ = (
        UniqueConstraint("student_id", "academic_session_id", "month", name="uq_attendance_summary"),
    )

    def __repr__(self) -> str:
        return f"AttendanceSummary(student={self.student_id}, month={self.month}, %={self.percentage})"


__all__ = ["StudentAttendance", "StaffAttendance", "AttendanceSummary"]