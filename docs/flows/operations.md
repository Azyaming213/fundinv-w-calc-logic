# Operations Flows

> Historical provider detail only. The current manual/Stripe-neutral approval
> and settlement boundary is defined in
> [Authoritative Fund Portal Workflow](../FUND_PORTAL_WORKFLOW.md).

## 1. Dashboard & Navigation Flow

```mermaid
sequenceDiagram
    participant Ops as Ops Team
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Ops->>App: Login at /login
    App->>API: POST /api/auth/login
    API-->>App: JWT token (role: operations)
    App-->>Ops: Redirect to /dashboard/operations

    App-->>Ops: Operations Console
    Note over Ops,App: Shows workflow guide:
    Note over Ops,App: 1. Initiate Deposit → Stripe link emailed
    Note over Ops,App: 2. Investor submits → pending_ops_team
    Note over Ops,App: 3. Approve → contact investor
    Note over Ops,App: 4. Confirm completion

    Ops->>App: Click "View Fund Flows" or Funds tab
    App-->>Ops: Navigate to Fund Flows page

    App->>API: GET /api/admin/fund-flows (default: all statuses)
    API->>DB: Query fund_flows JOIN investors
    API-->>App: Fund flow list with investor details + status + actions

    Ops->>App: Filter by "Pending Ops Team" to see new requests
    App->>API: GET /api/admin/fund-flows?status=pending_ops_team
    API-->>App: Filtered list
    App-->>Ops: Pending requests table
```

## 2. Initiate Deposit for Investor (NEW)

```mermaid
sequenceDiagram
    participant Ops as Ops Team
    participant App as Frontend
    participant API as Backend
    participant Stripe
    participant DB as Database
    participant Email as SMTP
    participant Inv as Investor

    Ops->>App: Click "Initiate Deposit"
    App-->>Ops: Modal: pick investor email + enter amount

    Ops->>App: Enter investor@example.com + $500
    App->>API: POST /api/admin/fund-flows/initiate-deposit { investor_email, amount }
    API->>DB: Verify investor exists + has active account
    API->>DB: Create FundFlow (status: pending, flow_type: deposit)
    API->>Stripe: Create Checkout Session (SGD, card/PayNow)
    Stripe-->>API: { id, url }
    API->>DB: Update FundFlow.request_id = session.id
    API->>Email: Send deposit email with Stripe payment link
    Email-->>Inv: Email: "FundInv Deposit — Pay $500.00"
    API-->>App: { checkout_url, flow_id }
    App-->>Ops: "Payment link sent to investor"
    Note over Inv,Stripe: Investor pays via Stripe link → webhook → auto-completes
```

## 3. Fund Flow Processing Flow

```mermaid
sequenceDiagram
    participant Ops as Ops Team
    participant App as Frontend
    participant API as Backend
    participant Stripe
    participant DB as Database
    participant Email as SMTP
    participant Inv as Investor

    Note over Ops,DB: Ops reviews pending requests
    Ops->>App: View fund flows filtered by "Pending Ops Team"
    App->>API: GET /api/admin/fund-flows?status=pending_ops_team
    API->>DB: Query flows with status = pending_ops_team
    API-->>App: List of pending requests (investor, type, amount, notes)

    Note over Ops,Stripe: Approve a Deposit
    Ops->>App: Click "Approve" on a deposit request
    App->>API: POST /api/admin/fund-flows/{id}/approve
    API->>DB: Verify status is pending_ops_team
    API->>Stripe: Create Checkout Session (amount in SGD, card/PayNow)
    Stripe-->>API: { id, url }
    API->>DB: Update: request_id=session.id, status=pending, processed_by=ops
    API->>Email: Send deposit approved email with Stripe payment link
    Email-->>Inv: Email: "Deposit Approved - Pay $X.XX via Stripe"
    API-->>App: { status: "pending", checkout_url }
    App-->>Ops: "Payment link sent to investor"
    Note over Inv,DB: Investor pays via Stripe → webhook → auto-completes → wallet credited

    Note over Ops,DB: Approve a Withdrawal
    Ops->>App: Click "Approve" on a withdrawal request
    App->>API: POST /api/admin/fund-flows/{id}/approve
    API->>DB: Verify status is pending_ops_team
    API->>DB: Update: status=pending_fund_transfer, processed_by=ops
    API->>Email: Send withdrawal approved email
    Email-->>Inv: Email: "Withdrawal Approved - Being Processed"
    API-->>App: { status: "pending_fund_transfer" }
    App-->>Ops: "Withdrawal approved"

    Note over Ops,DB: Complete a Transfer
    Ops->>App: Click "Complete" on pending_fund_transfer flow
    App->>API: POST /api/admin/fund-flows/{id}/complete
    API->>DB: Update: status=completed, processed_by=ops, processed_at=now
    alt flow_type = deposit
        API->>DB: Credit wallet balance += amount
    end
    API->>Email: Send completed email
    API-->>App: { status: "completed" }
    App-->>Ops: "Fund flow completed"

    Note over Ops,DB: Reject a Request
    Ops->>App: Click "Reject" on pending flow (any pending status)
    App->>API: POST /api/admin/fund-flows/{id}/reject
    API->>DB: Update: status=rejected, processed_by=ops
    alt flow_type = withdrawal
        API->>DB: Refund wallet balance += amount
    end
    API->>Email: Send rejected email with reason
    API-->>App: { status: "rejected" }
    App-->>Ops: "Fund flow rejected"
```

## Status State Machine

```mermaid
stateDiagram
    [*] --> pending_ops_team : Investor submits

    pending_ops_team --> pending : Approve deposit (Stripe created)
    pending_ops_team --> pending_fund_transfer : Approve withdrawal

    pending --> completed : Stripe webhook (paid)
    pending --> failed : Stripe webhook (expired)
    pending --> rejected : Ops rejects

    pending_fund_transfer --> completed : Ops completes
    pending_fund_transfer --> rejected : Ops rejects

    pending_ops_team --> rejected : Ops rejects

    completed --> [*]
    failed --> [*]
    rejected --> [*]

    note right of pending : Awaiting Stripe payment
    note right of pending_fund_transfer : Ops handles manually
    note right of completed : Wallet credited (deposit) or sent (withdrawal)
```

## Operations Scope Boundaries

**What Operations CAN do:**
- View ALL fund flow requests
- Initiate deposits on behalf of investors (send Stripe Checkout link)
- Approve / complete / reject fund flows
- Add notes to fund flow requests
- View investor account balances
- View own audit logs

**What Operations CANNOT do:**
- Browse fund catalogue / fund data
- View portfolio details / positions
- Create or edit funds
- Manage users or invites
- Trade on behalf of investors
- View articles (no `articles:read` claim)
