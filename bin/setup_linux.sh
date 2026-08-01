#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$ROOT_DIR/Server"
CLIENT_DIR="$ROOT_DIR/Client"
CONTAINER_NAME="${FUNDINV_DB_CONTAINER:-fundinv}"
DB_USER="${FUNDINV_DB_USER:-postgres}"
DB_PASSWORD="${FUNDINV_DB_PASSWORD:-postgres}"
DB_NAME="${FUNDINV_DB_NAME:-fundinv}"
DB_PORT="${FUNDINV_DB_PORT:-5432}"

required=(docker python3 node npm curl)
missing=()
for command_name in "${required[@]}"; do
    command -v "$command_name" >/dev/null 2>&1 || missing+=("$command_name")
done
if ((${#missing[@]})); then
    echo "Missing prerequisites: ${missing[*]}"
    echo "Install Docker Engine/Desktop, Python 3.12+, Node.js 20+ and curl, then rerun this script."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but its daemon is unavailable. Start Docker and rerun."
    exit 1
fi

echo "[1/6] Preparing environment configuration"
if [[ ! -f "$ROOT_DIR/.env" ]]; then
    cp "$ROOT_DIR/.env.template" "$ROOT_DIR/.env"
    secret="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
    python3 - "$ROOT_DIR/.env" "$secret" "$DB_USER" "$DB_PASSWORD" "$DB_NAME" "$DB_PORT" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
content = p.read_text().replace(
    "your_super_secret_jwt_signing_key_change_this_in_production_environments_only",
    sys.argv[2],
)
lines = content.splitlines()
database_url = f"postgresql://{sys.argv[3]}:{sys.argv[4]}@localhost:{sys.argv[6]}/{sys.argv[5]}"
lines = [f"DATABASE_URL={database_url}" if line.startswith("DATABASE_URL=") else line for line in lines]
p.write_text("\n".join(lines) + "\n")
PY
    echo "Created .env with a random local JWT secret. Add Stripe, Alpaca and SMTP credentials when required."
else
    echo ".env already exists; preserving it."
    echo "Confirm its DATABASE_URL uses host port $DB_PORT and database $DB_NAME."
fi

echo "[2/6] Preparing PostgreSQL 16"
if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    docker start "$CONTAINER_NAME" >/dev/null
    echo "Using existing container: $CONTAINER_NAME"
else
    docker run --name "$CONTAINER_NAME" \
        -e "POSTGRES_USER=$DB_USER" \
        -e "POSTGRES_PASSWORD=$DB_PASSWORD" \
        -e "POSTGRES_DB=$DB_NAME" \
        -p "$DB_PORT:5432" \
        -d postgres:16 >/dev/null
    echo "Created container: $CONTAINER_NAME"
fi

for _ in {1..60}; do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
if ! docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    echo "PostgreSQL did not become ready. Check: docker logs $CONTAINER_NAME"
    exit 1
fi

schema_exists="$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -Atc "SELECT CASE WHEN to_regclass('fundinv_auth.users') IS NULL THEN 'no' ELSE 'yes' END;")"
if [[ "$schema_exists" == "no" ]]; then
    docker exec -i "$CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/config/table/v0.0.1_init_schema.sql"
    docker exec -i "$CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/config/scripts/v0.0.1_seed_data.sql"
    echo "Initialized and seeded a new FundInv database."
else
    echo "FundInv schema already exists; no destructive schema/seed replay performed."
fi

echo "[3/6] Installing backend dependencies"
if [[ ! -x "$SERVER_DIR/venv/bin/python" ]]; then
    python3 -m venv "$SERVER_DIR/venv"
fi
"$SERVER_DIR/venv/bin/python" -m pip install --upgrade pip
"$SERVER_DIR/venv/bin/python" -m pip install -r "$SERVER_DIR/requirements.txt"

echo "[4/6] Applying database migrations"
(cd "$SERVER_DIR" && venv/bin/alembic upgrade head)

echo "[5/6] Installing frontend dependencies"
(cd "$CLIENT_DIR" && npm ci)

if [[ "${INSTALL_PLAYWRIGHT:-0}" == "1" ]]; then
    echo "Installing Playwright Chromium because INSTALL_PLAYWRIGHT=1"
    (cd "$CLIENT_DIR" && npx playwright install chromium)
fi

echo "[6/6] Verifying the setup"
(cd "$SERVER_DIR" && venv/bin/python -m unittest discover -s tests -v)
(cd "$CLIENT_DIR" && npm run lint)
(cd "$CLIENT_DIR" && NODE_OPTIONS=--max-old-space-size=2048 npm run build -- --webpack)

cat <<EOF

FundInv setup completed.

Start the application with:
  bash bin/run.sh

Then open:
  Frontend: http://localhost:3000
  API docs: http://localhost:8000/docs

Seed accounts are documented in README.md.
Manual fund-flow accounting works without Stripe. Stripe settlement, Alpaca paper orders,
and email delivery require their corresponding credentials in .env.
EOF
