"""Backfill opening positions from legacy holding snapshots.

Revision ID: v0.4.3_snapshot_positions
Revises: v0.4.2_share_pct
"""

from alembic import op


revision = "v0.4.3_snapshot_positions"
down_revision = "v0.4.2_share_pct"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older seed data recorded investor/fund values but did not populate the
    # account JSON balance consumed by v0.4.1. Use each pair's latest snapshot
    # as its opening normalized position. Existing positions always win.
    op.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (h.investor_id, h.fund_id)
                h.investor_id,
                h.fund_id,
                h.account_value,
                COALESCE(NULLIF(f.current_price, 0), 1)::numeric AS nav_per_unit
            FROM fundinv.portfolio_holdings h
            JOIN fundinv.funds f ON f.id = h.fund_id
            WHERE h.fund_id IS NOT NULL AND h.account_value > 0
            ORDER BY h.investor_id, h.fund_id, h.snapshot_date DESC, h.holding_date DESC
        ), account_for_investor AS (
            SELECT DISTINCT ON (a.investor_id) a.id, a.investor_id
            FROM fundinv.investment_accounts a
            WHERE a.deleted_at IS NULL AND a.status = 'active'
            ORDER BY a.investor_id, a.created_at, a.id
        )
        INSERT INTO fundinv.fund_positions
            (investment_account_id, investor_id, fund_id, units, cost_basis)
        SELECT
            a.id,
            l.investor_id,
            l.fund_id,
            ROUND(l.account_value / l.nav_per_unit, 10),
            ROUND(l.account_value, 4)
        FROM latest l
        JOIN account_for_investor a ON a.investor_id = l.investor_id
        ON CONFLICT (investment_account_id, fund_id) DO NOTHING
        """
    )

    # Make it explicit that legacy completed flows predate fund-level unit
    # accounting. They remain evidence of cash history, not settlement events.
    op.execute(
        """
        UPDATE fundinv.fund_flows ff
        SET notes = CONCAT_WS(E'\n', NULLIF(ff.notes, ''),
            '[Legacy] Completed before fund-level unit accounting; opening position reconstructed from snapshots.')
        WHERE ff.status = 'completed'
          AND ff.fund_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM fundinv.fund_balance_entries e WHERE e.fund_flow_id = ff.id
          )
          AND COALESCE(ff.notes, '') NOT LIKE '%[Legacy] Completed before fund-level unit accounting%'
        """
    )


def downgrade() -> None:
    # Financial opening positions may have since received real settlements;
    # never delete them automatically on downgrade.
    pass
