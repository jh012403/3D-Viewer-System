#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
AI3D_RUNTIME_CACHE_ROOT="${AI3D_RUNTIME_CACHE_ROOT:-/tmp/ai3d_cache}"
export AI3D_RUNTIME_CACHE_ROOT
export NUMBA_CACHE_DIR="${NUMBA_CACHE_DIR:-${AI3D_RUNTIME_CACHE_ROOT}/numba}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-${AI3D_RUNTIME_CACHE_ROOT}/xdg}"
export HOME="${HOME:-/tmp}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-max_split_size_mb:128,garbage_collection_threshold:0.8}"
export CUDA_MODULE_LOADING="${CUDA_MODULE_LOADING:-LAZY}"
mkdir -p "$AI3D_RUNTIME_CACHE_ROOT" "$NUMBA_CACHE_DIR" "$XDG_CACHE_HOME"

python -m workers.image_worker
