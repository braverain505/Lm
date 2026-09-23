"""Report card designs: create, edit, default-resolve, and read for rendering.

The whole point of this module is that a school's report card is *its own
document*. It keeps that promise in four ways:

* **The built-in card is a first-class layout.** ``BUILTIN_DEFAULT_LAYOUT`` is
  the widget-for-widget equivalent of the card the app rendered before the
  designer existed, so a school that never opens the designer prints exactly
  what it printed yesterday — no migration, no degraded output.
* **One default, always.** Creating the first design, marking one default,
  deleting the default, and duplicating all funnel through ``_make_default`` /
  ``_promote_default``, so ``default_layout`` can never return "no design" for a
  school that has one, and can never return two.
* **Validated on write, normalised on read.** ``validate_layout`` runs the
  pydantic contract; ``normalise_layout`` backfills missing widget ids and props
  for any row written by an older client, so renderers never need to defend
  themselves.
* **Renderer-facing read is tenant-scoped by construction.** Every function
  takes ``school_id`` and filters on it — a design can no more leak across
  schools than a student can.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import AuditLog, ReportCardTemplate
from ..schemas.report_card import (
    DEFAULT_THEME,
    LAYOUT_VERSION,
    ReportCardLayout,
    ReportCardTemplateIn,
    ReportCardTemplatePatch,
)

# ---------------------------------------------------------------------------
# The card the app drew before the designer existed, expressed as a layout.
# Order and theme are deliberately identical to the original hardcoded
# component so "no design saved" is not a downgrade.
# ---------------------------------------------------------------------------

def _w(widget_id: str, widget_type: str, **props) -> dict:
    return {"id": widget_id, "type": widget_type, "props": props, "hidden": False}


BUILTIN_DEFAULT_LAYOUT: dict = {
    "version": LAYOUT_VERSION,
    "theme": DEFAULT_THEME,
    "widgets": [
        _w("header", "header", show_photo=True, show_logo=True, title="Report Card"),
        _w("student_info", "student_info"),
        # Half-width pair, so the built-in card keeps its original two-column
        # "Cognitive | Psychomotor" band (see `layoutRows` in the web app).
        _w("cognitive_domain", "cognitive_domain", width="half"),
        _w("psychomotor_domain", "psychomotor_domain", width="half"),
        _w("grading_key", "grading_key"),
        _w("performance_summary", "performance_summary"),
        _w("best_in_subjects", "best_in_subjects"),
        _w("next_term", "next_term"),
        _w("comments", "comments"),
    ],
}


def builtin_layout() -> dict:
    """A deep-ish copy of the built-in layout.

    Returned by value because callers hand it to JSON serialisation; letting a
    request mutate the module constant would corrupt the fallback for the whole
    process.
    """
    import copy

    return copy.deepcopy(BUILTIN_DEFAULT_LAYOUT)


# ---------------------------------------------------------------------------
# Validation / normalisation
# ---------------------------------------------------------------------------

def validate_layout(raw: dict | None) -> dict:
    """Validate a layout and return it as a plain JSON-safe dict.

    Raises ``ValidationError`` (a 422 in the API envelope) naming the offending
    widget, which is what the designer shows the user inline.
    """
    try:
        layout = ReportCardLayout.model_validate(raw if raw is not None else {})
    except Exception as exc:  # pydantic ValidationError -> our 422 envelope
        raise ValidationError(f"That report card design is not valid: {_brief(exc)}") from exc
    return layout.model_dump(mode="json")


def _brief(exc: Exception) -> str:
    """One readable line out of a pydantic error, for the user-facing message."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return str(exc)
    try:
        first = errors()[0]
    except (IndexError, KeyError, TypeError):
        return str(exc)
    loc = " → ".join(str(p) for p in first.get("loc", ()) if p != "__root__")
    msg = first.get("msg", "invalid value")
    return f"{loc}: {msg}" if loc else str(msg)


def normalise_layout(raw: dict | None) -> dict:
    """Best-effort read-side repair for rows written before this contract.

    Reads must never 500 because a stored blob is slightly old: unknown widget
    types are dropped (there is no renderer for them) and missing ids/props are
    filled in. The theme is coerced to a known one rather than rejected, so a
    card always renders.
    """
    if not isinstance(raw, dict):
        return builtin_layout()

    from ..schemas.report_card import THEMES, WIDGET_TYPES

    theme = raw.get("theme") if raw.get("theme") in THEMES else DEFAULT_THEME
    widgets: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(raw.get("widgets") or []):
        if not isinstance(item, dict):
            continue
        widget_type = item.get("type")
        if widget_type not in WIDGET_TYPES:
            continue
        widget_id = str(item.get("id") or f"{widget_type}-{index}")[:64]
        if widget_id in seen:
            widget_id = f"{widget_id}-{index}"[:64]
        seen.add(widget_id)
        props = item.get("props")
        widgets.append(
            {
                "id": widget_id,
                "type": widget_type,
                "props": props if isinstance(props, dict) else {},
                "hidden": bool(item.get("hidden")),
            }
        )
    if not widgets:
        return builtin_layout()
    return {"version": LAYOUT_VERSION, "theme": theme, "widgets": widgets}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def list_templates(db: Session, school_id: uuid.UUID) -> list[ReportCardTemplate]:
    """Every design this school has, default first then newest."""
    return list(
        db.scalars(
            select(ReportCardTemplate)
            .where(ReportCardTemplate.school_id == school_id)
            .order_by(
                ReportCardTemplate.is_default.desc(),
                ReportCardTemplate.updated_at.desc(),
            )
        )
    )


