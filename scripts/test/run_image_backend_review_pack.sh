#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import importlib.util
import math
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.env import load_project_env


ROOT = Path.cwd()
REPORTS_DIR = ROOT / "storage" / "test_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build human review pack for image reconstruction backend comparison."
    )
    parser.add_argument(
        "--samples",
        nargs="+",
        help="Sample directory, .sample.json manifest, or image path list.",
        default=[],
    )
    parser.add_argument(
        "--heads",
        nargs="+",
        default=["trellis"],
        help="Reconstruction heads to compare in order.",
    )
    parser.add_argument(
        "--output-root",
        default="storage/review_packs/image_backend_comparison",
        help="Root directory for generated review pack.",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Optional explicit timestamp. Defaults to UTC timestamp.",
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="Skip viewer_screenshot generation and always copy thumbnail.",
    )
    return parser.parse_args()


def runtime_preflight() -> None:
    required_modules = ("trimesh", "PIL", "numpy")
    missing = [module for module in required_modules if importlib.util.find_spec(module) is None]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(
            "Missing required runtime modules for review-pack generation: "
            f"{joined}. Run this script with the project conda env, for example: "
            "`conda run -n ai3d-mvp bash scripts/test/run_image_backend_review_pack.sh ...`"
        )


def normalize_head_name(head: str) -> str:
    normalized = (head or "").strip().lower().replace("-", "_")
    if normalized in {"trellis", "trellis2", "trellis_2"}:
        return "trellis"
    if normalized in {"hunyuan3d", "hunyuan_3d", "hunyuan3d_2", "hunyuan"}:
        return "hunyuan3d"
    # Project policy: force all legacy/removed heads to trellis.
    return "trellis"


def safe_name(value: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip().lower())
    normalized = normalized.strip("_-")
    return normalized or "sample"


def parse_sample_json(json_path: Path) -> tuple[str, Path, dict[str, Any]] | None:
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    source = payload.get("source_asset")
    if not source:
        return None
    sample_path = Path(source)
    if not sample_path.is_absolute():
        sample_path = (ROOT / sample_path).resolve()
    if not sample_path.exists():
        return None

    name = str(payload.get("sample_name") or json_path.stem)
    return safe_name(name), sample_path, payload


def discover_samples(raw_values: list[str]) -> list[tuple[str, Path, dict[str, Any]]]:
    resolved: list[tuple[str, Path, dict[str, Any]]] = []
    seen_input: set[Path] = set()

    if not raw_values:
        defaults = [
            "storage/uploads/job_000050/input_image.jpg",
            "storage/uploads/job_000049/input_image.jpg",
            "storage/uploads/job_000031/input_image.jpg",
            "storage/uploads/job_000046/input_image.jpg",
        ]
        raw_values = defaults

    def add_item(label: str, path: Path, meta: dict[str, Any] | None) -> None:
        if not path.exists():
            print(f"[warn] sample not found: {path}", file=sys.stderr)
            return
        if path in seen_input:
            return
        seen_input.add(path)
        resolved.append((safe_name(label), path, meta or {}))

    for raw in raw_values:
        target = Path(raw).expanduser()
        if not target.exists():
            print(f"[warn] sample path not found: {target}", file=sys.stderr)
            continue

        if target.is_dir():
            json_samples = sorted(target.rglob("*.sample.json"))
            image_samples = sorted(
                p
                for p in target.rglob("*")
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
            )
            for sample_file in json_samples:
                parsed = parse_sample_json(sample_file)
                if parsed is None:
                    print(f"[warn] invalid sample manifest: {sample_file}", file=sys.stderr)
                    continue
                add_item(*parsed)

            if not json_samples:
                for img in image_samples:
                    add_item(img.stem, img, {"source_path": str(img), "input_type": "image"})
            continue

        if target.suffix.lower() == ".json":
            parsed = parse_sample_json(target)
            if parsed is None:
                print(f"[warn] invalid sample manifest: {target}", file=sys.stderr)
                continue
            add_item(*parsed)
            continue

        add_item(target.stem, target, {"source_path": str(target), "input_type": "image"})

    if not resolved:
        raise SystemExit("No valid samples were found.")
    return resolved


