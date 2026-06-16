from __future__ import annotations

import argparse
import json
import os
import traceback
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image
from torch.nn import functional as F

RUNTIME_LOCK_PROFILE = "trellis2_official_lock_2026_04_22_v1"


def _collect_mesh_stats(mesh_path: Path) -> dict[str, Any]:
    try:
        import trimesh

        loaded = trimesh.load(mesh_path, force="mesh")
        vertices = int(len(getattr(loaded, "vertices", [])))
        faces = int(len(getattr(loaded, "faces", [])))
        bounds = np.asarray(getattr(loaded, "bounds", np.zeros((2, 3), dtype=np.float32)), dtype=np.float32)
        extents = bounds[1] - bounds[0] if bounds.shape == (2, 3) else np.zeros((3,), dtype=np.float32)
        bbox_valid = bool(np.all(np.isfinite(extents)) and np.linalg.norm(extents) > 0.0)
        return {
            "vertex_count": vertices,
            "face_count": faces,
            "bbox_valid": bbox_valid,
            "bbox_size": [float(value) for value in extents.tolist()],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "vertex_count": 0,
            "face_count": 0,
            "bbox_valid": False,
            "bbox_size": [0.0, 0.0, 0.0],
            "stats_error": str(exc),
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRELLIS.2 helper for ai-3d-service pipeline.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-mesh", required=True)
    parser.add_argument("--summary-path", required=True)
    parser.add_argument("--runtime-log", required=True)
    parser.add_argument("--model-path", default="microsoft/TRELLIS.2-4B")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--resolution", default="1024")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--mesh-simplify-faces", type=int, default=16777216)
    parser.add_argument("--low-vram", action="store_true")
    return parser


def _extract_mesh(outputs: Any) -> Any:
    if isinstance(outputs, tuple) and outputs:
        outputs = outputs[0]
    if isinstance(outputs, (list, tuple)) and outputs:
        return outputs[0]
    return outputs


def _export_mesh(mesh: Any, output_mesh_path: Path, *, attr_layout: Any, grid_size: int) -> None:
    output_mesh_path.parent.mkdir(parents=True, exist_ok=True)
    import o_voxel

    decimation_target = int(os.getenv("TRELLIS_DECIMATION_TARGET", "500000"))
    texture_size = int(os.getenv("TRELLIS_TEXTURE_SIZE", "2048"))
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=attr_layout,
        grid_size=grid_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=decimation_target,
        texture_size=texture_size,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        use_tqdm=True,
    )
    glb.export(output_mesh_path, extension_webp=True)


