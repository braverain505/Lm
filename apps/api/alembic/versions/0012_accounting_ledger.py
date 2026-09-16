"""accounting: expenses, cash accounts, discounts, credit notes, refunds

Revision ID: 0012_accounting_ledger
Revises: 0011_login_lockout_columns
Create Date: 2026-09-15

Why this revision exists:
``0010_squashed_baseline`` emits the schema from ``Base.metadata.create_all``,
and ``create_all`` only ever creates *missing* tables — it never runs again once
a database has recorded a later revision. So the accounting tables added to the
models need an incremental revision to reach databases that are already at head;
without it the first accounting query dies with
``relation "expenses" does not exist``.

Two halves:

1. **New tables** — created straight from the model metadata (the same technique
   the squashed baseline uses), which keeps the DDL exactly in step with the
   models and is idempotent: ``create_all`` skips tables that already exist, so a
   fresh database (where the baseline already built them) is a no-op.

2. **New columns on the existing ``payments`` / ``refunds`` tables** —
   ``create_all`` cannot add columns to a table that already exists, so these
   are guarded ``ADD COLUMN IF NOT EXISTS`` statements plus an idempotent
   foreign key, in the same spirit as ``0011_login_lockout_columns``.
"""
from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models import Base
from app.models.accounting import (
    CashAccount,
    CreditNote,
    Expense,
    ExpenseCategory,
    Refund,
    StudentDiscount,
)

# revision identifiers, used by Alembic.
revision: str = "0012_accounting_ledger"
down_revision: Union[str, None] = "0011_login_lockout_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = [
    ExpenseCategory,
    CashAccount,
    Expense,
    StudentDiscount,
    CreditNote,
    Refund,
]

# (table, column, DDL type + default). NOT NULL with a DEFAULT backfills existing
# rows in place; the nullable columns can simply be added.
#
# ``refunds.approved_at`` is the approval timestamp the service records and the
# API returns, and it is part of the model — but a database that already ran this
# revision (while the column was missing from the model) still needs it added.
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("payments", "cash_account_id", "UUID"),
    ("payments", "reconciled", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("payments", "reconciled_at", "TIMESTAMPTZ"),
    ("payments", "bank_reference", "VARCHAR(100)"),
    ("refunds", "approved_at", "TIMESTAMPTZ"),
]

_FK_NAME = "fk_payments_cash_account_id_cash_accounts"


def upgrade() -> None:
    bind = op.get_bind()
    # Creates only the tables that are genuinely absent (metadata handles the
    # dependency order), so this is safe on both a fresh and a live database.
    Base.metadata.create_all(bind=bind, tables=[t.__table__ for t in _NEW_TABLES])

    for table, column, ddl in _ADDED_COLUMNS:
        op.execute(
            f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
        )

    # The model declares this FK; ALTER above only added the bare column, so add
    # the constraint too (guarded — ADD CONSTRAINT has no IF NOT EXISTS).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{_FK_NAME}'
            ) THEN
                ALTER TABLE "payments"
                    ADD CONSTRAINT "{_FK_NAME}"
                    FOREIGN KEY ("cash_account_id")
                    REFERENCES "cash_accounts" ("id")
                    ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        f'ALTER TABLE "payments" DROP CONSTRAINT IF EXISTS "{_FK_NAME}"'
    )
    for table, column, _ in _ADDED_COLUMNS:
        op.execute(f'ALTER TABLE "{table}" DROP COLUMN IF EXISTS "{column}"')
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[t.__table__ for t in reversed(_NEW_TABLES)])
