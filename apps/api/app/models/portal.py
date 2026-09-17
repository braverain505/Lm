"""Result portal: the result codes and per-student PINs that open it.

Three ways into the public report card, deliberately layered:

* ``StudentResultCode`` — **one live code per student**, carrying the school's
  initials (``GVS-7K42Q``). This is what the login screen asks for: the code
  names the child, so no admission number is needed. The exam office issues and
  reprints it per student.
* ``SchoolResultPin`` — the legacy **one-code-per-school** credential. A parent
  types it together with their child's admission number; kept for schools that
  broadcast a single code.
* ``StudentPin`` — the narrow per-student numeric PIN, kept for schools that
  would rather hand each family its own secret.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class SchoolResultPin(TenantScopedBase, Base):
    """The school's result-check code — exactly one live row per school.

    Unlike ``StudentPin`` (a per-person secret, stored only as a hash), this code
    is a *shared, distributable* credential: the exam office prints it on the
    results notice and broadcasts it to parents, and has to be able to re-read
    and reprint it at any time. So it is stored as issued, and is only ever used
    to narrow a lookup to *one school* — the publish gate and the child's
    admission number decide what is actually revealed.

    There is deliberately **no per-code lockout counter**: the code is shared by
    a whole school, so cooling it down after N bad guesses would let one person
    lock every parent out of their own result. Brute force is instead answered by
    the per-IP rate limit on the public endpoint, and by the fact that a correct
    code alone reveals nothing.

    Rotation revokes the old row rather than deleting it, so the audit trail of
    which code was live when survives — hence the *partial* unique index.
    """

    __tablename__ = "school_result_pins"
    __table_args__ = (
        Index(
            "uq_school_result_pin_one",
            "school_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
    )

    # The code exactly as issued, e.g. ``GVS-7K42Q``.
    code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # The school-initials half of the code, kept separately so the UI can show
    # "GVS-•••••" and so the parent can see which school the code belongs to.
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentResultCode(TenantScopedBase, Base):
    """A per-student result code — one live code per child, carrying the
    school's initials (e.g. ``GVS-7K42Q``).

    This is the credential the login screen asks for: a parent types the single
    code their school handed out for *their* child and opens that child's
    published report card. Because the code names the student, no separate
    admission number is needed on the public check-in.

    It is stored exactly as issued (not hashed), like the school-wide code: the
    exam office prints it on the results notice and has to be able to re-read
    and reprint it. Rotation revokes the old row rather than deleting it, so the
    audit trail of which code was live when survives — hence the *partial*
    unique index over the live rows only.
    """

    __tablename__ = "student_result_codes"
    __table_args__ = (
        Index(
            "uq_student_result_code_one",
            "school_id",
            "student_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    # The code exactly as issued, e.g. ``GVS-7K42Q``.
    code: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # The school-initials half, kept so the UI can show which school it belongs to.
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentPin(TenantScopedBase, Base):
    """One live PIN per student. A PIN is *replaced* on rotation and old rows
    stay (with ``revoked_at``) for audit. ``pin_hash`` is SHA-256 of
    ``school_id:student_id:pin`` — never store the plaintext."""

    __tablename__ = "student_pins"
    __table_args__ = (
        # Uniqueness is over the *live* rows only: revocation keeps the old row
        # for audit, so several historical rows per student are expected. (Same
        # technique as ``school_result_pins.uq_school_result_pin_one``.)
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
    failed_pin_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))