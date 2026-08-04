# FundInv Setup Guide

## Prerequisites

- Docker Engine/Desktop with PostgreSQL container support
- Python 3.12 or newer
- Node.js 20 or newer with npm
- Git Bash on Windows
- `curl`

Stripe, Alpaca, and SMTP credentials are optional for the core local portal.
They are needed only for Stripe-mode settlement, external paper orders, and
real email delivery respectively. Manual fund-flow settlement is the default.

## Linux one-time setup

From the project root:

```bash
bash bin/setup_linux.sh
```

Defaults: container `fundinv`, host DB port `5432`, database/user/password
`fundinv`/`postgres`/`postgres`.

To avoid an existing database port or container:

```bash
FUNDINV_DB_CONTAINER=fundinv-new FUNDINV_DB_PORT=5434 bash bin/setup_linux.sh
```

## Windows Git Bash one-time setup

Start Docker Desktop, open Git Bash in the extracted project, then run:

```bash
bash bin/setup_windows_gitbash.sh
```

Windows defaults are intentionally `fundinv-current` and host port `5434`, so
older projects on `5432` or `5433` do not conflict. The container still listens
on its internal port `5432`.

The setup scripts create `.env` only when it is absent, generate a random JWT
secret, initialize and seed only a new database, install dependencies, apply all
Alembic migrations, and run backend tests, lint, and a production Webpack build.
They preserve an existing `.env` and database.

## Normal startup

Linux:

```bash
bash bin/run.sh
```

Windows Git Bash:

```bash
bash bin/run.sh
```

`run.sh` automatically uses the OS-specific defaults above. If setup used
custom values, pass the same variables to startup. It refuses duplicate runner
instances and occupied ports, applies pending migrations, caps Node at 2 GB,
builds with stable Webpack, starts the standalone production frontend, and
stops both services on Ctrl+C.

Open:

- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/test`

## Seed logins

| Role | Email | Password |
|---|---|---|
| Admin | `admin@fundinv.com` | `admin123` |
| Manager | `manager@fundinv.com` | `admin123` |
| Operations | `operations@fundinv.com` | `admin123` |
| Investor | `investor@fundinv.com` | `investor123` |
| Investor | `alice@example.com` | `investor123` |

These passwords are demonstration-only.

## Environment essentials

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fundinv
FRONTEND_URL=http://localhost:3000
FUND_FLOW_PROVIDER=paynow_demo
PAYNOW_DEMO_RECIPIENT_NAME=FundInv Demo
PAYNOW_DEMO_UEN=T00FUNDINV
MAX_SUBSCRIPTION_AMOUNT=1000000.00
```

On default Windows setup, the database port in `DATABASE_URL` is `5434`.

`paynow_demo` shows a dummy fixed-amount QR and never moves real money. Use
`FUND_FLOW_PROVIDER=manual` for independently verified external transfers, or
`stripe` only with valid Stripe test keys and a signed webhook forwarder. Never
put `.env` in Git or a portable ZIP.

## Database safety and migrations

Current migration head: `v0.5.4_expose_demo_catalog`.

- Base schema/seed SQL runs only when `fundinv_auth.users` does not exist.
- `run.sh` applies pending Alembic migrations; it does not reset data.
- Do not manually replay seed SQL on an existing database.
- Back up a real database before upgrades.

## Verification commands

```bash
cd Server
venv/bin/python -m unittest discover -s tests -p 'test_*.py'

cd ../Client
npm run lint
npm run build -- --webpack
npm run test:e2e
```

On Windows, use `Server/venv/Scripts/python.exe` for the backend command.

## Troubleshooting

- `Another FundInv run.sh instance`: stop the older terminal with Ctrl+C. If it
  is truly gone, remove only the stale lock file in your temporary directory.
- Port conflict: reuse the same `FUNDINV_DB_PORT` and container values used at
  setup, or stop the conflicting service.
- `401` immediately after login: always open `http://localhost:3000`; do not mix
  `localhost` and `127.0.0.1`, because the HTTP-only session cookie is host-bound.
- High CPU during startup: one short production build is expected. Sustained
  growth usually means duplicate runners; `run.sh` now blocks them.
- Turbopack sandbox/binding errors: normal startup uses Webpack and is not
  affected. Turbopack itself also builds successfully in an unrestricted host
  environment.
