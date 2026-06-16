# Image Reconstruction Alternative Models

This project supports multiple image reconstruction heads; current production `auto_hq` path uses:

- `wonder3d` (primary)
- `triposr` (fallback)
- `instantmesh` (legacy fallback)

One-2-3-45 is currently a deferred candidate:

- `one2345` (`disabled_pending`): not included in `auto_hq` until repo/entry availability is restored.

## 1) One-2-3-45 (`one2345`) - disabled_pending

Wrapper file:

- `pipelines/image_to_3d/one2345_wrapper.py`

Configuration in `.env`:

- `ONE2345_REPO_DIR`: repository root path
- `ONE2345_CMD`: CLI command to execute the runtime
- `ONE2345_IMAGE_ARG`, `ONE2345_OUTPUT_DIR_ARG`, `ONE2345_NAME_ARG`: command argument names
- `ONE2345_MODEL_FORMAT`: expected mesh format (`obj|glb|ply`)

Expected contract:

- Input: normalized input image (typically `.png` / `.jpg`)
- Output: mesh artifact written under output/repo directories and detected by recursive scan

Current runtime status (as of last check):

- Current contract status:
  - `command_missing`
  - `repo_missing` when `.runtime/One2-3-45` is absent
- Kept disabled from auto_hq as of production policy `production_hq_v1`.
- Re-enable only after runtime entry and deterministic contract checks are fully prepared.

## 2) Wonder3D (`wonder3d`)

Wrapper file:

- `pipelines/image_to_3d/wonder3d_wrapper.py`

Configuration in `.env`:

- `WONDER3D_REPO_DIR`, `WONDER3D_CMD`, `WONDER3D_CONFIG`
- `WONDER3D_RECON_SUBDIR`, `WONDER3D_RECON_CMD`, `WONDER3D_RECON_CONFIG`
- `WONDER3D_MESH_BACKEND`: internal mesh backend selector

Expected contract:

- Input: normalized image or generated views
- Step 1: official Wonder3D generation step (`test_mvdiffusion_seq.py`)
- Step 2: mesh fallback backend (default `triposr`, then `instantmesh`)
- Output: mesh exported to canonical project path through selected mesh backend

Current runtime status:

- Generation step is available.
- Mesh export via `triposr`/`instantmesh` is selectable.
- Official `WONDER3D_MESH_BACKEND=official` is tracked as a recovery track due CUDA extension constraints.
- See `docs/wonder3d_official_recovery.md`.
- Runtime depends on cache-stable execution environment (NUMBA/pymatting/rembg chain).

## 3) TripoSR (`triposr`)

Wrapper file:

- `pipelines/image_to_3d/triposr_wrapper.py`

Configuration in `.env`:

- `TRIPOSR_REPO_DIR`, `TRIPOSR_CMD`, `TRIPOSR_MODEL_FORMAT`, `TRIPOSR_EXTRA_ARGS`

Expected contract:

- Input: image
- Command shape:
  - `python run.py <input_image> --output-dir <output_dir> --model-save-format <format>`
- Output: generated mesh file in output directory

Current runtime status:

- Available via environment checks, but shared dependency runtime stability is currently the blocker in some runs.
- Keep `TRIPOSR_NO_REMOVE_BG=true` as an operational fallback when removing background fails.
- `triposr_wrapper.triposr_contract()` should be consulted before scheduling.

## 4) InstantMesh (`instantmesh`)

Wrapper file:

- `pipelines/image_to_3d/instantmesh_wrapper.py`

Status:

- Still kept as baseline/final fallback only in this profile.

## Comparison Strategy (reference only)

For direct comparison, we execute:

1. `wonder3d`
2. `triposr`
3. `instantmesh` (legacy baseline)

The benchmark script writes:

- `storage/test_reports/image_recon_benchmark_<timestamp>.json`

## Runtime blocker notes

- one2345 requires `.runtime/One2-3-45` and a valid runtime entrypoint.
- wonder3d/triposr should be launched with cache variables set (`NUMBA_CACHE_DIR`, `XDG_CACHE_HOME`, `AI3D_RUNTIME_CACHE_ROOT`) via the run scripts.
