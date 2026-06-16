#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SAM3_ENV_NAME="${SAM3_ENV_NAME:-sam3}"
SAM3_REPO_DIR="${SAM3_REPO_DIR:-${ROOT_DIR}/.runtime/sam3}"
SAM3_REPO_URL="${SAM3_REPO_URL:-https://github.com/facebookresearch/sam3.git}"
SAM3_TORCH_INDEX_URL="${SAM3_TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"
SAM3_TORCH_PACKAGES="${SAM3_TORCH_PACKAGES:-torch==2.10.0 torchvision}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but was not found on PATH." >&2
  exit 1
fi

if ! conda env list | awk '{print $1}' | grep -qx "${SAM3_ENV_NAME}"; then
  echo "[sam3 setup] Creating conda env: ${SAM3_ENV_NAME}"
  conda create -y -n "${SAM3_ENV_NAME}" python=3.12 pip
fi

echo "[sam3 setup] Installing base Python build tools"
conda run -n "${SAM3_ENV_NAME}" python -m pip install --upgrade pip "setuptools<81" wheel
echo "[sam3 setup] Installing PyTorch CUDA packages. This can take several minutes."
conda run -n "${SAM3_ENV_NAME}" python -m pip install ${SAM3_TORCH_PACKAGES} --index-url "${SAM3_TORCH_INDEX_URL}"
echo "[sam3 setup] Installing SAM3 runtime dependencies"
conda run -n "${SAM3_ENV_NAME}" python -m pip install --upgrade huggingface_hub einops pycocotools psutil

mkdir -p "$(dirname "${SAM3_REPO_DIR}")"
if [ ! -d "${SAM3_REPO_DIR}/.git" ]; then
  echo "[sam3 setup] Cloning SAM3 repo into ${SAM3_REPO_DIR}"
  git clone "${SAM3_REPO_URL}" "${SAM3_REPO_DIR}"
else
  echo "[sam3 setup] Updating SAM3 repo in ${SAM3_REPO_DIR}"
  git -C "${SAM3_REPO_DIR}" pull --ff-only
fi

echo "[sam3 setup] Installing SAM3 package"
conda run -n "${SAM3_ENV_NAME}" python -m pip install -e "${SAM3_REPO_DIR}"

cat <<EOF
SAM3 environment is ready.

Next, authenticate Hugging Face if you have not already:
  hf auth login

Then verify from this env:
  conda run -n ${SAM3_ENV_NAME} python - <<'PY'
from huggingface_hub import whoami
print(whoami()["name"])
PY
EOF
