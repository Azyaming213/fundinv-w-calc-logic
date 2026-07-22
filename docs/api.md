# API Reference

Base URL: `http://localhost:8000`

## Authentication

All authenticated endpoints require a `Bearer` token in the `Authorization` header. Tokens are obtained via `POST /api/auth/login` and expire after `JWT_EXPIRY_MINUTES` (default: 60 minutes).

MFA-enabled accounts receive a temporary MFA token from login. The TOTP code must be submitted to `POST /api/auth/mfa/login` to obtain the final access token.

The JWT payload includes a `claims: string[]` field (claims are UI hints only; the backend re-verifies claims against `fundinv_auth.role_claims` on every request).

---

## Auth — `/api/auth`

Handles registration, login, MFA, password reset, and invites.

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| POST | `/register` | None | — | Register with invitation token |
| POST | `/login` | None | — | Login (returns token or MFA challenge) |
| POST | `/logout` | Token | — | Server-side logout |
| GET | `/me` | Token | — | Get current user profile |
| POST | `/forgot-password` | None | — | Request password reset email |
| POST | `/reset-password` | None | — | Reset password with token |
| POST | `/invites` | Token | `invites:write` | Create invitation |
| GET | `/invites` | Token | `invites:read` | List all invitations |
| DELETE | `/invites/{id}` | Token | `invites:write` | Delete invitation |
| POST | `/invites/{id}/resend` | Token | `invites:write` | Resend invite email |
| POST | `/mfa/setup` | Token | — | Generate MFA QR code |
| POST | `/mfa/verify` | Token | — | Enable MFA with TOTP |
| POST | `/mfa/login` | MFA token | — | Complete MFA login |
| POST | `/mfa/disable` | Token | — | Disable MFA |

---

## Admin — `/api/admin`

Platform administration. Guards now use claims, not role names.

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| GET | `/stats` | Token | `system_stats:read` | Total/active user counts |
| GET | `/audit-logs` | Token | `audit_logs:read` | Paginated audit log |
| GET | `/fund-flows` | Token | `fund_flows:read_all` | List deposit/withdrawal flows. Filters: `search`, `flow_type`, `status` |
| POST | `/fund-flows/{id}/approve` | Token | `fund_flows:approve` | **Ops only.** Approve flow (creates Stripe session, sends email) |
| POST | `/fund-flows/{id}/complete` | Token | `fund_flows:complete` | **Ops only.** Complete flow (credits wallet for deposits) |
| POST | `/fund-flows/{id}/reject` | Token | `fund_flows:reject` | **Ops only.** Reject flow (refunds wallet for withdrawals) |
| POST | `/fund-flows/initiate-deposit` | Token | `fund_flows:initiate_deposit` | **Ops only.** Create deposit + Stripe link for investor |
| GET | `/transactions` | Token | `audit_logs:read` | List all investment transactions |
| GET | `/reconcile` | Token | `system_stats:read` | Cross-check DB vs Alpaca vs Stripe |
| GET | `/fund-targeting` | Token | `fund_targeting:write` | **Manager only.** List fund-targeting rules |
| POST | `/fund-targeting` | Token | `fund_targeting:write` | **Manager only.** Set fund visibility for investor |
| GET | `/users` | Token | `users:read` | List all users with roles |
| PUT | `/users/{id}` | Token | `users:write` | Update user (email, name, role, password, active) |
| GET | `/investors` | Token | `users:read` | List all investors (read-only) |
| GET | `/articles` | Token | `articles:read` | Fetch Yahoo Finance news |

> **Removed**: `PUT /api/admin/investors/{id}` — Admin no longer modifies investor records directly.

---

## Manager — `/api/manager`

Fund and investor management for the manager role.

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| GET | `/investors` | Token | `investors:read_assigned` | List managed investors with portfolio stats |
| GET | `/investors/{id}` | Token | `investors:read_assigned` | Investor detail (accounts, orders, fund investments) |
| POST | `/investors/{id}/trade` | Token | `trading:execute` | Execute trade on behalf of investor |
| GET | `/funds` | Token | `funds:read` | List active funds (with composition + creator) |
| GET | `/funds/{id}/investors` | Token | `funds:read` | List investors subscribed to a fund |
| GET | `/search-stocks` | Token | `funds:create` | Search US equities on Alpaca |
| POST | `/funds` | Token | `funds:create` | Create managed fund |
| PUT | `/funds/{id}/composition` | Token | `fund_composition:write` | Update fund portfolio composition |
| POST | `/fund-assign` | Token | `fund_targeting:write` | Assign investor to fund (optional: invest amount) |
| GET | `/transactions` | Token | `transactions:read` | List manager's trade orders |
| GET | `/transactions/export` | Token | `transactions:read` | Export transactions as CSV |

