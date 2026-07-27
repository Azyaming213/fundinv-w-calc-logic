"""Allow ownership percentages up to and including 100.

Revision ID: v0.4.2_share_pct
Revises: v0.4.1_backfill_positions
"""

from alembic import op
import sqlalchemy as sa


revision = "v0.4.2_share_pct"
down_revision = "v0.4.1_backfill_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "portfolio_holdings",
        "shareholding_pct",
        existing_type=sa.Numeric(10, 8),
        type_=sa.Numeric(12, 8),
        existing_nullable=False,
        schema="fundinv",
    )
    op.alter_column(
        "portfolio_holdings",
        "opening_shareholding_pct",
        existing_type=sa.Numeric(10, 8),
        type_=sa.Numeric(12, 8),
        existing_nullable=True,
        schema="fundinv",
    )


def downgrade() -> None:
    op.alter_column(
        "portfolio_holdings",
        "opening_shareholding_pct",
        existing_type=sa.Numeric(12, 8),
        type_=sa.Numeric(10, 8),
        existing_nullable=True,
        schema="fundinv",
    )
    op.alter_column(
        "portfolio_holdings",
        "shareholding_pct",
        existing_type=sa.Numeric(12, 8),
        type_=sa.Numeric(10, 8),
        existing_nullable=False,
        schema="fundinv",
    )