def ensure_image_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_or_fallback(source: Path | None, destination: Path, *, fallback_text: str = "missing") -> dict[str, Any]:
    if source is None or not source.exists():
        destination.write_text(f"{fallback_text}: unavailable\n", encoding="utf-8")
        return {
            "status": "missing",
            "source": str(source) if source else None,
            "reason": "source_not_found",
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "status": "copied",
        "source": str(source),
        "reason": None,
    }


def choose_mesh_file(output_dir: Path) -> tuple[Path | None, str]:
    direct = output_dir / "object_mesh.glb"
    if direct.exists():
        return direct, "object_mesh.glb"
    for ext in (".glb", ".obj", ".stl", ".ply"):
        candidate = output_dir / f"object_mesh{ext}"
        if candidate.exists():
            return candidate, f"object_mesh{ext}"
    wildcard = sorted(output_dir.glob("object_mesh.*"))
    if wildcard:
        return wildcard[0], wildcard[0].name
    return None, "missing"


def select_segmented_input_source(metadata: dict[str, Any]) -> Path | None:
    image_preprocess = metadata.get("image_preprocess") if isinstance(metadata.get("image_preprocess"), dict) else {}
    candidates = [
        image_preprocess.get("normalized_foreground_file"),
        metadata.get("multiview_input_file"),
        metadata.get("foreground_file"),
        metadata.get("normalized_input_file"),
        metadata.get("mask_file"),
    ]
    for raw_path in candidates:
        if not raw_path:
            continue
        candidate = Path(str(raw_path))
        if not candidate.is_absolute():
            candidate = (ROOT / candidate).resolve()
        if candidate.exists():
            return candidate
    return None


def select_mask_source(metadata: dict[str, Any]) -> Path | None:
    image_preprocess = metadata.get("image_preprocess") if isinstance(metadata.get("image_preprocess"), dict) else {}
    candidates = [
        metadata.get("mask_file"),
        image_preprocess.get("normalized_mask_file"),
    ]
    for raw_path in candidates:
        if not raw_path:
            continue
        candidate = Path(str(raw_path))
        if not candidate.is_absolute():
            candidate = (ROOT / candidate).resolve()
        if candidate.exists():
            return candidate
    return None


