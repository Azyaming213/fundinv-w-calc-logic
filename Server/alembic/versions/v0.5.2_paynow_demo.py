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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]
        for column in inspector.get_columns("fund_flows", schema="fundinv")
    }
    if "paid_amount" not in columns:
        op.add_column(
            "fund_flows",
            sa.Column("paid_amount", sa.Numeric(precision=18, scale=4), nullable=True),
            schema="fundinv",
        )
    if "payment_received_at" not in columns:
        op.add_column(
            "fund_flows",
            sa.Column("payment_received_at", sa.DateTime(timezone=True), nullable=True),
            schema="fundinv",
        )

    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(
            "fund_flows", schema="fundinv"
        )
    }
    if "ck_fund_flows_paid_amount_positive" not in constraints:
        op.create_check_constraint(
            "ck_fund_flows_paid_amount_positive",
            "fund_flows",
            "paid_amount IS NULL OR paid_amount > 0",
            schema="fundinv",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints(
            "fund_flows", schema="fundinv"
        )
    }
    if "ck_fund_flows_paid_amount_positive" in constraints:
        op.drop_constraint(
            "ck_fund_flows_paid_amount_positive", "fund_flows",
            schema="fundinv", type_="check",
        )

    columns = {
        column["name"]
        for column in inspector.get_columns("fund_flows", schema="fundinv")
    }
    if "payment_received_at" in columns:
        op.drop_column("fund_flows", "payment_received_at", schema="fundinv")
    if "paid_amount" in columns:
        op.drop_column("fund_flows", "paid_amount", schema="fundinv")