def get_template(
    db: Session, school_id: uuid.UUID, template_id: uuid.UUID | str
) -> ReportCardTemplate:
    """One design, or a neutral 404.

    The ``school_id`` filter is part of the lookup rather than a check after it,
    so another school's id is indistinguishable from a nonexistent one.
    """
    try:
        parsed = uuid.UUID(str(template_id))
    except (ValueError, TypeError):
        raise NotFoundError("Report card design not found")
    row = db.scalar(
        select(ReportCardTemplate).where(
            ReportCardTemplate.id == parsed,
            ReportCardTemplate.school_id == school_id,
        )
    )
    if row is None:
        raise NotFoundError("Report card design not found")
    return row


def resolve_default(db: Session, school_id: uuid.UUID) -> ReportCardTemplate | None:
    """The school's default design, or None when it has never saved one."""
    return db.scalar(
        select(ReportCardTemplate)
        .where(
            ReportCardTemplate.school_id == school_id,
            ReportCardTemplate.is_default.is_(True),
        )
        .order_by(ReportCardTemplate.updated_at.desc())
    )


def default_layout(db: Session, school_id: uuid.UUID) -> dict:
    """The layout every renderer should use for this school.

    Falls back to ``BUILTIN_DEFAULT_LAYOUT`` when the school has no designs, so
    the exam office, a class teacher, a bulk PDF and the public portal all draw
    the same card in every state of the world.
    """
    row = resolve_default(db, school_id)
    if row is None:
        return builtin_layout()
    return normalise_layout(row.layout)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def _make_default(db: Session, school_id: uuid.UUID, keep: ReportCardTemplate) -> None:
    """Exactly one default: clear the flag everywhere, then set it on ``keep``."""
    db.execute(
        ReportCardTemplate.__table__.update()
        .where(
            ReportCardTemplate.school_id == school_id,
            ReportCardTemplate.id != keep.id,
        )
        .values(is_default=False)
    )
    keep.is_default = True
    db.flush()


def _promote_default(db: Session, school_id: uuid.UUID) -> None:
    """After deleting the default, hand the flag to the most recently edited
    survivor — a school always has a card, even mid-cleanup."""
    successor = db.scalar(
        select(ReportCardTemplate)
        .where(ReportCardTemplate.school_id == school_id)
        .order_by(ReportCardTemplate.updated_at.desc())
    )
    if successor is not None:
        successor.is_default = True
    db.flush()


