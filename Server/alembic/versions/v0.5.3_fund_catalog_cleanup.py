"""Remove individual securities that were incorrectly seeded as fund products.

Revision ID: v0.5.3_fund_catalog_cleanup
Revises: v0.5.2_paynow_demo
"""

from alembic import op


revision = "v0.5.3_fund_catalog_cleanup"
down_revision = "v0.5.2_paynow_demo"
branch_labels = None
depends_on = None


STOCK_TICKERS = "'AMD','NVDA','TSLA','COIN','AAPL','MSFT','AMZN'"


def upgrade() -> None:
    # Visibility rows are catalogue metadata and intentionally cascade. Any
    # accounting, transaction, or composition dependency blocks the migration
    # so a populated product can never be deleted silently.
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM fundinv.funds f
                WHERE f.ticker IN ({STOCK_TICKERS})
                  AND f.fund_type = 'stock'
                  AND (
                    EXISTS (SELECT 1 FROM fundinv.fund_balance_entries x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.fund_components x WHERE x.fund_id = f.id OR x.component_fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.fund_flows x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.fund_investments x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.fund_positions x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.fund_valuations x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.investment_accounts x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.investment_transactions x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.orders x WHERE x.fund_id = f.id) OR
                    EXISTS (SELECT 1 FROM fundinv.portfolio_holdings x WHERE x.fund_id = f.id)
                  )
            ) THEN
                RAISE EXCEPTION 'Stock catalogue cleanup blocked: a target row has accounting dependencies';
            END IF;

            DELETE FROM fundinv.funds
            WHERE ticker IN ({STOCK_TICKERS})
              AND fund_type = 'stock';
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        INSERT INTO fundinv.funds
            (name, ticker, description, fund_type, strategy, asset_class,
             risk_level, creator_manager_id, is_active, review_status)
        VALUES
            ('Advanced Micro Devices Inc', 'AMD', 'Semiconductor company stock', 'stock', 'aggressive', 'stock', 'high', NULL, TRUE, 'approved'),
            ('NVIDIA Corporation', 'NVDA', 'AI and GPU company stock', 'stock', 'aggressive', 'stock', 'high',
             (SELECT id FROM fundinv.managers WHERE email = 'manager@fundinv.com'), TRUE, 'approved'),
            ('Tesla Inc', 'TSLA', 'Electric vehicle and clean energy company', 'stock', 'aggressive', 'stock', 'high', NULL, TRUE, 'approved'),
            ('Coinbase Global Inc', 'COIN', 'Cryptocurrency exchange stock', 'stock', 'aggressive', 'stock', 'high', NULL, TRUE, 'approved'),
            ('Apple Inc', 'AAPL', 'Technology company stock', 'stock', 'growth', 'stock', 'medium', NULL, TRUE, 'approved'),
            ('Microsoft Corporation', 'MSFT', 'Technology company stock', 'stock', 'growth', 'stock', 'medium', NULL, TRUE, 'approved'),
            ('Amazon.com Inc', 'AMZN', 'E-commerce and cloud company stock', 'stock', 'growth', 'stock', 'medium', NULL, TRUE, 'approved')
        ON CONFLICT (ticker) DO NOTHING;

        INSERT INTO fundinv.fund_targeting (investor_id, fund_id, is_visible, risk_tolerance)
        SELECT i.id, f.id, TRUE, 'balanced'
        FROM fundinv.investors i
        CROSS JOIN fundinv.funds f
        WHERE f.ticker IN ('AMD','NVDA','TSLA','COIN','AAPL','MSFT','AMZN')
        ON CONFLICT (investor_id, fund_id) DO NOTHING;
    """)
