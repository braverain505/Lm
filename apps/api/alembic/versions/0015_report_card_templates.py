"""report cards: school-designed templates (``report_card_templates``)

Revision ID: 0015_report_card_templates
Revises: 0014_student_result_codes
Create Date: 2026-09-23

Why this revision exists:
Report card styling used to live in the browser (``localStorage``) as one of
four fixed CSS themes. That cannot express a school's own card — and, worse, it
is per-device: the exam office, a class teacher and a parent on the public
portal each rendered a different card for the same student. This revision adds
``report_card_templates`` so each school stores its own drag-and-drop designs
server-side and every renderer reads the same document.

The table is created straight from the model metadata (the same technique the
squashed baseline, ``0012_accounting_ledger``, ``0013_school_result_pins`` and
``0014_student_result_codes`` use), which keeps the DDL exactly in step with the
model and is idempotent: ``create_all`` skips a table that already exists, so a
fresh database — where the baseline already built it — is a no-op.

Both declared constraints travel with the table automatically: the
``uq_report_card_template_name`` unique constraint (one name per school) and the
``ix_report_card_template_default`` index over ``(school_id, is_default)`` that
the every-render default lookup reads.
"""
from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models import Base
from app.models.report_card import ReportCardTemplate

# revision identifiers, used by Alembic.
revision: str = "0015_report_card_templates"
down_revision: Union[str, None] = "0014_student_result_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = [ReportCardTemplate]


def upgrade() -> None:
    bind = op.get_bind()
    # Creates only the table if it is genuinely absent, so this is safe on both
    # a fresh and a live database.
    Base.metadata.create_all(bind=bind, tables=[t.__table__ for t in _NEW_TABLES])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[t.__table__ for t in reversed(_NEW_TABLES)])