def _fill_holes(binary_mask: np.ndarray) -> np.ndarray:
    h, w = binary_mask.shape
    inverse = ~binary_mask
    visited = np.zeros((h, w), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    def push(y: int, x: int) -> None:
        if 0 <= y < h and 0 <= x < w and inverse[y, x] and not visited[y, x]:
            visited[y, x] = True
            queue.append((y, x))

    for x in range(w):
        push(0, x)
        push(h - 1, x)
    for y in range(h):
        push(y, 0)
        push(y, w - 1)

    while queue:
        y, x = queue.popleft()
        push(y - 1, x)
        push(y + 1, x)
        push(y, x - 1)
        push(y, x + 1)

    holes = inverse & (~visited)
    return binary_mask | holes


def render_sam2_missing_regions_overlay(
    *,
    input_image_path: Path,
    mask_image_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if not input_image_path.exists() or not mask_image_path.exists():
        return {"status": "missing", "reason": "input_or_mask_missing"}

    with Image.open(input_image_path) as input_image:
        rgb = np.asarray(input_image.convert("RGB"), dtype=np.uint8)
    with Image.open(mask_image_path) as mask_image:
        mask_bool = np.asarray(mask_image.convert("L"), dtype=np.uint8) > 127

    if mask_bool.size == 0:
        return {"status": "failed", "reason": "empty_mask"}

    filled_mask = _fill_holes(mask_bool)
    missing_regions = filled_mask & (~mask_bool)

    overlay = rgb.astype(np.float32)
    # Segmented area tint (cyan) to make selected foreground easy to read.
    overlay[mask_bool] = (overlay[mask_bool] * 0.75) + np.array([30.0, 235.0, 255.0]) * 0.25
    # Missing/internal-hole area tint (red) for quick QA.
    overlay[missing_regions] = (overlay[missing_regions] * 0.25) + np.array([255.0, 64.0, 64.0]) * 0.75

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(overlay, 0, 255).astype(np.uint8), mode="RGB").save(output_path)

    missing_ratio = float(missing_regions.mean()) if missing_regions.size else 0.0
    return {
        "status": "generated",
        "missing_ratio": round(missing_ratio, 6),
    }


def generate_screenshot(mesh_path: Path, out_path: Path) -> dict[str, Any]:
    def load_preview_mesh(path: Path):
        import trimesh

        loaded = trimesh.load(path, force="scene")
        if isinstance(loaded, trimesh.Trimesh):
            return loaded
        if isinstance(loaded, trimesh.Scene):
            try:
                merged = loaded.to_geometry()
                if isinstance(merged, trimesh.Trimesh):
                    return merged
            except Exception:
                pass
            # Fallback for older trimesh behaviors.
            merged = loaded.dump(concatenate=True)
            if isinstance(merged, trimesh.Trimesh):
                return merged
        raise RuntimeError(f"unsupported mesh container: {type(loaded).__name__}")

    def render_projection(path: Path, output: Path) -> dict[str, Any]:
        mesh = load_preview_mesh(path)
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            return {"status": "failed", "method": "software_projection", "reason": "mesh_empty"}

        sample_count = int(min(35000, max(10000, len(mesh.vertices) * 2)))
        points, _ = mesh.sample(sample_count, return_index=True)
        if points.size == 0:
            return {"status": "failed", "method": "software_projection", "reason": "sample_empty"}
        points = points.astype(np.float64)

        center = points.mean(axis=0)
        points -= center
        span = np.ptp(points, axis=0)
        scale = float(np.max(span))
        if not np.isfinite(scale) or scale <= 1e-9:
            scale = 1.0
        points /= scale

        yaw = math.radians(35.0)
        pitch = math.radians(20.0)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cx, sx = math.cos(pitch), math.sin(pitch)
        rot_y = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
        rot_x = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float64)
        rotated = points @ (rot_x @ rot_y).T

        x = rotated[:, 0]
        y = rotated[:, 1]
        z = rotated[:, 2]

        width = 1024
        height = 1024
        padding = 0.12
        extent = max(float(np.max(np.abs(x))), float(np.max(np.abs(y))), 1e-6)
        pixel_scale = (1.0 - padding * 2.0) * (width / 2.0) / extent

        u = (x * pixel_scale + width / 2.0).astype(np.int32)
        v = (-y * pixel_scale + height / 2.0).astype(np.int32)
        in_bounds = (u >= 1) & (u < width - 1) & (v >= 1) & (v < height - 1)
        u = u[in_bounds]
        v = v[in_bounds]
        z = z[in_bounds]
        if z.size == 0:
            return {"status": "failed", "method": "software_projection", "reason": "projection_empty"}

        zmin, zmax = float(np.min(z)), float(np.max(z))
        if not np.isfinite(zmin) or not np.isfinite(zmax):
            return {"status": "failed", "method": "software_projection", "reason": "projection_invalid"}
        if zmax - zmin < 1e-9:
            tone = np.full_like(z, 0.85)
        else:
            tone = 0.35 + 0.65 * ((z - zmin) / (zmax - zmin))

        image = np.zeros((height, width, 3), dtype=np.uint8)
        for row in range(height):
            t = row / max(height - 1, 1)
            image[row, :, 0] = int(11 + 20 * t)
            image[row, :, 1] = int(20 + 34 * t)
            image[row, :, 2] = int(32 + 50 * t)

        z_buffer = np.full((height, width), -1e9, dtype=np.float64)
        order = np.argsort(z)
        base = np.array([95.0, 210.0, 230.0], dtype=np.float64)
        for idx in order:
            px = u[idx]
            py = v[idx]
            depth = z[idx]
            if depth >= z_buffer[py, px]:
                z_buffer[py, px] = depth
                color = np.clip(base * tone[idx], 0, 255).astype(np.uint8)
                image[py, px] = color
                image[py - 1, px] = color
                image[py + 1, px] = color
                image[py, px - 1] = color
                image[py, px + 1] = color

        output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(image, mode="RGB").save(output)
        return {"status": "generated", "method": "software_projection"}

    if not mesh_path.exists():
        return {"status": "missing", "method": "none", "reason": "mesh_missing"}

    try:
        import trimesh

        scene = trimesh.load(mesh_path, force="scene")
        png = scene.save_image()
        if png is None:
            soft = render_projection(mesh_path, out_path)
            if soft.get("status") == "generated":
                soft["fallback_from"] = "trimesh_render_returned_empty"
            return soft
        out_path.write_bytes(png)
        return {"status": "generated", "method": "trimesh"}
    except Exception as exc:
        soft = render_projection(mesh_path, out_path)
        if soft.get("status") == "generated":
            soft["fallback_from"] = "trimesh_headless_error"
            soft["trimesh_error"] = str(exc)
            return soft
        return {
            "status": "failed",
            "method": "trimesh+software_projection",
            "reason": str(exc),
            "software_reason": soft.get("reason"),
        }


