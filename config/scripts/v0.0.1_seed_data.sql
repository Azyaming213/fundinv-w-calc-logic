-- FundInv Solo - Seed Data v0.0.1
-- Run after v0.0.1_init_schema.sql against the target database

-- ============================================================
-- 0. SET search_path
-- ============================================================
SET search_path TO public, fundinv, fundinv_auth;

-- ============================================================
-- 1. Seed roles (investor, manager, admin)
-- ============================================================
INSERT INTO fundinv_auth.roles (name) VALUES ('investor'), ('manager'), ('admin'), ('operations')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 2. Seed role claims (role-scope refactor v0.2.8)
-- ============================================================
INSERT INTO fundinv_auth.role_claims (role_id, claim_key) VALUES
    -- 🟦 investor claims
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'readDashboard'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'readFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'depositToFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'withdrawFromFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'readOwnPortfolio'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'exportPortfolio'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'readArticles'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'readOwnFundFlows'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'createFeedback'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'investor'), 'readOwnFeedback'),
    -- manager claims
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'readDashboard'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'readFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'createFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'updateFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'submitFundsForReview'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'manageFundWeights'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'manageFundTargeting'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'readAssignedInvestors'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'readArticles'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'readTransactions'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'manager'), 'executeTrades'),
    -- operations claims
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'readDashboard'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'readAllFundFlows'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'approveFundFlows'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'completeFundFlows'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'rejectFundFlows'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'reviewFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'readAuditLogs'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'readFeedback'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'manageFeedback'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'operations'), 'requestInvites'),
    -- admin claims
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readDashboard'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readUsers'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'writeUsers'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readInvites'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'writeInvites'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'createInvites'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readRoles'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readAuditLogs'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readSystemStats'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readAllFundFlows'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readFunds'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readTransactions'),
    ((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readOrders')
    ,((SELECT id FROM fundinv_auth.roles WHERE name = 'admin'), 'readFeedback')
ON CONFLICT (role_id, claim_key) DO NOTHING;

-- ============================================================
-- 3. Seed users
-- ============================================================

-- Admin user (password: admin123)
INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id)
VALUES (
    gen_random_uuid(),
    'admin@fundinv.com',
    'Admin User',
    '$2b$12$PYcvXE9PmAVlrjDz1Yy.wu/WWYFV5ezuvhghmdjCnnTfzIN0WqsWa',
    TRUE,
    (SELECT id FROM fundinv_auth.roles WHERE name = 'admin')
) ON CONFLICT (email) DO NOTHING;

-- Manager user (password: admin123)
INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id)
VALUES (
    gen_random_uuid(),
    'manager@fundinv.com',
    'Manager User',
    '$2b$12$PYcvXE9PmAVlrjDz1Yy.wu/WWYFV5ezuvhghmdjCnnTfzIN0WqsWa',
    TRUE,
    (SELECT id FROM fundinv_auth.roles WHERE name = 'manager')
) ON CONFLICT (email) DO NOTHING;

-- Operations user (password: admin123)
INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id)
VALUES (
    gen_random_uuid(),
    'operations@fundinv.com',
    'Operations User',
    '$2b$12$PYcvXE9PmAVlrjDz1Yy.wu/WWYFV5ezuvhghmdjCnnTfzIN0WqsWa',
    TRUE,
    (SELECT id FROM fundinv_auth.roles WHERE name = 'operations')
) ON CONFLICT (email) DO NOTHING;

-- Investor user (password: investor123)
INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id)
VALUES (
    gen_random_uuid(),
    'investor@fundinv.com',
    'Test Investor',
    '$2b$12$ACAPGg2io2eGgaqDr.8M4OQjcHvvTx5ZjoxAADNqWMLf8gg3XyBBK',
    TRUE,
    (SELECT id FROM fundinv_auth.roles WHERE name = 'investor')
) ON CONFLICT (email) DO NOTHING;

-- Second investor user (password: investor123)
INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id)
VALUES (
    gen_random_uuid(),
    'alice@example.com',
    'Alice Johnson',
    '$2b$12$ACAPGg2io2eGgaqDr.8M4OQjcHvvTx5ZjoxAADNqWMLf8gg3XyBBK',
    TRUE,
    (SELECT id FROM fundinv_auth.roles WHERE name = 'investor')
) ON CONFLICT (email) DO NOTHING;