---

## Funds — `/api/funds`

Fund browsing, discovery, and investment.

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| GET | `/strategies` | Token | — | List strategy metadata |
| GET | `/` | Token | — | Browse funds (filters: strategy, type, search, sort) |
| GET | `/discover` | Token | — | Discover funds from Alpaca by strategy |
| POST | `/seed` | Token | `funds:create` | Seed funds from Alpaca into DB |
| GET | `/stock/{symbol}` | Token | — | Stock details + live price + 90-day chart |
| GET | `/positions` | Token | `portfolio:read_own` | Alpaca positions |
| GET | `/orders` | Token | `portfolio:read_own` | Recent Alpaca orders |
| GET | `/portfolio` | Token | `portfolio:read_own` | Alpaca account summary |
| GET | `/{id}` | Token | — | Single fund detail (investors see targeted only) |
| PUT | `/{id}` | Token | `funds:update` | **Manager only.** Update fund metadata |
| POST | `/invest` | Token | `funds:invest` | Invest in a fund |

---

## Portfolio — `/api/portfolio`

Personal portfolio management.

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| GET | `/chart-data` | Token | `portfolio:read_own` | Historical portfolio value |
| GET | `/summary` | Token | `portfolio:read_own` | Portfolio overview (value, accounts, fund breakdown) |
| POST | `/accounts` | Token | `portfolio:read_own` | Create investment account |
| PUT | `/accounts/{id}` | Token | `portfolio:read_own` | Update account name/strategy |
| GET | `/recent-transactions` | Token | `portfolio:read_own` | Last 10 transactions |
| POST | `/accounts/{id}/close` | Token | `portfolio:read_own` | Close account (liquidate) |
| POST | `/send-summary-email` | Token | `portfolio:export` | Email portfolio summary |
| GET | `/export-pdf` | Token | `portfolio:export` | Download PDF portfolio report |

---

## Wallet — `/api/wallet`

Wallet operations. Webhook is public (unathenticated).

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| GET | `/balance` | Token | `wallet:request_deposit` | Aggregated wallet balance |
| POST | `/topup` | Token | `wallet:request_deposit` | Create Stripe Checkout session (investor self-service) |
| POST | `/webhook` | None | — | Stripe webhook handler |
| POST | `/verify-payment` | Token | `wallet:request_deposit` | Verify payment after redirect |
| GET | `/history` | Token | `wallet:request_deposit` | Last 50 fund flows |
| POST | `/subscription/create` | Token | `wallet:request_deposit` | Create recurring subscription |
| POST | `/request-deposit` | Token | `wallet:request_deposit` | Submit ops-managed deposit request |
| POST | `/request-withdrawal` | Token | `wallet:request_withdrawal` | Submit ops-managed withdrawal request |

---

## Trading — `/api/trading`

Stock trading via Alpaca.

| Method | Path | Auth | Claim Required | Purpose |
|--------|------|------|---------------|---------|
| POST | `/buy` | Token | `funds:invest` | Buy security (deducts wallet, places Alpaca order) |
| POST | `/sell` | Token | `funds:invest` | Sell security (places Alpaca order, credits wallet) |
| GET | `/orders` | Token | `funds:invest` | Last 50 trading orders |

> Manager trades on behalf of investors use `/api/manager/investors/{id}/trade` with `trading:execute` claim.

---

## Standard Response Format

All endpoints return:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

On error:

```json
{
  "detail": "Error message"
}
```

---

## Fund Flow Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Awaiting Stripe payment (top-up or ops-approved deposit) |
| `pending_ops_team` | Awaiting ops review (investor submitted request) |
| `pending_fund_transfer` | Ops approved; awaiting fund transfer completion |
| `completed` | Transfer confirmed; wallet credited (deposit) or sent (withdrawal) |
| `failed` | Stripe payment expired or transaction failed |
| `rejected` | Ops rejected the request (withdrawal refunded) |
