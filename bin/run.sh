#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BACKEND_DIR="$ROOT_DIR/Server"
FRONTEND_DIR="$ROOT_DIR/Client"

case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) PLATFORM="windows-git-bash" ;;
    Linux*) PLATFORM="linux" ;;
    *) PLATFORM="unix" ;;
esac

if [ "$PLATFORM" = "windows-git-bash" ]; then
    POSTGRES_CONTAINER="${FUNDINV_DB_CONTAINER:-fundinv-current}"
    DB_PORT="${FUNDINV_DB_PORT:-5434}"
else
    POSTGRES_CONTAINER="${FUNDINV_DB_CONTAINER:-fundinv}"
    DB_PORT="${FUNDINV_DB_PORT:-5432}"
fi

if [ "$PLATFORM" = "windows-git-bash" ]; then
    BACKEND_PYTHON="$BACKEND_DIR/venv/Scripts/python.exe"
    SETUP_SCRIPT="bin/setup_windows_gitbash.sh"
else
    BACKEND_PYTHON="$BACKEND_DIR/venv/bin/python"
    SETUP_SCRIPT="bin/setup_linux.sh"
fi

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
# Keep the browser origin aligned with API_BASE (http://localhost:8000).
# Mixing 127.0.0.1 and localhost prevents SameSite session cookies from being
# sent on authenticated API requests.
FRONTEND_HOST="${FRONTEND_HOST:-localhost}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
NODE_MEMORY_MB="${NODE_MEMORY_MB:-2048}"
BACKEND_RELOAD="${BACKEND_RELOAD:-0}"
FRONTEND_MODE="${FRONTEND_MODE:-production}"

BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}/api/test"

BACKEND_PID=""
FRONTEND_PID=""
CLEANUP_DONE=0

port_is_open() {
    local port="$1"
    if command -v timeout >/dev/null 2>&1; then
        timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/$port" >/dev/null 2>&1
    else
        curl --connect-timeout 1 --silent "telnet://127.0.0.1:$port" </dev/null >/dev/null 2>&1
    fi
}

docker_cmd() {
    if [ "$PLATFORM" = "windows-git-bash" ]; then
        MSYS_NO_PATHCONV=1 docker "$@"
    else
        docker "$@"
    fi
}

stop_process_tree() {
    local pid="${1:-}"
    local child
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        return
    fi

    # Stop every descendant before its parent so compiler/server workers do
    # not survive a Ctrl+C or terminal close.
    if command -v pgrep >/dev/null 2>&1; then
        while read -r child; do
            [ -n "$child" ] && stop_process_tree "$child"
        done < <(pgrep -P "$pid" 2>/dev/null || true)
    fi
    kill -TERM "$pid" 2>/dev/null || true
}

cleanup() {
    if [ "$CLEANUP_DONE" -eq 1 ]; then
        return
    fi
    CLEANUP_DONE=1

    echo ""
    echo "Stopping dev services..."

    stop_process_tree "$FRONTEND_PID"
    stop_process_tree "$BACKEND_PID"

    wait "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true

    echo "Stopped."
}

trap cleanup EXIT INT TERM

# Prevent accidental duplicate dev stacks, which can create several compiler
# and file-watcher processes and consume large amounts of memory.
if command -v flock >/dev/null 2>&1; then
    exec 9>"${TMPDIR:-/tmp}/fundinv-solo-run.lock"
    if ! flock -n 9; then
        echo "ERROR: Another FundInv run.sh instance is already running."
        exit 1
    fi
fi

echo "========================================"
echo " Server Solo Dev Runner"
echo "========================================"

echo ""
echo "Project root: $ROOT_DIR"
echo "Backend dir:  $BACKEND_DIR"
echo "Frontend dir: $FRONTEND_DIR"
echo "Platform:     $PLATFORM"
echo "Node memory cap: ${NODE_MEMORY_MB} MB"
echo "Frontend mode: $FRONTEND_MODE"

if [ ! -d "$BACKEND_DIR" ]; then
    echo "ERROR: Backend directory not found: $BACKEND_DIR"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "ERROR: Frontend directory not found: $FRONTEND_DIR"
    exit 1
fi

if port_is_open "$BACKEND_PORT"; then
    echo "ERROR: Backend port $BACKEND_PORT is already in use."
    echo "Stop the existing service before running this script again."
    exit 1
fi

if port_is_open "$FRONTEND_PORT"; then
    echo "ERROR: Frontend port $FRONTEND_PORT is already in use."
    echo "Stop the existing service before running this script again."
    exit 1
fi

echo ""
echo "Checking PostgreSQL..."

