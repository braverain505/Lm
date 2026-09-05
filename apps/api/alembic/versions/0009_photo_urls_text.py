"""people photo_url varchar(500) -> Text (students + staff)

Revision ID: 0009_photo_urls_text
Revises: 0008_logo_url_text
Create Date: 2026-09-05

Student (and staff) photos are stored as Base64 data URLs so they survive
Render's ephemeral filesystem (the same reason school logos are Base64 in the
DB). A data URL for even a small image exceeds ``varchar(500)``, so widen the
columns to ``Text``.

Note: the downgrade restores ``varchar(500)`` and will fail on rows whose
photo exceeds 500 chars; that is the expected consequence of reverting.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009_photo_urls_text"
down_revision: Union[str, None] = "0008_logo_url_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "students",
        "photo_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "staff",
        "photo_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "students",
        "photo_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "staff",
        "photo_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
