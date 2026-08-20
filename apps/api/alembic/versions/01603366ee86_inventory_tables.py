"""inventory tables

Revision ID: 01603366ee86
Revises: 9f6246f5795d
Create Date: 2026-08-13 15:48:03.341352
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '01603366ee86'
down_revision: Union[str, None] = '9f6246f5795d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('inventory_categories',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'name', name='uq_inventory_category_school_name')
    )
    op.create_index(op.f('ix_inventory_categories_school_id'), 'inventory_categories', ['school_id'], unique=False)
    op.create_table('inventory_items',
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=True),
    sa.Column('sku', sa.String(length=60), nullable=True),
    sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('unit', sa.String(length=30), nullable=True),
    sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('low_stock_threshold', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['inventory_categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'sku', name='uq_inventory_item_school_sku')
    )
    op.create_index(op.f('ix_inventory_items_category_id'), 'inventory_items', ['category_id'], unique=False)
    op.create_index(op.f('ix_inventory_items_school_id'), 'inventory_items', ['school_id'], unique=False)
    op.create_index(op.f('ix_inventory_items_sku'), 'inventory_items', ['sku'], unique=False)
    op.create_table('stock_movements',
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('delta', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('movement_type', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.String(length=300), nullable=True),
    sa.Column('performed_by', sa.Uuid(), nullable=True),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['performed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stock_movements_item_id'), 'stock_movements', ['item_id'], unique=False)
    op.create_index(op.f('ix_stock_movements_school_id'), 'stock_movements', ['school_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_movements_school_id'), table_name='stock_movements')
    op.drop_index(op.f('ix_stock_movements_item_id'), table_name='stock_movements')
    op.drop_table('stock_movements')
    op.drop_index(op.f('ix_inventory_items_sku'), table_name='inventory_items')
    op.drop_index(op.f('ix_inventory_items_school_id'), table_name='inventory_items')
    op.drop_index(op.f('ix_inventory_items_category_id'), table_name='inventory_items')
    op.drop_table('inventory_items')
    op.drop_index(op.f('ix_inventory_categories_school_id'), table_name='inventory_categories')
    op.drop_table('inventory_categories')
