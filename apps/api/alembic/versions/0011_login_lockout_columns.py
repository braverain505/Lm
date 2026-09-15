"""add the login/PIN lockout columns to already-provisioned databases

Revision ID: 0011_login_lockout_columns
Revises: 0010_squashed_baseline
Create Date: 2026-09-15

Why this revision exists:
The production-readiness commit added four columns straight to the SQLAlchemy
models — ``users.failed_login_count``, ``users.locked_until``,
``student_pins.failed_pin_count`` and ``student_pins.pin_locked_until`` — but
shipped no incremental revision for them. ``0010_squashed_baseline`` emits the
schema with ``Base.metadata.create_all``, and ``create_all`` *skips tables that
already exist*, so a database that was provisioned before those columns were
declared kept its old ``users``/``student_pins`` shape and no migration ever
altered it. The API then dies on the first SELECT of ``User``:

    ERROR: column users.failed_login_count does not exist

which is exactly what made every login return 500.

Every statement is guarded with ``IF NOT EXISTS`` so this revision is safe on
both shapes of database: a fresh one built by ``0010`` (``create_all`` already
created the columns) and an older, already-provisioned one (the columns are
added here).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_login_lockout_columns"
down_revision: Union[str, None] = "0010_squashed_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, DDL type + default). NOT NULL with a DEFAULT backfills any
# existing rows in place; the nullable timestamp columns can simply be added.
_COLUMNS: list[tuple[str, str, str]] = [
    ("users", "failed_login_count", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "locked_until", "TIMESTAMPTZ"),
    ("student_pins", "failed_pin_count", "INTEGER NOT NULL DEFAULT 0"),
    ("student_pins", "pin_locked_until", "TIMESTAMPTZ"),
]


def upgrade() -> None:
    for table, column, ddl in _COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
        )


def downgrade() -> None:
    for table, column, _ in _COLUMNS:
        op.execute(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{column}"')
