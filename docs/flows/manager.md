# Manager Flows

## 1. Login & Dashboard Flow

```mermaid
sequenceDiagram
    participant Mgr as Manager
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Mgr->>App: Login at /login
    App->>API: POST /api/auth/login
    API-->>App: JWT token
    App-->>Mgr: Redirect to /dashboard/manager

    App->>API: GET /api/manager/investors
    API->>DB: Query investors WHERE manager_id = manager.id
    API-->>App: Investors list with wallet + portfolio stats

    App->>API: GET /api/manager/funds
    API->>DB: Query active funds
    API-->>App: Funds list with composition

    App-->>Mgr: Dashboard with stats cards (funds, investors, AUM) + investor table + fund sidebar

    Note over Mgr,DB: First-time manager: profile auto-created
    API->>DB: Check fundinv.managers for email
    alt Profile not found
        API->>DB: Auto-create Manager(email, full_name, is_active=true)
        API->>DB: Commit new manager profile
    end
```

## 2. Fund Creation Flow

```mermaid
sequenceDiagram
    participant Mgr as Manager
    participant App as Frontend
    participant API as Backend
    participant Alpaca as Alpaca Markets
    participant DB as Database

    Mgr->>App: Navigate to Funds tab → click "+ Create Fund"

    Note over Mgr,App: Section 1: Fund Details
    Mgr->>App: Enter fund name + description

    Note over Mgr,App: Section 2: Strategy & Risk
    Mgr->>App: Select strategy (Aggressive/Growth/Balanced/Conservative/Income)
    Mgr->>App: Select risk level (Low to High)

    Note over Mgr,App: Section 3: Portfolio Composition
    Mgr->>App: Type stock name/symbol in search bar
    App->>API: GET /api/manager/search-stocks?q={query}
    API->>Alpaca: Search US equities
    Alpaca-->>API: Ticker results (symbol + name)
    API-->>App: Stock search results (dropdown)
    Mgr->>App: Click stock → added to holdings list
    Mgr->>App: Set allocation % for each holding (total must = 100%)

    Mgr->>App: Click "Create Fund"
    App->>API: POST /api/manager/funds { name, description, strategy, risk_level }
    API->>DB: Verify manager profile exists
    API->>DB: Create Fund (fund_type: managed, creator_manager_id)
    API-->>App: { id, name, strategy }

    alt Fund has holdings
        App->>API: PUT /api/manager/funds/{id}/composition { holdings: [{symbol, allocation}] }
        API->>DB: Update fund.portfolio_composition JSONB
        API-->>App: { fund_id, holdings }
    end

    App->>API: GET /api/manager/funds (refresh list)
    App-->>Mgr: Toast: "Fund created successfully" + updated fund list
```

## 3. View Fund Investors Flow

```mermaid
sequenceDiagram
    participant Mgr as Manager
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Mgr->>App: Navigate to Funds tab
    App->>API: GET /api/manager/funds
    API->>DB: Query all active funds
    API-->>App: Fund list

    Mgr->>App: Click fund row → expand
    alt Composition panel
        App-->>Mgr: Show holdings list (symbol + allocation %)
        Note over App,DB: Data from fund.portfolio_composition JSONB
    end

    App->>API: GET /api/manager/funds/{id}/investors
    API->>DB: Query FundInvestment WHERE fund_id AND status=completed
    API->>DB: Join Investor table for name + email
    API-->>App: { investors: [{ investor_id, full_name, email, amount, invested_at }], total_invested }
    alt Investors panel
        App-->>Mgr: Show subscribed investors (name, email, amount, date)
    else No investors
        App-->>Mgr: "No investors subscribed yet"
    end
```

## 4. Trade for Investor Flow

```mermaid
sequenceDiagram
    participant Mgr as Manager
    participant App as Frontend
    participant API as Backend
    participant Alpaca as Alpaca Markets
    participant DB as Database

    Mgr->>App: Navigate to Transactions or Investor detail
    App->>API: GET /api/manager/investors/{id}
    API->>DB: Query investor accounts + wallet balances
    API-->>App: Investor detail (accounts, wallet, positions)

    Mgr->>App: Enter trade details (symbol, side: buy/sell, amount)
    App->>API: POST /api/manager/investors/{id}/trade { symbol, side, amount, investment_account_id, use_fund_balance? }

    API->>DB: Verify investor assigned to this manager
    API->>DB: Check wallet or fund balance >= amount

    API->>Alpaca: Place order (symbol, notional=amount, side)
    Alpaca-->>API: Order confirmation (id, status)

    alt Buy
        API->>DB: Deduct from wallet or manager_fund_balance
    else Sell
        API->>DB: Credit wallet balance
    end

    API->>DB: Create Order record (alpaca_order_id, performed_by_user_id=manager)
    API-->>App: { order_id, alpaca_order_id, symbol, side, amount, status }
    App-->>Mgr: Trade executed successfully
```

## 5. Fund Assignment Flow

```mermaid
sequenceDiagram
    participant Mgr as Manager
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Mgr->>App: Navigate to Investor detail
    App->>API: GET /api/manager/investors/{id}
    API-->>App: Investor detail with accounts

    Mgr->>App: Select fund + enter amount
    App->>API: POST /api/manager/fund-assign { investor_id, fund_id, amount? }

    API->>DB: Verify investor assigned to this manager
    API->>DB: Verify fund exists

    alt Fund targeting not set
        API->>DB: Create FundTargeting (is_visible=true)
    end

    alt Amount > 0
        API->>DB: Verify wallet balance >= amount
        API->>DB: Deduct wallet balance
        API->>DB: Add to manager_fund_balance[{fund_id}]
        API->>DB: Create FundInvestment (status: allocated)
    end

    API-->>App: { investor_id, fund_id, target_created }
    App-->>Mgr: Investor assigned to fund
```

## Manager Scope Boundaries

**What Manager CAN do:**
- Read fund catalogue, fund composition, fund targeting
- CRUD managed funds (create, update, manage composition)
- View assigned investor list, portfolio holdings, investment transactions
- Manage fund targeting (set investor visibility)
- Invite investors (auto-sets `investor.manager_id` to inviting manager)
- Execute trades on behalf of assigned investors
- Read and write articles

**What Manager CANNOT do:**
- Approve/completes/reject fund flows (Operations only)
- Initiate deposits or process withdrawals
- View other managers' investors or funds
- Manage users or system settings
- View audit logs