def _assert_name_free(
    db: Session, school_id: uuid.UUID, name: str, *, exclude_id: uuid.UUID | None = None
) -> None:
    """Two designs cannot share a name — the designer lists them by name."""
    stmt = select(ReportCardTemplate.id).where(
        ReportCardTemplate.school_id == school_id,
        ReportCardTemplate.name == name,
    )
    if exclude_id is not None:
        stmt = stmt.where(ReportCardTemplate.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError(f"A report card design called {name!r} already exists")


def _audit(
    db: Session,
    *,
    school_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    template: ReportCardTemplate,
    old: dict | None = None,
    new: dict | None = None,
) -> None:
    """Designs are school documents — who changed which one is worth keeping.

    ``action`` is the short verb the audit catalog uses (``create`` / ``update``
    / ``delete``); ``entity_type`` says which document family, and the specific
    operation rides in ``new['operation']`` rather than being crammed into the
    24-character action column.
    """
    db.add(
        AuditLog(
            school_id=school_id,
            user_id=actor_id,
            action=action,
            entity_type="report_card_template",
            entity_id=str(template.id),
            old=old,
            new=new,
        )
    )
    db.flush()


def create_template(
    db: Session,
    school_id: uuid.UUID,
    payload: ReportCardTemplateIn,
    *,
    actor_id: uuid.UUID | None,
) -> ReportCardTemplate:
    """Save a new design.

    The *first* design a school saves becomes the default automatically: the
    alternative — a school with one design and no default — would silently keep
    printing the built-in card, which is exactly the confusion this feature
    exists to remove.
    """
    _assert_name_free(db, school_id, payload.name)
    has_any = db.scalar(
        select(ReportCardTemplate.id).where(ReportCardTemplate.school_id == school_id)
    )
    row = ReportCardTemplate(
        school_id=school_id,
        name=payload.name,
        description=payload.description,
        layout=validate_layout(payload.layout.model_dump(mode="json")),
        is_default=False,
        created_by=actor_id,
    )
    # A savepoint, not a bare flush: two admins saving the same new name at the
    # same instant is a real race, and the unique constraint is the authority on
    # it. Rolling the *whole* transaction back for it would discard the rest of
    # the request's work; the savepoint discards only this insert.
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise ConflictError(f"A report card design called {payload.name!r} already exists") from exc

    if payload.is_default or has_any is None:
        _make_default(db, school_id, row)

    _audit(
        db,
        school_id=school_id,
        actor_id=actor_id,
        action="create",
        template=row,
        new={"name": row.name, "is_default": row.is_default, "operation": "create"},
    )
    return row


def update_template(
    db: Session,
    school_id: uuid.UUID,
    template_id: uuid.UUID,
    payload: ReportCardTemplatePatch,
    *,
    actor_id: uuid.UUID | None,
) -> ReportCardTemplate:
    """Update a design's name, note, layout and/or default flag."""
    row = get_template(db, school_id, template_id)
    data = payload.model_dump(exclude_unset=True)

    if data.get("name") is not None and data["name"] != row.name:
        _assert_name_free(db, school_id, data["name"], exclude_id=row.id)
        row.name = data["name"]
    if "description" in data:
        row.description = data["description"]
    if data.get("layout") is not None:
        row.layout = validate_layout(data["layout"])
    if "is_default" in data and data["is_default"] is False and row.is_default:
        # Clearing the default on the default itself would leave the school with
        # none; the flag moves by naming a successor, not by dropping it.
        raise ValidationError(
            "Set another design as the default instead of clearing this one"
        )

    if data.get("is_default") is True:
        _make_default(db, school_id, row)
    else:
        db.flush()

    _audit(
        db,
        school_id=school_id,
        actor_id=actor_id,
        action="update",
        template=row,
        new={
            "name": row.name,
            "is_default": row.is_default,
            "operation": "update",
            "fields": sorted(data),
        },
    )
    return row


def set_default(
    db: Session,
    school_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None,
) -> ReportCardTemplate:
    """Make one design the school's card."""
    row = get_template(db, school_id, template_id)
    _make_default(db, school_id, row)
    _audit(
        db,
        school_id=school_id,
        actor_id=actor_id,
        action="update",
        template=row,
        new={"name": row.name, "operation": "set_default", "is_default": True},
    )
    return row


def duplicate_template(
    db: Session,
    school_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None,
) -> ReportCardTemplate:
    """Copy a design under a free name — the usual way a school branches a card
    (start from its current one, change the parts it wants)."""
    source = get_template(db, school_id, template_id)
    name = _free_copy_name(db, school_id, source.name)
    row = ReportCardTemplate(
        school_id=school_id,
        name=name,
        description=source.description,
        layout=normalise_layout(source.layout),
        is_default=False,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        school_id=school_id,
        actor_id=actor_id,
        action="create",
        template=row,
        new={"name": row.name, "operation": "duplicate", "copied_from": str(source.id)},
    )
    return row


def _free_copy_name(db: Session, school_id: uuid.UUID, base: str) -> str:
    """``"Primary card"`` -> ``"Primary card (copy)"`` -> ``"... (copy 2)"``."""
    stem = re.sub(r"\s*\(copy(?: \d+)?\)$", "", base).strip()
    existing = {
        name
        for name in db.scalars(
            select(ReportCardTemplate.name).where(
                ReportCardTemplate.school_id == school_id
            )
        )
    }
    candidate = f"{stem} (copy)"[:80]
    counter = 2
    while candidate in existing:
        candidate = f"{stem} (copy {counter})"[:80]
        counter += 1
    return candidate


def delete_template(
    db: Session,
    school_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    actor_id: uuid.UUID | None,
) -> None:
    """Delete a design, promoting a successor if it was the default.

    Designs are hard-deleted (unlike students or comment-bank entries): a design
    is a draft document, the audit trail below keeps the record that it existed,
    and keeping dead designs would clutter the picker the exam office uses.
    """
    row = get_template(db, school_id, template_id)
    was_default = row.is_default
    _audit(
        db,
        school_id=school_id,
        actor_id=actor_id,
        action="delete",
        template=row,
        old={"name": row.name, "was_default": was_default, "operation": "delete"},
    )
    db.delete(row)
    db.flush()
    if was_default:
        _promote_default(db, school_id)


__all__ = [
    "BUILTIN_DEFAULT_LAYOUT",
    "builtin_layout",
    "create_template",
    "default_layout",
    "delete_template",
    "duplicate_template",
    "get_template",
    "list_templates",
    "normalise_layout",
    "resolve_default",
    "set_default",
    "update_template",
    "validate_layout",
]
