# Database Schema

## Entity-Relationship Diagram

```mermaid
erDiagram
    roles {
        int id
        string name
        datetime created_at
    }

    role_claims {
        int id
        int role_id
        string claim_key
        datetime created_at
    }

    users {
        int id
        string user_id
        string email
        string full_name
        string hashed_password
        bool is_active
        bool mfa_enabled
        string mfa_secret
        int role_id
        datetime created_at
        datetime updated_at
        datetime last_login_at
    }

    password_reset_tokens {
        int id
        int user_id
        string token
        datetime expires_at
        bool used
        datetime created_at
        datetime used_at
    }

    managers {
        int id
        string email
        string full_name
        bool is_active
        datetime created_at
        datetime updated_at
    }

    funds {
        int id
        string name
        string ticker
        string description
        string fund_type
        string strategy
        string asset_class
        string risk_level
        decimal current_price
        decimal change_pct
        decimal ytd_return
        decimal expense_ratio
        decimal aum
        bool is_featured
        bool is_active
        int creator_manager_id
        string portfolio_composition
        datetime created_at
        datetime updated_at
    }

    investors {
        int id
        int manager_id
        string email
        string full_name
        bool is_active
        decimal initial_capital
        datetime onboarded_at
        datetime updated_at
    }

    fund_targeting {
        int id
        int investor_id
        int fund_id
        bool is_visible
        datetime created_at
    }

    investment_accounts {
        int id
        int investor_id
        int fund_id
        string account_name
        string account_number
        string currency
        string status
        decimal total_invested
        decimal current_value
        decimal wallet_balance
        string manager_fund_balance
        string fund_allocations
        string investment_strategy
        bool is_recurring_payment
        decimal recurring_payment_amount
        string recurring_frequency
        date next_payment_date
        datetime created_at
        datetime updated_at
        datetime deleted_at
    }

    fund_flows {
        int id
        int investor_id
        int investment_account_id
        string flow_type
        decimal amount
        string status
        string request_id
        datetime requested_at
        datetime processed_at
        int processed_by_user_id
        string notes
    }

    investment_transactions {
        int id
        string ticket
        int investor_id
        datetime trade_time
        string trade_type
        string symbol
        decimal volume
        decimal price
        decimal profit
        decimal commission
        decimal swap
        decimal fee
        decimal net_pnl
        datetime created_at
    }

    portfolio_holdings {
        int id
        int investor_id
        datetime holding_date
        decimal account_value
        decimal shareholding_pct
        decimal daily_pnl
        datetime created_at
    }

    fund_investments {
        int id
        int investor_id
        int fund_id
        decimal amount
        string status
        datetime invested_at
    }

    orders {
        int id
        int investor_id
        int investment_account_id
        string alpaca_order_id
        string symbol
        string side
        decimal amount
        decimal filled_qty
        decimal filled_price
        string status
        int performed_by_user_id
        datetime created_at
        datetime updated_at
    }

    audit_logs {
        int id
        int user_id
        string action
        string details
        string entity_type
        int entity_id
        string changes
        string status
        string ip_address
        string user_agent
        datetime created_at
    }

    invites {
        int id
        string email
        string full_name
        int role_id
        string token
        datetime expires_at
        bool used
        int created_by_id
        datetime created_at
        datetime used_at
    }

    roles ||--o{ role_claims : "grants"
    roles ||--o{ users : "has"
    roles ||--o{ invites : "targets"
    users ||--o{ password_reset_tokens : "requests"
    users ||--o{ audit_logs : "performs"
    users ||--o{ invites : "creates"
    users ||--o{ orders : "executes"
    users ||--o{ fund_flows : "processes"
    managers ||--o{ investors : "manages"
    managers ||--o{ funds : "creates"
    investors ||--o{ investment_accounts : "owns"
    investors ||--o{ fund_flows : "requests"
    investors ||--o{ investment_transactions : "trades"
    investors ||--o{ portfolio_holdings : "has"
    investors ||--o{ fund_investments : "invests"
    investors ||--o{ orders : "places"
    investors ||--o{ fund_targeting : "sees"
    funds ||--o{ investment_accounts : "linked"
    funds ||--o{ fund_targeting : "targeted"
    investment_accounts ||--o{ fund_flows : "funded"
    investment_accounts ||--o{ orders : "placed"
```

