#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[image-stack] stopping backend/frontend/image worker processes..."

patterns=(
  "uvicorn backend.app.main:app"
  "vite --host"
  "python -m http.server .*--directory frontend"
  "http.server .*--directory frontend"
  "scripts/dev/no_cache_static.py .*--directory frontend"
  "workers.image_worker"
  "scripts/dev/run_image_stack.sh"
)

for pattern in "${patterns[@]}"; do
  pids="$(pgrep -f "$pattern" || true)"
  if [[ -z "$pids" ]]; then
    continue
  fi
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    if [[ "$pid" == "$$" ]]; then
      continue
    fi
    echo "[image-stack] kill $pid ($pattern)"
    kill "$pid" >/dev/null 2>&1 || true
  done <<< "$pids"
done

sleep 0.5

for pattern in "${patterns[@]}"; do
  pids="$(pgrep -f "$pattern" || true)"
  if [[ -z "$pids" ]]; then
    continue
  fi
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    if [[ "$pid" == "$$" ]]; then
      continue
    fi
    echo "[image-stack] force kill $pid ($pattern)"
    kill -9 "$pid" >/dev/null 2>&1 || true
  done <<< "$pids"
done

echo "[image-stack] done."
