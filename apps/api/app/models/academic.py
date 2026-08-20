"""Academic result: sessions, terms, class levels, arms, subjects, grading."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase, UUIDPkMixin, utcnow
from .enums import SessionStatus, TermStatus


class GradeScale(TenantScopedBase, Base):
    """A school's grading system (e.g. WAEC 9-point, 5-point, custom)."""

    __tablename__ = "grade_scales"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_grade_scale_name"),)

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    bands: Mapped[list["GradeBand"]] = relationship(
        back_populates="scale", cascade="all, delete-orphan"
    )


class GradeBand(TenantScopedBase, Base):
    """A single band within a grade scale.

    ``min_score``/``max_score`` are percentages on the 0–100 total.
    ``point`` is the grade point (WAEC: A1=1.0 … F9=9.0).
    """

    __tablename__ = "grade_bands"
    __table_args__ = (
        UniqueConstraint("grade_scale_id", "letter", name="uq_grade_band_letter"),
    )

    grade_scale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grade_scales.id", ondelete="CASCADE"), index=True, nullable=False
    )
    letter: Mapped[str] = mapped_column(String(3), nullable=False)
    min_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    point: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(80))

    scale: Mapped[GradeScale] = relationship(back_populates="bands")


class AcademicSession(TenantScopedBase, Base):
    """e.g. 2025/2026. A school has at most one 'current' session (partial unique
    index). """

    __tablename__ = "academic_sessions"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_session_name"),
        # Only one current session per school at a time.
        Index(
            "uq_session_current_school",
            "school_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[SessionStatus] = mapped_column(
        String(16), default=SessionStatus.PLANNED.value, nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    grade_scale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("grade_scales.id", ondelete="SET NULL")
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    terms: Mapped[list["Term"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    arms: Mapped[list["ClassArm"]] = relationship(back_populates="session")


class Term(TenantScopedBase, Base):
    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint("academic_session_id", "term_no", name="uq_term_no"),
    )

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="CASCADE"), index=True
    )
    term_no: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)  # First / Second / Third
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[TermStatus] = mapped_column(
        String(16), default=TermStatus.PLANNED.value, nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped[AcademicSession] = relationship(back_populates="terms")


class ClassArm(TenantScopedBase, Base):
    """A concrete class for a session, e.g. 'JSS 1A' in 2025/2026. The class
    itself is the unit — there are no separate class levels."""

    __tablename__ = "class_arms"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "academic_session_id", "name",
            name="uq_class_arm_session_name",
        ),
    )

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="CASCADE"), index=True
    )
    campus_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campuses.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)  # "JSS 1A"
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)  # "JSS 1A"
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staff.id", ondelete="SET NULL")
    )

    session: Mapped[AcademicSession] = relationship(back_populates="arms")
    offerings: Mapped[list["SubjectOffering"]] = relationship(
        back_populates="class_arm", cascade="all, delete-orphan"
    )


class Subject(TenantScopedBase, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("school_id", "code", name="uq_subject_code"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Core subjects drive "best in subject" awards on report cards and can be
    # designated per school (each tenant gets its own flag row).
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)
    # Optional linkage so AI tooling can pick up subject metadata later.
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class SubjectOffering(TenantScopedBase, Base):
    """Which subjects are taught at which class (drives scoring grids)."""

    __tablename__ = "subject_offerings"
    __table_args__ = (
        UniqueConstraint("class_arm_id", "subject_id", name="uq_offering_arm_subject"),
    )

    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    # Optional: core vs elective ordering for report cards.
    sort_order: Mapped[int] = mapped_column(default=0)

    class_arm: Mapped[ClassArm] = relationship(back_populates="offerings")
    subject: Mapped["Subject"] = relationship()  # noqa: F821


class SubjectAssignment(TenantScopedBase, Base):
    """Exactly one row per (arm, subject): 'Teacher X teaches Maths in JSS1A'.
    Swapping the teacher updates this row; co-teachers arrive as a join table later."""

    __tablename__ = "subject_assignments"
    __table_args__ = (
        UniqueConstraint("class_arm_id", "subject_id", name="uq_assignment_arm_subject"),
    )

    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT")
    )

    arm: Mapped[ClassArm] = relationship()
    subject: Mapped[Subject] = relationship()
    teacher: Mapped["Staff"] = relationship()  # noqa: F821


class LessonPlan(TenantScopedBase, Base):
    """A school's AI lesson plan for one subject × class × term × topic.

    One stored plan per (school, term, subject, class, topic);
    regenerating the same cell bumps ``revision`` and rewrites the JSONB plan.
    Like result comments, every generation is metered into ``ai_usage`` and the
    monthly ``usage_meters`` rollup.
    """

    __tablename__ = "lesson_plans"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "term_id",
            "subject_id",
            "class_arm_id",
            "topic",
            name="uq_lesson_plan_cell",
        ),
    )

    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(default=1, nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class QuestionBank(TenantScopedBase, Base):
    """A school's AI-generated question set for one subject × class × term ×
    topic.

    One stored per (school, term, subject, class, topic); regenerating
    the same cell bumps ``revision`` and rewrites the JSONB ``bank``. Like
    lesson plans and result comments, every generation is metered into
    ``ai_usage`` and the monthly ``usage_meters`` rollup.
    """

    __tablename__ = "question_banks"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "term_id",
            "subject_id",
            "class_arm_id",
            "topic",
            name="uq_question_bank_cell",
        ),
    )

    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    bank: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(default=1, nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


__all__ = [
    "GradeScale",
    "GradeBand",
    "AcademicSession",
    "Term",
    "ClassArm",
    "Subject",
    "SubjectOffering",
    "SubjectAssignment",
    "LessonPlan",
    "QuestionBank",
]