## Schemas

The database uses two PostgreSQL schemas:

| Schema | Purpose | Tables |
|--------|---------|--------|
| `fundinv_auth` | Authentication & authorization | `roles`, `role_claims`, `users`, `password_reset_tokens` |
| `fundinv` | Business domain | `managers`, `funds`, `investors`, `fund_targeting`, `invites`, `investment_accounts`, `fund_flows`, `investment_transactions`, `portfolio_holdings`, `fund_investments`, `orders`, `audit_logs`, `alembic_version` |

## Table Descriptions

### fundinv_auth.roles
User roles. 4 seeded: `investor`, `manager`, `admin`, `operations`.

### fundinv_auth.role_claims
Granular RBAC permissions per role. Each claim is a `resource:action` string (e.g., `funds:create`, `fund_flows:approve`).

### fundinv_auth.users
User accounts. Each has a UUID `user_id` (public-facing) and a SERIAL `id` (internal FK). Supports MFA via `mfa_secret` column.

### fundinv_auth.password_reset_tokens
Time-limited tokens for password reset. Tokens expire based on `expires_at`. `used` flag prevents replay.

### fundinv.managers
Fund manager profiles. Linked to `fundinv_auth.users` by email. Auto-created on first manager login if profile doesn't exist.

### fundinv.funds
Investment funds/products. Supports multiple types (etf, stock, crypto, bond, managed, hedge_fund, mutual_fund, other). Managed funds are created by managers with a `creator_manager_id`. The `portfolio_composition` JSONB stores holdings as `[{symbol, allocation}]`.

### fundinv.investors
Investor profiles. Each is assigned to a manager (`manager_id`). Has `initial_capital` tracking and an `onboarded_at` timestamp.

### fundinv.fund_targeting
Controls which funds are visible to which investors. Each row is a unique `(investor_id, fund_id)` pair with an `is_visible` boolean. CASCADE deletes when fund or investor is removed.

### fundinv.investment_accounts
Investor portfolios. Each account holds:
- **`wallet_balance`** — available cash for trading/investing
- **`manager_fund_balance`** — JSONB tracking money allocated to manager funds per fund ID
- **`fund_allocations`** — JSONB tracking stock positions
- **`investment_strategy`** — one of: aggressive, growth, balanced, conservative, income
- Supports recurring payments and soft delete (`deleted_at`)

### fundinv.fund_flows
Deposit and withdrawal records. Key columns:
- **`flow_type`** — `deposit`, `withdrawal`, `investment`
- **`status`** — `pending` (Stripe), `pending_ops_team`, `pending_fund_transfer`, `completed`, `failed`, `rejected`
- **`request_id`** — unique identifier (Stripe session ID or generated `REQ-DEP-*`/`REQ-WTH-*`)
- **`processed_by_user_id`** — tracks which admin/ops user processed the flow

### fundinv.investment_transactions
Trade records (buy/sell). Each has a unique `ticket` ID, trade metadata, and P&L columns (`profit`, `commission`, `net_pnl`). `net_pnl` = realized profit - costs for sells; 0 for buys.

### fundinv.portfolio_holdings
Daily portfolio snapshots. Records `account_value`, `shareholding_pct`, and `daily_pnl` for each investor on a given `holding_date`.

### fundinv.fund_investments
Records of investor investments in specific funds. Links investor to fund with amount and status (`pending`, `completed`, `failed`).

### fundinv.orders
Trading orders placed via Alpaca. Stores `alpaca_order_id`, symbol, side (buy/sell), amount, fill details, status, and which user (`performed_by_user_id`) executed the order.

### fundinv.audit_logs
Immutable audit trail. Records every significant action with user, action type, target entity, JSONB changes, IP address, and user agent.

### fundinv.invites
Invitation tokens for user onboarding. Created by admins/managers. Each has a unique `token`, expiry, and `used` tracking. Linked to a target `role_id`.

