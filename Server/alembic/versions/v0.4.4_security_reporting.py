"""Add revocable sessions, shared throttling, currency, and fund risk.

Revision ID: v0.4.4_security_reporting
Revises: v0.4.3_snapshot_positions
"""

from alembic import op
import sqlalchemy as sa


revision = "v0.4.4_security_reporting"
down_revision = "v0.4.3_snapshot_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("fundinv_auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_id", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="fundinv_auth",
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], schema="fundinv_auth")
    op.create_index("ix_auth_sessions_token_id", "auth_sessions", ["token_id"], unique=True, schema="fundinv_auth")
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], schema="fundinv_auth")
    op.create_index("ix_auth_sessions_revoked", "auth_sessions", ["revoked"], schema="fundinv_auth")

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("throttle_key", sa.String(64), nullable=False, unique=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="fundinv_auth",
    )
    op.create_index("ix_login_attempts_throttle_key", "login_attempts", ["throttle_key"], unique=True, schema="fundinv_auth")
    op.create_index("ix_login_attempts_blocked_until", "login_attempts", ["blocked_until"], schema="fundinv_auth")

    op.add_column("fund_flows", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"), schema="fundinv")
    op.create_check_constraint("ck_fund_flows_currency", "fund_flows", "currency ~ '^[A-Z]{3}$'", schema="fundinv")
    op.add_column("fund_targeting", sa.Column("risk_tolerance", sa.String(20), nullable=False, server_default="balanced"), schema="fundinv")
    op.create_check_constraint(
        "ck_fund_targeting_risk_tolerance", "fund_targeting",
        "risk_tolerance IN ('conservative','balanced','growth','aggressive')", schema="fundinv",
    )


def downgrade() -> None:
    op.drop_constraint("ck_fund_targeting_risk_tolerance", "fund_targeting", schema="fundinv", type_="check")
    op.drop_column("fund_targeting", "risk_tolerance", schema="fundinv")
    op.drop_constraint("ck_fund_flows_currency", "fund_flows", schema="fundinv", type_="check")
    op.drop_column("fund_flows", "currency", schema="fundinv")
    op.drop_table("login_attempts", schema="fundinv_auth")
    op.drop_table("auth_sessions", schema="fundinv_auth")