-- System actor (inactive login — used only as audit actor for Stripe webhooks, etc.)
INSERT INTO fundinv_auth.users (user_id, email, full_name, hashed_password, is_active, role_id)
VALUES (
    gen_random_uuid(),
    'system@fundinv.com',
    'System Actor',
    '$2b$12$PYcvXE9PmAVlrjDz1Yy.wu/WWYFV5ezuvhghmdjCnnTfzIN0WqsWa',
    FALSE,
    (SELECT id FROM fundinv_auth.roles WHERE name = 'admin')
) ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- 4. Seed manager profile
-- ============================================================
INSERT INTO fundinv.managers (email, full_name, is_active)
SELECT email, full_name, TRUE
FROM fundinv_auth.users
WHERE email = 'manager@fundinv.com'
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- 5. Seed investor profiles
-- ============================================================
INSERT INTO fundinv.investors (email, full_name, is_active, initial_capital)
SELECT email, full_name, TRUE, 10000.00
FROM fundinv_auth.users
WHERE email = 'investor@fundinv.com'
ON CONFLICT (email) DO NOTHING;

INSERT INTO fundinv.investors (email, full_name, is_active, initial_capital)
SELECT email, full_name, TRUE, 25000.00
FROM fundinv_auth.users
WHERE email = 'alice@example.com'
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- 6. Seed investment accounts
-- ============================================================
INSERT INTO fundinv.investment_accounts (investor_id, account_name, account_number, currency, status, investment_strategy)
SELECT id, 'Growth Portfolio', 'ACC-0001-001', 'USD', 'active', 'growth'
FROM fundinv.investors
WHERE email = 'investor@fundinv.com'
ON CONFLICT DO NOTHING;

INSERT INTO fundinv.investment_accounts (investor_id, account_name, account_number, currency, status, investment_strategy)
SELECT id, 'Balanced Portfolio', 'ACC-0002-001', 'USD', 'active', 'balanced'
FROM fundinv.investors
WHERE email = 'alice@example.com'
ON CONFLICT DO NOTHING;

-- ============================================================
-- 7. Seed custom funds (created by managers)
-- ============================================================
INSERT INTO fundinv.funds (name, ticker, description, fund_type, strategy, asset_class, risk_level, creator_manager_id, is_active) VALUES
('Invesco QQQ Trust', 'QQQ', 'Tracks the Nasdaq-100 index', 'etf', 'growth', 'etf', 'medium-high', (SELECT id FROM fundinv.managers WHERE email = 'manager@fundinv.com'), TRUE),
('Vanguard S&P 500 ETF', 'VOO', 'Tracks the S&P 500 index', 'etf', 'balanced', 'etf', 'medium', (SELECT id FROM fundinv.managers WHERE email = 'manager@fundinv.com'), TRUE),
('Vanguard Total Stock Market', 'VTI', 'Tracks the entire US stock market', 'etf', 'balanced', 'etf', 'medium', NULL, TRUE),
('SPDR S&P 500 ETF Trust', 'SPY', 'Tracks the S&P 500 index', 'etf', 'balanced', 'etf', 'medium', NULL, TRUE),
('Vanguard Total Bond Market', 'BND', 'Tracks the US bond market', 'etf', 'conservative', 'bond', 'low', NULL, TRUE),
('iShares Core US Aggregate Bond', 'AGG', 'Tracks US investment-grade bonds', 'etf', 'conservative', 'bond', 'low', NULL, TRUE),
('Vanguard High Dividend Yield', 'VYM', 'Focuses on high-dividend US stocks', 'etf', 'income', 'stock', 'low-medium', NULL, TRUE),
('Schwab US Dividend Equity ETF', 'SCHD', 'Tracks high-quality dividend stocks', 'etf', 'income', 'stock', 'low-medium', NULL, TRUE),
('Direxion Daily Semiconductor Bull 3X', 'SOXL', '3x leveraged semiconductor ETF', 'etf', 'aggressive', 'etf', 'high', (SELECT id FROM fundinv.managers WHERE email = 'manager@fundinv.com'), TRUE),
('ProShares UltraPro QQQ', 'TQQQ', '3x leveraged Nasdaq-100 ETF', 'etf', 'aggressive', 'etf', 'high', NULL, TRUE),
('iShares 20+ Year Treasury Bond', 'TLT', 'Long-term US treasury bonds', 'etf', 'conservative', 'bond', 'low', NULL, TRUE),
('Schwab Short-Term US Treasury ETF', 'SCHR', 'Short-term US treasury bonds', 'etf', 'conservative', 'bond', 'low', NULL, TRUE),
('Vanguard Dividend Appreciation ETF', 'VIG', 'Focuses on dividend growth stocks', 'etf', 'income', 'stock', 'low-medium', NULL, TRUE)
ON CONFLICT (ticker) DO NOTHING;