def _run(args: argparse.Namespace) -> dict[str, Any]:
    import torch

    from trellis2.pipelines import Trellis2ImageTo3DPipeline

    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"

    started = perf_counter()
    input_image_path = Path(args.input_image).expanduser().resolve()
    output_mesh_path = Path(args.output_mesh).expanduser().resolve()
    summary_path = Path(args.summary_path).expanduser().resolve()
    runtime_log_path = Path(args.runtime_log).expanduser().resolve()
    runtime_log_path.parent.mkdir(parents=True, exist_ok=True)
    output_mesh_path.parent.mkdir(parents=True, exist_ok=True)

    pipeline_type = {
        "512": "512",
        "1024": "1024_cascade",
        "1536": "1536_cascade",
    }.get(str(args.resolution).strip(), "512")

    runtime_lines = [
        "TRELLIS.2 Runtime Helper",
        f"runtime_lock_profile={RUNTIME_LOCK_PROFILE}",
        f"input_image={input_image_path}",
        f"output_mesh={output_mesh_path}",
        f"model_path={args.model_path}",
        f"device={device}",
        f"pipeline_type={pipeline_type}",
        f"attention_backend={os.getenv('ATTN_BACKEND', 'flash_attn')}",
        f"sparse_attention_backend={os.getenv('SPARSE_ATTN_BACKEND', os.getenv('ATTN_BACKEND', 'flash_attn'))}",
        f"sparse_conv_backend={os.getenv('SPARSE_CONV_BACKEND', 'flex_gemm')}",
        f"seed={args.seed}",
        f"decimation_target={os.getenv('TRELLIS_DECIMATION_TARGET', '500000')}",
        f"texture_size={os.getenv('TRELLIS_TEXTURE_SIZE', '2048')}",
        f"ss_steps={os.getenv('TRELLIS_SS_STEPS', '12')}",
        f"shape_steps={os.getenv('TRELLIS_SHAPE_STEPS', '12')}",
        f"tex_steps={os.getenv('TRELLIS_TEX_STEPS', '12')}",
        f"low_vram={args.low_vram}",
    ]

    try:
        image = Image.open(input_image_path).convert("RGBA")
        pipeline = Trellis2ImageTo3DPipeline.from_pretrained(args.model_path)
        if device.startswith("cuda"):
            pipeline.cuda()
        processed_image = pipeline.preprocess_image(image)
        processed_input_path = output_mesh_path.parent / "trellis_processed_input.png"
        processed_image.save(processed_input_path)

        outputs, latents = pipeline.run(
            processed_image,
            seed=args.seed,
            preprocess_image=False,
            sparse_structure_sampler_params={
                "steps": int(os.getenv("TRELLIS_SS_STEPS", "12")),
                "guidance_strength": float(os.getenv("TRELLIS_SS_GUIDANCE_STRENGTH", "7.5")),
                "guidance_rescale": float(os.getenv("TRELLIS_SS_GUIDANCE_RESCALE", "0.7")),
                "rescale_t": float(os.getenv("TRELLIS_SS_RESCALE_T", "5.0")),
            },
            shape_slat_sampler_params={
                "steps": int(os.getenv("TRELLIS_SHAPE_STEPS", "12")),
                "guidance_strength": float(os.getenv("TRELLIS_SHAPE_GUIDANCE_STRENGTH", "7.5")),
                "guidance_rescale": float(os.getenv("TRELLIS_SHAPE_GUIDANCE_RESCALE", "0.5")),
                "rescale_t": float(os.getenv("TRELLIS_SHAPE_RESCALE_T", "3.0")),
            },
            tex_slat_sampler_params={
                "steps": int(os.getenv("TRELLIS_TEX_STEPS", "12")),
                "guidance_strength": float(os.getenv("TRELLIS_TEX_GUIDANCE_STRENGTH", "1.0")),
                "guidance_rescale": float(os.getenv("TRELLIS_TEX_GUIDANCE_RESCALE", "0.0")),
                "rescale_t": float(os.getenv("TRELLIS_TEX_RESCALE_T", "3.0")),
            },
            pipeline_type=pipeline_type,
            return_latent=True,
        )
        if not isinstance(latents, tuple) or len(latents) != 3:
            raise RuntimeError("TRELLIS.2 did not return the expected latent state.")

        _preview_mesh = _extract_mesh(outputs)
        if _preview_mesh is None:
            raise RuntimeError("TRELLIS.2 returned no preview mesh object.")

        shape_slat, tex_slat, res = latents
        mesh = pipeline.decode_latent(shape_slat, tex_slat, res)[0]
        _export_mesh(mesh, output_mesh_path, attr_layout=pipeline.pbr_attr_layout, grid_size=res)
        runtime_sec = round(float(perf_counter() - started), 3)
        mesh_stats = _collect_mesh_stats(output_mesh_path)
        payload = {
            "status": "completed",
            "input_image": str(input_image_path),
            "processed_input_image": str(processed_input_path),
            "output_mesh": str(output_mesh_path),
            "model_path": args.model_path,
            "device": device,
            "resolution": str(args.resolution),
            "pipeline_type": pipeline_type,
            "runtime_lock_profile": RUNTIME_LOCK_PROFILE,
            "seed": int(args.seed),
            "decimation_target": int(os.getenv("TRELLIS_DECIMATION_TARGET", "500000")),
            "texture_size": int(os.getenv("TRELLIS_TEXTURE_SIZE", "2048")),
            "official_app_parity": True,
            "runtime_sec": runtime_sec,
            "mesh_stats": mesh_stats,
        }
        _write_json(summary_path, payload)
        runtime_lines.extend(
            [
                "status=completed",
                f"runtime_sec={runtime_sec}",
                f"mesh_stats={json.dumps(mesh_stats, ensure_ascii=False)}",
            ]
        )
        return payload
    except Exception as exc:  # noqa: BLE001
        runtime_sec = round(float(perf_counter() - started), 3)
        payload = {
            "status": "failed",
            "input_image": str(input_image_path),
            "output_mesh": str(output_mesh_path),
            "model_path": args.model_path,
            "device": device,
            "runtime_sec": runtime_sec,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        _write_json(summary_path, payload)
        runtime_lines.extend(
            [
                "status=failed",
                f"runtime_sec={runtime_sec}",
                f"error={exc}",
                payload["traceback"],
            ]
        )
        raise
    finally:
        runtime_log_path.write_text("\n".join(runtime_lines) + "\n", encoding="utf-8")
        try:
            if args.low_vram:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    args = build_parser().parse_args()
    _run(args)


if __name__ == "__main__":
    main()
