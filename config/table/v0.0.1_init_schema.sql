-- FundInv Solo - Full Schema v0.2.4
-- Safe to run on fresh or existing DB (uses IF NOT EXISTS / DROP IF EXISTS)
-- Run this in DBeaver connected to the fundinv database

-- ============================================================
-- 0. SET search_path
-- ============================================================
SET search_path TO public, fundinv, fundinv_auth;

-- ============================================================
-- 1. CREATE SCHEMAS
-- ============================================================
CREATE SCHEMA IF NOT EXISTS fundinv;
CREATE SCHEMA IF NOT EXISTS fundinv_auth;

-- ============================================================
-- 2. DROP OLD TABLES (in reverse dependency order)
-- ============================================================
DROP TABLE IF EXISTS fundinv.fund_targeting CASCADE;
DROP TABLE IF EXISTS fundinv.fund_components CASCADE;
DROP TABLE IF EXISTS fundinv.invite_requests CASCADE;
DROP TABLE IF EXISTS fundinv.feedback_tickets CASCADE;
DROP TABLE IF EXISTS fundinv.fund_balance_entries CASCADE;
DROP TABLE IF EXISTS fundinv.managers CASCADE;
DROP TABLE IF EXISTS fundinv.orders CASCADE;
DROP TABLE IF EXISTS fundinv.fund_investments CASCADE;
DROP TABLE IF EXISTS fundinv.funds CASCADE;
DROP TABLE IF EXISTS fundinv.investment_accounts CASCADE;
DROP TABLE IF EXISTS fundinv.portfolio_holdings CASCADE;
DROP TABLE IF EXISTS fundinv.investment_transactions CASCADE;
DROP TABLE IF EXISTS fundinv.fund_flows CASCADE;
DROP TABLE IF EXISTS fundinv.audit_logs CASCADE;
DROP TABLE IF EXISTS fundinv.invites CASCADE;
DROP TABLE IF EXISTS fundinv.investors CASCADE;
DROP TABLE IF EXISTS fundinv_auth.password_reset_tokens CASCADE;
DROP TABLE IF EXISTS fundinv_auth.users CASCADE;
DROP TABLE IF EXISTS fundinv_auth.role_claims CASCADE;
DROP TABLE IF EXISTS fundinv_auth.roles CASCADE;

-- Drop old public schema tables if they exist from bad migrations
DROP TABLE IF EXISTS public.users CASCADE;
DROP TABLE IF EXISTS public.roles CASCADE;
DROP TABLE IF EXISTS public.investors CASCADE;
DROP TABLE IF EXISTS public.fund_flows CASCADE;
DROP TABLE IF EXISTS public.investment_transactions CASCADE;
DROP TABLE IF EXISTS public.portfolio_holdings CASCADE;
DROP TABLE IF EXISTS public.invites CASCADE;
DROP TABLE IF EXISTS public.audit_logs CASCADE;
DROP TABLE IF EXISTS public.password_reset_tokens CASCADE;

-- Drop old enums
DROP TYPE IF EXISTS public.user_role CASCADE;

-- ============================================================
-- 3. fundinv_auth.roles (must come first -- referenced by users/invites)
-- ============================================================
CREATE TABLE fundinv_auth.roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 3a. fundinv_auth.role_claims
-- ============================================================
CREATE TABLE IF NOT EXISTS fundinv_auth.role_claims (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES fundinv_auth.roles(id),
    claim_key VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (role_id, claim_key)
);

CREATE INDEX ix_role_claims_role_id ON fundinv_auth.role_claims (role_id);