# Try Docker first; fall back to native PostgreSQL if Docker is unavailable.
if docker_cmd info >/dev/null 2>&1; then
    if docker_cmd ps -a --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        docker_cmd start "$POSTGRES_CONTAINER" >/dev/null
        echo "PostgreSQL container '$POSTGRES_CONTAINER' is running."
    else
        echo "PostgreSQL container '$POSTGRES_CONTAINER' not found."
        echo ""
        echo "Create it with:"
        echo "docker run --name fundinv \\"
        echo "  -e POSTGRES_USER=postgres \\"
        echo "  -e POSTGRES_PASSWORD=postgres \\"
        echo "  -e POSTGRES_DB=fundinv \\"
        echo "  -p ${DB_PORT}:5432 \\"
        echo "  -d postgres:16"
        exit 1
    fi
else
    echo "Docker daemon not reachable — checking for native PostgreSQL..."
    if command -v pg_isready &>/dev/null; then
        if pg_isready -h 127.0.0.1 -p "$DB_PORT" >/dev/null 2>&1; then
            echo "PostgreSQL is running on 127.0.0.1:${DB_PORT}."
        else
            echo "WARNING: PostgreSQL does not appear to be running on 127.0.0.1:${DB_PORT}."
            exit 1
        fi
    else
        if port_is_open "$DB_PORT"; then
            echo "PostgreSQL appears to be running on 127.0.0.1:${DB_PORT} (port open)."
        else
            echo "WARNING: Cannot reach PostgreSQL on 127.0.0.1:${DB_PORT}."
            exit 1
        fi
    fi
fi

echo ""
echo "Preparing FastAPI backend..."

cd "$BACKEND_DIR"

if [ ! -x "$BACKEND_PYTHON" ]; then
    echo "ERROR: venv Python not found at:"
    echo "$BACKEND_PYTHON"
    echo ""
    echo "Create it with:"
    echo "Run: bash $SETUP_SCRIPT"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
    echo "ERROR: requirements.txt not found at:"
    echo "$BACKEND_DIR/requirements.txt"
    exit 1
fi

echo ""
echo "Using backend Python:"
"$BACKEND_PYTHON" -c "import sys; print(sys.executable)"

echo ""
echo "Checking uvicorn..."
if ! "$BACKEND_PYTHON" -m uvicorn --version; then
    echo "ERROR: Backend dependencies are not installed."
    echo "Run: bash $SETUP_SCRIPT"
    exit 1
fi

echo ""
echo "Applying pending database migrations..."
"$BACKEND_PYTHON" -m alembic -c "$BACKEND_DIR/alembic.ini" upgrade head

# The challenge requires a reliable daily P&L ingestion pipeline. The local
# runner enables maintenance/accounting jobs and creates or refreshes today's
# idempotent snapshot on startup. Automated trading remains separately disabled.
export ENABLE_SCHEDULER="${ENABLE_SCHEDULER:-true}"
export RUN_PNL_ON_STARTUP="${RUN_PNL_ON_STARTUP:-true}"
export ENABLE_AUTOMATED_TRADING="${ENABLE_AUTOMATED_TRADING:-false}"

echo ""
echo "Starting FastAPI backend..."

UVICORN_ARGS=(main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT")
if [ "$BACKEND_RELOAD" = "1" ]; then
    echo "Backend reload explicitly enabled."
    UVICORN_ARGS+=(--reload --reload-dir "$BACKEND_DIR")
fi

"$BACKEND_PYTHON" -m uvicorn "${UVICORN_ARGS[@]}" &
BACKEND_PID=$!

echo "Backend started. PID: $BACKEND_PID"

echo ""
echo "Waiting for backend:"
echo "$BACKEND_URL"

WAIT_ATTEMPTS=0
until curl --fail --silent --show-error "$BACKEND_URL" >/dev/null 2>&1; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "ERROR: Backend exited before becoming ready."
        exit 1
    fi
    WAIT_ATTEMPTS=$((WAIT_ATTEMPTS + 1))
    if [ "$WAIT_ATTEMPTS" -ge 60 ]; then
        echo "ERROR: Backend did not become ready within 60 seconds."
        exit 1
    fi
    sleep 1
done

echo "Backend is ready."

echo ""
echo "Starting React frontend..."

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo "ERROR: Frontend dependencies are not installed."
    echo "Run: bash $SETUP_SCRIPT"
    exit 1
fi

export NEXT_TELEMETRY_DISABLED=1
export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=${NODE_MEMORY_MB}"

echo "Frontend URL: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
if [ "$FRONTEND_MODE" = "development" ]; then
    echo "Starting the opt-in Webpack development server..."
    npm run dev -- --webpack --hostname "$FRONTEND_HOST" --port "$FRONTEND_PORT" &
else
    echo "Building the production frontend with Webpack..."
    npm run build -- --webpack
    # output: "standalone" is enabled for Docker and local production. Next.js
    # intentionally does not copy static/public assets into that folder.
    mkdir -p .next/standalone/.next
    cp -R .next/static .next/standalone/.next/
    if [ -d public ]; then
        cp -R public .next/standalone/
    fi
    echo "Starting the standalone production frontend..."
    HOSTNAME="$FRONTEND_HOST" PORT="$FRONTEND_PORT" node .next/standalone/server.js &
fi
FRONTEND_PID=$!
wait "$FRONTEND_PID"
