# Failure Cases

Representative object-generation failures should be documented in two places:

- structured artifacts under `storage/failure_cases/`
- human-readable notes in this document

`storage/failure_cases/` is gitignored on purpose so local logs and failing inputs can be kept without polluting the repository.

## Failure Categories

| Category | Typical stage | Example reasons |
| --- | --- | --- |
| Object cutout / preprocessing failure | `object_mesh_failed` | `image_preprocess_failed`, `foreground_extraction_failed` |
| Reconstruction runtime failure | `object_mesh_failed` | `trellis_official_runtime_unavailable`, `trellis_runtime_error`, `reconstruction_runtime_error` |
| Mesh output failure | `object_mesh_failed` | `obj_missing`, `mesh_cleanup_failed`, `mesh_conversion_failed`, `thumbnail_render_failed` |
| Quality failure | `object_mesh_completed` | `poor_reconstruction`, `geometry_fragmented`, `single_view_ambiguity_high` |

## Failure Record Template

Use this template for each new case:

```markdown
### Case: <short_name>

- Input type: image_to_3d
- Dataset category: normal | low_texture | difficult
- Failed stage: object_mesh_failed | object_mesh_completed
- Reason: <taxonomy reason>
- Job id: <job_id>
- Log path: <storage/temp/{job_id}/stage_logs/...>
- Preview path: <storage/previews/{job_id}/...>
- Reproduction:
  1. <upload file>
  2. <enter prompt>
  3. <run command>
  4. <observe failure>
- Notes: <what looked suspicious>
```

## Local Storage Layout

Recommended local-only structure:

```text
storage/failure_cases/
├─ manifests/
├─ logs/
├─ previews/
└─ inputs/
```

## First Slots To Fill

- `Text prompt found wrong object in cluttered image`
- `Object cutout includes background fragments`
- `Thin object geometry collapses in single-view reconstruction`
- `FBX export opens with incorrect orientation in a target DCC`