-- ============================================================
-- 8. Seed fund targeting (which funds are visible to investors)
-- ============================================================
INSERT INTO fundinv.fund_targeting (investor_id, fund_id, is_visible)
SELECT
    i.id,
    f.id,
    CASE WHEN f.risk_level IN ('low', 'low-medium', 'medium', 'medium-high') THEN TRUE ELSE FALSE END
FROM fundinv.investors i
CROSS JOIN fundinv.funds f
WHERE i.email = 'investor@fundinv.com'
ON CONFLICT (investor_id, fund_id) DO NOTHING;

INSERT INTO fundinv.fund_targeting (investor_id, fund_id, is_visible)
SELECT
    i.id,
    f.id,
    TRUE
FROM fundinv.investors i
CROSS JOIN fundinv.funds f
WHERE i.email = 'alice@example.com'
ON CONFLICT (investor_id, fund_id) DO NOTHING;

-- ============================================================
-- 9. Seed fund flows (deposits and withdrawals)
-- ============================================================
INSERT INTO fundinv.fund_flows (investor_id, investment_account_id, flow_type, amount, status, request_id, requested_at, processed_at, notes) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'deposit', 5000.00, 'completed', 'REQ-0001-001',
    NOW() - INTERVAL '30 days', NOW() - INTERVAL '30 days',
    'Initial deposit'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'deposit', 3000.00, 'completed', 'REQ-0001-002',
    NOW() - INTERVAL '15 days', NOW() - INTERVAL '14 days',
    'Additional deposit'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'withdrawal', 500.00, 'pending', 'REQ-0001-003',
    NOW() - INTERVAL '2 days', NULL,
    'Test withdrawal'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    'deposit', 10000.00, 'completed', 'REQ-0002-001',
    NOW() - INTERVAL '20 days', NOW() - INTERVAL '20 days',
    'Alice initial deposit'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    'deposit', 5000.00, 'completed', 'REQ-0002-002',
    NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days',
    'Alice second deposit'
)
ON CONFLICT (request_id) DO NOTHING;

-- Ops-managed deposit request (pending ops review)
INSERT INTO fundinv.fund_flows (investor_id, investment_account_id, flow_type, amount, status, request_id, requested_at, notes) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'deposit', 2500.00, 'pending_ops_team', 'REQ-0001-004',
    NOW() - INTERVAL '1 day',
    'Bank transfer deposit request'
)
ON CONFLICT (request_id) DO NOTHING;

-- Ops-managed deposit request (approved by ops, awaiting transfer)
INSERT INTO fundinv.fund_flows (investor_id, investment_account_id, flow_type, amount, status, request_id, requested_at, processed_at, processed_by_user_id, notes) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    'deposit', 5000.00, 'pending_fund_transfer', 'REQ-0002-003',
    NOW() - INTERVAL '3 days', NOW() - INTERVAL '2 days',
    (SELECT id FROM fundinv_auth.users WHERE email = 'operations@fundinv.com'),
    'Approved - awaiting funds transfer'
)
ON CONFLICT (request_id) DO NOTHING;

-- Ops-managed withdrawal request (pending ops review)
INSERT INTO fundinv.fund_flows (investor_id, investment_account_id, flow_type, amount, status, request_id, requested_at, notes) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'withdrawal', 1000.00, 'pending_ops_team', 'REQ-0001-005',
    NOW() - INTERVAL '2 days',
    'Withdrawal request to bank account'
)
ON CONFLICT (request_id) DO NOTHING;

