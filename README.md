<div align="center">

# PRISM SCAN

Background product and prop 3D asset generation service for modeling-base and set-dressing workflows.

</div>

## Overview

PRISM SCAN is a single-image 3D asset generation service built for background props, product-like objects, and environment dressing assets.

The system takes an uploaded image, isolates the target object, extracts semantic metadata, generates a 3D asset through TRELLIS.2, and packages the result for browser preview and downstream DCC workflows.

This repository is intentionally scoped for background asset generation. It is not positioned as a hero-asset, facial likeness, or high-fidelity character generation system.

## Why This Project Exists

Most image-to-3D demos stop at "a mesh was generated."

This project focuses on the service layer around that generation step:

- text-guided object selection
- semantic metadata extraction
- viewer-ready result packaging
- transform cleanup
- material packaging
- export-oriented structure for downstream DCC usage

The core contribution is not inventing a new 3D foundation model. The core contribution is turning AI-generated background props into a service workflow that is easier to inspect, package, and reuse.

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

## Key Features

- Single-image upload flow for background prop generation
- Text-guided object cutout before 3D generation
- FastVLM-based semantic metadata extraction
- TRELLIS.2-based reconstruction pipeline
- Browser viewer with result view and mesh view
- Material, metadata, and output package sidecars
- Local dev stack startup from one script

## Repository Layout

```text
ai-3d-service/
├─ backend/      # FastAPI API service
├─ frontend/     # upload flow, viewer, export UI
├─ pipelines/    # segmentation, metadata, reconstruction, packaging
├─ workers/      # background job execution
├─ scripts/      # local startup and utility scripts
├─ docs/         # architecture and pipeline documents
├─ assets/       # lightweight demo/example assets
├─ storage/      # runtime working directories
├─ .env.example
├─ environment.yml
├─ pyproject.toml
└─ README.md
```

## Runtime Modes

| Mode | Purpose | Requirements |
| --- | --- | --- |
| `mock` | UI and pipeline shell validation | Python environment only |
| `real` | actual segmentation, metadata extraction, and 3D generation | local SAM3, FastVLM, TRELLIS.2 runtime setup |

The default `.env.example` uses:

```env
AI3D_MOCK_MODE=true
```

That makes it easy to bring the service up without first installing every external model runtime.

## Quick Start

### 1. Clone the repository

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

### 3. Create a local config

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

## One-Command Local Run

The main local entrypoint is:

```bash
./scripts/dev/start_prismscan.sh
```

This script starts:

- backend API
- image worker
- static frontend server

Logs are written under:

```text
storage/logs/dev/
```

If something is already running:

```bash
./scripts/dev/stop_image_stack.sh
```

## Frontend Dev Mode

If you want a Vite-based frontend workflow instead of the static server:

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

## Real Runtime Setup

The repository is designed to avoid machine-specific hardcoded paths.

If your runtimes are placed under the local repository like this:

```text
ai-3d-service/
├─ .runtime/
│  ├─ sam3/
│  └─ TRELLIS.2/
└─ ...
```

then these values may remain empty in `.env`:

```env
SAM3_REPO_DIR=
TRELLIS_REPO_DIR=
```

The service will auto-detect them relative to the repository root.

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

## Outputs

Generated job results are written under `storage/`.

Main output paths:

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

## Current Scope

This repository is best understood as:

- a graduation project
- a service prototype
- a workflow-oriented image-to-3D system

It is strong at pipeline orchestration, packaging, and viewer integration.

It is not intended to claim:

- hero-grade close-up asset generation
- robust face reconstruction
- production-final character quality

## Documentation

- `docs/architecture.md`
- `docs/pipelines.md`
- `docs/object_selection.md`
- `docs/result_contract.md`
- `docs/quality_gate.md`
- `docs/trellis2_runtime_lock.md`

## Notes

- `start_prismscan.sh` already uses repository-relative startup.
- Runtime artifacts, uploads, outputs, previews, logs, caches, and build outputs are intentionally excluded from Git.
- External model runtimes are expected to be installed by the user in their own local environment.

