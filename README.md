# PRISM SCAN: Background Product and Prop 3D Asset Generation Service

[![Project Page](https://img.shields.io/badge/Project%20Page-GitHub%20Pages-87CEEB)](https://jh012403.github.io/3D-Viewer-System/)
[![Repository](https://img.shields.io/badge/GitHub-3D--Viewer--System-181717)](https://github.com/jh012403/3D-Viewer-System)
[![Status](https://img.shields.io/badge/Status-Prototype-22C55E)](#)
[![Runtime](https://img.shields.io/badge/Runtime-SAM3%20%7C%20FastVLM%20%7C%20TRELLIS.2-0EA5E9)](#)

> **Official repository for PRISM SCAN, a single-image 3D asset generation service for background products and set-dressing props.**

PRISM SCAN is designed for **background and modeling-base asset generation**, not close-up hero assets.  
The service connects object cutout, metadata extraction, 3D generation, and viewer-based inspection in one workflow.

For visual results, viewer captures, and curated examples, a separate project page will be added later.

## Pipeline
![System Pipeline](https://raw.githubusercontent.com/jh012403/3D-Viewer-System/main/asset/system_pipeline.png)

## Quick Start

### 1. Clone

```bash
git clone git@github.com:jh012403/3D-Viewer-System.git
cd 3D-Viewer-System
```

### 2. Core Environment

```bash
conda env create -f environment.yml
conda activate ai3d-mvp
pip install -e .
cp .env.example .env
```

### 3. Runtime Preparation

This repository keeps the service layer in one place, but the heavy model runtimes are prepared separately.

- `sam3` conda environment: SAM3 object segmentation
- `trellis2` conda environment: TRELLIS.2 reconstruction and FastVLM metadata extraction
- Set `SAM3_REPO_DIR` and `TRELLIS_REPO_DIR` in `.env`, or place the runtime repositories under `./.runtime/`

The default `.env.example` is configured for safe local startup with mock mode enabled.  
For real inference, update `.env` to match your actual runtime setup.

### 4. Launch

```bash
./scripts/dev/start_prismscan.sh
```

Open:

```text
http://127.0.0.1:8080/prismscan-v2.html?mode=image
```

## Model References

- `facebook/sam3` - text-guided object segmentation
- `apple/FastVLM-0.5B` - semantic metadata extraction
- `microsoft/TRELLIS.2-4B` - single-image 3D asset generation
- `xinntao/Real-ESRGAN` - optional cutout enhancement utility

## Repository Focus

This repository is centered on the **service pipeline**:

- object selection and cutout flow
- metadata extraction and packaging
- TRELLIS.2 orchestration
- web viewer and mesh preview
- export and result delivery

It is **not** intended as a redistribution repository for the full upstream model sources.

## Notes

- Best suited for **background props, product-like objects, and modeling-base assets**
- Character faces, isolated facial parts, and hero-quality close-up assets are outside the main target scope
- Runtime quality depends heavily on segmentation quality, object coverage, GPU memory, and TRELLIS.2 settings

## Acknowledgements

This project integrates and builds around several excellent open-source projects:

- SAM3
- FastVLM
- TRELLIS.2
- Real-ESRGAN

Please follow the license terms of each upstream project when using their models or code.
