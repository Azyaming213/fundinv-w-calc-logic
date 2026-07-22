"""Add creator_manager_id to funds table

Revision ID: v0.2.7_add_fund_manager
Revises: v0.2.6_manager_fund_balance
Create Date: 2026-05-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'v0.2.7_add_fund_manager'
down_revision: Union[str, Sequence[str], None] = 'v0.2.6_manager_fund_balance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'funds',
        sa.Column('creator_manager_id', sa.Integer(), sa.ForeignKey('fundinv.managers.id'), nullable=True),
        schema='fundinv',
    )
    op.create_index('ix_funds_creator_manager_id', 'funds', ['creator_manager_id'], schema='fundinv')


def downgrade() -> None:
    op.drop_index('ix_funds_creator_manager_id', table_name='funds', schema='fundinv')
    op.drop_column('funds', 'creator_manager_id', schema='fundinv')
