"""users: optional username for sign-in (``users.username``)

Revision ID: 0017_user_usernames
Revises: 0016_term_result_archives
Create Date: 2026-10-30

Why this revision exists:
Asked to allow signing in with a username instead of an email — a teacher on a
school register often has no mailbox of their own. The column is nullable so
every existing account keeps working with its email, and unique so two people
cannot claim the same sign-in name. Emails stay unique and required; nothing
is backfilled.

Column-only revision (the baseline/0016 pattern creates tables, not columns),
so it inspects the table first: a database that already has the column (a fresh
install built from current models) is a no-op.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017_user_usernames"
down_revision: Union[str, None] = "0016_term_result_archives"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("users")}


def _indexes(bind) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes("users")}


def upgrade() -> None:
    bind = op.get_bind()
    if "username" not in _columns(bind):
        op.add_column("users", sa.Column("username", sa.String(length=40), nullable=True))
    if "uq_users_username" not in _indexes(bind):
        op.create_index("uq_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "uq_users_username" in _indexes(bind):
        op.drop_index("uq_users_username", table_name="users")
    if "username" in _columns(bind):
        op.drop_column("users", "username")