-- ============================================================
-- 4. fundinv_auth.users
-- ============================================================
CREATE TABLE fundinv_auth.users (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    role_id INTEGER NOT NULL REFERENCES fundinv_auth.roles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_users_id ON fundinv_auth.users (id);
CREATE UNIQUE INDEX ix_users_email ON fundinv_auth.users (email);

-- ============================================================
-- 5. fundinv_auth.password_reset_tokens
-- ============================================================
CREATE TABLE fundinv_auth.password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES fundinv_auth.users(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_password_reset_tokens_id ON fundinv_auth.password_reset_tokens (id);
CREATE UNIQUE INDEX ix_password_reset_tokens_token ON fundinv_auth.password_reset_tokens (token);
CREATE INDEX ix_password_reset_tokens_user_id ON fundinv_auth.password_reset_tokens (user_id);

-- ============================================================
-- 6. fundinv.managers
-- ============================================================
CREATE TABLE fundinv.managers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_managers_email ON fundinv.managers (email);

-- ============================================================
-- 7. fundinv.funds
-- ============================================================
CREATE TABLE fundinv.funds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20) UNIQUE,
    description VARCHAR(1000),
    fund_type VARCHAR(30) NOT NULL DEFAULT 'other',

    strategy VARCHAR(30),
    asset_class VARCHAR(30),
    risk_level VARCHAR(20),

    current_price NUMERIC(18,8),
    change_pct NUMERIC(10,4),
    ytd_return NUMERIC(10,4),
    expense_ratio NUMERIC(6,4),
    aum NUMERIC(18,2),

    is_featured BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    creator_manager_id INTEGER REFERENCES fundinv.managers(id),
    portfolio_composition JSONB,
    review_status VARCHAR(30) NOT NULL DEFAULT 'approved',
    submitted_at TIMESTAMP WITH TIME ZONE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by_user_id INTEGER REFERENCES fundinv_auth.users(id),
    review_notes VARCHAR(1000),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX ix_funds_ticker ON fundinv.funds (ticker);
CREATE INDEX ix_funds_strategy ON fundinv.funds (strategy);
CREATE INDEX ix_funds_asset_class ON fundinv.funds (asset_class);
CREATE INDEX ix_funds_creator_manager_id ON fundinv.funds (creator_manager_id);
CREATE INDEX ix_funds_review_status ON fundinv.funds (review_status);

-- ============================================================
-- 8a. fundinv.fund_components
-- ============================================================
CREATE TABLE fundinv.fund_components (
    id SERIAL PRIMARY KEY,
    fund_id INTEGER NOT NULL REFERENCES fundinv.funds(id) ON DELETE CASCADE,
    component_fund_id INTEGER REFERENCES fundinv.funds(id),
    symbol VARCHAR(20),
    component_name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(30) NOT NULL,
    target_pct NUMERIC(7,4) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT ck_fund_components_target_pct CHECK (target_pct > 0 AND target_pct <= 100),
    CONSTRAINT ck_fund_components_asset_reference CHECK (symbol IS NOT NULL OR component_fund_id IS NOT NULL)
);

CREATE INDEX ix_fund_components_fund_id ON fundinv.fund_components (fund_id);
CREATE INDEX ix_fund_components_component_fund_id ON fundinv.fund_components (component_fund_id);

-- ============================================================
-- 8. fundinv.investors
-- ============================================================
CREATE TABLE fundinv.investors (
    id SERIAL PRIMARY KEY,
    manager_id INTEGER REFERENCES fundinv.managers(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    initial_capital NUMERIC(18,4) DEFAULT 0,
    stripe_connect_account_id VARCHAR(255) UNIQUE,
    onboarded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_investors_id ON fundinv.investors (id);
CREATE UNIQUE INDEX ix_investors_email ON fundinv.investors (email);
CREATE INDEX ix_investors_manager_id ON fundinv.investors (manager_id);

-- ============================================================
-- 9. fundinv.fund_targeting
-- ============================================================
CREATE TABLE fundinv.fund_targeting (
    id SERIAL PRIMARY KEY,
    investor_id INTEGER NOT NULL REFERENCES fundinv.investors(id) ON DELETE CASCADE,
    fund_id INTEGER NOT NULL REFERENCES fundinv.funds(id) ON DELETE CASCADE,
    is_visible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_fund_targeting_investor_fund UNIQUE (investor_id, fund_id)
);

CREATE INDEX ix_fund_targeting_investor_id ON fundinv.fund_targeting (investor_id);

-- ============================================================
-- 10. fundinv.invites
-- ============================================================
CREATE TABLE fundinv.invites (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES fundinv_auth.roles(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_by_id INTEGER REFERENCES fundinv_auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_invites_id ON fundinv.invites (id);
CREATE INDEX ix_invites_email ON fundinv.invites (email);
CREATE UNIQUE INDEX ix_invites_token ON fundinv.invites (token);

-- ============================================================
-- 11. fundinv.investment_accounts
-- ============================================================
CREATE TABLE fundinv.investment_accounts (
    id SERIAL PRIMARY KEY,
    investor_id INTEGER NOT NULL REFERENCES fundinv.investors(id),
    fund_id INTEGER REFERENCES fundinv.funds(id),

    account_name VARCHAR(255) NOT NULL,
    account_number VARCHAR(50),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL DEFAULT 'active',

    total_invested NUMERIC(18,4) NOT NULL DEFAULT 0,
    current_value NUMERIC(18,4) NOT NULL DEFAULT 0,
    manager_fund_balance JSONB NOT NULL DEFAULT '{}',

    fund_allocations JSONB NOT NULL DEFAULT '{}',

    investment_strategy VARCHAR(30) NOT NULL DEFAULT 'balanced',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_investment_accounts_id ON fundinv.investment_accounts (id);
CREATE INDEX ix_investment_accounts_investor_id ON fundinv.investment_accounts (investor_id);
CREATE INDEX ix_investment_accounts_fund_id ON fundinv.investment_accounts (fund_id);

-- ============================================================
-- 12. fundinv.fund_flows
-- ============================================================
CREATE TABLE fundinv.fund_flows (
    id SERIAL PRIMARY KEY,
    investor_id INTEGER NOT NULL REFERENCES fundinv.investors(id),
    investment_account_id INTEGER REFERENCES fundinv.investment_accounts(id),
    flow_type VARCHAR(20) NOT NULL,
    amount NUMERIC(18,4) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    request_id VARCHAR(100) UNIQUE NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    processed_by_user_id INTEGER REFERENCES fundinv_auth.users(id),
    notes VARCHAR(500)
    ,fund_id INTEGER REFERENCES fundinv.funds(id)
    ,provider VARCHAR(30)
    ,provider_reference VARCHAR(255) UNIQUE
    ,payment_url VARCHAR(2000)
    ,failure_reason VARCHAR(1000)
);

CREATE INDEX ix_fund_flows_id ON fundinv.fund_flows (id);
CREATE INDEX ix_fund_flows_investor_id ON fundinv.fund_flows (investor_id);
CREATE INDEX ix_fund_flows_investment_account_id ON fundinv.fund_flows (investment_account_id);
CREATE INDEX ix_fund_flows_status ON fundinv.fund_flows (status);
CREATE INDEX ix_fund_flows_fund_id ON fundinv.fund_flows (fund_id);

-- ============================================================
-- 13. fundinv.investment_transactions
-- ============================================================
CREATE TABLE fundinv.investment_transactions (
    id SERIAL PRIMARY KEY,
    ticket VARCHAR(50) UNIQUE NOT NULL,
    order_ticket VARCHAR(50),
    investor_id INTEGER REFERENCES fundinv.investors(id),
    fund_id INTEGER REFERENCES fundinv.funds(id),
    investment_account_id INTEGER REFERENCES fundinv.investment_accounts(id),
    position_id VARCHAR(64),
    trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
    time_msc BIGINT,
    trade_type VARCHAR(20) NOT NULL,
    entry VARCHAR(4),
    symbol VARCHAR(20) NOT NULL,
    volume NUMERIC(18,4) NOT NULL,
    price NUMERIC(18,8) NOT NULL,
    profit NUMERIC(18,4) DEFAULT 0,
    commission NUMERIC(18,4) DEFAULT 0,
    swap NUMERIC(18,4) DEFAULT 0,
    fee NUMERIC(18,4) DEFAULT 0,
    net_pnl NUMERIC(18,4) DEFAULT 0,
    sl NUMERIC(18,8),
    tp NUMERIC(18,8),
    magic VARCHAR(64),
    reason VARCHAR(255),
    comment TEXT,
    external_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_investment_transactions_id ON fundinv.investment_transactions (id);
CREATE UNIQUE INDEX ix_investment_transactions_ticket ON fundinv.investment_transactions (ticket);
CREATE INDEX ix_investment_transactions_investor_id ON fundinv.investment_transactions (investor_id);
CREATE INDEX ix_investment_transactions_trade_time ON fundinv.investment_transactions (trade_time);
CREATE INDEX ix_investment_transactions_fund_id ON fundinv.investment_transactions (fund_id);
CREATE INDEX ix_investment_transactions_position_id ON fundinv.investment_transactions (position_id);
CREATE INDEX ix_investment_transactions_external_id ON fundinv.investment_transactions (external_id);
CREATE INDEX ix_investment_transactions_order_ticket ON fundinv.investment_transactions (order_ticket);

-- ============================================================
-- 14. fundinv.portfolio_holdings
-- ============================================================
CREATE TABLE fundinv.portfolio_holdings (
    id SERIAL PRIMARY KEY,
    investor_id INTEGER NOT NULL REFERENCES fundinv.investors(id),
    fund_id INTEGER REFERENCES fundinv.funds(id),
    holding_date TIMESTAMP WITH TIME ZONE NOT NULL,
    account_value NUMERIC(18,4) NOT NULL,
    shareholding_pct NUMERIC(10,8) NOT NULL,
    daily_pnl NUMERIC(18,4) DEFAULT 0,
    fund_nav NUMERIC(18,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_portfolio_holdings_id ON fundinv.portfolio_holdings (id);
CREATE INDEX ix_portfolio_holdings_investor_id ON fundinv.portfolio_holdings (investor_id);
CREATE INDEX ix_portfolio_holdings_holding_date ON fundinv.portfolio_holdings (holding_date);
CREATE INDEX ix_portfolio_holdings_fund_id ON fundinv.portfolio_holdings (fund_id);

-- ============================================================
-- 15. fundinv.fund_investments
-- ============================================================
CREATE TABLE fundinv.fund_investments (
    id SERIAL PRIMARY KEY,
    investor_id INTEGER NOT NULL REFERENCES fundinv.investors(id),
    fund_id INTEGER NOT NULL REFERENCES fundinv.funds(id),
    amount NUMERIC(18,4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    invested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_fund_investments_id ON fundinv.fund_investments (id);
CREATE INDEX ix_fund_investments_investor_id ON fundinv.fund_investments (investor_id);

-- ============================================================
-- 16. fundinv.orders
-- ============================================================
CREATE TABLE fundinv.orders (
    id SERIAL PRIMARY KEY,
    investor_id INTEGER NOT NULL REFERENCES fundinv.investors(id),
    investment_account_id INTEGER NOT NULL REFERENCES fundinv.investment_accounts(id),
    fund_id INTEGER REFERENCES fundinv.funds(id),
    alpaca_order_id VARCHAR(100),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    filled_qty NUMERIC(18,8),
    filled_price NUMERIC(18,8),
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    performed_by_user_id INTEGER REFERENCES fundinv_auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_orders_id ON fundinv.orders (id);
CREATE INDEX ix_orders_investor_id ON fundinv.orders (investor_id);
CREATE INDEX ix_orders_investment_account_id ON fundinv.orders (investment_account_id);
CREATE INDEX ix_orders_fund_id ON fundinv.orders (fund_id);
CREATE INDEX ix_orders_symbol ON fundinv.orders (symbol);

-- ============================================================
-- 17. fundinv.audit_logs
-- ============================================================
CREATE TABLE fundinv.audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES fundinv_auth.users(id),
    action VARCHAR(100) NOT NULL,
    details TEXT,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    changes JSONB,
    status VARCHAR(20),
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_audit_logs_id ON fundinv.audit_logs (id);
CREATE INDEX ix_audit_logs_user_id ON fundinv.audit_logs (user_id);
CREATE INDEX ix_audit_logs_action ON fundinv.audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON fundinv.audit_logs (created_at);
CREATE INDEX ix_audit_logs_entity_type ON fundinv.audit_logs (entity_type);

-- ============================================================
-- 19. fundinv.fund_balance_entries
-- ============================================================
CREATE TABLE fundinv.fund_balance_entries (
    id SERIAL PRIMARY KEY,
    investment_account_id INTEGER NOT NULL REFERENCES fundinv.investment_accounts(id),
    fund_id INTEGER NOT NULL REFERENCES fundinv.funds(id),
    fund_flow_id INTEGER REFERENCES fundinv.fund_flows(id),
    entry_type VARCHAR(30) NOT NULL,
    amount NUMERIC(18,4) NOT NULL,
    provider_reference VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_fund_balance_entries_flow_id UNIQUE (fund_flow_id)
);

CREATE INDEX ix_fund_balance_entries_account_id ON fundinv.fund_balance_entries (investment_account_id);
CREATE INDEX ix_fund_balance_entries_fund_id ON fundinv.fund_balance_entries (fund_id);
CREATE INDEX ix_fund_balance_entries_flow_id ON fundinv.fund_balance_entries (fund_flow_id);

-- ============================================================
-- 20. fundinv.feedback_tickets
-- ============================================================
CREATE TABLE fundinv.feedback_tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES fundinv_auth.users(id),
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    subject VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    assigned_to_user_id INTEGER REFERENCES fundinv_auth.users(id),
    response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_feedback_tickets_user_id ON fundinv.feedback_tickets (user_id);
CREATE INDEX ix_feedback_tickets_status ON fundinv.feedback_tickets (status);

-- ============================================================
-- 21. fundinv.invite_requests
-- ============================================================
CREATE TABLE fundinv.invite_requests (
    id SERIAL PRIMARY KEY,
    requested_by_user_id INTEGER NOT NULL REFERENCES fundinv_auth.users(id),
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role_id INTEGER NOT NULL REFERENCES fundinv_auth.roles(id),
    status VARCHAR(30) NOT NULL DEFAULT 'pending_admin_review',
    reviewed_by_user_id INTEGER REFERENCES fundinv_auth.users(id),
    review_notes VARCHAR(1000),
    invite_id INTEGER REFERENCES fundinv.invites(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_invite_requests_email ON fundinv.invite_requests (email);
CREATE INDEX ix_invite_requests_status ON fundinv.invite_requests (status);

-- ============================================================
-- 18. Alembic version tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS fundinv.alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- ============================================================
-- 19. Set default search_path on the database
-- ============================================================
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET search_path TO fundinv, fundinv_auth, public', current_database());
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Could not set search_path on database %: %', current_database(), SQLERRM;
END;
$$;
