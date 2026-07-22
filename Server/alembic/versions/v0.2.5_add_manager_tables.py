"""Add manager role, table, investor linkage, and fund targeting

Revision ID: v0.2.5_add_manager_tables
Revises: v0.2.4_enhance_audit_logs
Create Date: 2026-05-31 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'v0.2.5_add_manager_tables'
down_revision: Union[str, Sequence[str], None] = 'v0.2.4_enhance_audit_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO fundinv_auth.roles (name)
        SELECT 'manager'
        WHERE NOT EXISTS (SELECT 1 FROM fundinv_auth.roles WHERE name = 'manager')
    """)

    op.create_table(
        'managers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('auth_user_id', sa.Integer(), sa.ForeignKey('fundinv_auth.users.id'), unique=True, nullable=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        schema='fundinv',
    )
    op.create_index('ix_managers_email', 'managers', ['email'], schema='fundinv')
    op.create_index('ix_managers_auth_user_id', 'managers', ['auth_user_id'], schema='fundinv')

    op.add_column(
        'investors',
        sa.Column('manager_id', sa.Integer(), sa.ForeignKey('fundinv.managers.id'), nullable=True),
        schema='fundinv',
    )
    op.create_index('ix_investors_manager_id', 'investors', ['manager_id'], schema='fundinv')

    op.add_column(
        'orders',
        sa.Column('performed_by_user_id', sa.Integer(), sa.ForeignKey('fundinv_auth.users.id'), nullable=True),
        schema='fundinv',
    )

    op.create_table(
        'fund_targeting',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('investor_id', sa.Integer(), sa.ForeignKey('fundinv.investors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fund_id', sa.Integer(), sa.ForeignKey('fundinv.funds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_visible', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema='fundinv',
    )
    op.create_unique_constraint(
        'uq_fund_targeting_investor_fund',
        'fund_targeting',
        ['investor_id', 'fund_id'],
        schema='fundinv',
    )
    op.create_index('ix_fund_targeting_investor_id', 'fund_targeting', ['investor_id'], schema='fundinv')


def downgrade() -> None:
    op.drop_index('ix_fund_targeting_investor_id', table_name='fund_targeting', schema='fundinv')
    op.drop_table('fund_targeting', schema='fundinv')
    op.drop_column('orders', 'performed_by_user_id', schema='fundinv')
    op.drop_index('ix_investors_manager_id', table_name='investors', schema='fundinv')
    op.drop_column('investors', 'manager_id', schema='fundinv')
    op.drop_index('ix_managers_auth_user_id', table_name='managers', schema='fundinv')
    op.drop_index('ix_managers_email', table_name='managers', schema='fundinv')
    op.drop_table('managers', schema='fundinv')
    op.execute("DELETE FROM fundinv_auth.roles WHERE name = 'manager'")