def run_head(
    sample: tuple[str, Path, dict[str, Any]],
    head: str,
    pack_sample_dir: Path,
    index: int,
    head_index: int,
    sample_position: int,
    no_screenshot: bool,
) -> dict[str, Any]:
    sample_label, sample_path, sample_meta = sample
    head_dir = pack_sample_dir / head
    head_dir.mkdir(parents=True, exist_ok=True)

    job_id = f"review_{sample_label}_{head}_{sample_position:02d}_{head_index:02d}_{index:03d}"
    output_dir = ROOT / "storage" / "outputs" / job_id
    preview_dir = ROOT / "storage" / "previews" / job_id
    temp_dir = ROOT / "storage" / "temp" / job_id

    for directory in (output_dir, preview_dir, temp_dir):
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
    for directory in (output_dir, preview_dir, temp_dir):
        directory.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["AI3D_MOCK_MODE"] = "false"
    env["IMAGE_RECON_HEAD"] = head
    env["AI3D_IMAGE_QUALITY_MODE"] = "high_quality"
    # stable runtime cache locations for rembg/pymatting/numba dependent heads.
    runtime_cache_root = Path(env.get("AI3D_RUNTIME_CACHE_ROOT", "/tmp/ai3d_cache"))
    env["AI3D_RUNTIME_CACHE_ROOT"] = str(runtime_cache_root)
    env["NUMBA_CACHE_DIR"] = str(runtime_cache_root / "numba")
    env["XDG_CACHE_HOME"] = str(runtime_cache_root / "xdg")
    env["HOME"] = str(runtime_cache_root / "home")
    for folder in [Path(env["AI3D_RUNTIME_CACHE_ROOT"]), Path(env["NUMBA_CACHE_DIR"]), Path(env["XDG_CACHE_HOME"]), Path(env["HOME"])]:
        folder.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pipelines.image_to_3d.cli",
        "--job-id",
        job_id,
        "--input-file",
        str(sample_path),
        "--output-dir",
        str(output_dir),
        "--preview-dir",
        str(preview_dir),
        "--temp-dir",
        str(temp_dir),
        "--mode",
        "real",
        "--requested-reconstruction-head",
        head,
        "--image-quality-mode",
        "high_quality",
    ]

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    runtime_sec = round(time.perf_counter() - started, 3)

    metadata_path = output_dir / "object_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        metadata = {}
    segmented_input_source = select_segmented_input_source(metadata)
    sam2_mask_source = select_mask_source(metadata)

    output = output_dir / "object_mesh.glb"
    raw_mesh_file, raw_mesh_name = choose_mesh_file(output_dir)
    if raw_mesh_file is None:
        print(f"[warn] mesh not found for {head} | {job_id}", file=sys.stderr)

    preview_path = preview_dir / "object_thumbnail.png"

    if raw_mesh_file is not None and raw_mesh_file.suffix.lower() == ".glb":
        mesh_copy_status = copy_or_fallback(raw_mesh_file, head_dir / "mesh.glb", fallback_text="mesh unavailable")
    elif raw_mesh_file is not None and raw_mesh_file.suffix.lower() == ".obj":
        mesh_copy_status = copy_or_fallback(raw_mesh_file, head_dir / "mesh.glb", fallback_text="mesh unavailable")
        # keep source ext for traceability in metadata
        mesh_copy_status["source_format"] = raw_mesh_file.suffix.lower()
    else:
        mesh_copy_status = copy_or_fallback(
            raw_mesh_file,
            head_dir / "mesh.glb",
            fallback_text="mesh unavailable",
        )
    thumbnail_status = copy_or_fallback(preview_path, head_dir / "thumbnail.png", fallback_text="thumbnail unavailable")

    metadata_dest = head_dir / "metadata.json"
    if metadata:
        metadata_dest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    screenshot_path = head_dir / "viewer_screenshot.png"
    screenshot_meta = {"status": "fallback", "method": "thumbnail_copy"}
    if no_screenshot:
        screenshot_meta = {"status": "skipped", "method": "disabled_by_flag"}
        copy_or_fallback(preview_path, screenshot_path, fallback_text="screenshot disabled")
    else:
        render_result = generate_screenshot(raw_mesh_file, screenshot_path) if raw_mesh_file is not None else None
        if render_result and render_result.get("status") == "generated":
            screenshot_meta = render_result
        elif preview_path.exists():
            copy_or_fallback(preview_path, screenshot_path, fallback_text="thumbnail fallback")
            screenshot_meta = {
                "status": "copied_thumbnail",
                "method": "thumbnail_fallback",
                "render_failure": render_result,
            }
        else:
            screenshot_meta = {
                "status": "missing",
                "method": "none",
                "reason": "thumbnail_missing_and_render_failed",
                "render_failure": render_result,
            }

    reconstruction_head = metadata.get("reconstruction_head") if isinstance(metadata.get("reconstruction_head"), dict) else {}
    quality = metadata.get("quality") if isinstance(metadata.get("quality"), dict) else {}
    quality_checks = quality.get("checks") if isinstance(quality.get("checks"), dict) else {}
    quality_metrics = quality.get("metrics") if isinstance(quality.get("metrics"), dict) else {}

    requested_head = metadata.get("requested_reconstruction_head", head)
    resolved_backend = (
        metadata.get("resolved_backend")
        or reconstruction_head.get("used")
        or reconstruction_head.get("resolved_backend")
        or metadata.get("reconstruction_head", {}).get("used")
    )
    mesh_backend = (
        metadata.get("mesh_backend")
        or reconstruction_head.get("mesh_backend")
        or reconstruction_head.get("raw_outputs", {}).get("mesh_backend")
        or resolved_backend
    )

    mesh_file_path = head_dir / "mesh.glb"
    run_metadata = {
        "requested_head": requested_head,
        "resolved_backend": resolved_backend,
        "mesh_backend": mesh_backend,
        "fallback_used": bool(reconstruction_head.get("fallback_used", metadata.get("fallback_used", False))),
        "attempted_heads": reconstruction_head.get("attempted_heads", []),
        "fallback_chain": reconstruction_head.get("fallback_chain", metadata.get("fallback_chain")),
        "runtime_sec": runtime_sec,
        "returncode": completed.returncode,
        "status": "completed" if completed.returncode == 0 and metadata.get("status") == "completed" else "failed",
        "stage": metadata.get("stage"),
        "reason": metadata.get("reason"),
        "user_message": metadata.get("user_message"),
        "mesh_file": str(mesh_file_path),
        "mesh_file_source": str(raw_mesh_file) if raw_mesh_file else None,
        "mesh_source_name": raw_mesh_name,
        "mesh_copy_status": mesh_copy_status,
        "thumbnail": str(head_dir / "thumbnail.png"),
        "thumbnail_status": thumbnail_status,
        "screenshot": str(screenshot_path),
        "viewer_screenshot_status": screenshot_meta,
        "metadata_path": str(metadata_dest),
        "quality_status": metadata.get("quality_status") or quality.get("status"),
        "quality_metrics": quality_metrics,
        "quality_checks": quality_checks,
        "quality_hints": quality.get("hints", []),
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "raw_output_mesh": str(raw_mesh_file) if raw_mesh_file else None,
        "source_path": str(sample_path),
        "sam2_segmented_input_source": str(segmented_input_source) if segmented_input_source else None,
        "sam2_mask_source": str(sam2_mask_source) if sam2_mask_source else None,
    }

    review_pack_metadata = {
        "requested_reconstruction_head": requested_head,
        "resolved_backend": resolved_backend,
        "mesh_backend": mesh_backend,
        "fallback_used": bool(reconstruction_head.get("fallback_used", metadata.get("fallback_used", False))),
        "runtime_sec": runtime_sec,
        "quality_status": metadata.get("quality_status") or quality.get("status"),
        "result_status": run_metadata["status"],
        "reason": run_metadata["reason"],
        "user_message": run_metadata["user_message"],
    }
    (head_dir / "review_backend_metadata.json").write_text(
        json.dumps(review_pack_metadata, indent=2),
        encoding="utf-8",
    )

    return run_metadata


