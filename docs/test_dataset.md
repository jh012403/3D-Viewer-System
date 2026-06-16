# Test Dataset Guide

`assets/test_datasets/` is the reliability-layer entrypoint for curated validation samples.

## Directory Layout

```text
assets/test_datasets/
└─ image/
   ├─ normal/
   ├─ low_texture/
   └─ difficult/
```

## Classification Rules

- `normal`: baseline object samples that should usually pass mock and real smoke tests.
- `low_texture`: weak texture cues, repeated patterns, or smooth surfaces that can hurt object reconstruction quality.
- `difficult`: unusual lighting, reflective objects, cluttered backgrounds, occlusion, or ambiguous silhouettes.

## Recommended Sample Inventory

| Sample name | Input type | Category | Expected difficulty | Expected weak stage |
| --- | --- | --- | --- | --- |
| `sample_input.jpg` | image | normal | low | object baseline |
| `cake_topdown_object` | image | normal | medium | object cutout quality |
| `dino_museum_cluttered_background` | image | difficult | high | object cutout / cleanup |
| `costume_subject_cluttered_background` | image | difficult | high | object cutout / cleanup |
| `ceramic_mug_low_texture.jpg` | image | low_texture | medium | object mesh generation |
| `reflective_toy_difficult.jpg` | image | difficult | high | geometry / texture sanity |

## Minimum Smoke Set

These files are enough to wire the current repeatability script and manual smoke tests:

- `assets/mock/sample_input.jpg`

## Current Registered Samples

The repository tracks lightweight manifest files instead of shipping large media binaries. Each manifest points to a known local test artifact or reference job.

| Sample name | Manifest | Notes |
| --- | --- | --- |
| `sample_input_object_success` | `assets/test_datasets/image/normal/sample_input_object_success.sample.json` | Current real image success reference for viewer checks. |
| `cake_topdown_object` | `assets/test_datasets/image/normal/cake_topdown_object.sample.json` | Simpler object-centric image for object-selection comparison. |
| `dino_museum_cluttered_background` | `assets/test_datasets/image/difficult/dino_museum_cluttered_background.sample.json` | High-clutter museum scene used to compare object cutout behavior. |
| `costume_subject_cluttered_background` | `assets/test_datasets/image/difficult/costume_subject_cluttered_background.sample.json` | Busy indoor scene where the subject touches frame borders and cleanup remains challenging. |

## Sample Metadata Template

For each real sample, capture at least:

- `sample_name`
- `category`
- `input_type`
- `expected_difficulty`
- `expected_weak_stage`
- `notes`
