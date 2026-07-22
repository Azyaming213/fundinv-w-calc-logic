"""Add fund reviews, provider-safe flows, balance entries, and feedback.

Revision ID: v0.3.0_workflows
Revises: v0.2.9_remove_wallet
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v0.3.0_workflows"
down_revision: Union[str, Sequence[str], None] = "v0.2.9_remove_wallet"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM fundinv_auth.role_claims")
    claims = {
        "investor": ["readDashboard", "readFunds", "depositToFunds", "withdrawFromFunds", "readOwnPortfolio", "exportPortfolio", "readArticles", "readOwnFundFlows", "createFeedback", "readOwnFeedback"],
        "manager": ["readDashboard", "readFunds", "createFunds", "updateFunds", "submitFundsForReview", "manageFundWeights", "manageFundTargeting", "readAssignedInvestors", "readArticles", "readTransactions", "executeTrades"],
        "operations": ["readDashboard", "readAllFundFlows", "approveFundFlows", "completeFundFlows", "rejectFundFlows", "reviewFunds", "readAuditLogs", "readFeedback", "manageFeedback", "requestInvites"],
        "admin": ["readDashboard", "readUsers", "writeUsers", "readInvites", "writeInvites", "createInvites", "readRoles", "readAuditLogs", "readSystemStats", "readAllFundFlows", "readFunds", "readTransactions", "readOrders", "readFeedback"],
    }
    for role_name, role_claims in claims.items():
        for claim in role_claims:
            op.execute(
                "INSERT INTO fundinv_auth.role_claims (role_id, claim_key) "
                "VALUES ((SELECT id FROM fundinv_auth.roles WHERE name = :role_name), :claim) "
                "ON CONFLICT (role_id, claim_key) DO NOTHING",
                {"role_name": role_name, "claim": claim},
            )

    conn = op.get_bind()
    has_role_id = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'fundinv_auth' AND table_name = 'users' AND column_name = 'role_id')"
        )
    ).scalar()
    if not has_role_id:
        op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True), schema="fundinv_auth")
        op.create_foreign_key(
            "fk_users_role_id",
            "users",
            "roles",
            ["role_id"],
            ["id"],
            source_schema="fundinv_auth",
            referent_schema="fundinv_auth",
        )
        has_user_role = conn.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'fundinv_auth' AND table_name = 'user_role_claims')"
            )
        ).scalar()
        if has_user_role:
            op.execute(
                "UPDATE fundinv_auth.users u SET role_id = ur.role_id "
                "FROM fundinv_auth.user_role_claims ur WHERE ur.user_id = u.id"
            )
            op.drop_table("user_role_claims", schema="fundinv_auth")
        op.execute(
            "UPDATE fundinv_auth.users u SET role_id = r.id "
            "FROM fundinv_auth.roles r WHERE r.name = 'investor' AND u.role_id IS NULL"
        )
        op.alter_column("users", "role_id", nullable=False, schema="fundinv_auth")

    op.add_column("funds", sa.Column("review_status", sa.String(30), nullable=False, server_default="approved"), schema="fundinv")
    op.add_column("funds", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True), schema="fundinv")
    op.add_column("funds", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True), schema="fundinv")
    op.add_column("funds", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True), schema="fundinv")
    op.add_column("funds", sa.Column("review_notes", sa.String(1000), nullable=True), schema="fundinv")
    op.create_foreign_key(
        "fk_funds_reviewed_by_user_id",
        "funds",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        source_schema="fundinv",
        referent_schema="fundinv_auth",
    )

    op.create_table(
        "fund_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fundinv.funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_fund_id", sa.Integer(), sa.ForeignKey("fundinv.funds.id"), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("component_name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(30), nullable=False),
        sa.Column("target_pct", sa.Numeric(7, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="fundinv",
    )
    op.create_index("ix_fund_components_fund_id", "fund_components", ["fund_id"], schema="fundinv")
    op.create_index("ix_fund_components_component_fund_id", "fund_components", ["component_fund_id"], schema="fundinv")

    op.add_column("fund_flows", sa.Column("fund_id", sa.Integer(), nullable=True), schema="fundinv")
    op.add_column("fund_flows", sa.Column("provider", sa.String(30), nullable=True), schema="fundinv")
    op.add_column("fund_flows", sa.Column("provider_reference", sa.String(255), nullable=True), schema="fundinv")
    op.add_column("fund_flows", sa.Column("payment_url", sa.String(2000), nullable=True), schema="fundinv")
    op.add_column("fund_flows", sa.Column("failure_reason", sa.String(1000), nullable=True), schema="fundinv")
    op.create_foreign_key("fk_fund_flows_fund_id", "fund_flows", "funds", ["fund_id"], ["id"], source_schema="fundinv", referent_schema="fundinv")
    op.create_index("ix_fund_flows_fund_id", "fund_flows", ["fund_id"], schema="fundinv")
    op.create_unique_constraint("uq_fund_flows_provider_reference", "fund_flows", ["provider_reference"], schema="fundinv")

    op.execute("UPDATE fundinv.fund_investments SET fund_id = (SELECT MIN(id) FROM fundinv.funds) WHERE fund_id IS NULL")
    op.create_foreign_key("fk_fund_investments_fund_id", "fund_investments", "funds", ["fund_id"], ["id"], source_schema="fundinv", referent_schema="fundinv")

    op.add_column("orders", sa.Column("fund_id", sa.Integer(), nullable=True), schema="fundinv")
    op.create_foreign_key("fk_orders_fund_id", "orders", "funds", ["fund_id"], ["id"], source_schema="fundinv", referent_schema="fundinv")
    op.create_index("ix_orders_fund_id", "orders", ["fund_id"], schema="fundinv")

    op.add_column("investors", sa.Column("stripe_connect_account_id", sa.String(255), nullable=True), schema="fundinv")
    op.create_unique_constraint("uq_investors_stripe_connect_account_id", "investors", ["stripe_connect_account_id"], schema="fundinv")

    op.create_table(
        "fund_balance_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("investment_account_id", sa.Integer(), sa.ForeignKey("fundinv.investment_accounts.id"), nullable=False),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("fundinv.funds.id"), nullable=False),
        sa.Column("fund_flow_id", sa.Integer(), sa.ForeignKey("fundinv.fund_flows.id"), nullable=True),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="fundinv",
    )
    op.create_index("ix_fund_balance_entries_account_id", "fund_balance_entries", ["investment_account_id"], schema="fundinv")
    op.create_index("ix_fund_balance_entries_fund_id", "fund_balance_entries", ["fund_id"], schema="fundinv")
    op.create_index("ix_fund_balance_entries_flow_id", "fund_balance_entries", ["fund_flow_id"], schema="fundinv")
    op.create_unique_constraint("uq_fund_balance_entries_flow_id", "fund_balance_entries", ["fund_flow_id"], schema="fundinv")

    op.create_table(
        "feedback_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("fundinv_auth.users.id"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("fundinv_auth.users.id"), nullable=True),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        schema="fundinv",
    )
    op.create_index("ix_feedback_tickets_user_id", "feedback_tickets", ["user_id"], schema="fundinv")
    op.create_index("ix_feedback_tickets_status", "feedback_tickets", ["status"], schema="fundinv")

    op.create_table(
        "invite_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("fundinv_auth.users.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("fundinv_auth.roles.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_admin_review"),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("fundinv_auth.users.id"), nullable=True),
        sa.Column("review_notes", sa.String(1000), nullable=True),
        sa.Column("invite_id", sa.Integer(), sa.ForeignKey("fundinv.invites.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        schema="fundinv",
    )
    op.create_index("ix_invite_requests_email", "invite_requests", ["email"], schema="fundinv")
    op.create_index("ix_invite_requests_status", "invite_requests", ["status"], schema="fundinv")


def downgrade() -> None:
    op.drop_table("invite_requests", schema="fundinv")
    op.drop_table("feedback_tickets", schema="fundinv")
    op.drop_table("fund_balance_entries", schema="fundinv")
    op.drop_table("fund_components", schema="fundinv")

    op.drop_constraint("uq_investors_stripe_connect_account_id", "investors", schema="fundinv", type_="unique")
    op.drop_column("investors", "stripe_connect_account_id", schema="fundinv")

    op.drop_index("ix_orders_fund_id", table_name="orders", schema="fundinv")
    op.drop_constraint("fk_orders_fund_id", "orders", schema="fundinv", type_="foreignkey")
    op.drop_column("orders", "fund_id", schema="fundinv")

    op.drop_constraint("fk_fund_investments_fund_id", "fund_investments", schema="fundinv", type_="foreignkey")
    op.execute("UPDATE fundinv.fund_investments SET fund_id = NULL WHERE fund_id IS NOT NULL")

    op.drop_constraint("uq_fund_flows_provider_reference", "fund_flows", schema="fundinv", type_="unique")
    op.drop_index("ix_fund_flows_fund_id", table_name="fund_flows", schema="fundinv")
    op.drop_constraint("fk_fund_flows_fund_id", "fund_flows", schema="fundinv", type_="foreignkey")
    for column in ("failure_reason", "payment_url", "provider_reference", "provider", "fund_id"):
        op.drop_column("fund_flows", column, schema="fundinv")

    op.drop_constraint("fk_funds_reviewed_by_user_id", "funds", schema="fundinv", type_="foreignkey")
    for column in ("review_notes", "reviewed_by_user_id", "reviewed_at", "submitted_at", "review_status"):
        op.drop_column("funds", column, schema="fundinv")

    conn = op.get_bind()
    has_role_id = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'fundinv_auth' AND table_name = 'users' AND column_name = 'role_id')"
        )
    ).scalar()
    if has_role_id:
        op.drop_constraint("fk_users_role_id", "users", schema="fundinv_auth", type_="foreignkey")
        op.drop_column("users", "role_id", schema="fundinv_auth")
