# FundInv Solo

A full-stack investment fund management platform enabling fund managers to create and manage investment funds, investors to subscribe and invest, and operations teams to handle deposit and withdrawal workflows.

## Architecture

```
fundinv-solo/
├── bin/               # Dev startup scripts
├── config/            # Database schema & seed data
├── Server/            # Python FastAPI backend
└── Client/            # Next.js 16 frontend
```

### `bin/` — Startup Scripts

| File | Purpose |
|------|---------|
| `run.sh` | One-command dev environment: starts PostgreSQL (Docker), installs Python deps, runs FastAPI on port 8000, then Next.js on port 3000 |

### `config/` — Database Configuration

| File | Purpose |
|------|---------|
| `table/v0.0.1_init_schema.sql` | Full DDL: creates `fundinv` and `fundinv_auth` schemas, including normalized positions, valuations, settlement ledger, indexes, FKs, and constraints |
| `scripts/v0.0.1_seed_data.sql` | Seed data: 4 roles, 5 users, 20 funds, sample flows, transactions, portfolio holdings, invites |

### `Server/` — Python FastAPI Backend

| Directory / File | Purpose |
|---|---|
| `main.py` | App entry point: FastAPI instance, CORS, router registration, scheduler startup |
| `config.py` | Pydantic `Settings`: reads `.env` for DB URL, JWT, Stripe, Alpaca, SMTP configs |
| `database.py` | SQLAlchemy `engine`, `SessionLocal`, `Base` (declarative base) |
| `dependencies.py` | FastAPI dependency injection: `get_current_user` (JWT decode), `require_role` (RBAC guard) |
| `appconstants.py` | Centralized role names, permission claims, helper functions — single source of truth for RBAC |
| `alembic.ini` | Alembic migration config |
| `alembic/` | Versioned schema migrations; current head is `v0.5.3_fund_catalog_cleanup` |
| `models/` | SQLAlchemy ORM models across 2 PostgreSQL schemas (`fundinv_auth`, `fundinv`) |
| `routers/` | 8 FastAPI routers: auth, admin, funds, wallet, portfolio, trading, articles, manager |
| `services/` | Business logic: auth (bcrypt/JWT), email (yagmail/SMTP), MFA (TOTP), Alpaca API, audit logging |
| `schemas/` | Pydantic models for request/response validation |
| `jobs/` | APScheduler background tasks: reconciliation, rebalancing, email reports, cleanup, auto-migration |

### `Client/` — Next.js 16 Frontend

| Directory | Purpose |
|---|---|
| `app/dashboard/investor/` | Investor dashboard: portfolio, wallet, funds, articles, stock detail |
| `app/dashboard/manager/` | Manager dashboard: investor overview, fund creation/management, transactions |
| `app/dashboard/admin/` | Admin dashboard: users, investors, fund flows, transactions, audit logs, settings |
| `app/dashboard/operations/` | Operations dashboard: fund flow approval/rejection |
| `app/components/` | Shared UI: AuthGuard, Layout, Header, Footer, Button, Card, Input, InviteModal |
| `app/lib/` | API client (fetch wrapper), auth helpers (JWT decode/storage), role constants |
| `app/login/`, `app/register/`, `app/forgot-password/`, `app/reset-password/` | Auth pages |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+ (or Bun)
- PostgreSQL 16+ (or Docker)
- Stripe test account (optional; fixed-amount demo PayNow is the local default)
- Alpaca Markets account (paper trading)

### 1. Environment Setup

```bash
cp .env.template .env
# Edit .env with your values:
#   DATABASE_URL, SECRET_KEY, STRIPE_SECRET_KEY, ALPACA_API_KEY, SMTP_EMAIL, SMTP_PASSWORD
```

### 2. Database Setup

```bash
# Create the database
createdb fundinv

# Run schema
psql -d fundinv -f config/table/v0.0.1_init_schema.sql

# Run seed data
psql -d fundinv -f config/scripts/v0.0.1_seed_data.sql
```

