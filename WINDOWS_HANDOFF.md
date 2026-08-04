# FundInv Windows Machine Handoff

Last updated: 1 August 2026 (Asia/Singapore)

## Purpose

This document transfers the important context from the Linux development session to a new Codex/chat session on the Windows laptop. Give the new assistant this file and ask it to inspect the extracted project before changing anything.

## Project and repository

- Project folder in the portable archive: `fundinv-solo-portable`
- Private GitHub repository: `https://github.com/Azyaming213/fundinv-w-calc-logic.git`
- Stack:
  - Next.js 16 frontend
  - FastAPI backend
  - PostgreSQL 16
  - Alembic migrations
  - Docker Desktop for the Windows PostgreSQL container
- Roles: Admin, Manager, Operations, and Investor
- The portable archive intentionally excludes `.env`, `.git`, `node_modules`, `.next`, `Server/venv`, caches, logs, and database files.

## Important source-control warning

The latest Linux workspace contains uncommitted changes made after commit:

```text
53f2b21 Implement integrated fund accounting, security, reporting, and tests
```

The portable ZIP contains those current working files, but it does not contain `.git`. Do not assume the private GitHub repository already contains every change described here. Compare the Windows files with the remote repository before pulling, replacing, or pushing anything.

## Current Windows configuration

The recommended Windows database arrangement is:

| Item | Value |
|---|---|
| Docker container | `fundinv-current` |
| PostgreSQL Windows host port | `5434` |
| PostgreSQL container port | `5432` |
| Database | `fundinv` |
| User | `postgres` |
| Password | `postgres` |
| Frontend | `http://localhost:3000` |
| Backend | `http://localhost:8000` |
| API documentation | `http://localhost:8000/docs` |

Port 5434 was chosen because older projects may already use host ports 5432 and 5433. Containers can all use port 5432 internally as long as their Windows host ports differ.

## Windows prerequisites

- Windows 10 or 11, 64-bit
- Git for Windows / Git Bash
- Docker Desktop with the WSL 2 backend
- Python 3.12 or newer, available through `py -3` or `python`
- Node.js 20 or newer with npm
- 8 GB RAM minimum; 16 GB recommended
- Approximately 10 GB free space for Docker, dependencies, builds, and browser testing

Start Docker Desktop and wait for Docker Engine before running either script.

## Extract and set up

Extract the portable ZIP somewhere writable, preferably outside OneDrive and `Program Files`. Open Git Bash in the extracted `fundinv-solo-portable` folder.

Verify tools:

```bash
docker --version
py -3 --version
node --version
npm --version
```

Run the one-time setup:

```bash
FUNDINV_DB_CONTAINER=fundinv-current FUNDINV_DB_PORT=5434 bash bin/setup_windows_gitbash.sh
```

The setup script:

- creates `.env` only if it is absent;
- generates a random local JWT signing secret;
- sets the new database URL to `postgresql://postgres:postgres@localhost:5434/fundinv`;
- creates or starts the `fundinv-current` PostgreSQL container;
- initializes and seeds only a new database;
- preserves an existing FundInv database rather than replaying destructive SQL;
- creates `Server/venv` using the Windows `Scripts/python.exe` layout;
- installs backend and frontend dependencies;
- applies all Alembic migrations;
- runs backend tests and frontend lint;
- completes a production Webpack build before reporting success.

If `.env` already exists, the script deliberately preserves it. Manually confirm that its `DATABASE_URL` matches the chosen container and host port.

## Normal startup

From the extracted project root in Git Bash:

```bash
FUNDINV_DB_CONTAINER=fundinv-current FUNDINV_DB_PORT=5434 bash bin/run.sh
```

The same `run.sh` supports Linux and Windows Git Bash. On Windows it selects:

```text
Server/venv/Scripts/python.exe
```

It then:

- checks that ports 8000 and 3000 are free;
- starts the existing database container without resetting it;
- applies pending migrations;
- enables the scheduler and the idempotent startup P&L snapshot;
- keeps automated trading disabled by default;
- starts FastAPI without development reload by default;
- builds the frontend with Webpack under a 2 GB Node heap cap;
- starts the supported Next.js standalone production server;
- shuts down the frontend and backend when Ctrl+C is pressed.

A short CPU increase while Next.js performs its production build is expected. CPU and RAM should settle after the build. It should not continually create compiler processes or grow past the configured Node heap.

## Database safety

Neither setup nor `run.sh` resets an existing database.

- Base schema and seed SQL run only if `fundinv_auth.users` does not exist.
- Alembic applies only pending migrations.
- Current migration head: `v0.5.4_expose_demo_catalog`
- The `v0.4.6`–`v0.4.9` migrations normalize fund flows, repair historical NAV/unit records, reconcile cost basis/principal, and rebuild the legacy display cache.

