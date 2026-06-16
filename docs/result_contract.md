# Result Contract

The backend returns one object-generation result schema.

```json
{
  "job_id": "job_000011",
  "type": "image_to_3d",
  "viewer_type": "object_viewer",
  "mesh_url": "/storage/outputs/job_000011/object_mesh.glb",
  "thumbnail_url": "/storage/previews/job_000011/object_thumbnail.png",
  "stage": "object_mesh_completed",
  "reason": null,
  "quality_status": "passed",
  "quality": { "...": "..." },
  "job": { "...full job record..." },
  "metadata": { "...pipeline metadata..." }
}
```

## Top-Level Fields

| Field | Meaning |
| --- | --- |
| `job_id` | Stable job identifier |
| `type` | Always `image_to_3d` |
| `viewer_type` | Always `object_viewer` |
| `mesh_url` | Backend-served GLB used by the frontend viewer |
| `thumbnail_url` | Backend-served preview image URL |
| `stage` | Latest pipeline stage |
| `reason` | Failure or quality reason when applicable |
| `quality_status` | `passed` or `failed` when quality metadata exists |
| `metadata` | Pipeline-specific metadata object |

## Canonical Files

| File | Path |
| --- | --- |
| Mesh | `storage/outputs/{job_id}/object_mesh.glb` |
| Metadata | `storage/outputs/{job_id}/object_metadata.json` |
| Thumbnail | `storage/previews/{job_id}/object_thumbnail.png` |
| Export files | `storage/outputs/{job_id}/exports/*` |

## Export Contract

`GET /api/jobs/{job_id}/exports` lists available formats.

`POST /api/jobs/{job_id}/exports/{format}` creates or returns the requested export file.

Supported product formats:

- `glb`
- `gltf`
- `obj`
- `fbx`
- `stl`
- `3mf`
