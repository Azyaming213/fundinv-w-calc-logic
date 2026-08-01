"""Restore legacy fund-position cost basis after NAV normalization.

Revision ID: v0.4.7_cost_basis
Revises: v0.4.6_fund_portal
"""

from alembic import op


revision = "v0.4.7_cost_basis"
down_revision = "v0.4.6_fund_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # v0.4.5 initialized both units and cost basis from the latest account
    # value. After v0.4.6 restores true units/NAV, use the earliest auditable
    # holding value as the legacy opening capital. New subscriptions and
    # redemptions already update cost basis transactionally.
    op.execute(
        """
        WITH earliest AS (
            SELECT DISTINCT ON (investor_id, fund_id)
                   investor_id, fund_id, account_value AS opening_cost
            FROM fundinv.portfolio_holdings
            WHERE fund_id IS NOT NULL
              AND account_value IS NOT NULL
            ORDER BY investor_id, fund_id, snapshot_date, holding_date, id
        ), totals AS (
            SELECT investor_id, fund_id, SUM(units) AS total_units
            FROM fundinv.fund_positions
            GROUP BY investor_id, fund_id
        )
        UPDATE fundinv.fund_positions p
        SET cost_basis = CASE
            WHEN totals.total_units > 0
                THEN earliest.opening_cost * p.units / totals.total_units
            ELSE 0
        END
        FROM earliest, totals
        WHERE p.investor_id = earliest.investor_id
          AND p.fund_id = earliest.fund_id
          AND totals.investor_id = p.investor_id
          AND totals.fund_id = p.fund_id
        """
    )


def downgrade() -> None:
    # Restoring inflated latest-value cost basis would erase valid unrealized
    # P&L, so the corrected basis is intentionally retained.
    pass
