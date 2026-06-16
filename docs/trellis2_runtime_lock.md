# TRELLIS.2 Runtime Lock

This document pins the TRELLIS.2 runtime profile that produced the approved
quality level on `2026-04-22`.

The goal is stability, not experimentation. If this profile drifts, the service
should fail fast instead of silently producing different geometry.

## Locked runtime profile

- Runtime repo: `./.runtime/TRELLIS.2`
- Upstream repo: `https://github.com/microsoft/TRELLIS.2`
- Model: `microsoft/TRELLIS.2-4B`
- Conda env: `trellis2`
- Device: `cuda`
- Resolution: `1024`
- Seed: `363987120`
- Decimation target: `500000`
- Texture size: `2048`
- Low VRAM mode: `true`

## Locked package versions

- `torch==2.6.0+cu124`
- `torchvision==0.21.0+cu124`
- `transformers==4.57.3`
- `timm==1.0.22`
- `trimesh==4.10.1`
- `imageio==2.37.2`
- `flash_attn==2.7.3`

These versions are enforced by `pipelines/image_to_3d/trellis_wrapper.py` in
strict official mode. If the runtime drifts, the service should report the
runtime as unavailable instead of trying a compatibility patch.

## Official-style setup notes

The upstream README recommends:

```bash
. ./setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
```

For this machine, the working profile is:

- Linux
- NVIDIA RTX 3090 24 GB
- Driver compatible with CUDA 12.4 user-space packages
- `torch 2.6.0+cu124`

The important rule is not "match every package from the Hugging Face Space",
but "keep the local runtime pinned to the known-good profile above".

## Launch commands

Run the official TRELLIS.2 Gradio demo:

```bash
cd .runtime/TRELLIS.2
conda run -n trellis2 python app.py
```

Then open:

```text
http://127.0.0.1:7860
```

For consistent A/B comparisons:

- Use the same input image
- Use the same `Resolution`
- Disable randomized seed when comparing outputs
- Compare with seed `363987120` unless intentionally selecting a new visual baseline
- Keep `Decimation Target=500000` and `Texture Size=2048`

## Service integration rules

The service must treat TRELLIS.2 as an upstream runtime, not as editable local
business logic.

Allowed:

- Passing the uploaded image into the service TRELLIS helper
- Calling official TRELLIS.2 pipeline APIs from a service-side helper
- Writing outputs into `storage/` and `storage/temp/`

Not allowed:

- Editing files under `.runtime/TRELLIS.2/` to add compatibility patches
- Monkey-patching DINOv3 or other upstream components during service inference
- Silently falling back to a degraded path when the official runtime is broken
- Reintroducing service-side segmentation/crop/normalization into the product
  path without comparing against the official TRELLIS.2 Gradio output

## Service-side execution path

Current policy:

```text
user image or selected object image
-> ai-3d-service TRELLIS helper
-> TRELLIS official preprocess_image()
-> TRELLIS official run()
-> TRELLIS official decode_latent()
-> GLB export
```

The service helper may orchestrate inputs and outputs, but it should not alter
the internal behavior of the upstream TRELLIS runtime. The current product path
may prepare a user-selected object image before TRELLIS.2, but TRELLIS.2 must
still receive a normal image file and apply its own official image preprocessing.

## Verification commands

Check package versions:

```bash
conda run -n trellis2 python -c "import PIL, imageio, trimesh, transformers, timm, torch, flash_attn; print({'pillow': PIL.__version__, 'imageio': imageio.__version__, 'trimesh': trimesh.__version__, 'transformers': transformers.__version__, 'timm': timm.__version__, 'torch': torch.__version__, 'flash_attn': flash_attn.__version__})"
```

Check DINOv3 layout expected by TRELLIS:

```bash
conda run -n trellis2 python -c "from transformers import DINOv3ViTModel; m = DINOv3ViTModel.from_pretrained('facebook/dinov3-vitb16-pretrain-lvd1689m'); print(hasattr(m, 'layer'))"
```

Check runtime repo cleanliness:

```bash
git -C .runtime/TRELLIS.2 status --short
```

Expected result:

- no modified tracked files
- no service-side patching inside the upstream runtime
