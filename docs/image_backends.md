# Image Reconstruction Backend Policy

## Production policy (`production_trellis_only_v1`)

Current production policy for image jobs is:

- **Primary and only production backend**: TRELLIS.2 official runtime
- **Fallback backend**: none
- Legacy backends are removed from the user-facing path because their visual
  quality did not match the approved TRELLIS.2 demo result.

`IMAGE_RECON_HEAD=trellis` maps to:

```text
trellis
```

`object_metadata.json` records internal runtime details for debugging:

- `requested_head_chain`
- `resolved_backend`
- `mesh_backend`
- `fallback_chain`
- `fallback_used`
- `backend_policy`

Public API responses hide internal model/backend names by default when
`AI3D_EXPOSE_INTERNAL_MODEL_INFO=false`.

## Backend decision summary

| backend | production role | decision | reason |
| --- | --- | --- | --- |
| TRELLIS.2 | primary | keep | matched the approved official demo quality when the upstream runtime was kept clean and its own preprocessing was used |
| SAM2 preprocessing | none | remove from product flow | degraded the TRELLIS input in several samples and produced worse meshes |
| Hunyuan3D | none | removed | license/runtime uncertainty and no longer needed for image path |
| Wonder3D / TripoSR / InstantMesh / One-2-3-45 | none | removed/deprecated | lower quality or unstable runtime compared with the approved TRELLIS.2 path |

## Current service path

```text
uploaded image
-> ai-3d-service TRELLIS helper
-> upstream TRELLIS.2 preprocess_image()
-> upstream TRELLIS.2 generation/decode/export
-> object_mesh.glb
```

## Metadata / API impact

`object_metadata.json` and `/api/jobs/{job_id}/result` include:

- `requested_reconstruction_head`
- `requested_head_chain`
- `backend_policy`
- `resolved_backend`
- `mesh_backend`
- `fallback_chain`
- `fallback_used`

Example:

```json
{
  "requested_mode": "high_quality",
  "requested_head_chain": ["trellis"],
  "backend_policy": "production_trellis_only_v1",
  "resolved_backend": "trellis",
  "mesh_backend": "trellis",
  "fallback_chain": [],
  "fallback_used": false
}
```
