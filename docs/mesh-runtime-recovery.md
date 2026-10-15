# Mesh runtime recovery checkpoint

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
