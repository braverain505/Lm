"""platform admin foundation: geo columns, platform tables, analytics indexes

Revision ID: 0007_platform_admin
Revises: 9f6246f5795d
Create Date: 2026-08-19

Adds the platform-level entities that power the Super Admin command center:
  * ``schools.state`` / ``schools.country`` (geographic analytics)
  * ``platform_regions`` — expandable country/state catalog
  * ``platform_settings`` — key/value platform configuration
  * ``platform_announcements`` — broadcasts to schools
  * ``platform_tickets`` — support tickets
  * ``platform_notifications`` — Super Admin in-app alerts
  * ``subscription_events`` — auditable billing/renewal trail
  * ``impersonation_sessions`` — audited 'view as school admin' sessions
  * composite indexes for the analytics hot paths (ai_usage, audit_logs)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_platform_admin"
down_revision: Union[str, None] = "0006_drop_class_levels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Schools: geographic columns -------------------------------------------
    op.add_column("schools", sa.Column("state", sa.String(120), nullable=True))
    op.add_column(
        "schools",
        sa.Column("country", sa.String(2), nullable=False, server_default="NG"),
    )

    # --- Platform regions -------------------------------------------------------
    op.create_table(
        "platform_regions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("country_name", sa.String(80), nullable=False),
        sa.Column("state_code", sa.String(24), nullable=False),
        sa.Column("state_name", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("country_code", "state_code", name="uq_region_country_state"),
    )

    # --- Platform settings ------------------------------------------------------
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Platform announcements ---------------------------------------------------
    op.create_table(
        "platform_announcements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(24), nullable=False, server_default="all_schools"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- Platform tickets ----------------------------------------------------------
    op.create_table(
        "platform_tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("school_id", sa.Uuid(), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(40), nullable=False, server_default="general"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ticket_school_status", "platform_tickets", ["school_id", "status"])

    # --- Platform notifications ----------------------------------------------------
    op.create_table(
        "platform_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("category", sa.String(40), nullable=False, server_default="system"),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- Subscription events ---------------------------------------------------------
    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("school_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("school_id", sa.Uuid(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="success"),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sub_event_school_created", "subscription_events", ["school_id", "created_at"])

    # --- Impersonation sessions -------------------------------------------------------
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("platform_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("impersonated_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.Uuid(), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Analytics hot-path indexes ----------------------------------------------------
    op.create_index("ix_ai_usage_school_created", "ai_usage", ["school_id", "created_at"])
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])
    op.create_index("ix_school_subscriptions_status", "school_subscriptions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_school_subscriptions_status", table_name="school_subscriptions")
    op.drop_index("ix_audit_logs_created", table_name="audit_logs")
    op.drop_index("ix_ai_usage_school_created", table_name="ai_usage")
    op.drop_table("impersonation_sessions")
    op.drop_index("ix_sub_event_school_created", table_name="subscription_events")
    op.drop_table("subscription_events")
    op.drop_table("platform_notifications")
    op.drop_index("ix_ticket_school_status", table_name="platform_tickets")
    op.drop_table("platform_tickets")
    op.drop_table("platform_announcements")
    op.drop_table("platform_settings")
    op.drop_table("platform_regions")
    op.drop_column("schools", "country")
    op.drop_column("schools", "state")