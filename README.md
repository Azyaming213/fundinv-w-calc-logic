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
| `table/v0.0.1_init_schema.sql` | Full DDL: creates `fundinv` and `fundinv_auth` schemas, all 17 tables with indexes, FKs, and defaults |
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
| `alembic/` | Migration versions (7 scripts tracking schema evolution from v0.0.1 → v0.2.7) |
| `models/` | 15 SQLAlchemy ORM models across 2 PostgreSQL schemas (`fundinv_auth`, `fundinv`) |
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
- Stripe account (for payments)
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
- Request deposits into approved manager funds (operations review, Stripe Checkout payment link)
- Request withdrawals from approved manager funds (operations review, Stripe Connect payout)
- Browse and invest in funds
- Buy/sell stocks via Alpaca paper trading
- View stock details with historical charts
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
- Review pending deposit/withdrawal requests
- Approve or reject requests (sends Stripe Checkout or Connect setup links)
- Monitor provider-confirmed payment and payout completion
- Reject requests with reason (refunds wallet on withdrawals)
- Review and approve/reject manager-created funds
- View audit logs and handle investor feedback

---

## Features

| Feature | Implementation |
|---|---|
| **Stripe Payments** | Checkout Sessions for approved deposits; Connect onboarding and payout webhooks for withdrawals |
| **Alpaca Trading** | Paper trading API: order placement, position tracking, market snapshots, price bars, asset search |
| **Email Notifications** | HTML emails via SMTP (yagmail): invite links, fund flow approved/completed/rejected updates |
| **MFA / 2FA** | TOTP-based (pyotp): setup with QR code, verify on login, optional disable |
| **PDF Reports** | Portfolio summary export via WeasyPrint (HTML to PDF) |
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
| **PDF** | WeasyPrint (HTML → PDF) |
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
