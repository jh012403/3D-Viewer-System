# Object Selection Layer

This layer runs before TRELLIS.2 and is intentionally independent from the
locked reconstruction runtime.

## Goal

```text
uploaded image
-> object box proposals
-> SAM2.1 mask per proposal
-> user picks one candidate
-> selected object image
-> official TRELLIS.2 preprocess/run/export
```

TRELLIS.2 settings, seed, resolution, export code, and runtime repo must not be
changed by this layer.

## Recommended Runtime

| Stage | Recommended model | Role |
| --- | --- | --- |
| Object proposal | Florence-2 or Grounding DINO | Find semantic object boxes such as person, product, cake, fossil |
| Mask generation | SAM2.1 | Produce precise masks from the selected/proposed boxes |
| Reconstruction | TRELLIS.2 | Generate GLB from the selected object image |

## Environment Contract

```env
AI3D_OBJECT_DETECTOR_PROVIDER=florence2
FLORENCE2_CMD="conda run -n ai3d-mvp python"
FLORENCE2_MODEL_ID=microsoft/Florence-2-large
FLORENCE2_DEVICE=cuda
FLORENCE2_PROMPT=<OD>

SAM2_FOREGROUND_CMD="conda run -n ai3d-mvp python"
SAM2_REPO_DIR=/path/to/sam2
SAM2_FOREGROUND_CHECKPOINT=/path/to/sam2.1_hiera_large.pt
SAM2_FOREGROUND_CONFIG=configs/sam2.1/sam2.1_hiera_l.yaml
SAM2_FOREGROUND_DEVICE=cuda

AI3D_SEGMENT_UI_MAX_CANDIDATES=5
```

If the detector is disabled or unavailable, the backend falls back to SAM2
automatic mask candidates. If SAM2 is unavailable, the UI allows continuing with
the original uploaded image.

## Product UX Policy

- Show only the top object candidates, currently capped at 5.
- Do not expose internal model names in the user-facing UI.
- Store candidate assets under `storage/temp/{job_id}/sam2_candidates/`.
- Pass only the selected `segmented.png` candidate ID into the job options.
- Do not silently switch reconstruction backends.

## Candidate Output

```text
storage/temp/{job_id}/sam2_candidates/
├─ detector/object_boxes.json
└─ candidates/
   └─ guided_0000/
      ├─ segmented.png
      ├─ mask.png
      ├─ overlay.png
      └─ metadata.json
```

`segmented.png` is the only file used as the optional TRELLIS.2 input.
