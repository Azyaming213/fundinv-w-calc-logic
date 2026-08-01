#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${1:-/tmp/fundinv-run-usage.log}"
LIMIT_KIB=$((16 * 1024 * 1024))

system_used_kib() {
    awk '/MemTotal:/ { total=$2 } /MemAvailable:/ { available=$2 } END { print total-available }' /proc/meminfo
}

snapshot() {
    local used_kib
    used_kib="$(system_used_kib)"
    {
        printf '\n===== %s | system used: %.2f GiB =====\n' "$(date --iso-8601=seconds)" "$(awk -v kib="$used_kib" 'BEGIN { print kib/1024/1024 }')"
        ps -eo pid,ppid,pgid,%cpu,%mem,rss,etime,comm,args --sort=-rss | head -n 35
    } >>"$LOG_FILE"
}

stop_group() {
    local leader_pid="$1"
    kill -TERM -- "-$leader_pid" 2>/dev/null || true
    sleep 3
    kill -KILL -- "-$leader_pid" 2>/dev/null || true
}

: >"$LOG_FILE"
printf 'Diagnostic started: %s\n' "$(date --iso-8601=seconds)" >>"$LOG_FILE"
printf 'Automatic stop threshold: 16 GiB system RAM used\n' >>"$LOG_FILE"

setsid bash "$ROOT_DIR/bin/run.sh" >>"$LOG_FILE" 2>&1 &
RUN_PID=$!
printf 'Isolated run.sh process-group leader: %s\n' "$RUN_PID" >>"$LOG_FILE"

trap 'stop_group "$RUN_PID"' INT TERM EXIT

while kill -0 "$RUN_PID" 2>/dev/null; do
    snapshot
    USED_KIB="$(system_used_kib)"
    if [ "$USED_KIB" -ge "$LIMIT_KIB" ]; then
        printf '\nSAFETY LIMIT REACHED; stopping process group %s\n' "$RUN_PID" >>"$LOG_FILE"
        stop_group "$RUN_PID"
        break
    fi
    sleep 2
done

snapshot
trap - INT TERM EXIT
printf '\nDiagnostic finished: %s\n' "$(date --iso-8601=seconds)" >>"$LOG_FILE"
printf '%s\n' "$LOG_FILE"
