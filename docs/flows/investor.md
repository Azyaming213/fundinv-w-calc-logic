# Investor Flows

## 1. Onboarding Flow

```mermaid
sequenceDiagram
    participant Inv as Investor
    participant App as Frontend
    participant API as Backend
    participant DB as Database
    participant Email as SMTP

    Note over Inv,DB: Registration (requires invite token)
    Inv->>App: Visit /register?token=INVITE_TOKEN
    App->>API: GET /api/auth/me (validate token)
    API->>DB: Verify invite token exists + not expired
    API-->>App: Invite details (email, name, role)
    Inv->>App: Enter password + confirm
    App->>API: POST /api/auth/register { token, password }
    API->>DB: Create user + mark invite as used
    API-->>App: Registration successful
    App-->>Inv: Redirect to /login

    Note over Inv,DB: Login
    Inv->>App: Enter email + password
    App->>API: POST /api/auth/login { email, password }
    API->>DB: Verify credentials + check MFA
    alt No MFA
        API-->>App: { access_token, user }
        App->>App: Store token in localStorage
        App-->>Inv: Redirect to /dashboard/investor
    else MFA enabled
        API-->>App: { mfa_token, message: "MFA required" }
        App->>Inv: Show TOTP code input
        Inv->>App: Enter 6-digit TOTP
        App->>API: POST /api/auth/mfa/login { mfa_token, totp_code }
        API-->>App: { access_token, user }
        App-->>Inv: Redirect to /dashboard/investor
    end
```

## 2. Wallet Top-Up Flow (Stripe)

```mermaid
sequenceDiagram
    participant Inv as Investor
    participant App as Frontend
    participant API as Backend
    participant Stripe
    participant DB as Database

    Inv->>App: Navigate to Wallet
    App->>API: GET /api/portfolio/summary
    API->>DB: Query accounts + wallet balances
    API-->>App: Accounts list with balances

    Inv->>App: Select account + enter amount ($50, $100, $250, $500, or custom)
    App->>API: POST /api/wallet/topup { amount, investment_account_id }
    API->>DB: Create FundFlow (status: pending, flow_type: deposit)
    API->>Stripe: Create Checkout Session (SGD, card/PayNow)
    Stripe-->>API: { id, url }
    API->>DB: Update FundFlow.request_id = session.id
    API-->>App: { checkout_url }

    App->>Inv: Redirect to Stripe Checkout
    Inv->>Stripe: Complete payment (card or PayNow)
    Stripe->>API: POST /api/wallet/webhook (checkout.session.completed)
    API->>DB: Claim payment: status pending → completed
    API->>DB: Credit wallet balance += amount
    API-->>Stripe: 200 OK

    Note over App: On return from Stripe
    App->>API: POST /api/wallet/verify-payment { session_id }
    API->>DB: Verify flow status
    API-->>App: { status: "completed" }
    App->>API: Refresh balance + history
    App-->>Inv: Show updated wallet balance
```

## 3. Deposit Request Flow (Ops-Managed)

```mermaid
sequenceDiagram
    participant Inv as Investor
    participant App as Frontend
    participant API as Backend
    participant DB as Database
    participant Ops as Ops Team
    participant Stripe
    participant Email as SMTP

    Inv->>App: Navigate to Wallet → Bank Transfer section
    Inv->>App: Select account, enter amount ($1000-$10000), optional notes
    App->>API: POST /api/wallet/request-deposit { amount, investment_account_id, notes }
    API->>DB: Create FundFlow (status: pending_ops_team, request_id: REQ-DEP-XXXXX)
    API-->>App: { request_id, status, message }
    App-->>Inv: "Deposit request submitted. Operations team will review."

    Note over Ops,Email: Ops approves the request
    Ops->>App: Navigate to Fund Flows
    Ops->>API: POST /api/admin/fund-flows/{id}/approve
    API->>Stripe: Create Checkout Session for deposit amount
    Stripe-->>API: { id, url }
    API->>DB: Update FundFlow: request_id=session.id, status=pending
    API->>Email: Send deposit approved email with Stripe payment link
    Email-->>Inv: Email: "Deposit Approved - Pay $X.XX"

    Inv->>Stripe: Click payment link → pay
    Stripe->>API: Webhook: checkout.session.completed
    API->>DB: Claim payment: status pending → completed
    API->>DB: Credit wallet balance
    API->>Email: Send completed email
    Email-->>Inv: Email: "Deposit Completed"
```

