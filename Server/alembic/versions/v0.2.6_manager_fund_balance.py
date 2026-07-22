"""Add manager_fund_balance JSONB and fund_id FK to investment_accounts

Revision ID: v0.2.6_manager_fund_balance
Revises: v0.2.5_add_manager_tables
Create Date: 2026-05-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'v0.2.6_manager_fund_balance'
down_revision: Union[str, Sequence[str], None] = 'v0.2.5_add_manager_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'investment_accounts',
        sa.Column('manager_fund_balance', postgresql.JSONB(), nullable=False, server_default='{}'),
        schema='fundinv',
    )
    op.add_column(
        'investment_accounts',
        sa.Column('fund_id', sa.Integer(), sa.ForeignKey('fundinv.funds.id'), nullable=True),
        schema='fundinv',
    )
    op.create_index('ix_investment_accounts_fund_id', 'investment_accounts', ['fund_id'], schema='fundinv')


def downgrade() -> None:
    op.drop_index('ix_investment_accounts_fund_id', table_name='investment_accounts', schema='fundinv')
    op.drop_column('investment_accounts', 'fund_id', schema='fundinv')
    op.drop_column('investment_accounts', 'manager_fund_balance', schema='fundinv')
