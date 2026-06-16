# PRISM SCAN

Background product and prop 3D asset generation service built around a single-image workflow.

This project is designed for background set dressing and modeling-base asset creation, not close-up hero assets, character likeness, or face-quality reconstruction.

## Pipeline

```text
Image Input
-> SAM3 Object Segmentation
-> Object-only Image
-> FastVLM Metadata Extraction
-> TRELLIS.2 3D Asset Generation
-> Web Viewer
-> Export
```

## What This Repository Contains

- `backend/`
  FastAPI service for upload, job creation, polling, result lookup, and export endpoints
- `frontend/`
  upload flow, object cutout screen, result viewer, mesh viewer, and export UI
- `pipelines/`
  segmentation handoff, metadata extraction, TRELLIS runtime orchestration, mesh cleanup, and material packaging
- `workers/`
  background job execution
- `scripts/dev/`
  local startup scripts
- `docs/`
  architecture and pipeline documents

## Requirements

- Linux
- Conda
- Python environment from `environment.yml`
- Node.js is optional
  The default startup path serves the static frontend and does not require `npm run dev`.
- GPU runtime is optional for mock mode, required for real TRELLIS/SAM/FastVLM execution

## Quick Start

### 1. Clone and enter the repository

```bash
git clone <your-repo-url>
cd ai-3d-service
```

### 2. Create the main environment

```bash
conda env create -f environment.yml
conda activate ai3d-mvp
pip install -e .
```

### 3. Create local environment config

```bash
cp .env.example .env
```

### 4. Start the service

```bash
./scripts/dev/start_prismscan.sh
```

Open:

```text
http://127.0.0.1:8080/prismscan-v2.html?mode=image
```

The script starts:

- backend API
- image worker
- static frontend server

Logs are written under `storage/logs/dev/`.

## Default Run Mode

`.env.example` ships with:

```env
AI3D_MOCK_MODE=true
```

This lets the UI and pipeline shell run without requiring the full model stack.

If you want real model execution, switch to:

```env
AI3D_MOCK_MODE=false
```

and configure the runtimes below.

## Real Runtime Setup

This repository is portable by default.

Do not hardcode your machine path into the source code or `.env.example`.
The service already resolves the repository root automatically and can discover runtimes under the local `.runtime/` directory.

Recommended local layout:

```text
ai-3d-service/
├─ .runtime/
│  ├─ sam3/
│  └─ TRELLIS.2/
└─ ...
```

If `.runtime/sam3` and `.runtime/TRELLIS.2` exist, you can leave these values empty in `.env`:

```env
SAM3_REPO_DIR=
TRELLIS_REPO_DIR=
```

The code will auto-detect them relative to the repository root.

Example real runtime settings:

```env
AI3D_MOCK_MODE=false

SAM3_CMD="conda run -n sam3 python"
SAM3_REPO_DIR=
SAM3_MODEL_ID=facebook/sam3
SAM3_DEVICE=cuda

FASTVLM_CMD="conda run -n trellis2 python"
FASTVLM_MODEL_ID=apple/FastVLM-0.5B
FASTVLM_DEVICE=cuda
FASTVLM_DTYPE=float16

TRELLIS_CMD="conda run -n trellis2 python"
TRELLIS_REPO_DIR=
TRELLIS_MODEL_PATH=microsoft/TRELLIS.2-4B
TRELLIS_DEVICE=cuda
TRELLIS_RESOLUTION=1024
TRELLIS_LOW_VRAM_MODE=true
```

## Optional Frontend Dev Mode

If you want the Vite dev server instead of the static frontend server:

```bash
cd frontend
npm install
cd ..
AI3D_FRONTEND_SERVER=vite ./scripts/dev/start_prismscan.sh
```

Then open:

```text
http://127.0.0.1:5173
```

## Stop the Service

If a previous stack is still running:

```bash
./scripts/dev/stop_image_stack.sh
```

## Output Layout

Generated results are written under `storage/`.

Important paths:

- `storage/uploads/{job_id}/`
- `storage/jobs/{job_id}/job.json`
- `storage/outputs/{job_id}/object_mesh.glb`
- `storage/outputs/{job_id}/metadata.json`
- `storage/outputs/{job_id}/material.json`
- `storage/outputs/{job_id}/textures/`
- `storage/outputs/{job_id}/hdri/`
- `storage/previews/{job_id}/object_thumbnail.png`

## API Summary

- `POST /api/upload`
- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/result`
- `GET /api/jobs/{job_id}/exports`
- `POST /api/jobs/{job_id}/exports/{format}`
- `POST /api/jobs/{job_id}/segmentation-text-prompt`

## Important Notes

- `start_prismscan.sh` already uses repository-relative path resolution.
- The repository should not contain local absolute machine paths.
- Runtime artifacts, uploads, outputs, previews, logs, model caches, and build outputs should stay out of Git.
- The service is intended for background prop workflows, not facial likeness or hero character generation.

## Useful Documents

- `docs/architecture.md`
- `docs/pipelines.md`
- `docs/object_selection.md`
- `docs/result_contract.md`
- `docs/quality_gate.md`
- `docs/trellis2_runtime_lock.md`
