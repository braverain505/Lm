"""library tables

Revision ID: 2844480c25b9
Revises: 01603366ee86
Create Date: 2026-08-13 16:03:25.334184
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2844480c25b9'
down_revision: Union[str, None] = '01603366ee86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('books',
    sa.Column('title', sa.String(length=250), nullable=False),
    sa.Column('author', sa.String(length=200), nullable=True),
    sa.Column('isbn', sa.String(length=32), nullable=True),
    sa.Column('category', sa.String(length=80), nullable=True),
    sa.Column('publisher', sa.String(length=150), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('total_copies', sa.Integer(), nullable=False),
    sa.Column('available_copies', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_books_isbn'), 'books', ['isbn'], unique=False)
    op.create_index(op.f('ix_books_school_id'), 'books', ['school_id'], unique=False)
    op.create_table('borrowings',
    sa.Column('book_id', sa.Uuid(), nullable=False),
    sa.Column('borrower_type', sa.String(length=16), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=True),
    sa.Column('staff_id', sa.Uuid(), nullable=True),
    sa.Column('borrowed_on', sa.Date(), nullable=False),
    sa.Column('due_on', sa.Date(), nullable=False),
    sa.Column('returned_on', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['book_id'], ['books.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_borrowings_book_id'), 'borrowings', ['book_id'], unique=False)
    op.create_index(op.f('ix_borrowings_school_id'), 'borrowings', ['school_id'], unique=False)
    op.create_index(op.f('ix_borrowings_staff_id'), 'borrowings', ['staff_id'], unique=False)
    op.create_index(op.f('ix_borrowings_student_id'), 'borrowings', ['student_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_borrowings_student_id'), table_name='borrowings')
    op.drop_index(op.f('ix_borrowings_staff_id'), table_name='borrowings')
    op.drop_index(op.f('ix_borrowings_school_id'), table_name='borrowings')
    op.drop_index(op.f('ix_borrowings_book_id'), table_name='borrowings')
    op.drop_table('borrowings')
    op.drop_index(op.f('ix_books_school_id'), table_name='books')
    op.drop_index(op.f('ix_books_isbn'), table_name='books')
    op.drop_table('books')
