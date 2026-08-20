"""Cross-cutting tables: audit log, subscriptions, usage meters, AI usage,
notifications. Phase 1 stores these; billing/AI/notifications features land
in later phases."""

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

from .base import Base, TenantScopedBase, TimestampMixin, UUIDPkMixin, utcnow
from .enums import AuditAction, NotificationChannel, SubscriptionStatus


class AuditLog(UUIDPkMixin, Base):
    """Append-only coarse audit trail for administrative actions.

    This table is intentionally NOT tenant-scoped through the mixin because an
    operator's actions across schools are of interest; rows always carry the
    acting user's global id and the affected school_id is recorded if any.
    """

    __tablename__ = "audit_logs"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[AuditAction] = mapped_column(String(24), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(40))
    old: Mapped[dict | None] = mapped_column(JSONB)
    new: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SubscriptionPlan(UUIDPkMixin, TimestampMixin, Base):
    """Global product plans (Starter / Professional / Enterprise + AI add-on).
    ``features`` JSONB holds the feature entitlement map."""

    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_monthly_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    price_yearly_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    features: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class SchoolSubscription(TenantScopedBase, Base):
    __tablename__ = "school_subscriptions"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(16), default=SubscriptionStatus.TRIAL.value, nullable=False
    )
    ai_credits_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ai_credits_used: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageMeter(TenantScopedBase, Base):
    """Monthly usage rollup by feature (e.g. 'ai.credits', 'storage_gb')."""

    __tablename__ = "usage_meters"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "feature_code", "period", name="uq_usage_school_feature_period"
        ),
    )

    feature_code: Mapped[str] = mapped_column(String(64), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    count: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class AiUsage(TenantScopedBase, Base):
    """Every AI request row — the basis for AI credit metering and cost control."""

    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    feature: Mapped[str] = mapped_column(String(40), nullable=False)  # lesson_plan, ...
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    tokens_in: Mapped[int] = mapped_column(default=0)
    tokens_out: Mapped[int] = mapped_column(default=0)
    cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Notification(TenantScopedBase, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_recipient", "recipient_user_id"),)

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        String(8), default=NotificationChannel.IN_APP.value, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


__all__ = [
    "AuditLog",
    "SubscriptionPlan",
    "SchoolSubscription",
    "UsageMeter",
    "AiUsage",
    "Notification",
]