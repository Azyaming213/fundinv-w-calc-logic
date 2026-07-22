# System Flows

## 1. Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Note over User,DB: Standard Login
    User->>App: Enter email + password
    App->>API: POST /api/auth/login { email, password }
    API->>DB: SELECT user WHERE email
    API->>API: bcrypt.verify(password, hashed_password)

    alt Invalid credentials
        API-->>App: 401 Unauthorized
        App-->>User: "Invalid email or password"
    else Account inactive
        API-->>App: 403 Forbidden
    else MFA enabled
        API->>API: Generate MFA token (short-lived, mfa_ prefix)
        API-->>App: { mfa_token, message: "MFA required" }
        App->>User: Show TOTP input
        User->>App: Enter 6-digit code
        App->>API: POST /api/auth/mfa/login { mfa_token, totp_code }
        API->>API: pyotp.verify(secret, code)
        API-->>App: { access_token, user }
        App->>App: localStorage.setItem("fundinv_token", token)
    else No MFA
        API->>API: Create JWT (sub, email, role, claims, exp)
        API-->>App: { access_token, user }
        App->>App: localStorage.setItem("fundinv_token", token)
    end

    App->>App: getDashboardPath(user.role)
    App-->>User: Redirect to dashboard

    Note over App,API: Subsequent Requests
    App->>API: GET /api/portfolio/summary (Authorization: Bearer <token>)
    API->>API: Decode JWT, extract user_id and role
    alt Token expired
        API-->>App: 401 Unauthorized
        App->>App: clearAuth(), redirect to /login?expired=true
    else Valid token
        API->>DB: Process request with authenticated user
        API-->>App: Response
    end
```

## 2. Stripe Webhook Flow

```mermaid
sequenceDiagram
    participant Stripe
    participant API as Backend
    participant DB as Database

    Note over Stripe,DB: Payment Completed
    Stripe->>API: POST /api/wallet/webhook (checkout.session.completed)
    API->>API: Verify Stripe signature header
    API->>API: Parse event payload

    alt Signature invalid
        API-->>Stripe: 400 Invalid signature
    else Valid signature
        API->>DB: SELECT FundFlow WHERE request_id = session.id
        alt Flow found + status = pending
            API->>DB: UPDATE status = pending → completed, processed_at = now()
            API->>DB: UPDATE wallet_balance += amount (credit account)
            API-->>Stripe: 200 OK
        else Flow already completed
            API-->>Stripe: 200 OK (idempotent)
        else Flow not found
            API-->>Stripe: 200 OK (ignore unknown)
        end
    end

    Note over Stripe,DB: Session Expired
    Stripe->>API: POST /api/wallet/webhook (checkout.session.expired)
    API->>API: Verify signature
    API->>DB: UPDATE status = pending → failed, processed_at = now()
    API-->>Stripe: 200 OK
