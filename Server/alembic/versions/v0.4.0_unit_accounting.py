"""Merge workflow branches and add unit-based fund accounting.

Revision ID: v0.4.0_unit_accounting
Revises: add_permissions_tables, v0.3.1_pnl_tracking
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v0.4.0_unit_accounting"
down_revision: Union[str, Sequence[str], None] = (
    "add_permissions_tables",
    "v0.3.1_pnl_tracking",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("investment_account_id", sa.Integer(), sa.ForeignKey("fundinv.investment_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("investor_id", sa.Integer(), sa.ForeignKey("fundinv.investors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fundinv.funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("units", sa.Numeric(28, 10), nullable=False, server_default="0"),
        sa.Column("cost_basis", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("investment_account_id", "fund_id", name="uq_fund_positions_account_fund"),
        sa.CheckConstraint("units >= 0", name="ck_fund_positions_units_nonnegative"),
        sa.CheckConstraint("cost_basis >= 0", name="ck_fund_positions_cost_basis_nonnegative"),
        schema="fundinv",
    )
    op.create_index("ix_fund_positions_account_id", "fund_positions", ["investment_account_id"], schema="fundinv")
    op.create_index("ix_fund_positions_investor_id", "fund_positions", ["investor_id"], schema="fundinv")
    op.create_index("ix_fund_positions_fund_id", "fund_positions", ["fund_id"], schema="fundinv")

    op.create_table(
        "fund_valuations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fundinv.funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("opening_assets", sa.Numeric(18, 4), nullable=False),
        sa.Column("daily_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("closing_assets_before_flows", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_flow", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("closing_assets", sa.Numeric(18, 4), nullable=False),
        sa.Column("units_outstanding", sa.Numeric(28, 10), nullable=False),
        sa.Column("nav_per_unit", sa.Numeric(18, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("fund_id", "valuation_date", name="uq_fund_valuations_fund_date"),
        sa.CheckConstraint("opening_assets >= 0", name="ck_fund_valuations_opening_assets_nonnegative"),
        sa.CheckConstraint("closing_assets >= 0", name="ck_fund_valuations_closing_assets_nonnegative"),
        sa.CheckConstraint("units_outstanding >= 0", name="ck_fund_valuations_units_nonnegative"),
        sa.CheckConstraint("nav_per_unit > 0", name="ck_fund_valuations_nav_positive"),
        schema="fundinv",
    )
    op.create_index("ix_fund_valuations_fund_id", "fund_valuations", ["fund_id"], schema="fundinv")
    op.create_index("ix_fund_valuations_date", "fund_valuations", ["valuation_date"], schema="fundinv")

    op.add_column("fund_balance_entries", sa.Column("units", sa.Numeric(28, 10), nullable=True), schema="fundinv")
    op.add_column("fund_balance_entries", sa.Column("nav_per_unit", sa.Numeric(18, 8), nullable=True), schema="fundinv")

    op.add_column("portfolio_holdings", sa.Column("snapshot_date", sa.Date(), nullable=True), schema="fundinv")
    op.add_column("portfolio_holdings", sa.Column("units", sa.Numeric(28, 10), nullable=True), schema="fundinv")
    op.add_column("portfolio_holdings", sa.Column("nav_per_unit", sa.Numeric(18, 8), nullable=True), schema="fundinv")
    op.add_column("portfolio_holdings", sa.Column("opening_value", sa.Numeric(18, 4), nullable=True), schema="fundinv")
    op.add_column("portfolio_holdings", sa.Column("opening_shareholding_pct", sa.Numeric(10, 8), nullable=True), schema="fundinv")
    op.add_column("portfolio_holdings", sa.Column("closing_value_before_flows", sa.Numeric(18, 4), nullable=True), schema="fundinv")
    op.add_column("portfolio_holdings", sa.Column("net_flow", sa.Numeric(18, 4), nullable=False, server_default="0"), schema="fundinv")
    op.execute("UPDATE fundinv.portfolio_holdings SET snapshot_date = holding_date::date WHERE snapshot_date IS NULL")
    op.create_index("ix_portfolio_holdings_snapshot_date", "portfolio_holdings", ["snapshot_date"], schema="fundinv")
    op.create_unique_constraint(
        "uq_portfolio_holdings_investor_fund_date",
        "portfolio_holdings",
        ["investor_id", "fund_id", "snapshot_date"],
        schema="fundinv",
    )

    op.create_check_constraint("ck_fund_flows_amount_positive", "fund_flows", "amount > 0", schema="fundinv")
    op.create_check_constraint("ck_fund_flows_type", "fund_flows", "flow_type IN ('deposit', 'withdrawal', 'investment')", schema="fundinv")
    op.create_check_constraint("ck_portfolio_holdings_share_pct", "portfolio_holdings", "shareholding_pct >= 0 AND shareholding_pct <= 100", schema="fundinv")
    op.create_check_constraint("ck_investment_transactions_volume_positive", "investment_transactions", "volume > 0", schema="fundinv")
    op.create_check_constraint("ck_investment_transactions_price_nonnegative", "investment_transactions", "price >= 0", schema="fundinv")


def downgrade() -> None:
    op.drop_constraint("ck_investment_transactions_price_nonnegative", "investment_transactions", schema="fundinv", type_="check")
    op.drop_constraint("ck_investment_transactions_volume_positive", "investment_transactions", schema="fundinv", type_="check")
    op.drop_constraint("ck_portfolio_holdings_share_pct", "portfolio_holdings", schema="fundinv", type_="check")
    op.drop_constraint("ck_fund_flows_type", "fund_flows", schema="fundinv", type_="check")
    op.drop_constraint("ck_fund_flows_amount_positive", "fund_flows", schema="fundinv", type_="check")
    op.drop_constraint("uq_portfolio_holdings_investor_fund_date", "portfolio_holdings", schema="fundinv", type_="unique")
    op.drop_index("ix_portfolio_holdings_snapshot_date", table_name="portfolio_holdings", schema="fundinv")
    for column in ("net_flow", "closing_value_before_flows", "opening_shareholding_pct", "opening_value", "nav_per_unit", "units", "snapshot_date"):
        op.drop_column("portfolio_holdings", column, schema="fundinv")
    op.drop_column("fund_balance_entries", "nav_per_unit", schema="fundinv")
    op.drop_column("fund_balance_entries", "units", schema="fundinv")
    op.drop_table("fund_valuations", schema="fundinv")
    op.drop_table("fund_positions", schema="fundinv")
