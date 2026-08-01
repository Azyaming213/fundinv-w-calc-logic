"""Rebuild legacy account balance cache from authoritative fund positions.

Revision ID: v0.4.9_balance_cache
Revises: v0.4.8_principal
"""

from alembic import op


revision = "v0.4.9_balance_cache"
down_revision = "v0.4.8_principal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH latest_nav AS (
            SELECT DISTINCT ON (fund_id)
                fund_id,
                nav_per_unit
            FROM fundinv.fund_valuations
            ORDER BY fund_id, valuation_date DESC, id DESC
        ), rebuilt AS (
            SELECT
                position.investment_account_id,
                jsonb_object_agg(
                    position.fund_id::text,
                    to_jsonb(ROUND(position.units * COALESCE(latest_nav.nav_per_unit, fund.current_price, 1), 4)::text)
                ) AS balances
            FROM fundinv.fund_positions position
            JOIN fundinv.funds fund ON fund.id = position.fund_id
            LEFT JOIN latest_nav ON latest_nav.fund_id = position.fund_id
            GROUP BY position.investment_account_id
        )
        UPDATE fundinv.investment_accounts account
        SET manager_fund_balance = rebuilt.balances
        FROM rebuilt
        WHERE account.id = rebuilt.investment_account_id
        """
    )

    op.execute(
        """
        UPDATE fundinv.investment_accounts account
        SET manager_fund_balance = '{}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1
            FROM fundinv.fund_positions position
            WHERE position.investment_account_id = account.id
        )
        """
    )


def downgrade() -> None:
    # The cache is derived data; restoring stale legacy values is unsafe.
    pass
