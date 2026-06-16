# Image Reconstruction Head Benchmark

This document keeps the image reconstruction head comparison aligned to the production policy
(`production_hq_v1`) and the `auto_hq` chain.

## Active policy

Production policy for user-facing jobs is:

```text
wonder3d -> triposr -> instantmesh
```

`one2345` is currently **disabled pending runtime availability** and is excluded from
`auto_hq` and default benchmark scope.

## Comparison goal

Keep the shared preprocessing path fixed (`foreground -> normalize -> multiview`) and compare
only reconstruction heads.

## Heads

| Head | Status | Role in this policy | Note |
| --- | --- | --- | --- |
| `wonder3d` | active | primary | official Wonder3D generation + mesh backend (`WONDER3D_MESH_BACKEND`) |
| `triposr` | active | secondary fallback | direct single-image reconstruction |
| `instantmesh` | active | last-resort fallback | legacy single-head compatibility path |
| `one2345` | disabled_pending | future | runtime contract / entrypoint not ready for production |

## Benchmark runner

Run:

```bash
./scripts/test/run_image_recon_benchmark.sh
```

Optional explicit samples:

```bash
./scripts/test/run_image_recon_benchmark.sh \
  storage/uploads/job_000049/input_image.jpg \
  storage/uploads/job_000050/input_image.jpg \
  storage/uploads/job_000046/input_image.jpg
```

Default heads in this runner:

```text
wonder3d triposr instantmesh
```

The previous one-off comparison value (`one2345`) is intentionally not included in the default
run, but can still be benchmarked manually:

```bash
IMAGE_RECON_BENCHMARK_HEADS="one2345 triposr" \
  ./scripts/test/run_image_recon_benchmark.sh
```

The script writes:

- `storage/test_reports/image_recon_benchmark_<timestamp>.json`

## Current comparison snapshot

Latest automated snapshot:

- `storage/test_reports/image_recon_benchmark_20260417_231934.json`

### Snapshot (character / cake / museum)

| sample | head | runtime (s) | status | quality | shape summary | mesh_backend | fallback_used |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| character | wonder3d | 65.749 | completed | passed | shape_preserved | triposr | false |
| character | triposr | 32.707 | completed | passed | shape_preserved | triposr | false |
| character | instantmesh | 30.552 | completed | passed | shape_preserved | instantmesh | false |
| cake | wonder3d | 85.052 | completed | passed | shape_preserved | triposr | false |
| cake | triposr | 52.781 | completed | passed | shape_preserved | triposr | false |
| cake | instantmesh | 50.786 | completed | passed | shape_preserved | instantmesh | false |
| museum | wonder3d | 70.118 | completed | passed | shape_preserved | triposr | false |
| museum | triposr | 37.351 | completed | passed | shape_preserved | triposr | false |
| museum | instantmesh | 36.178 | completed | passed | shape_preserved | instantmesh | false |

Aggregate from this snapshot:

- average runtime (s): wonder3d `73.640`, triposr `40.946`, instantmesh `39.172`
- viewer-load success (`mesh_loadable`): all `true`
- stage/reason (`object_metadata`): all jobs completed with `quality_status=passed`

## Policy decision

For Commands 10C, we keep:

- **primary:** `wonder3d`
- **secondary:** `triposr`
- **last-resort fallback:** `instantmesh`
- `one2345`: `disabled_pending`

The final decision is based on policy intent and observed output consistency across difficult
samples rather than only wall-clock speed.
