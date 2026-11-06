"""sections: nursery / primary / secondary, and per-section scoresheets

Revision ID: 0019_sections
Revises: 0018_class_arm_group
Create Date: 2026-11-06

Why this revision exists:
A school that runs a primary and a secondary section usually marks them
differently — a primary scoresheet of three CAs and an exam is not the
secondary one — and draws a different report card for each. Nothing in the
schema said which part of the school a class belongs to, so every class had to
share one structure. ``class_arms.section`` is that answer, and
``assessment_components.section`` is what makes a scoresheet per section
possible: a school-wide row (NULL section) stays the single structure every
class uses, and a section row is that section's own structure.

The unique index on the component scope grows ``section`` so a school in
"separate sections" mode can have its own "1st CA" per section.

Backfill:
Class sections are guessed from the class name — JSS/SS for secondary, creche
and nursery names for nursery, Basic/Primary/Pry/Grade for primary — and left
NULL when the name says nothing. The guess is inert: a school uses one
scoresheet for every class until it chooses "separate sections" in settings,
and the classes page shows and edits the value either way. Nothing else is
rewritten: every existing component row stays school-wide (NULL section), so
every existing school scores, grades and ranks exactly as it did.

Column-and-index revision, so it inspects first: a database already built from
current models is a no-op apart from the index.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0019_sections"
down_revision: Union[str, None] = "0018_class_arm_group"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The name patterns behind the suggested section, most specific first. Written
# the same way the API's ``guess_section`` reads a name, so a class created
# after this migration lands on the section the backfill would have given it.
SECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("secondary", r"\m(jss|js|sss|ss|secondary)\M"),
    ("nursery", r"\m(creche|crèche|nursery|kindergarten|kg|playgroup|reception|prekg)\M"),
    ("primary", r"\m(basic|primary|pry|grade)\M"),
)


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _add_section(bind, table: str) -> None:
    if "section" not in _columns(bind, table):
        op.add_column(
            table, sa.Column("section", sa.String(length=16), nullable=True)
        )


def _rebuild_component_index(bind) -> None:
    """Widen the component scope key to include the section.

    Dropped and recreated rather than altered: the index is partial-unique with
    NULLS NOT DISTINCT, which has no ALTER form. Recreating it is a plain
    metadata-only swap on a table of a few dozen rows per school.
    """
    names = {index["name"] for index in sa.inspect(bind).get_indexes(
        "assessment_components"
    )}
    if "uq_component_scope_name" in names:
        op.drop_index("uq_component_scope_name", table_name="assessment_components")
    op.execute(
        "CREATE UNIQUE INDEX uq_component_scope_name "
        "ON assessment_components "
        "(school_id, term_id, class_arm_id, section, name) NULLS NOT DISTINCT"
    )


def _backfill_sections(bind) -> None:
    for section, pattern in SECTION_PATTERNS:
        bind.execute(
            sa.text(
                "UPDATE class_arms SET section = :section "
                "WHERE section IS NULL "
                "AND lower(regexp_replace(name, '[^a-zA-Z0-9]+', ' ', 'g')) ~ :pattern"
            ),
            {"section": section, "pattern": pattern},
        )


def upgrade() -> None:
    bind = op.get_bind()
    _add_section(bind, "class_arms")
    _add_section(bind, "assessment_components")
    _rebuild_component_index(bind)
    _backfill_sections(bind)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DROP INDEX IF EXISTS uq_component_scope_name"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_component_scope_name "
        "ON assessment_components "
        "(school_id, term_id, class_arm_id, name) NULLS NOT DISTINCT"
    )
    for table in ("assessment_components", "class_arms"):
        if "section" in _columns(bind, table):
            op.drop_column(table, "section")