## 4. Withdrawal Request Flow

```mermaid
sequenceDiagram
    participant Inv as Investor
    participant App as Frontend
    participant API as Backend
    participant DB as Database
    participant Ops as Ops Team
    participant Email as SMTP

    Inv->>App: Navigate to Wallet → Bank Transfer section
    Inv->>App: Enter withdrawal amount + optional notes
    App->>API: POST /api/wallet/request-withdrawal { amount, investment_account_id, notes }
    API->>DB: Verify sufficient wallet balance
    API->>DB: Deduct wallet balance (reserve funds)
    API->>DB: Create FundFlow (status: pending_ops_team)
    API-->>App: { request_id, message }
    App-->>Inv: "Withdrawal request submitted."

    Note over Ops,Email: Ops processes
    Ops->>App: Navigate to Fund Flows → filter Pending Ops Team
    Ops->>API: POST /api/admin/fund-flows/{id}/approve
    API->>DB: Update status: pending_ops_team → pending_fund_transfer
    API->>Email: Send withdrawal approved email
    Email-->>Inv: Email: "Withdrawal Approved - Being Processed"

    Ops->>API: POST /api/admin/fund-flows/{id}/complete
    API->>DB: Update status: pending_fund_transfer → completed
    API->>Email: Send completed email
    Email-->>Inv: Email: "Withdrawal Completed"
```

## 5. Fund Investment Flow

```mermaid
sequenceDiagram
    participant Inv as Investor
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Inv->>App: Navigate to Funds
    App->>API: GET /api/funds (browse targeted funds)
    API->>DB: Query funds JOIN fund_targeting (is_visible=true)
    API-->>App: Fund list with strategy, risk, price

    Inv->>App: Select fund → click Invest
    App->>API: GET /api/funds/{id}
    API->>DB: Get fund details + live price (Alpaca)
    API-->>App: Fund detail

    Inv->>App: Enter investment amount + select account
    App->>API: POST /api/funds/invest { fund_id, amount, investment_account_id }
    API->>DB: Verify fund exists + investor targeted
    API->>DB: Verify sufficient wallet balance
    API->>DB: Deduct wallet balance
    API->>DB: Add to manager_fund_balance[{fund_id}]
    API->>DB: Create FundInvestment (status: allocated)
    API->>DB: Create FundFlow (type: investment, status: completed)
    API-->>App: { success: true }
    App->>API: Refresh portfolio summary
    App-->>Inv: Updated portfolio with new fund allocation
```

## 6. Trading Flow

```mermaid
sequenceDiagram
    participant Inv as Investor
    participant App as Frontend
    participant API as Backend
    participant Alpaca as Alpaca Markets
    participant DB as Database

    Inv->>App: Navigate to stock search or browse funds
    App->>API: GET /api/funds/stock/{symbol}
    API->>Alpaca: Get asset info + snapshot + 90-day bars
    Alpaca-->>API: Stock data (price, change, chart)
    API-->>App: Stock detail with chart

    Inv->>App: Click Buy → enter amount
    App->>API: POST /api/trading/buy { symbol, amount, investment_account_id }
    API->>DB: Verify wallet balance >= amount
    API->>DB: Deduct wallet balance
    API->>Alpaca: Place buy order (notional)
    Alpaca-->>API: Order confirmation
    API->>DB: Create Order record (alpaca_order_id, symbol, side, amount, status)
    API->>DB: Create FundInvestment (status: completed)
    API-->>App: Order details

    Note over Inv,DB: Sell flow (reverse)
    Inv->>App: Click Sell → enter amount
    App->>API: POST /api/trading/sell { symbol, amount, investment_account_id }
    API->>Alpaca: Check position exists
    API->>Alpaca: Place sell order
    Alpaca-->>API: Order confirmation
    API->>DB: Credit wallet balance
    API->>DB: Create Order + FundInvestment records
    API-->>App: Order details
```

## Investor Scope Boundaries

**What Investor CAN do:**
- View own portfolio, balance, and transactions
- Browse fund catalogue (targeted funds only)
- Request deposits and withdrawals (Ops processes them)
- Invest in funds from wallet balance
- Export portfolio PDF
- Email portfolio summary
- Read articles

**What Investor CANNOT do:**
- Access any other investor's data or portfolio
- Manage funds or fund composition
- Manage fund targeting
- Approve or process fund flows
- Manage users or invites
- View audit logs or system stats
