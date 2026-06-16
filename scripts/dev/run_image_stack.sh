#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="${AI3D_DEV_LOG_DIR:-$ROOT_DIR/storage/logs/dev}"
mkdir -p "$LOG_DIR"

CONDA_ENV="${AI3D_CONDA_ENV:-ai3d-mvp}"
USE_CONDA="${AI3D_USE_CONDA:-auto}" # auto | always | never
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
FRONTEND_SERVER="${AI3D_FRONTEND_SERVER:-static}" # static | vite

declare -a PIDS=()
declare -A PROC_NAME=()
declare -A PROC_LOG=()

port_in_use() {
  local port="$1"
  ss -ltn "sport = :$port" | awk 'NR > 1 { found = 1 } END { exit found ? 0 : 1 }'
}

describe_port_owner() {
  local port="$1"
  ss -ltnp "sport = :$port" 2>/dev/null | sed -n '2,4p' || true
}

preflight_ports() {
  local backend_port="${BACKEND_PORT:-8000}"
  local frontend_port="$FRONTEND_PORT"
  local busy=0

  if port_in_use "$backend_port"; then
    echo "[image-stack] ERROR: backend port $backend_port is already in use." >&2
    describe_port_owner "$backend_port" >&2
    busy=1
  fi
  if port_in_use "$frontend_port"; then
    echo "[image-stack] ERROR: frontend port $frontend_port is already in use." >&2
    describe_port_owner "$frontend_port" >&2
    busy=1
  fi
  if [[ "$busy" == "1" ]]; then
    echo "[image-stack] stop the existing process first, or change BACKEND_PORT/FRONTEND_PORT." >&2
    exit 1
  fi
}

resolve_cmd() {
  local __result_var="$1"
  shift
  local base_cmd=("$@")

  if [[ "$USE_CONDA" == "never" ]]; then
    eval "$__result_var=(\"\${base_cmd[@]}\")"
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    if conda env list | awk '{print $1}' | grep -qx "$CONDA_ENV"; then
      eval "$__result_var=(conda run -n \"$CONDA_ENV\" \"\${base_cmd[@]}\")"
      return 0
    fi
  fi

  if [[ "$USE_CONDA" == "always" ]]; then
    echo "[image-stack] ERROR: conda env '$CONDA_ENV' not found." >&2
    exit 1
  fi

  eval "$__result_var=(\"\${base_cmd[@]}\")"
}

start_proc() {
  local name="$1"
  local log_file="$2"
  shift 2
  setsid "$@" >"$log_file" 2>&1 &
  local pid=$!
  PIDS+=("$pid")
  PROC_NAME["$pid"]="$name"
  PROC_LOG["$pid"]="$log_file"
  echo "[image-stack] started $name (pid=$pid, log=$log_file)"
}

cleanup() {
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -- "-$pid" >/dev/null 2>&1 || kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  sleep 0.3
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 -- "-$pid" >/dev/null 2>&1 || kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

preflight_ports

resolve_cmd BACKEND_CMD bash scripts/dev/run_backend.sh
resolve_cmd IMAGE_CMD bash scripts/dev/run_image_worker.sh
if [[ "$FRONTEND_SERVER" == "vite" ]]; then
  resolve_cmd FRONTEND_CMD bash scripts/dev/run_frontend.sh
else
  resolve_cmd FRONTEND_CMD python scripts/dev/no_cache_static.py "$FRONTEND_PORT" --bind 0.0.0.0 --directory frontend
fi

start_proc "backend" "$LOG_DIR/backend.log" "${BACKEND_CMD[@]}"
start_proc "image_worker" "$LOG_DIR/image_worker.log" "${IMAGE_CMD[@]}"
start_proc "frontend_${FRONTEND_SERVER}" "$LOG_DIR/frontend.log" "${FRONTEND_CMD[@]}"

echo
echo "[image-stack] running"
echo "[image-stack] backend:  http://127.0.0.1:${BACKEND_PORT:-8000}"
echo "[image-stack] app:      http://127.0.0.1:${FRONTEND_PORT}/prismscan-v2.html?mode=image"
echo "[image-stack] backend app fallback: http://127.0.0.1:${BACKEND_PORT:-8000}/prismscan-v2.html?mode=image"
echo "[image-stack] logs:     $LOG_DIR"
echo "[image-stack] stop: Ctrl+C"
echo

set +e
wait -n
exit_code=$?
set -e

for pid in "${PIDS[@]}"; do
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "[image-stack] process exited: ${PROC_NAME[$pid]} (pid=$pid)"
    echo "[image-stack] log: ${PROC_LOG[$pid]}"
  fi
done

exit "$exit_code"
