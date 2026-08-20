"""Platform-level entities for the SchoolOS Super Admin command center.

These tables are intentionally NOT tenant-scoped: they describe the SaaS
platform itself (regions, announcements, support tickets, platform
notifications, subscription billing events, audited impersonation sessions).
Tenant data is never aggregated here — the super admin service scopes every
aggregation across ``schools`` and the tenant-scoped tables explicitly.
"""
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
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPkMixin, utcnow


class PlatformRegion(UUIDPkMixin, Base):
    """Expandable country/state catalog for geographic analytics.

    Never hard-coded to one country: rows are seeded for Nigeria and can be
    extended to other countries without any application change.
    """

    __tablename__ = "platform_regions"
    __table_args__ = (
        UniqueConstraint("country_code", "state_code", name="uq_region_country_state"),
    )

    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    country_name: Mapped[str] = mapped_column(String(80), nullable=False)
    state_code: Mapped[str] = mapped_column(String(24), nullable=False)
    state_name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0)


class PlatformSetting(Base):
    """Key/value platform configuration (JSON values)."""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PlatformAnnouncement(UUIDPkMixin, TimestampMixin, Base):
    """A broadcast message the owner can send to schools or platform staff."""

    __tablename__ = "platform_announcements"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(
        String(24), default="all_schools"
    )  # all_schools | premium_only | internal
    severity: Mapped[str] = mapped_column(String(16), default="info")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class PlatformTicket(UUIDPkMixin, TimestampMixin, Base):
    """Support ticket raised by a school (or opened by the platform admin)."""

    __tablename__ = "platform_tickets"
    __table_args__ = (
        Index("ix_ticket_school_status", "school_id", "status"),
    )

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), index=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), default="general")
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(
        String(16), default="open"
    )  # open | in_progress | awaiting_school | resolved | closed
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class PlatformNotification(UUIDPkMixin, Base):
    """Super Admin in-app alert (platform level, never tenant-scoped)."""

    __tablename__ = "platform_notifications"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    category: Mapped[str] = mapped_column(String(40), default="system")
    data: Mapped[dict | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SubscriptionEvent(UUIDPkMixin, TimestampMixin, Base):
    """Billing/renewal events on a school subscription (auditable payment trail)."""

    __tablename__ = "subscription_events"
    __table_args__ = (
        Index("ix_sub_event_school_created", "school_id", "created_at"),
    )

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("school_subscriptions.id", ondelete="SET NULL"), index=True
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # trial_started, activated, renewed, payment_succeeded,
    # payment_failed, upgraded, downgraded, cancelled, expired
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(16), default="success")
    meta: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ImpersonationSession(UUIDPkMixin, Base):
    """Audited 'view as school admin' support session.

    One row per impersonation. The raw token is only ever shown to the platform
    admin once; the DB stores its SHA-256 hash. Entering/exiting impersonation
    is written to the audit log.
    """

    __tablename__ = "impersonation_sessions"

    platform_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    impersonated_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [
    "PlatformRegion",
    "PlatformSetting",
    "PlatformAnnouncement",
    "PlatformTicket",
    "PlatformNotification",
    "SubscriptionEvent",
    "ImpersonationSession",
]