Do not run this unless deliberately deleting the Windows database:

```bash
docker rm fundinv-current
```

To restart the preserved container:

```bash
docker start fundinv-current
```

## Seed accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@fundinv.com` | `admin123` |
| Manager | `manager@fundinv.com` | `admin123` |
| Operations | `operations@fundinv.com` | `admin123` |
| Investor | `investor@fundinv.com` | `investor123` |
| Investor | `alice@example.com` | `investor123` |

These credentials are for local demonstrations. Change them for any non-demo deployment.

## Fund-flow and role behavior

The intended cross-role flow is:

1. Investor selects a fund, account, and amount for a subscription.
2. The local `paynow_demo` provider immediately shows a clearly labelled dummy PayNow QR containing the exact server-locked amount and reference. It never moves real money.
3. The investor simulates scanning and paying; the server records the requested amount automatically, so the browser cannot submit an overpayment or underpayment.
4. Operations sees requested and received amounts side by side and uses **Verify & Complete** once. A mismatch blocks settlement, and units do not change before this action.
5. Manual subscriptions retain separate **Approve** and **Complete** actions because receipt is verified outside the portal. Stripe subscriptions require signed webhooks.
6. Redemptions retain approval, verified payout, and completion before units are removed.
7. Admin can audit transactions and fund flows. Manager can view fund performance and trade the underlying securities held by funds; Investors cannot trade securities directly.

Selecting a fund is deliberate because units and NAV belong to a specific fund. The local default is `FUND_FLOW_PROVIDER=paynow_demo`; Stripe, SMTP, and Alpaca credentials are not required for this core fund-accounting demonstration.

## P&L calculation flow

The accounting implementation separates investment performance from investor cash flows.

### Holdings and FIFO realized P&L

For each security position:

```text
Market value = quantity × current market price
Unrealized P&L = market value − remaining cost basis
Realized P&L = sale proceeds − FIFO cost of units sold − applicable costs
```

Historical purchases form FIFO lots. A sale consumes the oldest available lots first. Each sale is consumed only once, including partial-lot sales.

### Fund NAV and units

```text
Fund NAV = cash + total current market value of holdings
NAV per unit = fund NAV ÷ total outstanding units
Deposit units minted = approved deposit amount ÷ applicable NAV per unit
Withdrawal amount = units redeemed × applicable NAV per unit
Investor value = investor units × current NAV per unit
```

Current valuation prioritizes current market prices. Historical valuations remain historical snapshots and must not override the current price when calculating current NAV.

### Cash-flow-neutral return

External deposits and withdrawals are not investment profit. Daily return uses a cash-flow-adjusted calculation, and the cumulative return compounds daily returns instead of adding them:

```text
Cumulative return = product(1 + each daily return) − 1
```

The P&L service also preserves externally sourced/outstanding units that did not originate from portal fund-flow requests, preventing historical valuations from silently discarding them.

### Scheduled snapshots

- The local runner exports `ENABLE_SCHEDULER=true`.
- It exports `RUN_PNL_ON_STARTUP=true`.
- Startup creates or refreshes the current idempotent accounting snapshot.
- Daily jobs continue producing holdings, flow, NAV, unit, and P&L history.
- Failures are surfaced rather than silently treated as a successful snapshot.

## Relevant implementation files

### P&L and accounting

- `Server/services/fund_accounting_service.py`
- `Server/services/pnl_service.py`
- `Server/jobs/pnl_job.py`
- `Server/routers/portfolio_routers.py`
- `Server/main.py`
- `Server/config.py`
- `Server/alembic/versions/v0.4.6_fund_portal_model.py`
- `Server/alembic/versions/v0.4.7_legacy_cost_basis.py`
- `Server/alembic/versions/v0.4.8_account_principal.py`
- `Server/alembic/versions/v0.4.9_balance_cache.py`
- `Server/alembic/versions/v0.5.0_async_order_accounting.py`
- `Server/alembic/versions/v0.5.1_manager_valuations.py`
- `Server/tests/test_accounting_integration.py`

### Frontend and browser tests

- `Client/app/dashboard/investor/page.tsx`
- `Client/app/lib/types.ts`
- `Client/tests/e2e/cross-role.spec.ts`
- `Client/tests/e2e/paynow-lifecycle.spec.ts`
- `Client/playwright.config.ts`

### Setup and hosting