-- Ops-managed withdrawal request (approved, awaiting completion)
INSERT INTO fundinv.fund_flows (investor_id, investment_account_id, flow_type, amount, status, request_id, requested_at, processed_at, processed_by_user_id, notes) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    'withdrawal', 2000.00, 'pending_fund_transfer', 'REQ-0002-004',
    NOW() - INTERVAL '4 days', NOW() - INTERVAL '3 days',
    (SELECT id FROM fundinv_auth.users WHERE email = 'operations@fundinv.com'),
    'Approved - processing bank transfer'
)
ON CONFLICT (request_id) DO NOTHING;

-- Rejected deposit request
INSERT INTO fundinv.fund_flows (investor_id, investment_account_id, flow_type, amount, status, request_id, requested_at, processed_at, processed_by_user_id, notes) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'deposit', 100.00, 'rejected', 'REQ-0001-006',
    NOW() - INTERVAL '5 days', NOW() - INTERVAL '4 days',
    (SELECT id FROM fundinv_auth.users WHERE email = 'operations@fundinv.com'),
    'Rejected - test request'
)
ON CONFLICT (request_id) DO NOTHING;

-- ============================================================
-- 10. Seed investment transactions (trades)
-- REMOVED — investors should not have direct stock trades; trades
-- are executed by managers on behalf of funds. Trade records
-- belong in the orders table via the Alpaca reconciliation job.
-- ============================================================

-- ============================================================
-- 11. Seed portfolio holdings
-- REMOVED — portfolio holdings are daily snapshots generated by
-- the reconciliation job, not static seed data.
-- ============================================================

-- ============================================================
-- 12. Seed fund investments
-- ============================================================
INSERT INTO fundinv.fund_investments (investor_id, fund_id, amount, status, invested_at) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    2000.00, 'completed', NOW() - INTERVAL '20 days'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'QQQ'),
    1500.00, 'completed', NOW() - INTERVAL '10 days'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'SPY'),
    3000.00, 'completed', NOW() - INTERVAL '15 days'
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'BND'),
    2500.00, 'completed', NOW() - INTERVAL '8 days'
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 13. Seed orders
-- ============================================================
INSERT INTO fundinv.orders (investor_id, investment_account_id, alpaca_order_id, symbol, side, amount, filled_qty, filled_price, status, performed_by_user_id) VALUES
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'ALP-001', 'AAPL', 'buy', 2000.00, 10, 185.50, 'filled',
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com')
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'ALP-002', 'MSFT', 'buy', 2500.00, 5, 420.30, 'filled',
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com')
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    'ALP-003', 'NVDA', 'buy', 5000.00, NULL, NULL, 'new',
    NULL
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    'ALP-004', 'AMZN', 'buy', 1000.00, 3, 187.25, 'filled',
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com')
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    'ALP-005', 'TSLA', 'sell', 400.00, NULL, NULL, 'pending',
    NULL
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 14. Seed audit logs
-- ============================================================
INSERT INTO fundinv.audit_logs (user_id, action, details, entity_type, entity_id, status, ip_address, user_agent) VALUES
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'admin@fundinv.com'),
    'login_success', 'Admin login', 'user',
    (SELECT id FROM fundinv_auth.users WHERE email = 'admin@fundinv.com'),
    'success', '127.0.0.1', 'Mozilla/5.0'
),
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com'),
    'login_success', 'Manager login', 'user',
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com'),
    'success', '127.0.0.1', 'Mozilla/5.0'
),
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'investor@fundinv.com'),
    'login_success', 'Investor login', 'user',
    (SELECT id FROM fundinv_auth.users WHERE email = 'investor@fundinv.com'),
    'success', '127.0.0.1', 'Mozilla/5.0'
),
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com'),
    'fund_create', 'Created new fund SOXL', 'fund',
    (SELECT id FROM fundinv.funds WHERE ticker = 'SOXL'),
    'success', '127.0.0.1', 'Mozilla/5.0'
),
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com'),
    'order_create', 'Placed buy order for AAPL', 'order',
    (SELECT id FROM fundinv.orders WHERE alpaca_order_id = 'ALP-001'),
    'success', '127.0.0.1', 'Mozilla/5.0'
),
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'admin@fundinv.com'),
    'user_created', 'Created new investor alice@example.com', 'user',
    (SELECT id FROM fundinv_auth.users WHERE email = 'alice@example.com'),
    'success', '127.0.0.1', 'Mozilla/5.0'
),
(
    NULL,
    'login_failed', 'Failed login attempt', 'user', NULL,
    'failure', '192.168.1.100', 'Mozilla/5.0'
)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 15. Seed invites
-- ============================================================
INSERT INTO fundinv.invites (email, full_name, role_id, token, expires_at, used, created_by_id) VALUES
(
    'bob@example.com',
    'Bob Smith',
    (SELECT id FROM fundinv_auth.roles WHERE name = 'investor'),
    'invite-token-bob-investor-123',
    NOW() + INTERVAL '7 days',
    FALSE,
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com')
),
(
    'carol@example.com',
    'Carol Davis',
    (SELECT id FROM fundinv_auth.roles WHERE name = 'investor'),
    'invite-token-carol-investor-456',
    NOW() + INTERVAL '7 days',
    FALSE,
    (SELECT id FROM fundinv_auth.users WHERE email = 'manager@fundinv.com')
),
(
    'dave@example.com',
    'Dave Wilson',
    (SELECT id FROM fundinv_auth.roles WHERE name = 'manager'),
    'invite-token-dave-manager-789',
    NOW() + INTERVAL '7 days',
    FALSE,
    (SELECT id FROM fundinv_auth.users WHERE email = 'admin@fundinv.com')
)
ON CONFLICT (token) DO NOTHING;

