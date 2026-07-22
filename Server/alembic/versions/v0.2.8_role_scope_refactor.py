"""Role scope refactor — wipe and re-seed role_claims per target permission matrix.

Revision ID: v0.2.8_role_scope_refactor
Revises: v0.2.7_add_fund_manager
Create Date: 2026-06-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'v0.2.8_role_scope_refactor'
down_revision: Union[str, Sequence[str], None] = 'v0.2.7_add_fund_manager'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── new claim matrix per the role-scope refactor spec ──────────────
CLAIMS_BY_ROLE = {
    "investor": [
        "portfolio:read_own",
        "portfolio:export",
        "wallet:request_deposit",
        "wallet:request_withdrawal",
        "funds:read",
        "funds:invest",
        "articles:read",
        "dashboard:view",
        "fund_flows:read_own",
    ],
    "manager": [
        "dashboard:view",
        "funds:read",
        "funds:create",
        "funds:update",
        "fund_composition:write",
        "fund_targeting:write",
        "investors:read_assigned",
        "portfolio:read_own",
        "articles:read",
        "articles:write",
        "invites:write",
        "trading:execute",
        "transactions:read",
    ],
    "operations": [
        "dashboard:view",
        "fund_flows:read_all",
        "fund_flows:approve",
        "fund_flows:complete",
        "fund_flows:reject",
        "fund_flows:initiate_deposit",
        "fund_flows:add_notes",
        "audit_logs:read",
        "investors:read_assigned",
    ],
    "admin": [
        "dashboard:view",
        "users:read",
        "users:write",
        "invites:read",
        "invites:write",
        "roles:read",
        "audit_logs:read",
        "system_stats:read",
        "fund_flows:read_all",
        "funds:read",
        "articles:read",
        "articles:write",
    ],
}

SYSTEM_USER_SQL = (
    "INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id) "
    "VALUES ("
    "  gen_random_uuid(),"
    "  'system@fundinv.com',"
    "  'System Actor',"
    "  '$2b$12$PYcvXE9PmAVlrjDz1Yy.wu/WWYFV5ezuvhghmdjCnnTfzIN0WqsWa',"
    "  FALSE,"
    "  (SELECT id FROM fundinv_auth.roles WHERE name = 'admin')"
    ") ON CONFLICT (email) DO NOTHING;"
)


def upgrade() -> None:
    # 1‑wipe existing claims
    op.execute("DELETE FROM fundinv_auth.role_claims")

    # 2‑drop dead parallel RBAC tables (never wired into the app)
    op.execute("DROP TABLE IF EXISTS fundinv_auth.user_permissions CASCADE")
    op.execute("DROP TABLE IF EXISTS fundinv_auth.role_permissions CASCADE")
    op.execute("DROP TABLE IF EXISTS fundinv_auth.permissions CASCADE")

    # 3‑re‑seed claims
    for role_name, claim_keys in CLAIMS_BY_ROLE.items():
        for ck in claim_keys:
            op.execute(
                "INSERT INTO fundinv_auth.role_claims (role_id, claim_key) "
                "VALUES ("
                "  (SELECT id FROM fundinv_auth.roles WHERE name = :role_name),"
                "  :claim_key"
                ") ON CONFLICT (role_id, claim_key) DO NOTHING",
                parameters={"role_name": role_name, "claim_key": ck},
            )

    # 4‑seed system user for audit attribution
    op.execute(SYSTEM_USER_SQL)


def downgrade() -> None:
    # Re‑create permissions tables (minimal restore — does not re‑populate data)
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="fundinv_auth",
    )
    op.create_table(
        "user_permissions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["fundinv_auth.users.id"]),
        sa.ForeignKeyConstraint(["permission_id"], ["fundinv_auth.permissions.id"]),
        sa.PrimaryKeyConstraint("user_id", "permission_id"),
        schema="fundinv_auth",
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["fundinv_auth.roles.id"]),
        sa.ForeignKeyConstraint(["permission_id"], ["fundinv_auth.permissions.id"]),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        schema="fundinv_auth",
    )
    # Delete system user
    op.execute("DELETE FROM fundinv_auth.users WHERE email = 'system@fundinv.com'")
