"""Record fixed-amount demo PayNow settlement evidence.

Revision ID: v0.5.2_paynow_demo
Revises: v0.5.1_manager_values
"""

from alembic import op
import sqlalchemy as sa


revision = "v0.5.2_paynow_demo"
down_revision = "v0.5.1_manager_values"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fund_flows",
        sa.Column("paid_amount", sa.Numeric(precision=18, scale=4), nullable=True),
        schema="fundinv",
    )
    op.add_column(
        "fund_flows",
        sa.Column("payment_received_at", sa.DateTime(timezone=True), nullable=True),
        schema="fundinv",
    )
    op.create_check_constraint(
        "ck_fund_flows_paid_amount_positive",
        "fund_flows",
        "paid_amount IS NULL OR paid_amount > 0",
        schema="fundinv",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_fund_flows_paid_amount_positive", "fund_flows",
        schema="fundinv", type_="check",
    )
    op.drop_column("fund_flows", "payment_received_at", schema="fundinv")
    op.drop_column("fund_flows", "paid_amount", schema="fundinv")
