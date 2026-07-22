# Admin Flows

## 1. Login & Dashboard Flow

```mermaid
sequenceDiagram
    participant Adm as Admin
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Adm->>App: Login at /login
    App->>API: POST /api/auth/login
    API-->>App: JWT token (role: admin)
    App-->>Adm: Redirect to /dashboard/admin

    App->>API: GET /api/admin/stats
    API->>DB: SELECT COUNT(*) FROM users
    API-->>App: { total_users, active_users }

    App->>API: GET /api/admin/audit-logs?page=1&page_size=10
    API->>DB: Query audit_logs JOIN users ORDER BY created_at DESC
    API-->>App: Paginated audit log entries

    App-->>Adm: Dashboard: stats cards + audit log table
```

## 2. User Management Flow

```mermaid
sequenceDiagram
    participant Adm as Admin
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Adm->>App: Navigate to Users tab
    App->>API: GET /api/admin/users
    API->>DB: Query users JOIN roles
    API-->>App: User list (id, email, name, role, active, MFA, last_login)

    Adm->>App: Click Edit on a user
    Adm->>App: Modify: email, full_name, role, new_password, is_active
    App->>API: PUT /api/admin/users/{id} { email?, full_name?, role_id?, new_password?, is_active? }
    API->>DB: Update user record
    alt password changed
        API->>API: bcrypt hash new password
    end
    API-->>App: Updated user
    App->>API: GET /api/admin/users (refresh)
    App-->>Adm: Updated user list
```

## 3. Fund Flows View (Read-Only)

Admin can view fund flows but CANNOT approve, complete, or reject them. Those actions belong to Operations.

```mermaid
sequenceDiagram
    participant Adm as Admin
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Adm->>App: Navigate to Fund Flows (if visible)
    App->>API: GET /api/admin/fund-flows (filters: type, status, search)
    API->>DB: Query fund_flows JOIN investors
    API-->>App: Fund flow list with investor + status
    App-->>Adm: Read-only table of fund flows
    Note over Adm,DB: No Approve/Complete/Reject buttons shown
```

## 4. Audit Logs

```mermaid
sequenceDiagram
    participant Adm as Admin
    participant App as Frontend
    participant API as Backend
    participant DB as Database

    Adm->>App: Navigate to Audit Logs
    App->>API: GET /api/admin/audit-logs?page=1&page_size=20
    API->>DB: Query audit_logs JOIN users ORDER BY created_at DESC
    API-->>App: Paginated audit log entries with filters
    App-->>Adm: Audit log table (action, user, entity, timestamp, changes)
```

## 5. Reconciliation Flow

```mermaid
sequenceDiagram
    participant Adm as Admin
    participant App as Frontend
    participant API as Backend
    participant DB as Database
    participant Alpaca as Alpaca Markets
    participant Stripe

    Adm->>App: Navigate to Admin → Reconcile
    App->>API: GET /api/admin/reconcile

    Note over API,Alpaca: Check orders
    API->>DB: Get all Order records with alpaca_order_id
    API->>Alpaca: Get all orders (limit 100)
    API->>API: Compare: DB IDs vs Alpaca IDs

    Note over API,Stripe: Check fund flows
    API->>DB: Get all FundFlow records (filter: request_id LIKE 'cs_%')
    API->>Stripe: List checkout sessions (limit 50)
    API->>API: Compare: DB Stripe refs vs actual Stripe sessions

    API-->>App: { healthy: boolean, discrepancies: [...] }
    App-->>Adm: Reconciliation results
```

## 6. Admin Scope Boundaries

**What Admin CAN do:**
- View all users, invites, roles (read-only)
- Create/update/deactivate user accounts
- Send invites via email
- View full audit logs with filters
- View system statistics
- View fund flows (read-only table)
- View fund catalogue
- Manage articles

**What Admin CANNOT do:**
- Approve, complete, or reject fund flows (Operations only)
- Create or edit funds (Manager only)
- Manage fund targeting (Manager only)
- Trade on behalf of investors (Manager only)
- View individual investor portfolio data
