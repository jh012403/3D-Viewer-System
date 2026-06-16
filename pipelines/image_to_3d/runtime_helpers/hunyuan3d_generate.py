from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image


def _collect_mesh_stats(mesh: Any) -> dict[str, Any]:
    try:
        vertex_count = int(len(getattr(mesh, "vertices", [])))
    except Exception:  # noqa: BLE001
        vertex_count = 0
    try:
        face_count = int(len(getattr(mesh, "faces", [])))
    except Exception:  # noqa: BLE001
        face_count = 0
    try:
        bounds = np.asarray(getattr(mesh, "bounds", np.zeros((2, 3), dtype=np.float32)), dtype=np.float32)
        if bounds.shape == (2, 3):
            extents = bounds[1] - bounds[0]
        else:
            extents = np.zeros((3,), dtype=np.float32)
        bbox_valid = bool(np.all(np.isfinite(extents)) and np.linalg.norm(extents) > 0.0)
        bbox_size = [float(value) for value in extents.tolist()]
    except Exception:  # noqa: BLE001
        bbox_valid = False
        bbox_size = [0.0, 0.0, 0.0]
    return {
        "vertex_count": vertex_count,
        "face_count": face_count,
        "bbox_valid": bbox_valid,
        "bbox_size": bbox_size,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hunyuan3D helper for ai-3d-service pipeline.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-mesh", required=True)
    parser.add_argument("--summary-path", required=True)
    parser.add_argument("--runtime-log", required=True)
    parser.add_argument("--model-path", default="tencent/Hunyuan3D-2mini")
    parser.add_argument("--subfolder", default="hunyuan3d-dit-v2-mini-turbo")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--num-inference-steps", type=int, default=28)
    parser.add_argument("--guidance-scale", type=float, default=5.5)
    parser.add_argument("--octree-resolution", type=int, default=320)
    parser.add_argument("--mc-level", type=float, default=0.0)
    parser.add_argument("--mc-algo", default="mc")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-faces", type=int, default=120000)
    parser.add_argument("--enable-flashvdm", action="store_true")
    parser.add_argument("--enable-postprocess", action="store_true")
    parser.add_argument("--enable-tex", action="store_true")
    parser.add_argument("--tex-model-path", default="tencent/Hunyuan3D-2")
    parser.add_argument("--low-vram", action="store_true")
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from hy3dgen.shapegen import (  # type: ignore[import-not-found]
        DegenerateFaceRemover,
        FaceReducer,
        FloaterRemover,
        Hunyuan3DDiTFlowMatchingPipeline,
    )

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"

    started = perf_counter()
    runtime_log_path = Path(args.runtime_log).expanduser().resolve()
    input_image_path = Path(args.input_image).expanduser().resolve()
    output_mesh_path = Path(args.output_mesh).expanduser().resolve()
    summary_path = Path(args.summary_path).expanduser().resolve()
    output_mesh_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_log_path.parent.mkdir(parents=True, exist_ok=True)

    runtime_lines = [
        "Hunyuan3D Runtime Helper",
        f"input_image={input_image_path}",
        f"output_mesh={output_mesh_path}",
        f"model_path={args.model_path}",
        f"subfolder={args.subfolder}",
        f"device={device}",
        f"num_inference_steps={args.num_inference_steps}",
        f"guidance_scale={args.guidance_scale}",
        f"octree_resolution={args.octree_resolution}",
        f"enable_flashvdm={args.enable_flashvdm}",
        f"enable_tex={args.enable_tex}",
    ]

    try:
        image = Image.open(input_image_path).convert("RGBA")

        pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            args.model_path,
            subfolder=args.subfolder,
            use_safetensors=True,
            device=device,
        )
        if args.enable_flashvdm:
            pipeline.enable_flashvdm(mc_algo=args.mc_algo)

        generator = None
        if args.seed >= 0:
            generator = torch.Generator(device=device).manual_seed(args.seed)

        mesh = pipeline(
            image=image,
            num_inference_steps=max(1, args.num_inference_steps),
            guidance_scale=args.guidance_scale,
            octree_resolution=max(128, args.octree_resolution),
            mc_level=args.mc_level,
            mc_algo=args.mc_algo,
            generator=generator,
            output_type="trimesh",
            enable_pbar=False,
        )[0]

        if args.enable_postprocess:
            mesh = FloaterRemover()(mesh)
            mesh = DegenerateFaceRemover()(mesh)
            mesh = FaceReducer()(mesh, max_facenum=max(10000, args.max_faces))

        if args.enable_tex:
            from hy3dgen.texgen import Hunyuan3DPaintPipeline  # type: ignore[import-not-found]

            tex_pipeline = Hunyuan3DPaintPipeline.from_pretrained(args.tex_model_path)
            mesh = tex_pipeline(mesh, image=image)

        mesh.export(output_mesh_path)
        mesh_stats = _collect_mesh_stats(mesh)
        runtime_sec = round(float(perf_counter() - started), 3)

        payload: dict[str, Any] = {
            "status": "completed",
            "input_image": str(input_image_path),
            "output_mesh": str(output_mesh_path),
            "model_path": args.model_path,
            "subfolder": args.subfolder,
            "device": device,
            "num_inference_steps": int(args.num_inference_steps),
            "guidance_scale": float(args.guidance_scale),
            "octree_resolution": int(args.octree_resolution),
            "mc_algo": args.mc_algo,
            "enable_flashvdm": bool(args.enable_flashvdm),
            "enable_postprocess": bool(args.enable_postprocess),
            "enable_tex": bool(args.enable_tex),
            "runtime_sec": runtime_sec,
            "mesh_stats": mesh_stats,
        }
        _write_json(summary_path, payload)
        runtime_lines.extend(
            [
                f"status=completed",
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
            "subfolder": args.subfolder,
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
