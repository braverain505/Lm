"""Report card design schemas: the document a school builds in the designer.

The layout is *data*, and this module is the contract for it. Widget types are
validated against a closed catalog and free text is length-bounded and
tag-stripped before it is ever stored, so:

* a card can never reference a renderer the web app does not have (a design made
  by a newer/older client is rejected at the edge, not broken at print time);
* school-authored copy on a card cannot smuggle markup into a document that is
  printed and mailed home.

The catalog here and ``apps/web/src/lib/report-layout.ts`` are deliberately
two halves of one contract: add a widget on both sides, or not at all.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --- The widget catalog -------------------------------------------------------
# Every widget the designer offers. Order is the order the designer's palette
# groups them in, not the order they appear on a card (that is per-school).
WIDGET_TYPES: tuple[str, ...] = (
    "header",
    "student_info",
    "cognitive_domain",
    "psychomotor_domain",
    "performance_summary",
    "grading_key",
    "best_in_subjects",
    "attendance",
    "conduct",
    "next_term",
    "comments",
    "signatures",
    "custom_text",
    "spacer",
)

# Visual themes. Each maps onto a ``rc-template-<id>`` class in
# ``report-card-templates.css``, so the original four themes keep working and a
# school that never opens the designer keeps the card it already had.
THEMES: tuple[str, ...] = ("classic", "modern", "elegant", "minimal")

DEFAULT_THEME = "classic"
LAYOUT_VERSION = 1

# Bounds. Generous for a real card, hostile to a payload used as storage.
MAX_WIDGETS = 40
MAX_PROPS = 12
MAX_PROP_VALUE = 2000
MAX_CUSTOM_TEXT = 2000

_TAGS = re.compile(r"<[^>]+>")
# Script/style *bodies* are dropped with their tags: their text is never report
# copy, and leaving it behind would print "alert(1)" across a card.
_SCRIPTS = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def strip_tags(value: str) -> str:
    """Remove markup but keep the text as written.

    Deliberately *not* ``html.escape`` — the card is rendered as React text
    nodes, which escape on their own. Escaping here would print ``&amp;``
    literally on a parent's report card.
    """
    return _TAGS.sub("", _SCRIPTS.sub(" ", value)).strip()


class LayoutWidget(BaseModel):
    """One element on a card: a catalog type plus its own settings.

    ``id`` is the instance identity the designer drags around (a school may put
    two custom-text notes on one card, so the type alone is not unique).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    hidden: bool = False

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in WIDGET_TYPES:
            raise ValueError(
                f"Unknown report card widget {value!r}. Known types: "
                f"{', '.join(WIDGET_TYPES)}"
            )
        return value

    @field_validator("props")
    @classmethod
    def _bounded_props(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > MAX_PROPS:
            raise ValueError(f"A widget may set at most {MAX_PROPS} options")
        cleaned: dict[str, Any] = {}
        for key, raw in value.items():
            if not isinstance(key, str) or len(key) > 40:
                raise ValueError("Widget option names must be short strings")
            if isinstance(raw, str):
                text = strip_tags(raw)
                if len(text) > MAX_PROP_VALUE:
                    raise ValueError(
                        f"Widget option {key!r} is too long (max {MAX_PROP_VALUE})"
                    )
                cleaned[key] = text
            elif isinstance(raw, (bool, int, float)) or raw is None:
                cleaned[key] = raw
            else:
                # Lists/objects/tuples in props — not a shape any widget needs.
                raise ValueError(f"Widget option {key!r} must be text, a number or a flag")
        return cleaned


class ReportCardLayout(BaseModel):
    """A complete card design: a theme plus the ordered widgets to render."""

    model_config = ConfigDict(extra="forbid")

    version: int = LAYOUT_VERSION
    theme: str = DEFAULT_THEME
    widgets: list[LayoutWidget] = Field(min_length=1, max_length=MAX_WIDGETS)

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, value: str) -> str:
        if value not in THEMES:
            raise ValueError(
                f"Unknown theme {value!r}. Known themes: {', '.join(THEMES)}"
            )
        return value

    @model_validator(mode="after")
    def _unique_widget_ids(self) -> "ReportCardLayout":
        if len({w.id for w in self.widgets}) != len(self.widgets):
            raise ValueError("Widget ids must be unique within a layout")
        return self


class ReportCardTemplateIn(BaseModel):
    """Create/update payload for one design."""

    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    layout: ReportCardLayout
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = strip_tags(value)
        if not cleaned:
            raise ValueError("Give the design a name")
        return cleaned

    @field_validator("description")
    @classmethod
    def _clean_description(cls, value: str | None) -> str | None:
        return strip_tags(value) or None if value else None


class ReportCardTemplatePatch(BaseModel):
    """Partial update — every field optional, so the designer can save a layout
    without resending (or revalidating) the name it did not touch."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    layout: ReportCardLayout | None = None
    is_default: bool | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = strip_tags(value)
        if not cleaned:
            raise ValueError("Give the design a name")
        return cleaned


class ReportCardTemplateOut(BaseModel):
    """One stored design."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    layout: dict
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ReportCardTemplateBrief(BaseModel):
    """The design a renderer should draw, with just enough metadata to say
    which one it is.

    ``builtin`` is true when the school has saved no design and the app is
    falling back to the card it shipped with — the UI says so explicitly rather
    than pretending the school chose it.
    """

    template_id: uuid.UUID | None = None
    name: str
    theme: str = DEFAULT_THEME
    layout: dict
    builtin: bool = False


__all__ = [
    "DEFAULT_THEME",
    "LAYOUT_VERSION",
    "MAX_WIDGETS",
    "ReportCardLayout",
    "ReportCardTemplateBrief",
    "ReportCardTemplateIn",
    "ReportCardTemplateOut",
    "ReportCardTemplatePatch",
    "THEMES",
    "WIDGET_TYPES",
    "LayoutWidget",
    "strip_tags",
]
