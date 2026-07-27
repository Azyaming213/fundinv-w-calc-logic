"""Backfill normalized unit positions from legacy account balances.

Revision ID: v0.4.1_backfill_positions
Revises: v0.4.0_unit_accounting
"""

from alembic import op


revision = "v0.4.1_backfill_positions"
down_revision = "v0.4.0_unit_accounting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO fundinv.fund_positions
            (investment_account_id, investor_id, fund_id, units, cost_basis)
        SELECT
            account.id,
            account.investor_id,
            fund.id,
            ROUND(balance.amount / CASE
                WHEN COALESCE(fund.current_price, 0) > 0 THEN fund.current_price
                ELSE 1
            END, 10),
            ROUND(balance.amount, 4)
        FROM fundinv.investment_accounts AS account
        CROSS JOIN LATERAL (
            SELECT key, value::numeric AS amount
            FROM jsonb_each_text(COALESCE(account.manager_fund_balance, '{}'::jsonb))
            WHERE key !~ '^_' AND value ~ '^[0-9]+(\\.[0-9]+)?$'
        ) AS balance
        JOIN fundinv.funds AS fund ON fund.id = balance.key::integer
        WHERE balance.amount > 0
        ON CONFLICT (investment_account_id, fund_id) DO NOTHING
        """
    )


def downgrade() -> None:
    # Backfilled positions cannot be distinguished safely from positions
    # created after this migration, so downgrade preserves financial data.
    pass