def build_index_markdown(review_root: Path, samples: list[dict[str, Any]], generated_at: str) -> str:
    lines = [
        "# Image Backend Comparison Review Pack",
        "",
        f"- generated_at: `{generated_at}`",
        f"- review_root: `{review_root}`",
        f"- sample_count: {len(samples)}",
        "",
    ]

    for sample in samples:
        sample_name = sample["sample_name"]
        input_rel = sample["input_png"]
        segmented_rel = sample.get("sam2_segmented_input_png")
        mask_rel = sample.get("sam2_mask_png")
        missing_rel = sample.get("sam2_missing_regions_png")
        lines.extend(
            [
                f"## {sample_name}",
                "",
                f"- input: [{input_rel}]({input_rel})",
                f"- sam2 segmented input: [{segmented_rel}]({segmented_rel})" if segmented_rel else "- sam2 segmented input: unavailable",
                f"- sam2 mask: [{mask_rel}]({mask_rel})" if mask_rel else "- sam2 mask: unavailable",
                f"- sam2 missing regions: [{missing_rel}]({missing_rel})" if missing_rel else "- sam2 missing regions: unavailable",
                "",
                "| backend | status | stage | resolved_backend | mesh_backend | fallback_used | runtime_sec | quality | mesh | thumbnail | screenshot |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for result in sample["results"]:
            mesh_rel = Path(result["mesh"]).as_posix()
            thumb_rel = Path(result["thumbnail"]).as_posix()
            shot_rel = Path(result["viewer_screenshot"]).as_posix()
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(result["backend"]),
                        str(result["status"]),
                        str(result["stage"]),
                        str(result["resolved_backend"]),
                        str(result["mesh_backend"]),
                        str(result["fallback_used"]),
                        str(result["runtime_sec"]),
                        str(result["quality_status"]),
                        f"[mesh]({mesh_rel})",
                        f"[thumb]({thumb_rel})",
                        f"[shot]({shot_rel})",
                    ]
                )
                + " |"
            )
        lines.extend(["", "", ""])
    return "\n".join(lines)


