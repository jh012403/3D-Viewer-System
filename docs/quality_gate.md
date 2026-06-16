# Quality Gate

The service distinguishes pipeline completion from output usability.

- `job.status = completed` means canonical artifacts were written.
- `metadata.quality.status = passed|failed` means the final artifacts cleared sanity checks.

## Object Quality Checks

`pipelines/common/quality_gate.py` validates:

- `mesh_exists`
- `mesh_non_empty`
- `thumbnail_exists`
- `mesh_loadable`
- `bbox_valid`
- `vertex_count_ok`
- `component_count_ok`
- `largest_component_ratio_ok`
- `bbox_tightness_ok`
- `silhouette_consistency_ok`
- `view_count_ok`
- `view_diversity_ok`

Quality hints can include:

- `geometry_fragmented`
- `fragmented_shape`
- `geometry_slab_like`
- `bbox_too_loose`
- `bbox_too_tight`
- `background_complexity_high`
- `single_view_ambiguity_high`
- `foreground_provider_fallback_used`

These hints do not automatically fail every job, but they explain why a completed result may still look less reliable.

## Example Payload

```json
{
  "quality": {
    "status": "passed",
    "usable": true,
    "checks": {
      "mesh_exists": true,
      "mesh_loadable": true,
      "component_count_ok": true,
      "largest_component_ratio_ok": true
    },
    "metrics": {
      "vertex_count": 17688,
      "component_count": 1,
      "largest_component_ratio": 1.0
    },
    "hints": [
      "background_complexity_high"
    ]
  }
}
```

## Stage Log Format

Every stage writes structured logs under:

- `storage/temp/{job_id}/stage_logs/`

Those logs are local runtime artifacts and are intentionally gitignored.
