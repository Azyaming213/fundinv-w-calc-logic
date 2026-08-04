"""Expose the complete approved catalogue to the demonstration investor.

Revision ID: v0.5.4_expose_demo_catalog
Revises: v0.5.3_fund_catalog_cleanup
"""

from alembic import op


revision = "v0.5.4_expose_demo_catalog"
down_revision = "v0.5.3_fund_catalog_cleanup"
branch_labels = None
depends_on = None


CATALOG_TICKERS = (
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


def upgrade() -> None:
    # This migration deliberately does not insert, approve, activate, rename,
    # or otherwise modify funds. It only exposes the thirteen existing active,
    # approved demonstration products to investor@fundinv.com. The count guard
    # prevents a partial catalogue from being silently presented as complete.
    tickers_sql = ", ".join(f"'{ticker}'" for ticker in CATALOG_TICKERS)
    op.execute(f"""
        DO $$
        DECLARE
            demo_investor_id INTEGER;
            approved_catalogue_count INTEGER;
        BEGIN
            SELECT id
            INTO demo_investor_id
            FROM fundinv.investors
            WHERE email = 'investor@fundinv.com'
              AND is_active IS TRUE;

            IF demo_investor_id IS NULL THEN
                RAISE EXCEPTION 'Active demonstration investor investor@fundinv.com was not found';
            END IF;

            SELECT COUNT(*)
            INTO approved_catalogue_count
            FROM fundinv.funds
            WHERE ticker IN ({tickers_sql})
              AND is_active IS TRUE
              AND review_status = 'approved'
              AND fund_type IN ('etf', 'bond', 'managed', 'mutual_fund', 'hedge_fund');

            IF approved_catalogue_count <> 13 THEN
                RAISE EXCEPTION
                    'Expected 13 active approved demonstration funds, found %',
                    approved_catalogue_count;
            END IF;

            INSERT INTO fundinv.fund_targeting
                (investor_id, fund_id, is_visible, risk_tolerance)
            SELECT demo_investor_id, f.id, TRUE, 'balanced'
            FROM fundinv.funds f
            WHERE f.ticker IN ({tickers_sql})
              AND f.is_active IS TRUE
              AND f.review_status = 'approved'
              AND f.fund_type IN ('etf', 'bond', 'managed', 'mutual_fund', 'hedge_fund')
            ON CONFLICT ON CONSTRAINT uq_fund_targeting_investor_fund
            DO UPDATE SET is_visible = TRUE;
        END $$;
    """)


def downgrade() -> None:
    # Visibility may have been changed intentionally after this migration. A
    # downgrade must not hide products again or overwrite those later choices.
    pass
