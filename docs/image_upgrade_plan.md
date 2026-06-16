# Image Upgrade Plan

Commands 10 upgrades the image pipeline again by replacing the purely heuristic foreground step with a provider-based structure.

```text
input image
-> foreground_extract
-> image_normalize
-> multiview_prior (passthrough hook)
-> InstantMesh
-> mesh_cleanup
-> object_mesh.glb
```

## What changed in Commands 10

- foreground extraction now supports `auto | rembg | heuristic | sam` request modes
- `auto` currently tries a real `rembg` model (`u2netp` by default) and falls back to the heuristic crop path if needed
- provider metadata is now recorded in `image_preprocess`
- background and border clutter are reduced before InstantMesh sees the image
- center crop fallback is still used when foreground extraction is weak
- a future multiview prior stage now has a stable handoff point
- raw disconnected mesh fragments are cleaned before the final GLB export

## Current limits

- `sam` is a reserved provider mode, but the current MVP runtime only implements `rembg` as the real foreground model
- `multiview_prior` is a passthrough hook today
- highly cluttered or human-centric scenes can still produce ambiguous single-view geometry even when the foreground crop is better

## Provider contract

`pipelines/image_to_3d/foreground_extract.py` now returns:

- `foreground_provider_requested`
- `foreground_provider_used`
- `foreground_provider_fallback_used`
- `foreground_provider_attempts`
- `foreground_model`
- `foreground_model_name`

Those fields are persisted under `object_metadata.json -> image_preprocess`.

## Commands 10 reference comparisons

- `job_000050`:
  - pre-Commands 10 museum sample using heuristic-centered fallback
  - `foreground_extracted=false`
  - hints: `center_crop_fallback_applied`, `complex_background_detected`, `small_foreground_ratio`

- `imgfg_20260416_02`:
  - same museum-family sample after provider upgrade
  - `foreground_provider_used=rembg`
  - `foreground_extracted=true`
  - cleanup still removed `1` disconnected component
  - final quality: `passed`

- `job_000049`:
  - top-down cake sample with heuristic foreground
  - bbox covered almost the full image and `crop_applied=false`
  - quality hints: `background_complexity_high`, `single_view_ambiguity_high`

- `imgfg_20260416_01`:
  - same cake-family sample after provider upgrade
  - `foreground_provider_used=rembg`
  - `crop_applied=true`
  - quality hints cleared
  - final quality: `passed`

- `imgfg_20260416_03`:
  - cluttered costume subject with `rembg`
  - foreground extraction succeeded, but `occlusion_detected` remained and cleanup had to remove `6` small fragments
  - final quality still passed, but the scene remains a harder single-view case than object-centric captures