def describe_shape(summary: dict[str, Any]) -> str:
    if summary.get("status") != "passed":
        return "failed"
    if not summary.get("checks", {}).get("bbox_valid", True):
        return "invalid_bbox"
    component_count = summary.get("metrics", {}).get("component_count")
    if isinstance(component_count, int) and component_count > 1:
        return "fragmented"
    largest_ratio = summary.get("metrics", {}).get("largest_component_ratio")
    if isinstance(largest_ratio, (float, int)) and float(largest_ratio) < 0.75:
        return "fragmented"
    quality_hints = summary.get("hints", [])
    if any("slab" in str(item).lower() for item in quality_hints):
        return "slab_like"
    return "shape_preserved"


def main() -> None:
    args = parse_args()
    args.timestamp = args.timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    args.heads = sorted({normalize_head_name(head) for head in args.heads})
    load_project_env()
    runtime_preflight()

    samples = discover_samples(args.samples)
    review_root = ROOT / args.output_root / args.timestamp
    review_root.mkdir(parents=True, exist_ok=True)

    summary_entries: list[dict[str, Any]] = []
    overall_started = time.perf_counter()

    for sample_position, sample in enumerate(samples, start=1):
        label, source_path, sample_meta = sample
        sample_dir = review_root / label
        if sample_dir.exists():
            shutil.rmtree(sample_dir, ignore_errors=True)
        sample_dir.mkdir(parents=True, exist_ok=True)

        input_png = sample_dir / "input.png"
        copy_or_fallback(source_path, input_png, fallback_text="input copy failed")
        sample_results: list[dict[str, Any]] = []
        for head_index, raw_head in enumerate(args.heads):
            head = normalize_head_name(raw_head)
            if not head:
                continue
            print(f"[run] sample={label} head={head}")
            result = run_head(
                (label, source_path, sample_meta),
                head,
                sample_dir,
                index=head_index + 1,
                head_index=head_index,
                sample_position=sample_position,
                no_screenshot=args.no_screenshot,
            )
            result["backend"] = head
            result["sample_name"] = label
            result["input_png"] = str(input_png)
            result["shape_quality_summary"] = describe_shape(
                {
                    "status": result["quality_status"],
                    "checks": result["quality_checks"],
                    "metrics": result["quality_metrics"],
                    "hints": result["quality_hints"],
                }
            )
            sample_results.append(result)

        segmented_rel: str | None = None
        mask_rel: str | None = None
        missing_rel: str | None = None
        for result in sample_results:
            source_raw = result.get("sam2_segmented_input_source")
            if not source_raw:
                continue
            source_path_obj = Path(str(source_raw))
            if not source_path_obj.exists():
                continue
            segmented_path = sample_dir / "sam2_segmented_input.png"
            copy_or_fallback(source_path_obj, segmented_path, fallback_text="sam2 segmented input unavailable")
            segmented_rel = str(segmented_path.relative_to(review_root))
            break

        for result in sample_results:
            source_raw = result.get("sam2_mask_source")
            if not source_raw:
                continue
            source_path_obj = Path(str(source_raw))
            if not source_path_obj.exists():
                continue
            mask_path = sample_dir / "sam2_mask.png"
            copy_or_fallback(source_path_obj, mask_path, fallback_text="sam2 mask unavailable")
            mask_rel = str(mask_path.relative_to(review_root))
            break

        if mask_rel is not None:
            overlay_path = sample_dir / "sam2_missing_regions.png"
            overlay_meta = render_sam2_missing_regions_overlay(
                input_image_path=input_png,
                mask_image_path=sample_dir / "sam2_mask.png",
                output_path=overlay_path,
            )
            if overlay_meta.get("status") == "generated":
                missing_rel = str(overlay_path.relative_to(review_root))

        summary_entries.append(
            {
                "sample_name": label,
                "input_png": str(input_png.relative_to(review_root)),
                "sam2_segmented_input_png": segmented_rel,
                "sam2_mask_png": mask_rel,
                "sam2_missing_regions_png": missing_rel,
                "input_path": str(source_path),
                "input_metadata": sample_meta,
                "results": [
                    {
                        "backend": result["backend"],
                        "status": result["status"],
                        "runtime_sec": result["runtime_sec"],
                        "returncode": result["returncode"],
                        "stage": result["stage"],
                        "reason": result["reason"],
                        "resolved_backend": result["resolved_backend"],
                        "mesh_backend": result["mesh_backend"],
                        "fallback_used": result["fallback_used"],
                        "quality_status": result["quality_status"],
                        "quality_summary": result["shape_quality_summary"],
                        "mesh": str(Path(result["mesh_file"]).relative_to(review_root)),
                        "thumbnail": str(Path(result["thumbnail"]).relative_to(review_root)),
                        "viewer_screenshot": str(Path(result["screenshot"]).relative_to(review_root)),
                        "mesh_copy_status": result["mesh_copy_status"],
                        "metadata_path": str(Path(result["metadata_path"]).relative_to(review_root)),
                        "stdout": result["stdout"][:4000],
                        "stderr": result["stderr"][:2000],
                        "attempted_heads": result["attempted_heads"],
                        "fallback_chain": result["fallback_chain"],
                        "viewer_screenshot_status": result["viewer_screenshot_status"],
                    }
                    for result in sample_results
                ],
            }
        )

    total_runtime = round(time.perf_counter() - overall_started, 3)
    report = {
        "timestamp": args.timestamp,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "scripts/test/run_image_backend_review_pack.sh",
        "command": " ".join(shlex.quote(part) for part in sys.argv),
        "review_root": str(review_root),
        "runtime_sec": total_runtime,
        "samples": summary_entries,
    }
    summary_path = review_root / "summary.json"
    summary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    index_path = review_root / "index.md"
    index_path.write_text(build_index_markdown(review_root, summary_entries, report["generated_at"]), encoding="utf-8")

    print(f"Review pack created: {review_root}")
    print(f"summary: {summary_path}")
    print(f"index: {index_path}")


if __name__ == "__main__":
    main()
PY
