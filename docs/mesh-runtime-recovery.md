# Mesh runtime recovery checkpoint

## 2026-10-17 current runtime

Ubuntu-22.04 is running without a Windows restart. Native Windows SAM3 and FastVLM use `.runtime/scene312-env`; TRELLIS uses `/opt/prism/trellis2` inside WSL, the clean official checkout at `/opt/prism/TRELLIS.2`, and the strict PyTorch 2.6.0/cu124 runtime lock. `scripts/start-mesh-wsl.ps1` launches the original generic backend/worker; `-ProbeOnly` runs the official-runtime preflight. `scripts/setup_trellis_wsl.sh` and `scripts/link_wsl_model_cache.py` document installation and reuse of local weights. CUDA toolkit installation did not change the Windows driver or GPU power settings.

A 12GiB WSL swap file supports model loading with the default VM memory allowance. The bridge activates it when present; no reboot is requested. Required cuMesh, flex_gemm, o_voxel, nvdiffrast and flash-attn extensions are installed. The optional nvdiffrec build failed; it is not used by the successfully exercised textured GLB export path.

The first actual run produced a 17MB textured GLB, but Windows completion failed because the helper reported a Linux `/mnt/c/...` path. The wrapper now falls back to its explicit shared output destination when the subprocess path is not accessible from the host. The failed job remains preserved as failed. Fresh end-to-end validation is recorded separately in `twin-real-mesh-run.json` once complete.

Fresh job `job_000002` completed through the generic UI with real SAM3, FastVLM and TRELLIS inference. TRELLIS runtime was 323.729s; the standalone downloaded GLB is 17,123,724 bytes and its binary header was verified. The initial viewer check exposed a classic-script/ES-module mismatch in the local Meshopt decoder; the npm synchronization now emits its required global-script adapter. The follow-up standalone viewer/download check has zero browser errors and zero external requests. The initial error remains in the run record for traceability.

FastVLM ran on CUDA but its JSON was truncated and the existing parser used `invalid_json_fallback`; category/material fields are fallback observations, not independent verification. The small source cutout also produces incomplete hidden/bottom geometry in the generated mesh. The videos use the actual result, not a replacement prop, and make no reconstruction-accuracy claim. Generic missing metadata no longer falls back to an unrelated dinosaur description.

Native job storage now uses portable portalocker locking; its multiprocess/exception-release test passes. The generic result viewer and all Draco/Basis/Meshopt decoders are installed locally, with pinned npm packages under `frontend/vendor-package`; the existing scene viewer's Three.js version is unchanged. Rebuild vendor files with `node scripts/sync-local-viewer.mjs` from `frontend` after installing that vendor package.

## Historical checkpoint (superseded by the runtime above)

The native Windows scene environment runs FastVLM-0.5B through the existing helper. Model weights are under `.runtime/weights/FastVLM-0.5B`. A SAM3-selected chair cutout passed real CUDA inference with valid JSON and category `chair` (512-token limit); see `mesh-recovery-check.json`. The earlier whole-scene groceries smoke test produced a correct SUV/grocery description but truncated metadata, so only the selected-chair test counts as FastVLM recovery. Neither test verifies TRELLIS mesh generation.

Downloaded model directories total approximately 20.9 GB: TRELLIS.2-4B 16.24 GB, FastVLM 1.53 GB, DINOv3 1.21 GB, RMBG 1.77 GB and sparse decoder 0.15 GB. Official TRELLIS.2 source commit: `75fbf0183001ed9876c8dbb35de6b68552ee08bd`.

TRELLIS.2 official code is tested on Linux and requires compiled CUDA extensions. The repository's existing strict lock requires PyTorch 2.6.0+cu124, torchvision 0.21.0+cu124, transformers 4.57.3, timm 1.0.22, trimesh 4.10.1, imageio 2.37.2 and flash-attn 2.7.3. The scene environment is intentionally not substituted for this lock.

`C:\Program Files\WSL\wsl.exe --install --distribution Ubuntu-22.04 --no-launch --web-download` returned that changes require a system restart. No reboot was initiated. No Ubuntu distribution can currently run; mesh generation has not passed end to end.

After the user's Windows restart:

1. Run `& 'C:\Program Files\WSL\wsl.exe' --status` and `--list --verbose`. Complete Ubuntu-22.04 installation if not registered. If virtualization remains unavailable, inspect firmware virtualization and Virtual Machine Platform before attempting inference.
2. In Ubuntu install Conda and CUDA toolkit 12.4 (toolkit only, use Windows GPU driver). Follow `docs/trellis2_runtime_lock.md`; install the official setup components without modifying upstream sources.
3. Reuse downloaded TRELLIS.2-4B, DINOv3, RMBG-2.0 and TRELLIS-image-large decoder weights from the Windows workspace. Configure runtime paths for Linux, not Windows drive paths.
4. Install the existing service and SAM3 runtime, configure real inference in a local `.env`, then execute `scripts/dev/run_image_stack.sh`. Do not use mock output as validation.
5. Upload a new photograph, choose an object, generate `storage/outputs/JOB/object_mesh.glb`, then click **3D 공간에 배치** in the result view. The scene workspace also lists completed GLBs and copies/normalizes them into its own asset storage, leaving source outputs intact.

Sources: [official TRELLIS.2 installation](https://github.com/microsoft/TRELLIS.2#-installation), [Microsoft WSL installation](https://learn.microsoft.com/en-us/windows/wsl/install), [official FastVLM model](https://huggingface.co/apple/FastVLM-0.5B).
