"""psychomotor assessment rows for report cards

Revision ID: 0004_psychomotor
Revises: 9f6246f5795d
Create Date: 2026-08-17 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_psychomotor'
down_revision: Union[str, None] = '2844480c25b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'psychomotor_assessments',
        sa.Column('student_enrollment_id', sa.Uuid(), nullable=False),
        sa.Column('term_id', sa.Uuid(), nullable=False),
        sa.Column('learning_area', sa.String(length=80), nullable=False),
        sa.Column('achievement_level', sa.String(length=24), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_enrollment_id'], ['student_enrollments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['term_id'], ['terms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'school_id',
            'student_enrollment_id',
            'term_id',
            'learning_area',
            name='uq_psychomotor_area',
        ),
    )
    op.create_index(
        op.f('ix_psychomotor_assessments_student_enrollment_id'),
        'psychomotor_assessments',
        ['student_enrollment_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_psychomotor_assessments_term_id'),
        'psychomotor_assessments',
        ['term_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_psychomotor_enrollment_term'),
        'psychomotor_assessments',
        ['student_enrollment_id', 'term_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_psychomotor_enrollment_term'), table_name='psychomotor_assessments'
    )
    op.drop_index(
        op.f('ix_psychomotor_assessments_term_id'),
        table_name='psychomotor_assessments',
    )
    op.drop_index(
        op.f('ix_psychomotor_assessments_student_enrollment_id'),
        table_name='psychomotor_assessments',
    )
    op.drop_table('psychomotor_assessments')