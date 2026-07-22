"""Add investment_account_id to fund_flows

Revision ID: v0.2.3_add_fund_flows_account_id
Revises: af1d51e22989
Create Date: 2026-05-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'v0.2.3_add_fund_flows_account_id'
down_revision: Union[str, Sequence[str], None] = 'af1d51e22989'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'fund_flows',
        sa.Column('investment_account_id', sa.Integer(), nullable=True),
        schema='fundinv',
    )
    op.create_foreign_key(
        'fk_fund_flows_investment_account_id',
        'fund_flows',
        'investment_accounts',
        ['investment_account_id'],
        ['id'],
        source_schema='fundinv',
        referent_schema='fundinv',
    )
    op.create_index(
        'ix_fund_flows_investment_account_id',
        'fund_flows',
        ['investment_account_id'],
        schema='fundinv',
    )


def downgrade() -> None:
    op.drop_index('ix_fund_flows_investment_account_id', schema='fundinv')
    op.drop_constraint('fk_fund_flows_investment_account_id', 'fund_flows', schema='fundinv')
    op.drop_column('fund_flows', 'investment_account_id', schema='fundinv')
