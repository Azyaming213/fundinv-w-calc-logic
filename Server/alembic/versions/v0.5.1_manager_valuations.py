"""Add auditable Manager finalisation metadata to fund valuations.

Revision ID: v0.5.1_manager_values
Revises: v0.5.0_async_orders
"""

from alembic import op
import sqlalchemy as sa


revision = "v0.5.1_manager_values"
down_revision = "v0.5.0_async_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fund_valuations", sa.Column("status", sa.String(20), nullable=False, server_default="finalized"), schema="fundinv")
    op.add_column("fund_valuations", sa.Column("source", sa.String(30), nullable=False, server_default="scheduled_snapshot"), schema="fundinv")
    op.add_column("fund_valuations", sa.Column("finalized_by_user_id", sa.Integer(), nullable=True), schema="fundinv")
    op.add_column("fund_valuations", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True), schema="fundinv")
    op.add_column("fund_valuations", sa.Column("notes", sa.Text(), nullable=True), schema="fundinv")
    op.create_foreign_key(
        "fk_fund_valuations_finalized_by_user",
        "fund_valuations", "users",
        ["finalized_by_user_id"], ["id"],
        source_schema="fundinv", referent_schema="fundinv_auth",
    )
    op.execute("UPDATE fundinv.fund_valuations SET finalized_at = COALESCE(created_at, now())")


def downgrade() -> None:
    op.drop_constraint("fk_fund_valuations_finalized_by_user", "fund_valuations", schema="fundinv", type_="foreignkey")
    for column in ("notes", "finalized_at", "finalized_by_user_id", "source", "status"):
        op.drop_column("fund_valuations", column, schema="fundinv")
