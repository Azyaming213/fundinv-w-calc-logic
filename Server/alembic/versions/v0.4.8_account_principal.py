"""Reconcile account principal with normalized fund-position cost basis.

Revision ID: v0.4.8_principal
Revises: v0.4.7_cost_basis
"""

from alembic import op


revision = "v0.4.8_principal"
down_revision = "v0.4.7_cost_basis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE fundinv.investment_accounts account
        SET total_invested = COALESCE(position_totals.cost_basis, 0)
        FROM (
            SELECT investment_account_id, SUM(cost_basis) AS cost_basis
            FROM fundinv.fund_positions
            GROUP BY investment_account_id
        ) position_totals
        WHERE account.id = position_totals.investment_account_id
        """
    )


def downgrade() -> None:
    # Correct principal is derived from auditable position basis and should not
    # be replaced with the inconsistent legacy value.
    pass
