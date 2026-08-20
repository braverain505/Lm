"""Results: assessment components, scores, results, and the event journal."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase, UUIDPkMixin, utcnow
from .enums import ResultStatus


class AssessmentComponent(TenantScopedBase, Base):
    """A component of the final score (CA1, CA2, Assignment, Project, Exam, ...).

    Versioned per term: NULL ``class_arm_id`` rows are the school-wide default
    for that term; arm rows override. Changing the component set touches only
    the target term, never past terms.
    """

    __tablename__ = "assessment_components"
    __table_args__ = (
        # One component per (school, term, scope, name). NULL class_arm_id rows
        # are the school-wide default, and a NULL-arm default with the same name
        # as an arm-level override must be allowed — so the uniqueness treats
        # NULLs as NOT DISTINCT (Postgres 15+). A plain UniqueConstraint would
        # let duplicate school-wide names slip through.
        Index(
            "uq_component_scope_name",
            "school_id",
            "term_id",
            "class_arm_id",
            "name",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    class_arm_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)  # "CA", "Exam"
    max_score: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)  # % towards 100
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def score_to_weighted(self, score: float) -> float:
        """Contribution to the 0–100 total: (score / max) * weight.

        max_score/weight are Numeric columns, so they surface as Decimal when
        read back from the DB — coerce to float before arithmetic.
        """
        max_score = float(self.max_score)
        weight = float(self.weight)
        if max_score <= 0:
            return 0.0
        return round((score / max_score) * weight, 2)


class Score(TenantScopedBase, Base):
    """One cell in the score grid: a student's score for one component of one
    subject in their enrollment. (enrollment, subject, component) is unique —
    exactly one value per cell."""

    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint(
            "student_enrollment_id",
            "subject_id",
            "assessment_component_id",
            name="uq_score_cell",
        ),
        Index("ix_score_lookup", "class_arm_id", "subject_id"),
    )

    student_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    assessment_component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_components.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    entered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Result(TenantScopedBase, Base):
    """Computed result for one student × subject × term. The state machine
    (draft→submitted→verified→approved→published|rejected) is enforced in the
    results service; this row also snapshots totals at publish."""

    __tablename__ = "results"
    __table_args__ = (
        UniqueConstraint(
            "student_enrollment_id", "subject_id", "term_id", name="uq_result_row"
        ),
        Index("ix_result_status", "term_id", "class_arm_id", "status"),
    )

    student_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), index=True
    )
    class_arm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("class_arms.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ResultStatus] = mapped_column(
        String(16), default=ResultStatus.DRAFT.value, nullable=False
    )
    total: Mapped[float | None] = mapped_column(Numeric(5, 2))
    grade_letter: Mapped[str | None] = mapped_column(String(3))
    grade_point: Mapped[float | None] = mapped_column(Numeric(4, 2))
    remark: Mapped[str | None] = mapped_column(String(80))
    position: Mapped[int | None]
    recomputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Frozen totals/components at publish — prevents silent drift later.
    published_snapshot: Mapped[dict | None] = mapped_column(JSONB)


class ResultEvent(TenantScopedBase, Base):
    """Append-only journal of every transition a result takes."""

    __tablename__ = "result_events"

    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("results.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str | None] = mapped_column(String(16))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ResultComment(TenantScopedBase, Base):
    """Comment on a student's term report, per role.

    One row per (school, term, enrollment, role). ``role`` is one of
    ``principal`` / ``vice_principal`` / ``homeroom``. Regeneration rewrites
    ``body`` and bumps ``revision`` — the row itself is not append-only, but
    every AI generation journals an ``AiUsage`` row so the full history of
    generations is metered and auditable. Manual saves record ``provider`` as
    ``manual`` so report consumers can distinguish authored vs generated text.
    """

    __tablename__ = "result_comments"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "term_id",
            "student_enrollment_id",
            "role",
            name="uq_result_comment_role",
        ),
    )

    student_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(24), default="principal", nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    revision: Mapped[int] = mapped_column(default=1, nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class CommentBankEntry(TenantScopedBase, Base):
    """A reusable comment in the school's comment bank.

    Teachers and administrators can search by category + sentiment, preview,
    and insert a saved comment into any of the report-card comment areas. Rows
    are soft-deactivated (``is_active``) so history is never destroyed.
    """

    __tablename__ = "comment_bank"
    __table_args__ = (
        Index("ix_comment_bank_category", "school_id", "category"),
        Index("ix_comment_bank_sentiment", "school_id", "sentiment"),
    )

    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(24), nullable=False)
    applicable_domain: Mapped[str | None] = mapped_column(String(40))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PsychomotorAssessment(TenantScopedBase, Base):
    """One psychomotor/affective learning area scored on a student's term
    report card (e.g. Handwriting, Physical Education, ICT Skills).

    Achievement levels use the school's report vocabulary (Excellent, Very
    Good, Good, Fair, Poor); the printable card averages them.
    """

    __tablename__ = "psychomotor_assessments"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "student_enrollment_id",
            "term_id",
            "learning_area",
            name="uq_psychomotor_area",
        ),
        Index("ix_psychomotor_enrollment_term", "student_enrollment_id", "term_id"),
    )

    student_enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_enrollments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("terms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    learning_area: Mapped[str] = mapped_column(String(80), nullable=False)
    achievement_level: Mapped[str] = mapped_column(String(24), nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0)


__all__ = [
    "AssessmentComponent",
    "Score",
    "Result",
    "ResultComment",
    "ResultEvent",
    "PsychomotorAssessment",
    "CommentBankEntry",
]