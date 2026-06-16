#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

AI3D_RUNTIME_CACHE_ROOT="${AI3D_RUNTIME_CACHE_ROOT:-/tmp/ai3d_cache}"
export AI3D_RUNTIME_CACHE_ROOT
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-${AI3D_RUNTIME_CACHE_ROOT}/numba}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-${AI3D_RUNTIME_CACHE_ROOT}/xdg}"
export HOME="${HOME:-/tmp}"
mkdir -p "$AI3D_RUNTIME_CACHE_ROOT" "$NUMBA_CACHE_DIR" "$XDG_CACHE_HOME"

uvicorn backend.app.main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}" --reload
