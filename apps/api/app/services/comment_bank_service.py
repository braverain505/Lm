"""Comment bank: reusable report-card remarks.

A school's bank holds pre-approved phrases (``comment_text``) tagged by
``category`` (performance, effort, behavior, attendance, conduct, general) and
``sentiment`` (positive / neutral / negative) with an optional
``applicable_domain`` (e.g. ``vice_principal`` / ``homeroom`` / ``principal`` /
``all``) so each report role sees the phrases meant for it. Teachers search,
preview and insert bank entries into the report-card comment areas; principals
and heads-of-academics curate the bank. Rows are soft-deactivated so history
is preserved.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError
from ..models import CommentBankEntry

BANK_CATEGORIES = ("performance", "effort", "behavior", "attendance", "conduct", "general")
BANK_SENTIMENTS = ("positive", "neutral", "negative")


def list_comment_bank(
    db: Session,
    school_id: uuid.UUID,
    *,
    category: str | None = None,
    sentiment: str | None = None,
    search: str | None = None,
    active_only: bool = True,
    limit: int = 100,
) -> list[CommentBankEntry]:
    stmt = select(CommentBankEntry).where(CommentBankEntry.school_id == school_id)
    if active_only:
        stmt = stmt.where(CommentBankEntry.is_active.is_(True))
    if category:
        stmt = stmt.where(CommentBankEntry.category == category)
    if sentiment:
        stmt = stmt.where(CommentBankEntry.sentiment == sentiment)
    if search:
        stmt = stmt.where(CommentBankEntry.comment_text.ilike(f"%{search}%"))
    stmt = stmt.order_by(CommentBankEntry.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_comment_bank_entry(db: Session, school_id: uuid.UUID, entry_id: uuid.UUID) -> CommentBankEntry:
    row = db.scalar(
        select(CommentBankEntry).where(
            CommentBankEntry.school_id == school_id,
            CommentBankEntry.id == entry_id,
        )
    )
    if row is None:
        raise NotFoundError("Comment bank entry not found")
    return row


def create_comment_bank_entry(
    db: Session,
    school_id: uuid.UUID,
    *,
    comment_text: str,
    category: str,
    sentiment: str,
    applicable_domain: str | None,
    actor_id: uuid.UUID,
) -> CommentBankEntry:
    row = CommentBankEntry(
        school_id=school_id,
        comment_text=comment_text,
        category=category,
        sentiment=sentiment,
        applicable_domain=applicable_domain or "all",
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def update_comment_bank_entry(
    db: Session,
    school_id: uuid.UUID,
    entry_id: uuid.UUID,
    *,
    comment_text: str | None,
    category: str | None,
    sentiment: str | None,
    applicable_domain: str | None,
    is_active: bool | None,
) -> CommentBankEntry:
    row = get_comment_bank_entry(db, school_id, entry_id)
    if comment_text is not None:
        row.comment_text = comment_text
    if category is not None:
        row.category = category
    if sentiment is not None:
        row.sentiment = sentiment
    if applicable_domain is not None:
        row.applicable_domain = applicable_domain
    if is_active is not None:
        row.is_active = is_active
    db.flush()
    return row