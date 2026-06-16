#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SAM3_ENV_NAME="${SAM3_ENV_NAME:-sam3}"
SAM3_REPO_DIR="${SAM3_REPO_DIR:-${ROOT_DIR}/.runtime/sam3}"
SAM3_MODEL_ID="${SAM3_MODEL_ID:-facebook/sam3}"
SAM3_DEVICE="${SAM3_DEVICE:-cuda}"
SAM3_CONFIDENCE_THRESHOLD="${SAM3_CONFIDENCE_THRESHOLD:-0.5}"
SAM3_MERGE_MODE="${SAM3_MERGE_MODE:-best}"

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 /path/to/image.jpg \"text prompt\" [output_dir]" >&2
  echo "Example: $0 storage/uploads/job_000001/input.jpg dinosaur" >&2
  exit 2
fi

INPUT_IMAGE="$1"
TEXT_PROMPT="$2"
OUTPUT_DIR="${3:-${ROOT_DIR}/storage/temp/sam3_probe_$(date +%Y%m%d_%H%M%S)}"
CANDIDATES_DIR="${OUTPUT_DIR}/candidates"

mkdir -p "${OUTPUT_DIR}" "${CANDIDATES_DIR}"

PYTHONPATH="${ROOT_DIR}${PYTHONPATH:+:${PYTHONPATH}}" conda run -n "${SAM3_ENV_NAME}" python \
  "${ROOT_DIR}/pipelines/image_to_3d/runtime_helpers/sam3_extract.py" \
  --input-image "${INPUT_IMAGE}" \
  --output-dir "${OUTPUT_DIR}" \
  --sam3-repo-dir "${SAM3_REPO_DIR}" \
  --model-id "${SAM3_MODEL_ID}" \
  --device "${SAM3_DEVICE}" \
  --text-prompt "${TEXT_PROMPT}" \
  --confidence-threshold "${SAM3_CONFIDENCE_THRESHOLD}" \
  --merge-mode "${SAM3_MERGE_MODE}" \
  --dump-candidates-dir "${CANDIDATES_DIR}" \
  --max-candidates 3

echo "SAM3 probe output:"
echo "  ${OUTPUT_DIR}"
echo "Preview candidate PNGs:"
find "${CANDIDATES_DIR}" -maxdepth 2 -name segmented_preview.png -print
