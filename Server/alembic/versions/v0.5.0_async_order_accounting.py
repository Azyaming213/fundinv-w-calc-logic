"""Track idempotent accounting of asynchronous external order fills.

Revision ID: v0.5.0_async_orders
Revises: v0.4.9_balance_cache
"""

from alembic import op
import sqlalchemy as sa


revision = "v0.5.0_async_orders"
down_revision = "v0.4.9_balance_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("accounting_recorded_at", sa.DateTime(timezone=True), nullable=True),
        schema="fundinv",
    )
    op.create_unique_constraint(
        "uq_orders_alpaca_order_id", "orders", ["alpaca_order_id"], schema="fundinv"
    )


def downgrade() -> None:
    op.drop_constraint("uq_orders_alpaca_order_id", "orders", schema="fundinv", type_="unique")
    op.drop_column("orders", "accounting_recorded_at", schema="fundinv")
