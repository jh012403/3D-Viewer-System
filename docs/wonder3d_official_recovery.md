# Wonder3D Official Recovery Track

## Current status

`WONDER3D_MESH_BACKEND=official` is not used by default for the MVP demo.
The default now uses `triposr`, with `instantmesh` retained as a stable fallback.

## Observed blocker

- `tinycudann` extension load is typically unavailable in the default conda env used for local runs.
- In this environment, official Wonder3D reconstruction exits before mesh export, producing runtime errors during back-projection.
- Recent benchmark logs also show a shared runtime dependency failure in dependency stacks:
  - `pymatting` import raises `RuntimeError: cannot cache function ... no locator available` (numba cache path in package site-packages).
  - Both Wonder3D and TripoSR paths hit this while importing `rembg` -> `pymatting`.

## Recovery plan (separate track)

1. Provision CUDA/PyTorch extension-compatible toolchain:
   - Install `ninja`
   - Install `tiny-cuda-nn` from source (matching CUDA version)
2. Validate `WONDER3D_RECON_CHECKPOINT` and launch paths in environment.
3. Run:
   - `python -m pipelines.image_to_3d.wonder3d_wrapper --debug`
   - `--input-image` debug execution for end-to-end sanity.
4. Compare:
   - `mesh_backend` and `mesh_backend_attempts` in `object_metadata.json`.
   - quality and component metrics from `quality` section.

## Temporary rule for 09F+

- Demo default remains `WONDER3D_MESH_BACKEND=triposr`.
- `official` path is a recovery route and should be enabled only when extension/runtime is prepared.
- `instantmesh` stays as the final fallback for robustness.
