"""portal: per-student result codes (``student_result_codes``)

Revision ID: 0014_student_result_codes
Revises: 0013_school_result_pins
Create Date: 2026-09-17

Why this revision exists:
The login screen no longer asks for an admission number. Instead, each student
gets their own result code (``GVS-7K42Q``) that identifies the child on its own,
so the public ``/result-check`` door needs a table keyed by student. This adds
``student_result_codes`` next to the legacy school-wide ``school_result_pins``.

The table is created straight from the model metadata (the same technique the
squashed baseline, ``0012_accounting_ledger`` and ``0013_school_result_pins``
use), which keeps the DDL exactly in step with the model and is idempotent:
``create_all`` skips a table that already exists, so a fresh database — where the
baseline already built it — is a no-op.

The *partial* unique index (``uq_student_result_code_one``, ``school_id`` +
``student_id`` ``WHERE revoked_at IS NULL``) travels with the table automatically,
because it is declared in ``__table_args__``. Rotation keeps the revoked row for
audit, which is exactly why uniqueness cannot be a plain constraint.
"""
from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models import Base
from app.models.portal import StudentResultCode

# revision identifiers, used by Alembic.
revision: str = "0014_student_result_codes"
down_revision: Union[str, None] = "0013_school_result_pins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = [StudentResultCode]


def upgrade() -> None:
    bind = op.get_bind()
    # Creates only the table if it is genuinely absent, so this is safe on both
    # a fresh and a live database.
    Base.metadata.create_all(bind=bind, tables=[t.__table__ for t in _NEW_TABLES])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[t.__table__ for t in reversed(_NEW_TABLES)])
