"""Assign the approved seed catalogue to the demonstration Manager.

Revision ID: v0.5.4_assign_seed_funds
Revises: v0.5.3_fund_catalog_cleanup

The original catalogue predates Manager-created funds, so most approved seed
products have no creator_manager_id. In the single-Manager demonstration this
made those products investable by Investors but impossible for the Manager to
value. Scope the backfill to the known seed tickers and only fill NULL values;
Manager-created products and existing assignments are never changed.
"""

from alembic import op


revision = "v0.5.4_assign_seed_funds"
down_revision = "v0.5.3_fund_catalog_cleanup"
branch_labels = None
depends_on = None


SEED_FUND_TICKERS = (
    "QQQ",
    "VOO",
    "VTI",
    "SPY",
    "BND",
    "AGG",
    "VYM",
    "SCHD",
    "SOXL",
    "TQQQ",
    "TLT",
    "SCHR",
    "VIG",
)


def _quoted_tickers() -> str:
    return ",".join(f"'{ticker}'" for ticker in SEED_FUND_TICKERS)


def upgrade() -> None:
    op.execute(f"""
        UPDATE fundinv.funds AS fund
        SET creator_manager_id = manager.id
        FROM fundinv.managers AS manager
        WHERE manager.email = 'manager@fundinv.com'
          AND fund.creator_manager_id IS NULL
          AND fund.fund_type <> 'stock'
          AND fund.review_status = 'approved'
          AND fund.ticker IN ({_quoted_tickers()})
    """)


def downgrade() -> None:
    op.execute(f"""
        UPDATE fundinv.funds AS fund
        SET creator_manager_id = NULL
        FROM fundinv.managers AS manager
        WHERE manager.email = 'manager@fundinv.com'
          AND fund.creator_manager_id = manager.id
          AND fund.ticker IN ({_quoted_tickers()})
          AND fund.ticker NOT IN ('QQQ', 'VOO', 'SOXL')
    """)
