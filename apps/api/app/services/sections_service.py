"""Sections: nursery, primary, secondary.

A school that runs a primary and a secondary section almost always marks them
differently and draws a different report card for each. The whole feature hangs
off one decision the school makes once, in settings:

    "same"      — one scoresheet and one card style for every class. This is
                  the default, and exactly how every school worked before
                  sections existed.
    "separate"  — each section follows its own scoresheet and its own card.

This module holds only the vocabulary and the switch, so the scoresheet side
(``results_service``), the report card side (``report_card_service``) and the
classes page all read the same words and cannot drift apart.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from ..models import ClassArm, School

SECTION_NURSERY = "nursery"
SECTION_PRIMARY = "primary"
SECTION_SECONDARY = "secondary"

#: In the order a school reads them — youngest first.
SECTIONS: tuple[str, ...] = (SECTION_NURSERY, SECTION_PRIMARY, SECTION_SECONDARY)

SECTION_LABELS: dict[str, str] = {
    SECTION_NURSERY: "Nursery",
    SECTION_PRIMARY: "Primary",
    SECTION_SECONDARY: "Secondary",
}

SECTION_SAME = "same"
SECTION_SEPARATE = "separate"
SECTION_MODES: tuple[str, ...] = (SECTION_SAME, SECTION_SEPARATE)

# What a class name suggests, most specific first. Deliberately conservative: a
# name that says nothing leaves the class unclassified, and an unclassified
# class follows the school-wide structure.
SECTION_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (SECTION_SECONDARY, ("jss", "js", "sss", "ss", "secondary")),
    (
        SECTION_NURSERY,
        (
            "creche", "crèche", "nursery", "kindergarten", "kg",
            "playgroup", "reception", "prekg",
        ),
    ),
    (SECTION_PRIMARY, ("basic", "primary", "pry", "grade")),
)


def is_section(value) -> bool:
    return isinstance(value, str) and value in SECTIONS


def guess_section(name: str | None) -> str | None:
    """The section a class name suggests, or None when it says nothing.

    Only ever a suggestion: the value is stored on the class and stays the
    school's to change, and it changes nothing about scoring until the school
    chooses separate sections.
    """
    tokens = {token for token in re.split(r"[^a-z0-9]+", (name or "").lower()) if token}
    for section, hints in SECTION_HINTS:
        if tokens.intersection(hints):
            return section
    return None


def mode_for(db: Session, school_id: uuid.UUID) -> str:
    """Whether this school keeps one structure for every class or one per
    section. Anything unrecognised reads as "same", which is the behaviour a
    school that has never touched the setting expects."""
    school = db.get(School, school_id)
    raw = (school.settings or {}).get("section_mode") if school is not None else None
    return SECTION_SEPARATE if raw == SECTION_SEPARATE else SECTION_SAME


def is_separate(db: Session, school_id: uuid.UUID) -> bool:
    return mode_for(db, school_id) == SECTION_SEPARATE


def section_for_arm(db: Session, arm: ClassArm | None) -> str | None:
    """A class's section, or None when the school has not classified it."""
    return arm.section if arm is not None else None
