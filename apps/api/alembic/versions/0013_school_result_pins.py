"""portal: the school-wide result code (``school_result_pins``)

Revision ID: 0013_school_result_pins
Revises: 0012_accounting_ledger
Create Date: 2026-09-17

Why this revision exists:
``0010_squashed_baseline`` emits the schema from ``Base.metadata.create_all``,
and ``create_all`` only ever creates *missing* tables — it never runs again once
a database has recorded a later revision. So the ``school_result_pins`` table
added to the models needs an incremental revision to reach databases that are
already at head; without it the first portal-code query dies with
``relation "school_result_pins" does not exist``.

One table, created straight from the model metadata (the same technique the
squashed baseline and ``0012_accounting_ledger`` use), which keeps the DDL
exactly in step with the model and is idempotent: ``create_all`` skips a table
that already exists, so a fresh database — where the baseline already built it —
is a no-op.

Note the *partial* unique index (``uq_school_result_pin_one``, ``school_id``
``WHERE revoked_at IS NULL``) comes along with the table automatically, because
it is declared in ``__table_args__``. Rotation keeps the revoked row for audit,
which is exactly why uniqueness cannot be a plain constraint on ``school_id``.
"""
from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models import Base
from app.models.portal import SchoolResultPin

# revision identifiers, used by Alembic.
revision: str = "0013_school_result_pins"
down_revision: Union[str, None] = "0012_accounting_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = [SchoolResultPin]


def upgrade() -> None:
    bind = op.get_bind()
    # Creates only the table if it is genuinely absent, so this is safe on both
    # a fresh and a live database.
    Base.metadata.create_all(bind=bind, tables=[t.__table__ for t in _NEW_TABLES])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[t.__table__ for t in reversed(_NEW_TABLES)])
