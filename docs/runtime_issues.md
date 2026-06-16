# Runtime Dependency Issues (Image Reconstruction Pipeline)

This document tracks the current runtime blockers and the mitigations applied for image reconstruction heads.

## 1) rembg / pymatting / numba cache locator error

### Symptom

`pymatting` or the rembg call chain can fail with messages similar to:

- `RuntimeError: cannot cache function ... no locator available`

This occurs when numba cache location is not writable/resolvable in the process runtime.

### Root cause

- Missing or uninitialized cache directories in non-interactive runs (`NUMBA_CACHE_DIR`, `XDG_CACHE_HOME`).
- Some execution entrypoints bypassing `build_runtime_env` and starting with bare env.

### Remediation (applied)

- Centralized cache defaults in `pipelines/common/env.py`:
  - `AI3D_RUNTIME_CACHE_ROOT` (default `/tmp/ai3d_cache`)
  - `NUMBA_CACHE_DIR=${AI3D_RUNTIME_CACHE_ROOT}/numba`
  - `XDG_CACHE_HOME=${AI3D_RUNTIME_CACHE_ROOT}/xdg`
- Set these variables before launching backend/worker dev scripts:
  - `scripts/dev/run_backend.sh`
  - `scripts/dev/run_image_worker.sh`
  - `scripts/dev/start_all.sh`
- `scripts/debug/debug_rembg_runtime.py` captures:
  - `NUMBA_CACHE_DIR`
  - `XDG_CACHE_HOME`
  - `HOME`
  - `AI3D_RUNTIME_CACHE_ROOT`
  - cache directory existence and import checks.

### Current status

- Standalone check is currently successful when launching through the configured cache environment:
  - `python scripts/debug/debug_rembg_runtime.py` succeeds and writes JSON log under `storage/temp/debug_logs/`.

## 2) One-2-3-45 (one2345) availability

### Symptom

- `one2345_contract()` returns:
  - `command_missing`
  - `repo_missing:<repo-root>/.runtime/One2-3-45`

### Root cause

- `.runtime/One2-3-45` repository is not checked out in the local workspace.
- `ONE2345_CMD` is defined, but the expected entrypoint is not present.

### Remediation / next step

- Stage contract as unavailable until repository and entrypoint are provisioned.
- Update `.env.example` and deployment docs with explicit bootstrap steps before enabling `one2345` in benchmark.

## 3) Wonder3D official / TripoSR shared dependency path

### Symptom

- Prior runs showed failures through rembg/pymatting stack during official/head fallback paths when invoking external toolchains.

### Status

- Production profile keeps `WONDER3D_MESH_BACKEND=triposr` to avoid `official` path by default.
- Official Wonder3D remains tracked in `docs/wonder3d_official_recovery.md`.

### Next step

- If re-enabling `WONDER3D_MESH_BACKEND=official`, verify `tinycudann` availability and run:
  - `python -m pipelines.image_to_3d.wonder3d_wrapper --debug`

## 4) SV3D VRAM ceiling on 24GB GPUs

### Symptom

- `MULTIVIEW_PROVIDER=sv3d` runs can peak at ~24GB VRAM and intermittently fail with CUDA OOM.

### Root cause

- High-step SV3D sampling (`sv3d_p`, large `num_steps`) can consume nearly full VRAM.
- Fragmentation increases risk when the worker runs many jobs in sequence.

### Remediation (applied)

- Added SV3D runtime knobs in `.env.example`:
  - `SV3D_VERSION`, `SV3D_NUM_STEPS`, `SV3D_DECODING_T`, `SV3D_DEVICE`, `SV3D_SEED`
  - `SV3D_OOM_RETRY_*` profile for automatic OOM retry
- Added OOM-aware retry flow in `pipelines/image_to_3d/multiview_wrapper.py`:
  - if primary SV3D run fails with CUDA OOM, retry once with reduced profile
  - attempts are recorded in `multiview_wrapper.log` and metadata fields:
    - `sv3d_attempts`
    - `sv3d_oom_retry_used`
- Added worker-level CUDA allocator defaults in `scripts/dev/run_image_worker.sh`:
  - `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,garbage_collection_threshold:0.8`
  - `CUDA_MODULE_LOADING=LAZY`

### Recommended 24GB baseline

- `SV3D_VERSION=sv3d_u`
- `SV3D_NUM_STEPS=16`
- `SV3D_DECODING_T=2`
- `SV3D_OOM_RETRY_NUM_STEPS=12`
- `SV3D_OOM_RETRY_DECODING_T=1`
