#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BACKEND_DIR="$ROOT_DIR/Server"
FRONTEND_DIR="$ROOT_DIR/Client"

POSTGRES_CONTAINER="fundinv"
BACKEND_URL="http://127.0.0.1:8000/api/test"
BACKEND_PYTHON="$BACKEND_DIR/venv/bin/python"

BACKEND_PID=""

cleanup() {
    echo ""
    echo "Stopping dev services..."

    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi

    jobs -p | xargs -r kill 2>/dev/null || true

    echo "Stopped."
}

trap cleanup EXIT INT TERM

echo "========================================"
echo " Server Solo Dev Runner"
echo "========================================"

echo ""
echo "Project root: $ROOT_DIR"
echo "Backend dir:  $BACKEND_DIR"
echo "Frontend dir: $FRONTEND_DIR"

if [ ! -d "$BACKEND_DIR" ]; then
    echo "ERROR: Backend directory not found: $BACKEND_DIR"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "ERROR: Frontend directory not found: $FRONTEND_DIR"
    exit 1
fi

echo ""
echo "Checking PostgreSQL..."

# Try Docker first; fall back to native PostgreSQL if Docker is unavailable.
if docker info >/dev/null 2>&1; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        docker start "$POSTGRES_CONTAINER" >/dev/null
        echo "PostgreSQL container '$POSTGRES_CONTAINER' is running."
    else
        echo "PostgreSQL container '$POSTGRES_CONTAINER' not found."
        echo ""
        echo "Create it with:"
        echo "docker run --name fundinv \\"
        echo "  -e POSTGRES_USER=admin \\"
        echo "  -e POSTGRES_PASSWORD=admin \\"
        echo "  -e POSTGRES_DB=fundinv \\"
        echo "  -p 5432:5432 \\"
        echo "  -d postgres:16"
        exit 1
    fi
else
    echo "Docker daemon not reachable — checking for native PostgreSQL..."
    if command -v pg_isready &>/dev/null; then
        if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
            echo "PostgreSQL is running on 127.0.0.1:5432."
        else
            echo "WARNING: PostgreSQL does not appear to be running on 127.0.0.1:5432."
            exit 1
        fi
    else
        if timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/5432' 2>/dev/null; then
            echo "PostgreSQL appears to be running on 127.0.0.1:5432 (port open)."
        else
            echo "WARNING: Cannot reach PostgreSQL on 127.0.0.1:5432."
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
    echo "cd Server && python -m venv venv"
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
echo "Installing backend requirements..."
"$BACKEND_PYTHON" -m pip install --upgrade pip
"$BACKEND_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt"

echo ""
echo "Checking uvicorn..."
"$BACKEND_PYTHON" -m uvicorn --version

echo ""
echo "Starting FastAPI backend..."

"$BACKEND_PYTHON" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Backend started. PID: $BACKEND_PID"

echo ""
echo "Waiting for backend:"
echo "$BACKEND_URL"

until curl -s "$BACKEND_URL" >/dev/null; do
    sleep 1
done

echo "Backend is ready."

echo ""
echo "Starting React frontend..."

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo "node_modules not found. Running npm install..."
    npm install
fi

npm run dev

