"""core subjects, per-role result comments, comment bank

Revision ID: 0005_comment_system
Revises: 0004_psychomotor
Create Date: 2026-08-17 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005_comment_system'
down_revision: Union[str, None] = '0004_psychomotor'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subjects',
        sa.Column('is_core', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'result_comments',
        sa.Column('role', sa.String(length=24), nullable=False, server_default='principal'),
    )
    op.drop_constraint('uq_result_comment', 'result_comments', type_='unique')
    op.create_unique_constraint(
        'uq_result_comment_role',
        'result_comments',
        ['school_id', 'term_id', 'student_enrollment_id', 'role'],
    )
    op.create_table(
        'comment_bank',
        sa.Column('comment_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('sentiment', sa.String(length=24), nullable=False),
        sa.Column('applicable_domain', sa.String(length=40), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('school_id', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_comment_bank_category'), 'comment_bank', ['school_id', 'category'], unique=False
    )
    op.create_index(
        op.f('ix_comment_bank_sentiment'), 'comment_bank', ['school_id', 'sentiment'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_comment_bank_sentiment'), table_name='comment_bank')
    op.drop_index(op.f('ix_comment_bank_category'), table_name='comment_bank')
    op.drop_table('comment_bank')
    op.drop_constraint('uq_result_comment_role', 'result_comments', type_='unique')
    op.create_unique_constraint(
        'uq_result_comment',
        'result_comments',
        ['school_id', 'term_id', 'student_enrollment_id'],
    )
    op.drop_column('result_comments', 'role')
    op.drop_column('subjects', 'is_core')