```

## 3. Email Notification Flow

```mermaid
sequenceDiagram
    participant Trigger as Trigger Event
    participant Service as Email Service
    participant Yag as yagmail
    participant SMTP as SMTP Server
    participant Recipient

    Trigger->>Service: Call email function (e.g., send_fund_flow_approved_email)

    Service->>Service: Build HTML template (inline CSS, branded header)
    Service->>Service: Format data (amount, request_id, flow_type)
    alt Deposit approved
        Service->>Service: Include Stripe checkout URL button
    else Withdrawal approved
        Service->>Service: Include processing confirmation
    end

    Service->>Yag: yag.send(to, subject, contents=html_body)
    Yag->>SMTP: Connect (settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
    SMTP-->>Yag: Authenticated
    Yag->>SMTP: Send email
    SMTP-->>Recipient: Deliver email
    Yag-->>Service: Return True

    alt SMTP fails
        Service-->>Trigger: Return False (silently caught)
    end

    Note over Trigger,Recipient: Email Types
    Note over Trigger,Recipient: 1. Invite (user onboarding)
    Note over Trigger,Recipient: 2. Fund Flow Approved (deposit: Stripe link; withdrawal: confirmed)
    Note over Trigger,Recipient: 3. Fund Flow Completed (funds received/sent)
    Note over Trigger,Recipient: 4. Fund Flow Rejected (reason provided)
    Note over Trigger,Recipient: 5. Weekly Summary (portfolio performance)
    Note over Trigger,Recipient: 6. Monthly Performance (P&L report)
```

## 4. Scheduled Jobs Flow

```mermaid
graph TD
    Startup[App Startup] --> AutoMigrate{AUTO_MIGRATE?}
    AutoMigrate -->|true| RunMigrations[Run Alembic upgrade head]
    AutoMigrate -->|false| SchedulerStart[Start APScheduler]
    RunMigrations --> SchedulerStart

    SchedulerStart --> Daily3AM[Daily 3:00 AM]
    SchedulerStart --> Daily4AM[Daily 4:00 AM]
    SchedulerStart --> WeeklySun[Weekly Sunday 10:00 AM]
    SchedulerStart --> WeeklyMon[Weekly Monday 9:00 AM]
    SchedulerStart --> Monthly1st[Monthly 1st 9:00 AM]

    Daily3AM --> ExpireInvites[expire_unused_invites]
    ExpireInvites --> LogExpired[Log expired unused invites]

    Daily4AM --> Reconcile[run_daily_reconciliation]
    Reconcile --> CheckOrders[Compare DB orders vs Alpaca API]
    Reconcile --> CheckStripe[Compare Stripe sessions vs DB fund_flows]
    Reconcile --> Report[Report discrepancies]

    WeeklySun --> Rebalance[auto_rebalance_portfolio]
    Rebalance --> CheckDrift[Check allocation drift vs target]
    Rebalance --> RebalanceDrift{Rebalance if drift > 5%?}

    WeeklyMon --> WeeklyEmail[send_weekly_summaries]
    WeeklyEmail --> ForEachInv[For each active investor]
    ForEachInv --> BuildSummary[Build portfolio summary email]
    BuildSummary --> SendEmail[Send via SMTP]

    Monthly1st --> MonthlyEmail[send_monthly_performance]
    MonthlyEmail --> BuildReport[Build P&L report]
    BuildReport --> SendMonthly[Send via SMTP]
```

## 5. Database Schema Relationships

```mermaid
graph TD
    subgraph "fundinv_auth (Authentication)"
        Roles[roles] --> RoleClaims[role_claims]
        Roles --> Users[users]
        Roles --> Invites[invites]
        Users --> PasswordReset[password_reset_tokens]
        Users --> AuditLogs[audit_logs]
        Users --> Orders[orders]
        Users --> FundFlows[fund_flows]
        Users --> Invites
    end

    subgraph "fundinv (Business Domain)"
        Managers[managers] --> Investors[investors]
        Managers --> Funds[funds]
        Investors --> FundTargeting[fund_targeting]
        Investors --> InvestmentAccounts[investment_accounts]
        Investors --> FundFlows
        Investors --> InvestmentTransactions[investment_transactions]
        Investors --> PortfolioHoldings[portfolio_holdings]
        Investors --> FundInvestments[fund_investments]
        Investors --> Orders
        Funds --> FundTargeting
        Funds --> InvestmentAccounts
        Funds --> FundInvestments
        InvestmentAccounts --> FundFlows
        InvestmentAccounts --> Orders
    end

    style Roles fill:#e1f5fe
    style Users fill:#e1f5fe
    style RoleClaims fill:#e1f5fe
    style PasswordReset fill:#e1f5fe
    style Managers fill:#e8f5e9
    style Funds fill:#e8f5e9
    style Investors fill:#e8f5e9
    style InvestmentAccounts fill:#e8f5e9
    style FundFlows fill:#fff3e0
    style FundInvestments fill:#fff3e0
    style Orders fill:#fff3e0
```
