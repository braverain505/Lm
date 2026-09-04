"""schools.logo_url varchar(500) -> Text

Revision ID: 0008_logo_url_text
Revises: 0007_platform_admin
Create Date: 2026-09-04

School logos are stored as Base64 data URLs (``data:image/png;base64,...``),
which exceed ``varchar(500)`` for even a small image. PostgreSQL rejects the
write, so uploads fail with a 500. Widen the column to ``Text``.

Note: the downgrade restores ``varchar(500)`` and will fail on rows whose logo
exceeds 500 chars; that is the expected consequence of reverting this change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_logo_url_text"
down_revision: Union[str, None] = "0007_platform_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "schools",
        "logo_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "schools",
        "logo_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )