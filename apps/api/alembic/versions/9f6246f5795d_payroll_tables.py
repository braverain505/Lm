"""payroll tables

Revision ID: 9f6246f5795d
Revises: 0003_fees_attendance
Create Date: 2026-08-13 15:20:33.421614
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9f6246f5795d'
down_revision: Union[str, None] = '0003_fees_attendance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('salary_structures',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('basic_salary', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('tax_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_salary_structures_school_id'), 'salary_structures', ['school_id'], unique=False)
    op.create_table('staff_salaries',
    sa.Column('staff_id', sa.Uuid(), nullable=False),
    sa.Column('structure_id', sa.Uuid(), nullable=False),
    sa.Column('effective_from', sa.String(length=10), nullable=True),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['structure_id'], ['salary_structures.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'staff_id', name='uq_staff_salary_school_staff')
    )
    op.create_index(op.f('ix_staff_salaries_school_id'), 'staff_salaries', ['school_id'], unique=False)
    op.create_index(op.f('ix_staff_salaries_staff_id'), 'staff_salaries', ['staff_id'], unique=False)
    op.create_index(op.f('ix_staff_salaries_structure_id'), 'staff_salaries', ['structure_id'], unique=False)
    op.create_table('pay_runs',
    sa.Column('month', sa.String(length=7), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('total_gross', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('total_tax', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('total_net', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('paid_at', sa.DateTime(), nullable=True),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'month', name='uq_pay_run_school_month')
    )
    op.create_index(op.f('ix_pay_runs_school_id'), 'pay_runs', ['school_id'], unique=False)
    op.create_table('payslips',
    sa.Column('pay_run_id', sa.Uuid(), nullable=False),
    sa.Column('staff_id', sa.Uuid(), nullable=False),
    sa.Column('structure_id', sa.Uuid(), nullable=True),
    sa.Column('gross', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('tax', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('net', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('school_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['pay_run_id'], ['pay_runs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['structure_id'], ['salary_structures.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pay_run_id', 'staff_id', name='uq_payslip_run_staff')
    )
    op.create_index(op.f('ix_payslips_pay_run_id'), 'payslips', ['pay_run_id'], unique=False)
    op.create_index(op.f('ix_payslips_school_id'), 'payslips', ['school_id'], unique=False)
    op.create_index(op.f('ix_payslips_staff_id'), 'payslips', ['staff_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payslips_staff_id'), table_name='payslips')
    op.drop_index(op.f('ix_payslips_school_id'), table_name='payslips')
    op.drop_index(op.f('ix_payslips_pay_run_id'), table_name='payslips')
    op.drop_table('payslips')
    op.drop_index(op.f('ix_pay_runs_school_id'), table_name='pay_runs')
    op.drop_table('pay_runs')
    op.drop_index(op.f('ix_staff_salaries_structure_id'), table_name='staff_salaries')
    op.drop_index(op.f('ix_staff_salaries_staff_id'), table_name='staff_salaries')
    op.drop_index(op.f('ix_staff_salaries_school_id'), table_name='staff_salaries')
    op.drop_table('staff_salaries')
    op.drop_index(op.f('ix_salary_structures_school_id'), table_name='salary_structures')
    op.drop_table('salary_structures')
