"""Result portal: per-student PINs that unlock the public report card view."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class StudentPin(TenantScopedBase, Base):
    """One live PIN per student. A PIN is *replaced* on rotation and old rows
    stay (with ``revoked_at``) for audit. ``pin_hash`` is SHA-256 of
    ``school_id:student_id:pin`` — never store the plaintext."""

    __tablename__ = "student_pins"
    __table_args__ = (
        # Uniqueness is over the *live* rows only: revocation keeps the old row
        # for audit, so several historical rows per student are expected.
        Index(
            "uq_student_pin_one",
            "school_id",
            "student_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    pin_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))