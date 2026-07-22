"""Enhance audit_logs with entity_type, entity_id, changes, status

Revision ID: v0.2.4_enhance_audit_logs
Revises: v0.2.3_add_fund_flows_account_id
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'v0.2.4_enhance_audit_logs'
down_revision: Union[str, Sequence[str], None] = 'v0.2.3_add_fund_flows_account_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'audit_logs',
        sa.Column('entity_type', sa.String(50), nullable=True),
        schema='fundinv',
    )
    op.add_column(
        'audit_logs',
        sa.Column('entity_id', sa.Integer(), nullable=True),
        schema='fundinv',
    )
    op.add_column(
        'audit_logs',
        sa.Column('changes', postgresql.JSONB(), nullable=True),
        schema='fundinv',
    )
    op.add_column(
        'audit_logs',
        sa.Column('status', sa.String(20), nullable=True),
        schema='fundinv',
    )
    op.create_index(
        'ix_audit_logs_entity_type',
        'audit_logs',
        ['entity_type'],
        schema='fundinv',
    )


def downgrade() -> None:
    op.drop_index('ix_audit_logs_entity_type', schema='fundinv')
    op.drop_column('audit_logs', 'status', schema='fundinv')
    op.drop_column('audit_logs', 'changes', schema='fundinv')
    op.drop_column('audit_logs', 'entity_id', schema='fundinv')
    op.drop_column('audit_logs', 'entity_type', schema='fundinv')
