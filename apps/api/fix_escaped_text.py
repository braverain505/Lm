"""Repair text that was stored HTML-escaped by the old sanitizer.

Until this fix, ``sanitize_text_input`` ran ``html.escape`` on every write, so
a pupil named ``Dan'azumi`` was saved as ``Dan&#x27;azumi`` and displayed
verbatim. The sanitizer no longer escapes on write, but rows already written
keep the entities until they happen to be edited, and each re-save escaped the
ampersand again (``&amp;#x27;``). This unescapes them.

    DATABASE_URL='postgresql://...' python fix_escaped_text.py
    DATABASE_URL='postgresql://...' python fix_escaped_text.py --apply

Nothing is written without ``--apply``. It is idempotent: a value with no
entities is left alone, so re-running is safe.
"""
from __future__ import annotations

import argparse
import html
import re

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Staff, Student

# Only entity forms ``html.escape`` can produce, so ordinary text that happens
# to contain an ampersand is not touched.
ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|apos|#\d{1,7}|#x[0-9a-fA-F]{1,6});")

# Fields the old sanitizer was wired into (see ``app/schemas/people.py``).
TARGETS: list[tuple[type, tuple[str, ...]]] = [
    (
        Student,
        ("admission_no", "first_name", "middle_name", "last_name",
         "address", "medical_notes", "previous_school"),
    ),
    (Staff, ("staff_no", "full_name", "phone")),
]


def unescape(value: str, max_rounds: int = 5) -> str:
    """Undo repeated escaping — a value saved twice may be double-encoded."""
    for _ in range(max_rounds):
        if not ENTITY_RE.search(value):
            break
        value = html.unescape(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        total = 0
        for model, columns in TARGETS:
            for column in columns:
                attr = getattr(model, column)
                rows = db.scalars(
                    select(model).where(attr.is_not(None), attr.like("%&%"))
                ).all()
                for row in rows:
                    before = getattr(row, column)
                    after = unescape(before)
                    if after == before:
                        continue
                    total += 1
                    print(f"{model.__tablename__}.{column}  {row.id}")
                    print(f"  before: {before}")
                    print(f"  after : {after}")
                    setattr(row, column, after)

        if not total:
            print("Nothing to repair — no escaped entities found.")
            return

        if args.apply:
            db.commit()
            print(f"\nApplied {total} change(s).")
        else:
            db.rollback()
            print(f"\n{total} change(s) found. Re-run with --apply to write them.")
    finally:
        db.close()


if __name__ == "__main__":
    main()