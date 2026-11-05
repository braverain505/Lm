"""class_arms: the group classes are ranked with (``class_arms.group_name``)

Revision ID: 0018_class_arm_group
Revises: 0017_user_usernames
Create Date: 2026-11-05

Why this revision exists:
A school that streams a year group into separate classes (SS 1 Science, SS 1
Arts, SS 1 Commercial) still wants one position list for the whole year group,
computed over the subjects each pupil actually offers. Nothing in the schema
said those classes belong together, so every ranking was confined to one arm.
This column is the school's own answer to that: classes sharing a
``group_name`` in the same session are ranked as one.

Nullable on purpose. A class with no group is a group of one, so every existing
school keeps exactly the positions it had before — nothing is backfilled and no
row is rewritten.

Column-only revision (the baseline/0016 pattern creates tables, not columns),
so it inspects the table first: a database that already has the column (a fresh
install built from current models) is a no-op.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0018_class_arm_group"
down_revision: Union[str, None] = "0017_user_usernames"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("class_arms")}


def upgrade() -> None:
    bind = op.get_bind()
    if "group_name" not in _columns(bind):
        op.add_column(
            "class_arms",
            sa.Column("group_name", sa.String(length=40), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "group_name" in _columns(bind):
        op.drop_column("class_arms", "group_name")
