# Pipelines

This document summarizes the current product pipeline contract.

## `image_to_3d` Object Pipeline

The real object pipeline lives in [`pipelines/image_to_3d/pipeline.py`](../pipelines/image_to_3d/pipeline.py).

### End-to-End Flow

```text
storage/uploads/{job_id}/input_image.jpg
-> optional text-guided object cutout
-> trellis_direct_input
-> TRELLIS.2 official preprocess_image()
-> TRELLIS.2 official run/decode/export path
-> object_mesh.glb
-> object_thumbnail.png
-> object_metadata.json
-> optional export conversion
```

### Intermediate Artifacts

| Step | Output path | Notes |
| --- | --- | --- |
| Uploaded image | `storage/uploads/{job_id}/input_image.jpg` | Original user upload |
| Text prompt cutout | `storage/temp/{job_id}/sam2_candidates/candidates/*/segmented.png` | Object-only image generated before reconstruction |
| TRELLIS processed image | `storage/temp/{job_id}/reconstruction/trellis/trellis_processed_input.png` | Output of official TRELLIS.2 preprocessing |
| Raw mesh | `storage/temp/{job_id}/reconstruction/trellis/trellis_raw.glb` | Raw TRELLIS.2 GLB export |
| Raw archive | `storage/outputs/{job_id}/object_raw.glb` | Copy of raw TRELLIS output for diagnosis |
| Final mesh | `storage/outputs/{job_id}/object_mesh.glb` | Canonical browser/download asset |
| Exports | `storage/outputs/{job_id}/exports/*` | Optional GLB-derived export formats |

### Reconstruction Contract

The service does not modify TRELLIS.2 internals. Optional object selection is a separate pre-step: it creates a user-selected object image, then passes that image to TRELLIS.2 exactly as a normal input so the upstream runtime still applies its official preprocessing and generation path.

Recorded metadata keys include:

- `image_preprocess.direct_input_enabled`
- `image_preprocess.trellis_input_strategy`
- `image_preprocess.trellis_input_file`
- `image_preprocess.object_candidate_id`
- `image_preprocess.object_candidate_image`
- `image_preprocess.hints`

### Mesh Cleanup Contract

The cleanup stage lives in [`pipelines/image_to_3d/mesh_cleanup.py`](../pipelines/image_to_3d/mesh_cleanup.py).

Current behavior:

- TRELLIS.2 exports GLB directly.
- The cleanup stage uses GLB passthrough for TRELLIS outputs to avoid changing geometry that matched the official demo behavior.
- The final canonical file is `object_mesh.glb`.

Recorded metadata keys include:

- `mesh_cleanup.raw_component_count`
- `mesh_cleanup.removed_small_components`
- `mesh_cleanup.largest_component_ratio`
- `mesh_cleanup.cleanup_status`

### Export Contract

Additional formats are derived from the canonical `object_mesh.glb` and stored under `storage/outputs/{job_id}/exports/`.

Supported product formats:

- `glb`
- `gltf`
- `obj`
- `fbx`
- `stl`
- `3mf`

FBX conversion requires a Blender CLI binary configured through `BLENDER_BIN` or available on `PATH`.

## Thumbnail Fallback Policy

The image pipeline tries `trimesh.scene.save_image()`, then copies an available TRELLIS intermediate image if headless rendering fails, then falls back to the generic placeholder.
