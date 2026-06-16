#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_NAME="${1:-ai3d-mvp}"
BLENDER_VERSION="${BLENDER_VERSION:-4.3.2}"
BLENDER_RELEASE="${BLENDER_RELEASE:-4.3}"
BLENDER_ARCHIVE="blender-${BLENDER_VERSION}-linux-x64.tar.xz"
BLENDER_URL="${BLENDER_URL:-https://download.blender.org/release/Blender${BLENDER_RELEASE}/${BLENDER_ARCHIVE}}"
INSTALL_ROOT="${BLENDER_INSTALL_ROOT:-$ROOT_DIR/.runtime/blender}"
INSTALL_DIR="$INSTALL_ROOT/blender-${BLENDER_VERSION}-linux-x64"
BLENDER_BIN="$INSTALL_DIR/blender"
ARCHIVE_PATH="$INSTALL_ROOT/$BLENDER_ARCHIVE"

mkdir -p "$INSTALL_ROOT"

if [[ ! -x "$BLENDER_BIN" ]]; then
  echo "[fbx-export] downloading Blender ${BLENDER_VERSION}"
  echo "[fbx-export] ${BLENDER_URL}"
  curl -L --fail --progress-bar "$BLENDER_URL" -o "$ARCHIVE_PATH"

  echo "[fbx-export] extracting"
  rm -rf "$INSTALL_DIR"
  tar -xJf "$ARCHIVE_PATH" -C "$INSTALL_ROOT"
fi

if [[ ! -x "$BLENDER_BIN" ]]; then
  echo "[fbx-export] ERROR: Blender binary was not found after install: $BLENDER_BIN" >&2
  exit 1
fi

CONDA_PREFIX_PATH=""
if command -v conda >/dev/null 2>&1; then
  CONDA_PREFIX_PATH="$(conda run -n "$ENV_NAME" python -c 'import sys; print(sys.prefix)' 2>/dev/null || true)"
fi

if [[ -n "$CONDA_PREFIX_PATH" && -d "$CONDA_PREFIX_PATH/bin" ]]; then
  LINK_PATH="$CONDA_PREFIX_PATH/bin/blender"
  if [[ -e "$LINK_PATH" && ! -L "$LINK_PATH" ]]; then
    echo "[fbx-export] existing blender binary left untouched: $LINK_PATH"
  else
    ln -sfn "$BLENDER_BIN" "$LINK_PATH"
    echo "[fbx-export] linked into ${ENV_NAME}: $LINK_PATH"
  fi
fi

touch .env
if grep -q '^BLENDER_BIN=' .env; then
  sed -i "s|^BLENDER_BIN=.*|BLENDER_BIN=$BLENDER_BIN|" .env
else
  printf '\nBLENDER_BIN=%s\n' "$BLENDER_BIN" >> .env
fi

echo "[fbx-export] ready"
echo "[fbx-export] BLENDER_BIN=$BLENDER_BIN"
echo "[fbx-export] If the backend was already running outside ${ENV_NAME}, restart it."
