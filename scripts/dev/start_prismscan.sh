#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
exec bash scripts/dev/run_image_stack.sh "$@"
