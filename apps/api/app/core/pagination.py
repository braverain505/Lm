"""Pagination helper returning a consistent envelope."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def paginate(
    db: Session,
    stmt: Select,
    page: int = 1,
    per_page: int = 25,
) -> dict[str, Any]:
    """Execute ``stmt`` with paging. ``per_page`` is clamped to 100.

    Returns {"items": [...], "page": n, "per_page": n, "total": n, "pages": n}
    """
    page = max(1, page)
    per_page = min(max(1, per_page), 100)

    total = db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    )
    rows = db.scalars(stmt.offset((page - 1) * per_page).limit(per_page)).all()
    pages = (total + per_page - 1) // per_page if total else 0

    return {
        "items": [r for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total or 0,
        "pages": pages,
    }