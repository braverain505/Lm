"""Report card design: the layouts a school builds for its own cards.

A school's report card is a *document the school owns*, not a fixed pixel
layout. This module stores each design a school builds in the drag-and-drop
designer as a JSONB ``layout`` blob — an ordered list of widgets plus a theme —
so the printed card, the on-screen card and the public portal all render the
same thing.

Two rules the model deliberately encodes:

* **Many designs, one default.** A school keeps several named templates
  (Primary vs Secondary, per campus, "with psychomotor" vs not) and marks one as
  its default. ``is_default`` is a column the service flips inside a single
  transaction, so there is exactly one default at rest and no second source of
  truth to drift out of step.
* **The layout is data, not code.** Widget *types* are validated against the
  server-side catalog in ``report_card_service`` before a layout is ever stored,
  so a card can never reference a renderer the API does not know about, and a
  malformed design is rejected at the edge instead of breaking a parent's
  printed card months later.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedBase


class ReportCardTemplate(TenantScopedBase, Base):
    """One named report-card design belonging to a school.

    ``layout`` holds the designer's document: ``{"version": 1, "theme": ...,
    "widgets": [{id, type, props, hidden}, ...]}``. It is validated by
    ``report_card_service.validate_layout`` on every write and normalised on
    read, so consumers can rely on its shape without defensive parsing.
    """

    __tablename__ = "report_card_templates"
    __table_args__ = (
        # A school may not have two designs with the same name — the designer
        # lists them by name, so duplicates would be indistinguishable there.
        UniqueConstraint("school_id", "name", name="uq_report_card_template_name"),
        # The default lookup is the hot path (every report card render and every
        # public portal check-in reads it), so it is indexed on its own.
        Index("ix_report_card_template_default", "school_id", "is_default"),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Exactly one row per school may carry this flag; the service flips it in a
    # single transaction so the invariant holds after every write.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


__all__ = ["ReportCardTemplate"]
