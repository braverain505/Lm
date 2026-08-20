"""People: staff (teachers + non-teaching), students, guardians."""
import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase, UUIDPkMixin
from .enums import (
    EmploymentStatus,
    EnrollmentStatus,
    GuardianRelationship,
    StaffType,
)


class Staff(TenantScopedBase, Base):
    """Teachers and non-teaching staff in one table. ``teacher_id`` FKs
    (e.g. subject_assignments) point at rows with membership_type='teaching'."""

    __tablename__ = "staff"
    __table_args__ = (
        UniqueConstraint("school_id", "staff_no", name="uq_staff_no"),
        Index("uq_staff_user", "school_id", "user_id", unique=True),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    staff_no: Mapped[str] = mapped_column(String(40), nullable=False)
    membership_type: Mapped[StaffType] = mapped_column(
        String(16), default=StaffType.TEACHING.value, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    joined_date: Mapped[date | None] = mapped_column(Date)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        String(16), default=EmploymentStatus.ACTIVE.value, nullable=False
    )
    photo_url: Mapped[str | None] = mapped_column(String(500))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    assignments: Mapped[list["SubjectAssignment"]] = relationship(
        back_populates="teacher", foreign_keys="SubjectAssignment.teacher_id"
    )
    attendance_records: Mapped[list["StaffAttendance"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )


class Student(TenantScopedBase, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "admission_no", name="uq_student_admission_no"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    admission_no: Mapped[str] = mapped_column(String(40), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(80))
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String(80))
    lga: Mapped[str | None] = mapped_column(String(80))
    blood_group: Mapped[str | None] = mapped_column(String(10))
    medical_notes: Mapped[str | None] = mapped_column(Text)
    previous_school: Mapped[str | None] = mapped_column(String(200))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    enrollments: Mapped[list["StudentEnrollment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    guardians: Mapped[list["StudentGuardian"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list["StudentAttendance"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.middle_name or ''} {self.last_name}".replace("  ", " ")


class StudentEnrollment(TenantScopedBase, Base):
    """One row per student per academic session: history and current class in a
    single query. ``is_current`` marks the live enrollment."""

    __tablename__ = "student_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "academic_session_id", name="uq_enrollment_student_session"
        ),
        Index("ix_enroll_arm_current", "class_arm_id", "is_current"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    campus_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL")
    )
    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="RESTRICT"), index=True
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="CASCADE"), index=True
    )
    enrolled_at: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        String(16), default=EnrollmentStatus.ACTIVE.value, nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    student: Mapped[Student] = relationship(back_populates="enrollments")
    arm: Mapped["ClassArm"] = relationship()  # noqa: F821


class Guardian(TenantScopedBase, Base):
    __tablename__ = "guardians"
    __table_args__ = (
        UniqueConstraint("school_id", "email", name="uq_guardian_email", deferrable=False),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(Text)
    occupation: Mapped[str | None] = mapped_column(String(120))

    students: Mapped[list["StudentGuardian"]] = relationship(
        back_populates="guardian", cascade="all, delete-orphan"
    )


class StudentGuardian(TenantScopedBase, Base):
    __tablename__ = "student_guardians"
    __table_args__ = (
        UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guardians.id", ondelete="CASCADE"), index=True
    )
    guardian_relationship: Mapped[GuardianRelationship] = mapped_column(
        String(16), default=GuardianRelationship.GUARDIAN.value, nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped[Student] = relationship(back_populates="guardians")
    guardian: Mapped[Guardian] = relationship(back_populates="students")


__all__ = [
    "Staff",
    "Student",
    "StudentEnrollment",
    "Guardian",
    "StudentGuardian",
]