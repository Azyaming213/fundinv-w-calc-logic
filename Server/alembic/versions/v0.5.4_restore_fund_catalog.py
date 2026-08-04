"""Restore the approved demonstration fund catalogue for every investor.

Revision ID: v0.5.4_restore_fund_catalog
Revises: v0.5.3_fund_catalog_cleanup
"""

from alembic import op


revision = "v0.5.4_restore_fund_catalog"
down_revision = "v0.5.3_fund_catalog_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The portable seed originally contained thirteen genuine fund products
    # plus seven individual stocks. v0.5.3 correctly removed the stocks, but
    # existing installations may still contain only the three manager-owned
    # demonstration funds. Upsert the complete product catalogue without
    # changing ownership or any financial/accounting records.
    op.execute("""
        INSERT INTO fundinv.funds
            (name, ticker, description, fund_type, strategy, asset_class,
             risk_level, is_active, review_status)
        VALUES
            ('Invesco QQQ Trust', 'QQQ', 'Tracks the Nasdaq-100 index', 'etf', 'growth', 'etf', 'medium-high', TRUE, 'approved'),
            ('Vanguard S&P 500 ETF', 'VOO', 'Tracks the S&P 500 index', 'etf', 'balanced', 'etf', 'medium', TRUE, 'approved'),
            ('Vanguard Total Stock Market', 'VTI', 'Tracks the entire US stock market', 'etf', 'balanced', 'etf', 'medium', TRUE, 'approved'),
            ('SPDR S&P 500 ETF Trust', 'SPY', 'Tracks the S&P 500 index', 'etf', 'balanced', 'etf', 'medium', TRUE, 'approved'),
            ('Vanguard Total Bond Market', 'BND', 'Tracks the US bond market', 'etf', 'conservative', 'bond', 'low', TRUE, 'approved'),
            ('iShares Core US Aggregate Bond', 'AGG', 'Tracks US investment-grade bonds', 'etf', 'conservative', 'bond', 'low', TRUE, 'approved'),
            ('Vanguard High Dividend Yield', 'VYM', 'Focuses on high-dividend US stocks', 'etf', 'income', 'stock', 'low-medium', TRUE, 'approved'),
            ('Schwab US Dividend Equity ETF', 'SCHD', 'Tracks high-quality dividend stocks', 'etf', 'income', 'stock', 'low-medium', TRUE, 'approved'),
            ('Direxion Daily Semiconductor Bull 3X', 'SOXL', '3x leveraged semiconductor ETF', 'etf', 'aggressive', 'etf', 'high', TRUE, 'approved'),
            ('ProShares UltraPro QQQ', 'TQQQ', '3x leveraged Nasdaq-100 ETF', 'etf', 'aggressive', 'etf', 'high', TRUE, 'approved'),
            ('iShares 20+ Year Treasury Bond', 'TLT', 'Long-term US treasury bonds', 'etf', 'conservative', 'bond', 'low', TRUE, 'approved'),
            ('Schwab Short-Term US Treasury ETF', 'SCHR', 'Short-term US treasury bonds', 'etf', 'conservative', 'bond', 'low', TRUE, 'approved'),
            ('Vanguard Dividend Appreciation ETF', 'VIG', 'Focuses on dividend growth stocks', 'etf', 'income', 'stock', 'low-medium', TRUE, 'approved')
        ON CONFLICT (ticker) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            fund_type = EXCLUDED.fund_type,
            strategy = EXCLUDED.strategy,
            asset_class = EXCLUDED.asset_class,
            risk_level = EXCLUDED.risk_level,
            is_active = TRUE,
            review_status = 'approved';
    """)

    # The catalogue is a discovery surface. Risk remains clearly labelled,
    # while suitability is handled by the investor's saved risk tolerance and
    # the application's risk messaging rather than hiding legitimate products.
    op.execute("""
        INSERT INTO fundinv.fund_targeting
            (investor_id, fund_id, is_visible, risk_tolerance)
        SELECT i.id, f.id, TRUE, 'balanced'
        FROM fundinv.investors i
        CROSS JOIN fundinv.funds f
        WHERE i.is_active IS TRUE
          AND f.ticker IN (
              'QQQ', 'VOO', 'VTI', 'SPY', 'BND', 'AGG', 'VYM',
              'SCHD', 'SOXL', 'TQQQ', 'TLT', 'SCHR', 'VIG'
          )
          AND f.is_active IS TRUE
          AND f.review_status = 'approved'
        ON CONFLICT ON CONSTRAINT uq_fund_targeting_investor_fund
        DO UPDATE SET is_visible = TRUE;
    """)


def downgrade() -> None:
    # This is an additive catalogue repair. Removing restored funds on
    # downgrade could destroy or orphan later subscriptions, valuations, and
    # ledger entries, so financial data is intentionally preserved.
    pass
