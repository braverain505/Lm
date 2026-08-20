"""Declarative base, shared mixins, and UUID helpers."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class UUIDPkMixin:
    """Primary key: server-agnostic UUID generated in Python."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class TenantScopedBase(UUIDPkMixin, TimestampMixin):
    """Base for every table that belongs to exactly one school (tenant).

    Every tenant-scoped table carries ``school_id`` and is queried exclusively
    through school-scoped dependencies. The combination of a UUID primary key
    and a widely-indexed ``school_id`` is what makes the shared-schema
    multi-tenant model safe: no composite primary keys, one tenant column.
    """

    school_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("schools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


class NoPkTenantScopedBase(TimestampMixin):
    """Tenant-scoped rows without their own surrogate PK (rare join tables)."""

    school_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("schools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )