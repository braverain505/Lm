"""squashed baseline: full current schema, emitted from the SQLAlchemy models

Revision ID: 0010_squashed_baseline
Revises:
Create Date: 2026-09-14

Why a single model-driven baseline:
The previous history (0001_baseline + 11 incremental revisions) was broken in
two ways: (a) ``0001_baseline`` itself ran ``Base.metadata.create_all`` for the
*current* models, so every later ``create_table`` revision collided with tables
that already existed — ``alembic upgrade head`` could not build a fresh
database at all; and (b) the revision graph was tangled (0004 descended from a
hash-named revision that looped back through 0009), so even the ordering was
unreliable. The 12 revisions are replaced by this one.

Fresh databases:
    alembic upgrade head

Existing databases already migrated through the old chain (any DB whose
``alembic_version`` row says ``0009_photo_urls_text``, which was the old head
and whose schema equals the current models):
    alembic stamp 0010_squashed_baseline

This baseline intentionally emits the schema straight from ``Base.metadata``
(so it includes the login/PIN lockout columns on ``users`` and
``student_pins``); future changes must be *incremental* revisions — never
re-run create_all against a populated database.
"""
from typing import Sequence, Union

from alembic import op

import app.models  # noqa: F401 — registers every table on Base.metadata
from app.models import Base

# revision identifiers, used by Alembic.
revision: str = "0010_squashed_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create every table in dependency order (handled by metadata). Indexes
    # (including partial unique indexes) are created too.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
