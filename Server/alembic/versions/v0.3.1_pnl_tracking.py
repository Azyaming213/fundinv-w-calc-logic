"""Add PNL tracking columns per challenge statement sections 5.3, 5.4, 8.1, 8.2.

Revision ID: v0.3.1_pnl_tracking
Revises: v0.3.0_workflows
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v0.3.1_pnl_tracking"
down_revision: Union[str, Sequence[str], None] = "v0.3.0_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    has_fund_id = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='fundinv' AND table_name='investment_transactions' "
            "AND column_name='fund_id')"
        )
    ).scalar()
    if not has_fund_id:
        op.add_column("investment_transactions",
                      sa.Column("fund_id", sa.Integer(), nullable=True), schema="fundinv")
        op.create_foreign_key(
            "fk_investment_transactions_fund_id",
            "investment_transactions", "funds",
            ["fund_id"], ["id"],
            source_schema="fundinv", referent_schema="fundinv",
        )

    for col, typ in [
        ("order_ticket", sa.String(length=50)),
        ("investment_account_id", sa.Integer()),
        ("position_id", sa.String(length=64)),
        ("time_msc", sa.BigInteger()),
        ("entry", sa.String(length=4)),
        ("sl", sa.Numeric(precision=18, scale=8)),
        ("tp", sa.Numeric(precision=18, scale=8)),
        ("magic", sa.String(length=64)),
        ("reason", sa.String(length=255)),
        ("comment", sa.Text()),
        ("external_id", sa.String(length=100)),
    ]:
        exists = bind.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='fundinv' AND table_name='investment_transactions' "
                f"AND column_name='{col}')"
            )
        ).scalar()
        if not exists:
            nullable = col != "investment_account_id"
            op.add_column("investment_transactions", sa.Column(col, typ, nullable=nullable),
                          schema="fundinv")

    has_acct_fk = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema='fundinv' AND table_name='investment_transactions' "
            "AND constraint_name='fk_investment_transactions_investment_account_id')"
        )
    ).scalar()
    if not has_acct_fk and has_fund_id:
        op.create_foreign_key(
            "fk_investment_transactions_investment_account_id",
            "investment_transactions", "investment_accounts",
            ["investment_account_id"], ["id"],
            source_schema="fundinv", referent_schema="fundinv",
        )

    op.create_index("ix_investment_transactions_order_ticket", "investment_transactions",
                    ["order_ticket"], schema="fundinv")
    op.create_index("ix_investment_transactions_position_id", "investment_transactions",
                    ["position_id"], schema="fundinv")
    op.create_index("ix_investment_transactions_external_id", "investment_transactions",
                    ["external_id"], schema="fundinv")

    has_ph_fund_id = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='fundinv' AND table_name='portfolio_holdings' "
            "AND column_name='fund_id')"
        )
    ).scalar()
    if not has_ph_fund_id:
        op.add_column("portfolio_holdings",
                      sa.Column("fund_id", sa.Integer(), nullable=True), schema="fundinv")
        op.create_foreign_key(
            "fk_portfolio_holdings_fund_id",
            "portfolio_holdings", "funds",
            ["fund_id"], ["id"],
            source_schema="fundinv", referent_schema="fundinv",
        )

    has_ph_nav = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='fundinv' AND table_name='portfolio_holdings' "
            "AND column_name='fund_nav')"
        )
    ).scalar()
    if not has_ph_nav:
        op.add_column("portfolio_holdings",
                      sa.Column("fund_nav", sa.Numeric(precision=18, scale=4), nullable=True),
                      schema="fundinv")


def downgrade() -> None:
    op.drop_column("portfolio_holdings", "fund_nav", schema="fundinv")
    op.drop_column("portfolio_holdings", "fund_id", schema="fundinv")
    op.drop_index("ix_investment_transactions_external_id", table_name="investment_transactions",
                  schema="fundinv")
    op.drop_index("ix_investment_transactions_position_id", table_name="investment_transactions",
                  schema="fundinv")
    op.drop_index("ix_investment_transactions_order_ticket", table_name="investment_transactions",
                  schema="fundinv")
    for col in [
        "external_id", "comment", "reason", "magic", "tp", "sl", "entry",
        "time_msc", "position_id", "investment_account_id", "order_ticket",
    ]:
        op.drop_column("investment_transactions", col, schema="fundinv")
    op.drop_column("investment_transactions", "fund_id", schema="fundinv")