-- ============================================================
-- 16. Seed password reset tokens
-- ============================================================
INSERT INTO fundinv_auth.password_reset_tokens (user_id, token, expires_at, used) VALUES
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'investor@fundinv.com'),
    'reset-token-investor-abc123',
    NOW() + INTERVAL '24 hours',
    FALSE
),
(
    (SELECT id FROM fundinv_auth.users WHERE email = 'alice@example.com'),
    'reset-token-alice-def456',
    NOW() - INTERVAL '1 day',
    TRUE
)
ON CONFLICT (token) DO NOTHING;

-- ============================================================
-- 17. Seed investment transactions (challenge 5.4 — FIFO realized PNL)
-- Each buy opens a position (entry='in'); the sell closes it (entry='out')
-- with FIFO realized profit recorded in the profit/net_pnl columns.
-- ============================================================
INSERT INTO fundinv.investment_transactions (
    ticket, order_ticket, investor_id, fund_id, investment_account_id, position_id,
    trade_time, time_msc, trade_type, entry, symbol, volume, price,
    profit, commission, swap, fee, net_pnl, external_id, comment
) VALUES
(
    'BUY-AAPL-0001', 'BUY-AAPL-0001',
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    '2:VOO:1', NOW() - INTERVAL '20 days', (EXTRACT(EPOCH FROM NOW() - INTERVAL '20 days') * 1000)::BIGINT,
    'buy', 'in', 'AAPL', 10.0000, 185.50000000,
    0.0000, -2.0000, 0.0000, -0.5000, -2.5000, 'ALP-001', 'Seed buy — opens AAPL position'
),
(
    'BUY-MSFT-0002', 'BUY-MSFT-0002',
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'QQQ'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    '2:MSFT:2', NOW() - INTERVAL '10 days', (EXTRACT(EPOCH FROM NOW() - INTERVAL '10 days') * 1000)::BIGINT,
    'buy', 'in', 'MSFT', 5.0000, 420.30000000,
    0.0000, -2.0000, 0.0000, -0.5000, -2.5000, 'ALP-002', 'Seed buy — opens MSFT position'
),
(
    'SELL-AAPL-0003', 'SELL-AAPL-0003',
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0001-001'),
    '2:VOO:1', NOW() - INTERVAL '3 days', (EXTRACT(EPOCH FROM NOW() - INTERVAL '3 days') * 1000)::BIGINT,
    'sell', 'out', 'AAPL', 4.0000, 195.00000000,
    38.0000, -2.0000, 0.0000, -0.5000, 35.5000, 'ALP-003', 'Seed sell — FIFO matched 4 @ avg 185.50'
),
(
    'BUY-AMZN-0004', 'BUY-AMZN-0004',
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'SPY'),
    (SELECT id FROM fundinv.investment_accounts WHERE account_number = 'ACC-0002-001'),
    '3:AMZN:3', NOW() - INTERVAL '15 days', (EXTRACT(EPOCH FROM NOW() - INTERVAL '15 days') * 1000)::BIGINT,
    'buy', 'in', 'AMZN', 3.0000, 187.25000000,
    0.0000, -2.0000, 0.0000, -0.5000, -2.5000, 'ALP-004', 'Seed buy — opens AMZN position'
)
ON CONFLICT (ticket) DO NOTHING;