- `bin/run.sh`
- `bin/setup_linux.sh`
- `bin/setup_windows_gitbash.sh`
- `bin/diagnose_run_usage.sh`
- `terraform/templates/Dockerfile.frontend`
- `.env.template`

## Verification completed

- All 11 backend accounting and settlement tests passed.
- The tests cover deposits, withdrawals, unit overdraw rejection, proportional cost basis, FIFO realized P&L, partial lots, idempotency, cash-flow-neutral return, compounded fund return, and a two-investor lifecycle.
- Frontend ESLint passed.
- TypeScript and the production Webpack build passed.
- All 33 Next.js routes built successfully.
- Playwright cross-role suite previously passed 10/10 using the production frontend.
- On the Windows laptop, the final non-mutating Playwright run passed 10/10; the opt-in demo PayNow lifecycle test also passed separately.
- The Windows PayNow test confirmed the fixed requested amount, exact recorded payment, single Operations **Verify & Complete** action, idempotent completion, and exactly one accounting-ledger entry.
- Database migration reached `v0.5.4_expose_demo_catalog`.
- NAV/assets, account principal/cost basis, and normalized-position/cache equations reconciled with zero variance.
- Live `/api/test` returned HTTP 200.
- Live `/login` returned HTTP 200.
- The startup P&L snapshot completed.
- Ctrl+C stopped the application services cleanly.

The cross-platform scripts pass Bash syntax validation. The Windows setup, production runner, Docker PostgreSQL connection, role routes, and PayNow demonstration have now been smoke-tested on the target Windows laptop.

## Recommended Windows acceptance test

After setup and startup:

1. Open `http://localhost:8000/api/test` and confirm a successful response.
2. Open `http://localhost:3000/login`.
3. Log into each role.
4. Submit an Investor subscription and confirm the dummy PayNow QR immediately shows the selected fund, fixed amount, and unique reference.
5. Select **Simulate QR Scan & Payment** and confirm Operations sees matching requested and received amounts while units remain unchanged.
6. Select **Verify & Complete** once as Operations, then confirm units, fund value, transaction history, and cash-flow-neutral P&L.
7. Perform the equivalent redemption flow; verify unit and proportional cost-basis reductions.
8. Verify Manager performance and Admin audit/fund-flow pages.
9. Run automated checks:

```bash
cd Server
./venv/Scripts/python.exe -m unittest discover -s tests -v
cd ../Client
npm run lint
NODE_OPTIONS=--max-old-space-size=2048 npm run build -- --webpack
```

Optional Playwright installation and test:

```bash
INSTALL_PLAYWRIGHT=1 FUNDINV_DB_CONTAINER=fundinv-current FUNDINV_DB_PORT=5434 bash bin/setup_windows_gitbash.sh
cd Client
npm run test:e2e
```

## Provider-backed features

- Stripe must use test keys.
- Alpaca must use paper-account credentials.
- SMTP credentials in `.env` define the sender account.
- The logged-in investor's linked real email address is the Email Summary recipient.
- Seed addresses such as `investor@fundinv.com` are not necessarily deliverable inboxes.
- Gmail SMTP should use an App Password, not the normal Google account password.
- Never paste secrets into chat or commit `.env`.

## Known caveats

- Provider-backed Stripe, Alpaca, and SMTP operations depend on valid credentials and internet access.
- School-managed Wi-Fi or Windows policy may block Docker Desktop, WSL 2, local ports, or external providers.
- The frontend production build intentionally uses Webpack because Turbopack previously caused severe CPU/RAM behavior on the Linux PC.
- `run.sh` uses `localhost` for the browser-facing frontend to keep authentication cookies aligned with the API configuration. Avoid mixing `localhost` and `127.0.0.1` in browser URLs during one session.
- Initial requests made before login may return 401 and redirect to `/login?expired=true`; authenticated requests should return 200 after a successful login.

## Prompt for the new assistant

Copy the following into the new conversation after attaching or opening this file:

> I am continuing development of FundInv from another machine. Read `WINDOWS_HANDOFF.md`, `README.md`, `docs/setup.md`, and `docs/FundInv_Windows_Local_Setup_Guide.docx` fully. Inspect the actual files before making assumptions. I am using Windows Git Bash and Docker Desktop with container `fundinv-current`, PostgreSQL host port 5434, backend port 8000, and frontend port 3000. First verify setup and `run.sh` on Windows without resetting or deleting my database. Then run backend tests, lint, production build, and—if installed—Playwright. Pay particular attention to the complete investor → operations approval → units/NAV → portfolio/P&L → manager/admin audit flow. Preserve `.env`, do not expose secrets, do not destructively replay schema or seed SQL, and report any discrepancy between this handoff and the actual workspace.
