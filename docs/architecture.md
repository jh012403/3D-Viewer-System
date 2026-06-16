# Architecture

## Separation of Responsibilities

- `frontend/`: image upload, text prompt, object cutout UX, job polling, 3D object viewer, and export UI.
- `backend/`: upload API, job creation, job status/result API, export conversion API, and static file serving.
- `workers/`: queue polling, status transition management, and object pipeline CLI invocation.
- `pipelines/`: only place where model execution, mock output generation, and mesh processing live.

## Storage Layout

- `storage/uploads/{job_id}/input_image.jpg`
- `storage/jobs/{job_id}/job.json`
- `storage/outputs/{job_id}/object_mesh.glb`
- `storage/outputs/{job_id}/object_metadata.json`
- `storage/outputs/{job_id}/exports/*`
- `storage/previews/{job_id}/object_thumbnail.png`
- `storage/temp/{job_id}/stage_logs/`
- `storage/temp/{job_id}/reconstruction/`

## Queue Model

1. `POST /api/upload` reserves `job_000001` style IDs and stores the uploaded image.
2. `POST /api/jobs` creates a `queued` job manifest.
3. The image worker claims the job and marks it `running`.
4. The worker runs `python -m pipelines.image_to_3d.cli`.
5. The pipeline writes outputs, previews, metadata, and temp artifacts.
6. The worker marks the job `completed` or `failed`.

## Real Model Integration

- The product path is `image_to_3d` only.
- Optional text-guided cutout runs before reconstruction.
- The reconstruction stage passes the selected image into the official TRELLIS.2 helper path.
- Mock mode and real mode both emit the same final file names.
- Export conversion derives additional formats from the canonical `object_mesh.glb`.
