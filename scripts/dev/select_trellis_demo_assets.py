#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


IMAGE_EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg"}


def _component_sizes(mask: np.ndarray) -> list[int]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    sizes: list[int] = []
    for y in range(height):
        xs = np.where(mask[y] & ~seen[y])[0]
        for start_x in xs:
            if seen[y, start_x] or not mask[y, start_x]:
                continue
            queue: deque[tuple[int, int]] = deque([(y, int(start_x))])
            seen[y, start_x] = True
            size = 0
            while queue:
                current_y, current_x = queue.popleft()
                size += 1
                for next_y in (current_y - 1, current_y, current_y + 1):
                    for next_x in (current_x - 1, current_x, current_x + 1):
                        if next_y == current_y and next_x == current_x:
                            continue
                        if (
                            0 <= next_y < height
                            and 0 <= next_x < width
                            and mask[next_y, next_x]
                            and not seen[next_y, next_x]
                        ):
                            seen[next_y, next_x] = True
                            queue.append((next_y, next_x))
            sizes.append(size)
    return sorted(sizes, reverse=True)


def _resampled(image: Image.Image, max_size: int = 256) -> Image.Image:
    if max(image.size) <= max_size:
        return image.copy()
    scale = max_size / max(image.size)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def analyze_image(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        return {
            "file": str(path),
            "status": "reject",
            "issues": [f"unreadable:{type(exc).__name__}:{exc}"],
        }

    width, height = image.size
    rgba = np.asarray(image)
    alpha = rgba[:, :, 3]
    alpha_coverage = float(np.mean(alpha > 8))
    transparent_ratio = float(np.mean(alpha < 250))
    has_alpha_cutout = bool(alpha.min() < 250)

    sample = _resampled(image)
    sample_rgba = np.asarray(sample)
    sample_alpha = sample_rgba[:, :, 3]
    mask = sample_alpha > 8
    coverage_sample = float(mask.mean())

    gray = np.asarray(sample.convert("L"), dtype=np.float32)
    foreground = gray[mask]
    variance = float(foreground.var()) if foreground.size else 0.0
    grad_y, grad_x = np.gradient(gray)
    edge_strength = np.sqrt(grad_x * grad_x + grad_y * grad_y)
    edge_density = float(np.mean((edge_strength > args.edge_threshold) & mask) / max(coverage_sample, 1e-6))

    component_sizes = _component_sizes(mask)
    component_count = len(component_sizes)
    small_component_ratio = 0.0
    if component_sizes:
        small_component_ratio = float(sum(component_sizes[1:]) / max(sum(component_sizes), 1))

    ys, xs = np.where(mask)
    bbox_fill = 0.0
    bbox_aspect = 0.0
    if xs.size:
        bbox_width = int(xs.max() - xs.min() + 1)
        bbox_height = int(ys.max() - ys.min() + 1)
        bbox_area = max(1, bbox_width * bbox_height)
        bbox_fill = float(mask.sum() / bbox_area)
        bbox_aspect = float(max(bbox_width, bbox_height) / max(1, min(bbox_width, bbox_height)))

    if not has_alpha_cutout:
        issues.append("no_alpha_cutout")
    if max(width, height) > args.max_dimension:
        issues.append(f"too_large_without_service_resize:{width}x{height}")
    if alpha_coverage < args.min_alpha_coverage:
        issues.append(f"foreground_too_small:{alpha_coverage:.3f}")
    if alpha_coverage > args.max_alpha_coverage:
        issues.append(f"foreground_too_large:{alpha_coverage:.3f}")
    if edge_density > args.reject_edge_density:
        issues.append(f"high_detail_oom_risk:{edge_density:.3f}")
    elif edge_density > args.review_edge_density:
        warnings.append(f"detailed_surface_review:{edge_density:.3f}")
    if bbox_fill < args.min_bbox_fill:
        warnings.append(f"fragmented_or_sparse_silhouette:{bbox_fill:.3f}")
    if bbox_aspect > args.max_bbox_aspect:
        warnings.append(f"extreme_aspect_ratio:{bbox_aspect:.2f}")
    if component_count > args.max_components or small_component_ratio > args.max_small_component_ratio:
        warnings.append(f"many_alpha_islands:{component_count}:{small_component_ratio:.3f}")

    status = "ready"
    if issues:
        status = "reject"
    elif warnings:
        status = "review"

    return {
        "file": str(path),
        "file_name": path.name,
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "width": width,
        "height": height,
        "file_size_bytes": path.stat().st_size,
        "alpha_coverage": round(alpha_coverage, 4),
        "transparent_ratio": round(transparent_ratio, 4),
        "edge_density": round(edge_density, 4),
        "foreground_variance": round(variance, 4),
        "component_count": component_count,
        "small_component_ratio": round(small_component_ratio, 4),
        "bbox_fill": round(bbox_fill, 4),
        "bbox_aspect": round(bbox_aspect, 4),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select alpha-masked TRELLIS.2 example images that are safer for RTX 3090 demos."
    )
    parser.add_argument("--source", default="assets", help="Directory containing TRELLIS.2 example images.")
    parser.add_argument(
        "--manifest",
        default="assets/trellis_demo_candidates.json",
        help="JSON report path to write.",
    )
    parser.add_argument(
        "--copy-dir",
        default="",
        help="Optional directory where ready images are copied. Files are never deleted.",
    )
    parser.add_argument(
        "--copy-status",
        default="ready",
        help="Comma-separated statuses to copy when --copy-dir is set. Example: ready,review",
    )
    parser.add_argument("--recursive", action="store_true", help="Scan source recursively.")
    parser.add_argument("--max-dimension", type=int, default=1200)
    parser.add_argument("--min-alpha-coverage", type=float, default=0.10)
    parser.add_argument("--max-alpha-coverage", type=float, default=0.68)
    parser.add_argument("--edge-threshold", type=float, default=28.0)
    parser.add_argument("--review-edge-density", type=float, default=0.20)
    parser.add_argument("--reject-edge-density", type=float, default=0.23)
    parser.add_argument("--min-bbox-fill", type=float, default=0.42)
    parser.add_argument("--max-bbox-aspect", type=float, default=3.2)
    parser.add_argument("--max-components", type=int, default=8)
    parser.add_argument("--max-small-component-ratio", type=float, default=0.035)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = Path(args.source).expanduser().resolve()
    pattern = "**/*" if args.recursive else "*"
    files = sorted(
        path
        for path in source.glob(pattern)
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    results = [analyze_image(path, args) for path in files]
    counts = {
        status: sum(1 for item in results if item.get("status") == status)
        for status in ("ready", "review", "reject")
    }
    payload = {
        "source": str(source),
        "summary": counts,
        "criteria": {
            "max_dimension": args.max_dimension,
            "alpha_coverage": [args.min_alpha_coverage, args.max_alpha_coverage],
            "review_edge_density": args.review_edge_density,
            "reject_edge_density": args.reject_edge_density,
            "min_bbox_fill": args.min_bbox_fill,
            "max_bbox_aspect": args.max_bbox_aspect,
        },
        "items": results,
    }

    manifest = Path(args.manifest).expanduser().resolve()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    copied = 0
    if args.copy_dir:
        copy_status = {value.strip() for value in args.copy_status.split(",") if value.strip()}
        copy_dir = Path(args.copy_dir).expanduser().resolve()
        copy_dir.mkdir(parents=True, exist_ok=True)
        for item in results:
            if item.get("status") in copy_status:
                shutil.copy2(item["file"], copy_dir / Path(item["file"]).name)
                copied += 1

    print(f"source: {source}")
    print(f"manifest: {manifest}")
    print(f"ready={counts['ready']} review={counts['review']} reject={counts['reject']} copied={copied}")
    for item in results[:12]:
        status = item.get("status")
        issues = ", ".join(item.get("issues") or item.get("warnings") or [])
        print(f"{status:6} {Path(item['file']).name} edge={item.get('edge_density')} alpha={item.get('alpha_coverage')} {issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
