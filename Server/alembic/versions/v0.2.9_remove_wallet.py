"""Remove wallet_balance and recurring fields from investment_accounts; update claims to camelCase.

Revision ID: v0.2.9_remove_wallet
Revises: v0.2.8_role_scope_refactor
Create Date: 2026-06-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'v0.2.9_remove_wallet'
down_revision: Union[str, Sequence[str], None] = 'v0.2.8_role_scope_refactor'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_CLAIMS_BY_ROLE = {
    "investor": [
        "readDashboard", "readFunds", "depositToFunds", "withdrawFromFunds",
        "readOwnPortfolio", "exportPortfolio", "readArticles", "readOwnFundFlows",
    ],
    "manager": [
        "readDashboard", "readFunds", "createFunds", "updateFunds",
        "manageFundWeights", "manageFundTargeting", "readAssignedInvestors",
        "readArticles", "readTransactions", "createInvites", "executeTrades",
    ],
    "operations": [
        "readDashboard", "readAllFundFlows", "approveFundFlows",
        "completeFundFlows", "rejectFundFlows", "initiateDeposits",
        "initiateWithdrawals", "readAssignedInvestors",
    ],
    "admin": [
        "readDashboard", "readUsers", "writeUsers", "readInvites",
        "writeInvites", "readRoles", "readAuditLogs", "readSystemStats",
        "readAllFundFlows", "readFunds", "readTransactions", "readOrders",
    ],
}


def upgrade() -> None:
    # 1 - drop wallet_balance and recurring fields from investment_accounts (IF EXISTS for fresh DBs)
    op.execute("ALTER TABLE fundinv.investment_accounts DROP COLUMN IF EXISTS wallet_balance")
    op.execute("ALTER TABLE fundinv.investment_accounts DROP COLUMN IF EXISTS is_recurring_payment")
    op.execute("ALTER TABLE fundinv.investment_accounts DROP COLUMN IF EXISTS recurring_payment_amount")
    op.execute("ALTER TABLE fundinv.investment_accounts DROP COLUMN IF EXISTS recurring_frequency")
    op.execute("ALTER TABLE fundinv.investment_accounts DROP COLUMN IF EXISTS next_payment_date")

    # 2 - wipe and re-seed role_claims with camelCase names
    op.execute("DELETE FROM fundinv_auth.role_claims")

    for role_name, claim_keys in NEW_CLAIMS_BY_ROLE.items():
        for ck in claim_keys:
            op.execute(
                "INSERT INTO fundinv_auth.role_claims (role_id, claim_key) "
                "VALUES ("
                "  (SELECT id FROM fundinv_auth.roles WHERE name = :role_name),"
                "  :claim_key"
                ") ON CONFLICT (role_id, claim_key) DO NOTHING",
                parameters={"role_name": role_name, "claim_key": ck},
            )


def downgrade() -> None:
    op.execute("ALTER TABLE fundinv.investment_accounts ADD COLUMN IF NOT EXISTS wallet_balance NUMERIC(18,4) NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE fundinv.investment_accounts ADD COLUMN IF NOT EXISTS is_recurring_payment BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE fundinv.investment_accounts ADD COLUMN IF NOT EXISTS recurring_payment_amount NUMERIC(18,4) DEFAULT 0")
    op.execute("ALTER TABLE fundinv.investment_accounts ADD COLUMN IF NOT EXISTS recurring_frequency VARCHAR(20)")
    op.execute("ALTER TABLE fundinv.investment_accounts ADD COLUMN IF NOT EXISTS next_payment_date DATE")

    # 2 - the old claims are not restored (data loss is acceptable on downgrade)
    pass
