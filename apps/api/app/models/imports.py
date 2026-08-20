"""Legacy data import: import batches and their raw rows.

Every batch stores the uploaded rows *verbatim* as JSONB from day one (the
roadmap requirement: "store rows as raw JSON in DB"), so a mapping can be
changed and the batch re-imported without re-uploading the file. Per-row
validation errors and user-applied pre-import fixes are held alongside the
raw data; the batch lifecycle is:

    uploaded → ready → running → completed
                          └──→ failed

``rows_imported`` / ``rows_failed`` are updated in chunks while ``status``
is ``running`` so the UI can poll and render live progress (3.2).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase, utcnow

# Batch lifecycle states.
STATUS_UPLOADED = "uploaded"  # raw rows stored, mapping not yet set
STATUS_READY = "ready"  # mapping set + rows validated; can run
STATUS_RUNNING = "running"  # import in progress (live progress via counts)
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# Row lifecycle states.
ROW_PENDING = "pending"  # mapping not yet applied
ROW_VALID = "valid"
ROW_INVALID = "invalid"  # has errors; fixable before import
ROW_IMPORTED = "imported"
ROW_FAILED = "failed"


class ImportBatch(TenantScopedBase, Base):
    """One uploaded file (or re-import) of legacy records for one entity type."""

    __tablename__ = "import_batches"

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)  # e.g. "students"
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=STATUS_UPLOADED, nullable=False, index=True
    )
    # Detected source columns (from the raw rows' keys), in first-seen order.
    columns: Mapped[list] = mapped_column(JSONB, default=list)
    # Source column -> target field, set by the mapping step.
    column_mapping: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    # For re-imports: the batch whose rows this one reuses.
    parent_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL")
    )

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_invalid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Summary counts keyed by target field (e.g. {"first_name": 3}) for the UI.
    error_summary: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    parent: Mapped["ImportBatch | None"] = relationship(
        remote_side="ImportBatch.id"
    )


class ImportRow(TenantScopedBase, Base):
    """A single raw row from an import file, plus its validation + fix state."""

    __tablename__ = "import_rows"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True, nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based (after header)
    # The row exactly as uploaded — raw JSON, never normalized until run time.
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ROW_PENDING, nullable=False, index=True
    )
    # Field-level validation errors: {field: [messages]}.
    errors: Mapped[dict] = mapped_column(JSONB, default=dict)
    # User-applied pre-import fixes: {field: corrected value} layered over data.
    fixes: Mapped[dict] = mapped_column(JSONB, default=dict)
    # The created record (e.g. student) when this row is imported.
    imported_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")

    @property
    def is_invalid(self) -> bool:
        return bool(self.errors)

    @property
    def effective_data(self) -> dict:
        """Raw row with user fixes layered on top — what import actually uses."""
        merged = dict(self.data)
        if self.fixes:
            merged.update(self.fixes)
        return merged


__all__ = [
    "ImportBatch",
    "ImportRow",
    "STATUS_UPLOADED",
    "STATUS_READY",
    "STATUS_RUNNING",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "ROW_PENDING",
    "ROW_VALID",
    "ROW_INVALID",
    "ROW_IMPORTED",
    "ROW_FAILED",
]