## Fund Flow Status Lifecycle

```mermaid
stateDiagram
    [*] --> pending_ops_team : Investor submits request

    pending_ops_team --> pending : Ops approves deposit (Stripe session created)
    pending_ops_team --> pending_fund_transfer : Ops approves withdrawal

    pending --> completed : Stripe webhook (payment confirmed)
    pending --> failed : Stripe webhook (session expired)

    pending_fund_transfer --> completed : Ops completes (credits/deducts wallet)
    pending_fund_transfer --> rejected : Ops rejects

    pending_ops_team --> rejected : Ops rejects
    pending --> rejected : Ops rejects

    completed --> [*]
    failed --> [*]
    rejected --> [*]
```

## Permissions Matrix (v0.2.8+)

| Claim | investor | manager | operations | admin |
|-------|:--------:|:-------:|:----------:|:-----:|
| `dashboard:view` | ✓ | ✓ | ✓ | ✓ |
| `portfolio:read_own` | ✓ | ✓ | — | — |
| `portfolio:export` | ✓ | — | — | — |
| `wallet:request_deposit` | ✓ | — | — | — |
| `wallet:request_withdrawal` | ✓ | — | — | — |
| `funds:read` | ✓ | ✓ | — | ✓ |
| `funds:invest` | ✓ | — | — | — |
| `funds:create` | — | ✓ | — | — |
| `funds:update` | — | ✓ | — | — |
| `fund_composition:write` | — | ✓ | — | — |
| `fund_targeting:write` | — | ✓ | — | — |
| `investors:read_assigned` | — | ✓ | ✓ | — |
| `fund_flows:read_all` | — | — | ✓ | ✓ |
| `fund_flows:read_own` | ✓ | — | — | — |
| `fund_flows:approve` | — | — | ✓ | — |
| `fund_flows:complete` | — | — | ✓ | — |
| `fund_flows:reject` | — | — | ✓ | — |
| `fund_flows:initiate_deposit` | — | — | ✓ | — |
| `fund_flows:add_notes` | — | — | ✓ | — |
| `audit_logs:read` | — | — | ✓ | ✓ |
| `articles:read` | ✓ | ✓ | — | ✓ |
| `articles:write` | — | ✓ | — | ✓ |
| `invites:write` | — | ✓ | — | ✓ |
| `invites:read` | — | — | — | ✓ |
| `users:read` | — | — | — | ✓ |
| `users:write` | — | — | — | ✓ |
| `roles:read` | — | — | — | ✓ |
| `system_stats:read` | — | — | — | ✓ |
| `trading:execute` | — | ✓ | — | — |
| `transactions:read` | — | ✓ | — | — |

## Seed Data

Running `config/scripts/v0.0.1_seed_data.sql` creates:

| Section | Records |
|---------|---------|
| Roles | 4 (investor, manager, admin, operations) |
| Role Claims | 42 claims across all roles |
| Users | 6 (admin, manager, ops, 2 investors, system@fundinv.com) |
| Manager Profiles | 1 (linked to manager@fundinv.com) |
| Investor Profiles | 2 (investor@fundinv.com, alice@example.com) |
| Investment Accounts | 2 (Growth Portfolio, Balanced Portfolio) |
| Funds | 20 (QQQ, VOO, SPY, NVDA, TSLA, etc.) |
| Fund Targeting | Per-investor visibility rules |
| Fund Flows | 11 (deposits, withdrawals, ops-managed) |
| Investment Transactions | 7 (buy/sell AAPL, MSFT, NVDA, TSLA, AMZN) |
| Portfolio Holdings | 5 daily snapshots |
| Fund Investments | 4 (VOO, QQQ, SPY, BND) |
| Orders | 5 Alpaca orders |
| Audit Logs | 7 events |
| Invites | 3 pending invites |
| Password Reset Tokens | 2 tokens |

### System User

`system@fundinv.com` is a seeded inactive user (role: admin) used exclusively as an actor for audit events triggered by system processes (e.g., Stripe webhook completions). Its login is permanently disabled (`is_active = FALSE`).