-- ============================================================
-- 18. Seed portfolio holdings (challenge 5.3, 8.1 — daily shareholding snapshots)
-- Rows track each investor's dollar share, % shareholding, daily PNL, and fund NAV
-- over a 5-day window so the dashboard chart renders out of the box.
-- ============================================================
INSERT INTO fundinv.portfolio_holdings (
    investor_id, fund_id, holding_date, account_value, shareholding_pct, daily_pnl, fund_nav
) VALUES
-- investor@fundinv.com — VOO holdings over 5 days (fund NAV grows + PNL allocated per share)
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    NOW() - INTERVAL '5 days', 2000.0000, 40.00000000, 0.0000, 5000.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    NOW() - INTERVAL '4 days', 2010.0000, 40.00000000, 10.0000, 5025.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    NOW() - INTERVAL '3 days', 2025.0000, 40.00000000, 15.0000, 5062.5000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    NOW() - INTERVAL '2 days', 2030.0000, 40.00000000, 5.0000, 5075.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'VOO'),
    NOW() - INTERVAL '1 days', 2042.0000, 40.00000000, 12.0000, 5105.0000
),
-- investor@fundinv.com — QQQ holdings over 3 days
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'QQQ'),
    NOW() - INTERVAL '3 days', 1500.0000, 30.00000000, 0.0000, 5000.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'QQQ'),
    NOW() - INTERVAL '2 days', 1515.0000, 30.00000000, 15.0000, 5050.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'investor@fundinv.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'QQQ'),
    NOW() - INTERVAL '1 days', 1520.0000, 30.00000000, 5.0000, 5066.6667
),
-- alice@example.com — SPY holdings over 4 days
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'SPY'),
    NOW() - INTERVAL '4 days', 3000.0000, 60.00000000, 0.0000, 5000.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'SPY'),
    NOW() - INTERVAL '3 days', 3030.0000, 60.00000000, 30.0000, 5050.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'SPY'),
    NOW() - INTERVAL '2 days', 3015.0000, 60.00000000, -15.0000, 5025.0000
),
(
    (SELECT id FROM fundinv.investors WHERE email = 'alice@example.com'),
    (SELECT id FROM fundinv.funds WHERE ticker = 'SPY'),
    NOW() - INTERVAL '1 days', 3050.0000, 60.00000000, 35.0000, 5083.3333
)
ON CONFLICT DO NOTHING;

UPDATE fundinv.portfolio_holdings
SET snapshot_date = holding_date::date
WHERE snapshot_date IS NULL;

-- Create normalized opening positions from each investor/fund's latest
-- historical snapshot. New deposits and withdrawals update these positions.
WITH latest AS (
    SELECT DISTINCT ON (h.investor_id, h.fund_id)
        h.investor_id, h.fund_id, h.account_value,
        COALESCE(NULLIF(f.current_price, 0), 1)::numeric AS nav_per_unit
    FROM fundinv.portfolio_holdings h
    JOIN fundinv.funds f ON f.id = h.fund_id
    WHERE h.fund_id IS NOT NULL AND h.account_value > 0
    ORDER BY h.investor_id, h.fund_id, h.snapshot_date DESC, h.holding_date DESC
), account_for_investor AS (
    SELECT DISTINCT ON (a.investor_id) a.id, a.investor_id
    FROM fundinv.investment_accounts a
    WHERE a.deleted_at IS NULL AND a.status = 'active'
    ORDER BY a.investor_id, a.created_at, a.id
)
INSERT INTO fundinv.fund_positions
    (investment_account_id, investor_id, fund_id, units, cost_basis)
SELECT a.id, l.investor_id, l.fund_id,
       ROUND(l.account_value / l.nav_per_unit, 10), ROUND(l.account_value, 4)
FROM latest l
JOIN account_for_investor a ON a.investor_id = l.investor_id
ON CONFLICT (investment_account_id, fund_id) DO NOTHING;

-- ============================================================
-- 19. Track schema version
-- ============================================================
DELETE FROM fundinv.alembic_version;
INSERT INTO fundinv.alembic_version (version_num) VALUES ('v0.4.4_security_reporting');
