"""Align legacy data with fund-unit accounting and role ownership.

Revision ID: v0.4.6_fund_portal
Revises: v0.4.5_pnl_history
"""

from collections import defaultdict
from decimal import Decimal

from alembic import op
from sqlalchemy import text


revision = "v0.4.6_fund_portal"
down_revision = "v0.4.5_pnl_history"
branch_labels = None
depends_on = None


ZERO = Decimal("0")
ONE = Decimal("1")


def _decimal(value, default=ZERO):
    return Decimal(str(value)) if value is not None else default


def upgrade() -> None:
    connection = op.get_bind()

    # Investors subscribe/redeem fund units. Only managers execute underlying
    # instrument trades.
    connection.execute(text("""
        DELETE FROM fundinv_auth.role_claims rc
        USING fundinv_auth.roles r
        WHERE rc.role_id = r.id
          AND r.name = 'investor'
          AND rc.claim_key = 'executeTrades'
    """))

    # Older /invest requests used a third, ambiguous flow type. Recover rows
    # that have a fund allocation; quarantine unallocated rows instead of ever
    # allowing Operations to mistake them for withdrawals.
    connection.execute(text("""
        UPDATE fundinv.fund_flows
        SET flow_type = 'deposit',
            notes = concat_ws(E'\n', notes, '[Migration v0.4.6: normalized investment to subscription]')
        WHERE flow_type = 'investment'
          AND fund_id IS NOT NULL
    """))
    connection.execute(text("""
        UPDATE fundinv.fund_flows
        SET status = 'failed',
            processed_at = COALESCE(processed_at, now()),
            failure_reason = 'Legacy investment request had no fund allocation and cannot be settled safely',
            notes = concat_ws(E'\n', notes, '[Migration v0.4.6: quarantined ambiguous legacy request]')
        WHERE flow_type = 'investment'
          AND fund_id IS NULL
          AND status NOT IN ('completed', 'failed', 'rejected')
    """))

    # v0.4.5 preserved legacy dollar values at NAV 1 by making P&L create
    # units. Repair only those recognizable legacy rows. The first opening
    # assets establish the unit base; thereafter P&L changes NAV and net cash
    # flow alone changes units.
    rows = connection.execute(text("""
        SELECT id, fund_id, valuation_date, opening_assets, daily_pnl,
               closing_assets_before_flows, net_flow, closing_assets,
               units_outstanding, nav_per_unit
        FROM fundinv.fund_valuations
        WHERE nav_per_unit = 1
          AND abs(units_outstanding - closing_assets) < 0.0001
        ORDER BY fund_id, valuation_date, id
    """)).mappings().all()

    by_fund = defaultdict(list)
    for row in rows:
        by_fund[row["fund_id"]].append(row)

    latest_nav_by_fund = {}
    for fund_id, valuations in by_fund.items():
        first = valuations[0]
        opening_units = _decimal(first["opening_assets"])
        if opening_units <= ZERO:
            opening_units = _decimal(first["units_outstanding"], ONE)
        if opening_units <= ZERO:
            opening_units = ONE

        for row in valuations:
            closing_before = _decimal(row["closing_assets_before_flows"])
            net_flow = _decimal(row["net_flow"])
            closing_assets = _decimal(row["closing_assets"])
            nav_before_flow = closing_before / opening_units if opening_units > ZERO else ONE
            if nav_before_flow <= ZERO:
                nav_before_flow = ONE
            flow_units = net_flow / nav_before_flow
            closing_units = opening_units + flow_units
            if closing_units <= ZERO:
                closing_units = ONE
            closing_nav = closing_assets / closing_units

            connection.execute(text("""
                UPDATE fundinv.fund_valuations
                SET units_outstanding = :units,
                    nav_per_unit = :nav
                WHERE id = :id
            """), {"units": closing_units, "nav": closing_nav, "id": row["id"]})
            connection.execute(text("""
                UPDATE fundinv.portfolio_holdings
                SET units = CASE WHEN :nav > 0 THEN account_value / :nav ELSE 0 END,
                    nav_per_unit = :nav
                WHERE fund_id = :fund_id
                  AND snapshot_date = :valuation_date
            """), {
                "nav": closing_nav,
                "fund_id": fund_id,
                "valuation_date": row["valuation_date"],
            })
            opening_units = closing_units
            latest_nav_by_fund[fund_id] = closing_nav

    # Preserve each investor/fund's latest recorded value while moving its
    # authoritative position from legacy dollar-as-units to true fund units.
    for fund_id, nav in latest_nav_by_fund.items():
        investor_values = connection.execute(text("""
            SELECT DISTINCT ON (investor_id)
                   investor_id, account_value
            FROM fundinv.portfolio_holdings
            WHERE fund_id = :fund_id
            ORDER BY investor_id, snapshot_date DESC, holding_date DESC, id DESC
        """), {"fund_id": fund_id}).mappings().all()
        for value_row in investor_values:
            positions = connection.execute(text("""
                SELECT id, units
                FROM fundinv.fund_positions
                WHERE fund_id = :fund_id AND investor_id = :investor_id
                ORDER BY id
            """), {
                "fund_id": fund_id,
                "investor_id": value_row["investor_id"],
            }).mappings().all()
            if not positions or nav <= ZERO:
                continue
            target_units = _decimal(value_row["account_value"]) / nav
            old_total = sum((_decimal(position["units"]) for position in positions), ZERO)
            assigned_values = []
            for index, position in enumerate(positions):
                if index == len(positions) - 1:
                    assigned = target_units - sum(assigned_values, ZERO)
                elif old_total > ZERO:
                    assigned = target_units * _decimal(position["units"]) / old_total
                else:
                    assigned = target_units / Decimal(len(positions))
                assigned_values.append(assigned)
                connection.execute(text("""
                    UPDATE fundinv.fund_positions SET units = :units WHERE id = :id
                """), {"units": assigned, "id": position["id"]})

        connection.execute(text("""
            UPDATE fundinv.funds
            SET current_price = :nav
            WHERE id = :fund_id
              AND (current_price IS NULL OR abs(current_price - 1) < 0.00000001)
        """), {"nav": nav, "fund_id": fund_id})

    # Old seed flows predate fund allocation. Keep them visible for audit but
    # explicitly mark why no normalized ledger can be fabricated.
    connection.execute(text("""
        UPDATE fundinv.fund_flows
        SET notes = concat_ws(E'\n', notes, '[Legacy completed flow: fund allocation unavailable; no ledger entry fabricated]')
        WHERE status = 'completed'
          AND fund_id IS NULL
          AND COALESCE(notes, '') NOT LIKE '%no ledger entry fabricated%'
    """))


def downgrade() -> None:
    # The migration preserves all recorded cash values and only repairs their
    # unit representation. Reintroducing investor trading or corrupting NAV
    # back to 1.00 would be unsafe, so data changes are intentionally retained.
    pass
