# Setup Guide

## Prerequisites

- **Python** 3.12 or later
- **Node.js** 20 or later (or **Bun** as a faster alternative)
- **PostgreSQL** 16 or later — server running and accessible
- **Docker** (optional — `bin/run.sh` uses a PostgreSQL container)
- **Stripe** account with API keys (for wallet top-ups)
- **Alpaca Markets** account with paper trading API keys (for trading/market data)
- **SMTP** credentials (Gmail App Password or similar — for email notifications)

## Step 1: Clone and Configure Environment

```bash
git clone <repo-url> fundinv-solo
cd fundinv-solo

# Copy and edit environment variables
cp .env.template .env
```

Edit `.env` with your values:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fundinv

# JWT
SECRET_KEY=<generate-a-random-64-char-string>
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60

# Frontend
FRONTEND_URL=http://localhost:3000

# Stripe (for wallet top-up payments)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SUCCESS_URL=http://localhost:3000/dashboard/investor/wallet?payment=success
STRIPE_CANCEL_URL=http://localhost:3000/dashboard/investor/wallet?payment=cancelled

# Alpaca Markets (for paper trading)
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets

# Email (SMTP)
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Auto-migration on startup (set to "true" to auto-run Alembic)
AUTO_MIGRATE=false
```

## Step 2: Database Setup

### Option A: Using Docker (recommended for dev)

```bash
# Start PostgreSQL container
docker run -d --name fundinv-pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=fundinv \
  -p 5432:5432 \
  postgres:16
```

### Option B: Local PostgreSQL

```bash
createdb fundinv
```

### Run Schema and Seed

```bash
psql -d fundinv -f config/table/v0.0.1_init_schema.sql
psql -d fundinv -f config/scripts/v0.0.1_seed_data.sql
```

## Step 3: Install Dependencies

### Backend (Python)

```bash
cd Server
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Frontend (Node.js)

```bash
cd Client
npm install
# or: bun install
```

## Step 4: Run the Application

### Option A: Quick Start Script

```bash
bash bin/run.sh
```

This starts PostgreSQL (Docker), installs Python deps, runs the FastAPI server on port 8000, then the Next.js dev server on port 3000.

### Option B: Manual Start

Terminal 1 — Backend:
```bash
cd Server
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — Frontend:
```bash
cd Client
npm run dev
# or: bun run dev
```

## Step 5: Verify

- **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs) — FastAPI Swagger UI
- **API Health:** [http://localhost:8000/api/test](http://localhost:8000/api/test)
- **Frontend:** [http://localhost:3000](http://localhost:3000)

### Test Login

Use one of the seed users:

| Email | Password | Role | Dashboard |
|-------|----------|------|-----------|
| `admin@fundinv.com` | `admin123` | Admin | `/dashboard/admin` |
| `manager@fundinv.com` | `admin123` | Manager | `/dashboard/manager` |
| `operations@fundinv.com` | `admin123` | Operations | `/dashboard/operations` |
| `investor@fundinv.com` | `investor123` | Investor | `/dashboard/investor` |
| `alice@example.com` | `investor123` | Investor | `/dashboard/investor` |

## External Service Setup

### Stripe Webhook (for local testing)

Use the [Stripe CLI](https://stripe.com/docs/stripe-cli) to forward webhooks locally:

```bash
stripe listen --forward-to localhost:8000/api/wallet/webhook
```

Copy the webhook signing secret and update `STRIPE_WEBHOOK_SECRET` in `.env`.

### Alpaca Markets

Use the Paper API keys from your [Alpaca dashboard](https://app.alpaca.markets/). The application uses the paper trading endpoint by default.

### SMTP (Gmail)

1. Enable 2FA on your Gmail account
2. Generate an [App Password](https://myaccount.google.com/apppasswords)
3. Set `SMTP_EMAIL` to your Gmail address and `SMTP_PASSWORD` to the App Password

## Database Migrations

The project uses Alembic for schema migrations. When `AUTO_MIGRATE=true` is set in `.env`, migrations run automatically on startup.

To run manually:

```bash
cd Server
source venv/bin/activate
alembic upgrade head
```

### Migration History

| Version | Description |
|---------|-------------|
| `bdc05495d650` | Initial 4 core tables (investors, fund_flows, transactions, portfolio_holdings) |
| `af1d51e22989` | v0.2: Add users, invites, password_reset_tokens, audit_logs |
| `v0.2.3` | Add investment_account_id FK to fund_flows |
| `v0.2.4` | Enhance audit_logs with entity_type, entity_id, changes JSONB |
| `v0.2.5` | Add manager role, managers table, fund_targeting |
| `v0.2.6` | Add manager_fund_balance JSONB and fund_id FK to investment_accounts |
| `v0.2.7` | Add creator_manager_id FK to funds |

## Troubleshooting

### Database connection refused
Ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct.

### Stripe checkout fails
Verify `STRIPE_SECRET_KEY` is set and starts with `sk_test_`. Check that `FRONTEND_URL` matches the URL where the frontend is running.

### Alpaca API returns errors
Verify `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` are set. The paper API URL is `https://paper-api.alpaca.markets`.

### Emails not sending
Ensure `SMTP_EMAIL` and `SMTP_PASSWORD` are set correctly. For Gmail, use an App Password (not your account password).

### Port conflicts
Change the ports in commands: `--port 8001` for backend, `-p 3001` for frontend. Update `FRONTEND_URL` accordingly.
