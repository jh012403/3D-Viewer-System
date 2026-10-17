#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-dev build-essential git wget curl libjpeg-dev libgl1 libglib2.0-0 ninja-build
mkdir -p /opt/prism
if ! command -v nvcc >/dev/null && [ ! -x /usr/local/cuda-12.4/bin/nvcc ]; then
 wget -q https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb -O /opt/prism/cuda-keyring.deb
 dpkg -i /opt/prism/cuda-keyring.deb
 apt-get update
 apt-get install -y cuda-toolkit-12-4
fi
export CUDA_HOME=/usr/local/cuda-12.4
export PATH="$CUDA_HOME/bin:$PATH"
export MAX_JOBS=4 TORCH_CUDA_ARCH_LIST=8.6
[ -d /opt/prism/trellis2 ] || python3 -m venv /opt/prism/trellis2
source /opt/prism/trellis2/bin/activate
pip install -U pip wheel 'setuptools<81' packaging ninja
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
pip install transformers==4.57.3 timm==1.0.22 trimesh==4.10.1 imageio==2.37.2 'numpy<2' imageio-ffmpeg tqdm easydict opencv-python-headless tensorboard pandas lpips zstandard kornia scipy fastapi uvicorn python-multipart pydantic-settings sqlalchemy redis celery pillow huggingface-hub safetensors sentencepiece einops
pip install git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8
pip install flash-attn==2.7.3 --no-build-isolation
cd /opt/prism
[ -d TRELLIS.2 ] || git clone --recursive https://github.com/microsoft/TRELLIS.2.git
cd TRELLIS.2
git checkout 75fbf0183001ed9876c8dbb35de6b68552ee08bd
# Official setup commands build upstream extensions, without editing sources.
bash setup.sh --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
python -c 'import torch,flash_attn,cumesh,flex_gemm,o_voxel; print(torch.__version__,torch.cuda.is_available())'