### 3. Install Dependencies

```bash
# Backend
cd Server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd Client
npm install  # or: bun install
```

### 4. Run

```bash
# Option A: One command
bash bin/run.sh

# Option B: Manual
cd Server && uvicorn main:app --reload --port 8000 &
cd Client && npm run dev
```

- **Backend:** [http://localhost:8000](http://localhost:8000) — API docs at [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend:** [http://localhost:3000](http://localhost:3000)

### Automated setup scripts

For a clean extracted copy, use the platform-specific bootstrap script. Both
scripts preserve an existing `.env` and existing database, create them only
when absent, install dependencies, apply migrations, run backend tests and
frontend lint, and complete a production frontend build.

```bash
# Linux
bash bin/setup_linux.sh

# Windows (run from Git Bash with Docker Desktop running)
bash bin/setup_windows_gitbash.sh
```

After either setup completes, the same command starts the full stack:

```bash
bash bin/run.sh
```

Set `INSTALL_PLAYWRIGHT=1` before the command if the machine also needs the
Chromium browser used by `npm run test:e2e`.

### Preparing a source-only zip

Do not include machine-specific or reinstallable artifacts: `.env`,
`Client/node_modules`, `Client/.next`, `Server/venv`, Python caches, test
reports, logs, or OS/IDE metadata. Keep `.env.template`, lockfiles, migrations,
source code, tests, configuration SQL, setup scripts, README, and documentation.

### Seed Users (after running seed data)

| Email | Password | Role |
|-------|----------|------|
| `admin@fundinv.com` | `admin123` | Admin |
| `manager@fundinv.com` | `admin123` | Manager |
| `operations@fundinv.com` | `admin123` | Operations |
| `investor@fundinv.com` | `investor123` | Investor |
| `alice@example.com` | `investor123` | Investor |

---

## User Roles & Capabilities

### Investor
- View portfolio dashboard with charts and P&L tracking
- Request subscriptions into a specifically selected approved fund. The local demo presents a fixed-amount PayNow QR immediately; units are issued only after Operations verifies the recorded receipt.
- Request redemptions from existing fund-unit holdings. Units are removed only after verified settlement.
- Browse the approved fund catalogue and review fund performance data
- View the fund products and underlying holdings made available by fund managers
- Read financial news articles

### Manager
- Dashboard with fund/investor stats and AUM summary
- Create managed funds with stock portfolio composition (search stocks via Alpaca)
- Include stocks, ETFs, and approved funds with percentage targets
- Submit new funds for operations approval; approved funds are automatically rebalanced by target percentage
- View fund details: holdings, allocation percentages, subscribed investors
- Assign investors to funds and execute trades on their behalf
- Submit fund changes for operations review
- Export transaction history as CSV
- Auto-created profile on first login (no seed required)

### Admin
- Full platform oversight: stats, audit logs, user management
- Manage investors: assign managers, toggle active status
- Manage users: edit roles, names, emails, passwords, activation
- Send invitations by email and approve operations invite requests
- View all audit logs and feedback activity
- Set fund visibility targeting per investor
- Invite management (create, list, delete, resend)
- Platform reconciliation: DB vs Alpaca vs Stripe

### Operations
- Review pending subscription/redemption requests
- Verify and complete demo PayNow subscriptions in one action after payment is recorded. Manual transfers retain separate approval and completion steps.
- Monitor provider-confirmed payment and payout completion
- Reject requests with reason (refunds wallet on withdrawals)
- Review and approve/reject manager-created funds
- View audit logs and handle investor feedback

---

## Features

| Feature | Implementation |
|---|---|
| **Fund-flow provider** | Fixed-amount demo PayNow by default; optional manual verification or Stripe Checkout/Connect with signed webhooks |
| **Alpaca Trading** | Paper trading API: order placement, position tracking, market snapshots, price bars, asset search |
| **Email Notifications** | HTML emails via SMTP (yagmail): invite links, fund flow approved/completed/rejected updates |
| **MFA / 2FA** | TOTP-based (pyotp): setup with QR code, verify on login, optional disable |
| **PDF Reports** | Cross-platform portfolio summary export via ReportLab |

## Fund-flow lifecycle

Deposits are fund subscriptions, not unallocated wallet top-ups:

1. The investor selects an investment account, an approved fund/ETF, and an amount.
2. In default `paynow_demo` mode, FundInv immediately presents a dummy QR containing the exact server-locked amount. The simulation records that same amount as received; the investor cannot type a different paid amount.
3. Operations sees requested and received amounts together and selects **Verify & Complete** once. A mismatch blocks settlement. Manual mode retains **Approve**, external verification, then **Complete**; Stripe mode relies on a signed webhook.
4. Only after verified completion does FundInv issue units at the current NAV, update the normalized position and compatibility cache, write one idempotent settlement-ledger entry, and mark the flow completed.

A provider-pending request has not changed the investor's units. Only `completed` means the verified cash movement and unit change have been recorded.

## Scheduler safety

`ENABLE_SCHEDULER=true` enables maintenance, reconciliation, reporting, and the daily accounting snapshot. Automated rebalancing remains off unless the separate `ENABLE_AUTOMATED_TRADING=true` switch is deliberately enabled. In a multi-instance deployment, run the scheduler in exactly one dedicated worker rather than in every API instance.

```bash
cd Server
ENABLE_SCHEDULER=false venv/bin/python scheduler_worker.py
```

The API process should keep `ENABLE_SCHEDULER=false`; the worker registers and runs the schedules itself. Keep `ENABLE_AUTOMATED_TRADING=false` unless real automatic orders are explicitly authorised.
| **Scheduled Jobs** | APScheduler: daily reconciliation, invite cleanup, weekly portfolio summaries, monthly performance reports, auto-rebalancing |
| **Database Migrations** | Alembic versioned migrations (7 versions); optional auto-migrate on startup |
| **Role-Based Access** | 4 roles with granular claims; enforced at API level (dependencies) and UI level (AuthGuard) |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy, Pydantic |
| **Database** | PostgreSQL 16 (schemas: `fundinv`, `fundinv_auth`) |
| **Auth** | bcrypt password hashing, JWT (python-jose), TOTP MFA (pyotp) |
| **Payments** | Stripe Checkout Sessions (SGD), webhooks |
| **Trading** | Alpaca Markets Paper Trading API |
| **Email** | yagmail (SMTP) — HTML templates |
| **Scheduling** | APScheduler (in-process) |
| **PDF** | ReportLab |
| **Migrations** | Alembic |
| **DevOps** | Docker (PostgreSQL container for dev) |

---

## External Services Required

| Service | Purpose | Env Variable |
|---------|---------|-------------|
| Stripe | Wallet top-up payments | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Alpaca Markets | Paper trading & market data | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` |
| SMTP Server | Email notifications | `SMTP_EMAIL`, `SMTP_PASSWORD` |
| PostgreSQL | Primary database | `DATABASE_URL` |

---

## Documentation

See the [`docs/`](./docs) directory for detailed documentation:

- [Architecture](./docs/architecture.md) — System design, data flow, technology decisions
- [Setup Guide](./docs/setup.md) — Detailed environment configuration and deployment
- [API Reference](./docs/api.md) — Complete endpoint listing with request/response schemas
- [Database Schema](./docs/database.md) — ERD diagram, table descriptions, relationships
- [User Flows](./docs/flows/) — Mermaid sequence diagrams for each role:
  - [Investor](./docs/flows/investor.md) — Onboarding, wallet, trading, fund investing
  - [Manager](./docs/flows/manager.md) — Fund creation, investor assignment, trading
  - [Admin](./docs/flows/admin.md) — User management, fund flow approval, reconciliation
  - [Operations](./docs/flows/operations.md) — Fund flow processing
  - [System](./docs/flows/system.md) — Auth, webhooks, scheduled jobs, email

## License

Proprietary. All rights reserved.
