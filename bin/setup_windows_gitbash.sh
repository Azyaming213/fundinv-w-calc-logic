#!/usr/bin/env bash

# Run this from Git Bash on Windows. Docker Desktop must already be running.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$ROOT_DIR/Server"
CLIENT_DIR="$ROOT_DIR/Client"
CONTAINER_NAME="${FUNDINV_DB_CONTAINER:-fundinv-current}"
DB_USER="${FUNDINV_DB_USER:-postgres}"
DB_PASSWORD="${FUNDINV_DB_PASSWORD:-postgres}"
DB_NAME="${FUNDINV_DB_NAME:-fundinv}"
DB_PORT="${FUNDINV_DB_PORT:-5434}"

# Prevent Git Bash from rewriting Linux paths intended for commands inside
# the PostgreSQL container, without breaking Windows paths passed to Python.
docker_cmd() { MSYS_NO_PATHCONV=1 docker "$@"; }

for command_name in docker node npm curl; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "Missing prerequisite: $command_name"
        echo "Install Docker Desktop, Git for Windows, Python 3.12+ and Node.js 20+, then reopen Git Bash."
        exit 1
    fi
done

if command -v py >/dev/null 2>&1; then
    system_python() { py -3 "$@"; }
elif command -v python >/dev/null 2>&1; then
    system_python() { python "$@"; }
else
    echo "Python was not found. Install Python 3.12+ and enable 'Add python.exe to PATH'."
    exit 1
fi

if ! docker_cmd info >/dev/null 2>&1; then
    echo "Docker Desktop is unavailable. Start Docker Desktop and wait until it is ready."
    exit 1
fi

echo "[1/6] Preparing environment configuration"
if [[ ! -f "$ROOT_DIR/.env" ]]; then
    cp "$ROOT_DIR/.env.template" "$ROOT_DIR/.env"
    secret="$(system_python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    system_python - "$ROOT_DIR/.env" "$secret" "$DB_USER" "$DB_PASSWORD" "$DB_NAME" "$DB_PORT" <<'PY'
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
    echo "Created .env with a random local JWT secret."
else
    echo ".env already exists; preserving it."
    echo "Confirm its DATABASE_URL uses host port $DB_PORT and database $DB_NAME."
fi

echo "[2/6] Preparing PostgreSQL 16 in Docker Desktop"
if docker_cmd ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
    docker_cmd start "$CONTAINER_NAME" >/dev/null
else
    docker_cmd run --name "$CONTAINER_NAME" \
        -e "POSTGRES_USER=$DB_USER" \
        -e "POSTGRES_PASSWORD=$DB_PASSWORD" \
        -e "POSTGRES_DB=$DB_NAME" \
        -p "$DB_PORT:5432" \
        -d postgres:16 >/dev/null
fi

for _ in {1..60}; do
    if docker_cmd exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then break; fi
    sleep 1
done
if ! docker_cmd exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    echo "PostgreSQL did not become ready. Run: docker logs $CONTAINER_NAME"
    exit 1
fi

schema_exists="$(docker_cmd exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -Atc "SELECT CASE WHEN to_regclass('fundinv_auth.users') IS NULL THEN 'no' ELSE 'yes' END;")"
if [[ "$schema_exists" == "no" ]]; then
    docker_cmd exec -i "$CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/config/table/v0.0.1_init_schema.sql"
    docker_cmd exec -i "$CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/config/scripts/v0.0.1_seed_data.sql"
    echo "Initialized and seeded a new FundInv database."
else
    echo "FundInv schema already exists; preserving its data."
fi

echo "[3/6] Installing backend dependencies"
if [[ ! -x "$SERVER_DIR/venv/Scripts/python.exe" ]]; then
    system_python -m venv "$SERVER_DIR/venv"
fi
BACKEND_PYTHON="$SERVER_DIR/venv/Scripts/python.exe"
"$BACKEND_PYTHON" -m pip install --upgrade pip
"$BACKEND_PYTHON" -m pip install -r "$SERVER_DIR/requirements.txt"

echo "[4/6] Applying database migrations"
(cd "$SERVER_DIR" && ./venv/Scripts/python.exe -m alembic upgrade head)

echo "[5/6] Installing frontend dependencies"
(cd "$CLIENT_DIR" && npm ci)

if [[ "${INSTALL_PLAYWRIGHT:-0}" == "1" ]]; then
    (cd "$CLIENT_DIR" && npx playwright install chromium)
fi

echo "[6/6] Verifying the setup"
(cd "$SERVER_DIR" && ./venv/Scripts/python.exe -m unittest discover -s tests -v)
(cd "$CLIENT_DIR" && npm run lint)
(cd "$CLIENT_DIR" && NODE_OPTIONS=--max-old-space-size=2048 npm run build -- --webpack)

cat <<'EOF'

FundInv setup completed for Windows Git Bash.

From the fundinv-solo directory, start both services with:
  bash bin/run.sh

Open http://localhost:3000 and http://localhost:8000/docs.
Manual fund-flow accounting works without Stripe. Stripe settlement, Alpaca paper orders,
and email delivery require their corresponding credentials in .env.
EOF
