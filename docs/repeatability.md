# Repeatability

The smoke-level repeatability runner lives at:

- `scripts/test/run_repeat_tests.sh`

It submits the same image input multiple times through the public API and records:

- run index
- job id
- success or failure
- duration
- final stage
- failure reason
- quality status

## Usage

Assuming backend and the image worker are already running:

```bash
cd <repo-root>
IMAGE_RUNS=3 scripts/test/run_repeat_tests.sh
```

Optional environment variables:

- `BACKEND_URL`
- `IMAGE_FILE`
- `IMAGE_RUNS`
- `POLL_INTERVAL_SEC`
- `TIMEOUT_SEC`

## Output

Reports are written to:

- `storage/test_reports/repeatability_<timestamp>.json`

This directory is intentionally gitignored.

## Report Shape

```json
{
  "started_at": "...",
  "backend_url": "http://127.0.0.1:8000",
  "image_runs": 3,
  "runs": [
    {
      "job_type": "image_to_3d",
      "run_index": 1,
      "job_id": "job_000123",
      "status": "completed",
      "duration_sec": 104.2,
      "stage": "object_mesh_completed",
      "reason": null,
      "quality_status": "passed"
    }
  ]
}
```

## Interpretation

- Stable success with `quality_status=passed` is the happy path.
- Repeated `completed` with `quality_status=failed` indicates the pipeline is finishing but not producing reliable geometry.
- Repeated failure at the same `stage/reason` is a strong signal for targeted debugging.
