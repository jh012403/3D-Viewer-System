# Local scene workspace

Run `powershell -ExecutionPolicy Bypass -File scripts/start-scene.ps1` from the repository. Open http://127.0.0.1:5173/scene.html?scene=sunroom . The script reports its process IDs for shutdown. The original mesh service is separate and unchanged.

The default checked demonstration mode loads local PLY, geometry, photographs and graph JSON only. Four cached backgrounds are sunroom, ceramics, hall and groceries (d4f646fcc79650d6). Uncheck demonstration mode to generate a new background and graph. Select an existing GLB, click a visible horizontal surface, then use move/rotate/scale and Save. Export contains an original-camera PNG and graph JSON with model and geometry limitations.

The library displays descriptive Korean names. Initial previews use a small edge crop; original-camera exports retain full framing. Orbit is limited per scene: sunroom 0.5°, ceramics 3°, hall and groceries 1.5° each side. GLB category defaults to filename-based automatic selection; chairs use the existing 1m normalization policy. Generated meshes can be selected directly from the scene's results list or opened with the result page's placement link. Mesh runtime recovery still requires a Windows restart; see [recovery checkpoint](mesh-runtime-recovery.md).

## Environment

Python 3.12 is the supported combined environment: SAM3 requires NumPy <2, which conflicts with the original Python 3.13 environment. Install CUDA torch 2.11.0 / torchvision 0.26.0 from the official cu128 index, then `pip install -r pipelines/scene/requirements-windows.txt` in `.runtime/scene312-env`. Existing SHARP, DAV2 and SAM3 checkouts and local weights are required. SAM3 requires an authorized Hugging Face account for its initial download; never store a token in this repository.

The legacy Python 3.13 environment produced the first 15-photo evaluation; its SAM3 NumPy requirement is unsatisfied despite successful inference. Retained for traceability, not the default launch environment. WSL setup still requires a Windows restart; native Windows inference does not require that restart. GPU power settings are user-managed.

## Rebuilding caches and evaluating

Use `python -m pipelines.scene.build IMAGE --output storage/scene_cache/SCENE` for SHARP and metric depth. `python -m pipelines.scene.graph docs/scene-evaluation-set.json` generates names, masks, visible-surface boxes and geometric relations for the separate 15-photo set. Existing generated graphs are reused. `python -m pipelines.scene.evaluate` writes the reference audit table. Cache files are large local ignored assets; their hashes and provenance are recorded in `scene-cache-manifest.json`.

## Accuracy limits

See [the 15-photo reference audit](scene-evaluation.md). Selected correspondence is 33/36 and selected relation recovery 11/16. These are assistant-annotated provisional subsets, not full precision or independent ground truth. Previous user-reported 14/36 and 9/10 use unavailable different data; no valid improvement claim is possible.

Remaining errors include reflected objects, object parts, missed support surfaces and contact relations lost to monocular depth/axis-aligned box uncertainty. A category's VLM attributes do not establish the appearance of each instance. Gravity is assumed from the camera vertical. Transparent glass and hidden surfaces cannot be reconstructed reliably. The radial shadow replaces unavailable original shadow code.

If local naming quality remains insufficient, a hosted vision model can replace only the names/attributes provider after choosing a service and approving photo transmission. It must not produce spatial relations. A larger VLM alone will not fix depth/contact geometry errors. A full accuracy claim requires independent exhaustive object and relation annotations.

Original generated cases, rm06_U01 and the original 15 backgrounds have no available backup. TRELLIS.2 and FastVLM runtime weights are still absent; existing mesh generation has not been reinstalled or changed by this scene workspace.
