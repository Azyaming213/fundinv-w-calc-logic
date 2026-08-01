"""Backfill auditable valuations and normalized legacy holding fields.

Revision ID: v0.4.5_pnl_history
Revises: v0.4.4_security_reporting
"""

from alembic import op


revision = "v0.4.5_pnl_history"
down_revision = "v0.4.4_security_reporting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical seed snapshots predate unit accounting. NAV 1.00 preserves
    # their recorded dollar values while making every intermediate equation
    # explicit and auditable.
    op.execute(
        """
        UPDATE fundinv.portfolio_holdings
        SET opening_value = account_value - COALESCE(daily_pnl, 0),
            opening_shareholding_pct = shareholding_pct,
            closing_value_before_flows = account_value,
            net_flow = COALESCE(net_flow, 0),
            units = account_value,
            nav_per_unit = 1.00000000
        WHERE opening_value IS NULL
           OR closing_value_before_flows IS NULL
           OR units IS NULL
           OR nav_per_unit IS NULL
        """
    )

    # Reconstruct total fund valuations from the historical fund NAV series.
    # fund_nav includes portal and non-portal ownership, so units_outstanding
    # intentionally preserves that external ownership at NAV 1.00.
    op.execute(
        """
        WITH daily AS (
            SELECT
                fund_id,
                snapshot_date AS valuation_date,
                MAX(fund_nav)::numeric AS closing_assets,
                LAG(MAX(fund_nav)::numeric) OVER (
                    PARTITION BY fund_id ORDER BY snapshot_date
                ) AS previous_assets
            FROM fundinv.portfolio_holdings
            WHERE fund_id IS NOT NULL
              AND snapshot_date IS NOT NULL
              AND fund_nav IS NOT NULL
            GROUP BY fund_id, snapshot_date
        )
        INSERT INTO fundinv.fund_valuations (
            fund_id, valuation_date, opening_assets, daily_pnl,
            closing_assets_before_flows, net_flow, closing_assets,
            units_outstanding, nav_per_unit
        )
        SELECT
            fund_id,
            valuation_date,
            COALESCE(previous_assets, closing_assets),
            closing_assets - COALESCE(previous_assets, closing_assets),
            closing_assets,
            0,
            closing_assets,
            closing_assets,
            1.00000000
        FROM daily
        WHERE closing_assets > 0
        ON CONFLICT (fund_id, valuation_date) DO NOTHING
        """
    )

    # Keep flow settlement and subsequent snapshots on the same NAV basis for
    # legacy seeded funds until a market-data update supplies a newer price.
    op.execute(
        """
        UPDATE fundinv.funds f
        SET current_price = latest.nav_per_unit
        FROM (
            SELECT DISTINCT ON (fund_id) fund_id, nav_per_unit
            FROM fundinv.fund_valuations
            ORDER BY fund_id, valuation_date DESC
        ) latest
        WHERE f.id = latest.fund_id
          AND (f.current_price IS NULL OR f.current_price <= 0)
        """
    )


def downgrade() -> None:
    # Derived historical data is financially meaningful and may have been used
    # by later snapshots. Preserve it rather than deleting audit history.
    pass
