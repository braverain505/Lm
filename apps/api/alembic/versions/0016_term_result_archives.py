"""results: archived report cards per term (``term_result_archives``)

Revision ID: 0016_term_result_archives
Revises: 0015_report_card_templates
Create Date: 2026-10-29

Why this revision exists:
A school can reopen a closed term to correct a result. That rewrites the rows a
printed report card was built from, so the version a parent already holds would
otherwise vanish. This table stores a frozen copy of every published card
(including the layout it rendered with) before the term is reopened — one row
per archive event, versioned within the term.

Created from model metadata, the same idempotent technique as 0010/0012/0013/
0014/0015: the DDL stays exactly in step with the model and a fresh database
where the baseline already built the table is a no-op.
"""
from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models import Base
from app.models.results import TermResultArchive

# revision identifiers, used by Alembic.
revision: str = "0016_term_result_archives"
down_revision: Union[str, None] = "0015_report_card_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = [TermResultArchive]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[t.__table__ for t in _NEW_TABLES])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[t.__table__ for t in reversed(_NEW_TABLES)])
