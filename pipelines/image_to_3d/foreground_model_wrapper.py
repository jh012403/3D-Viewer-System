from __future__ import annotations

import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from pipelines.common.io import ensure_dir, write_json


def _mask_bbox(mask: np.ndarray) -> dict[str, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return {
        "left": int(xs.min()),
        "top": int(ys.min()),
        "right": int(xs.max() + 1),
        "bottom": int(ys.max() + 1),
        "width": int(xs.max() - xs.min() + 1),
        "height": int(ys.max() - ys.min() + 1),
    }


def _touches_border(bbox: dict[str, int], width: int, height: int, margin: int = 4) -> bool:
    return (
        bbox["left"] <= margin
        or bbox["top"] <= margin
        or bbox["right"] >= width - margin
        or bbox["bottom"] >= height - margin
    )


def _count_components(binary_mask: np.ndarray) -> int:
    height, width = binary_mask.shape
    if height == 0 or width == 0:
        return 0
    visited = np.zeros((height, width), dtype=bool)
    count = 0
    points = np.argwhere(binary_mask)
    for y, x in points:
        if visited[y, x]:
            continue
        count += 1
        stack = [(int(y), int(x))]
        visited[y, x] = True
        while stack:
            cy, cx = stack.pop()
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if ny < 0 or nx < 0 or ny >= height or nx >= width:
                    continue
                if not binary_mask[ny, nx] or visited[ny, nx]:
                    continue
                visited[ny, nx] = True
                stack.append((ny, nx))
    return count


def _fill_internal_holes(binary_mask: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Fill holes fully enclosed by the foreground mask.

    We flood-fill the background from the image border and only fill
    background regions that are not reachable from the border.
    """
    if binary_mask.size == 0:
        return binary_mask, 0, 0

    inverse = ~binary_mask
    height, width = inverse.shape
    reachable = np.zeros((height, width), dtype=bool)
    stack: list[tuple[int, int]] = []

    for x in range(width):
        if inverse[0, x]:
            stack.append((0, x))
        if inverse[height - 1, x]:
            stack.append((height - 1, x))
    for y in range(height):
        if inverse[y, 0]:
            stack.append((y, 0))
        if inverse[y, width - 1]:
            stack.append((y, width - 1))

    while stack:
        cy, cx = stack.pop()
        if cy < 0 or cx < 0 or cy >= height or cx >= width:
            continue
        if reachable[cy, cx] or not inverse[cy, cx]:
            continue
        reachable[cy, cx] = True
        stack.extend([(cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)])

    holes = inverse & (~reachable)
    hole_pixels = int(holes.sum())
    if hole_pixels <= 0:
        return binary_mask, 0, 0
    hole_regions = _count_components(holes)
    return (binary_mask | holes), hole_pixels, hole_regions


def _collect_components(binary_mask: np.ndarray) -> list[dict[str, object]]:
    height, width = binary_mask.shape
    visited = np.zeros((height, width), dtype=bool)
    components: list[dict[str, object]] = []
    points = np.argwhere(binary_mask)
    for y, x in points:
        if visited[y, x]:
            continue
        stack = [(int(y), int(x))]
        visited[y, x] = True
        coords: list[tuple[int, int]] = []
        touches_border = False
        while stack:
            cy, cx = stack.pop()
            coords.append((cy, cx))
            if cy == 0 or cx == 0 or cy == (height - 1) or cx == (width - 1):
                touches_border = True
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if ny < 0 or nx < 0 or ny >= height or nx >= width:
                    continue
                if visited[ny, nx] or not binary_mask[ny, nx]:
                    continue
                visited[ny, nx] = True
                stack.append((ny, nx))
        components.append(
            {
                "coords": coords,
                "area": len(coords),
                "touches_border": touches_border,
            }
        )
    return components


def _boundary_gap_repair(binary_mask: np.ndarray) -> tuple[np.ndarray, int, int]:
    if binary_mask.size == 0:
        return binary_mask, 0, 0
    if os.getenv("AI3D_SEGMENT_BOUNDARY_REPAIR_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return binary_mask, 0, 0

    radius = int(os.getenv("AI3D_SEGMENT_BOUNDARY_REPAIR_RADIUS", "10").strip() or "10")
    filter_size = max(3, (radius * 2) + 1)
    if filter_size % 2 == 0:
        filter_size += 1

    mask_img = Image.fromarray((binary_mask.astype(np.uint8) * 255), mode="L")
    closed = mask_img.filter(ImageFilter.MaxFilter(filter_size)).filter(ImageFilter.MinFilter(filter_size))
    closed_mask = np.asarray(closed) > 127
    additions = closed_mask & (~binary_mask)
    if int(additions.sum()) <= 0:
        return binary_mask, 0, 0

    max_add_ratio = float(os.getenv("AI3D_SEGMENT_BOUNDARY_REPAIR_MAX_ADD_RATIO", "0.02").strip() or "0.02")
    max_add_pixels = max(1, int(binary_mask.size * max_add_ratio))
    min_comp_pixels = int(os.getenv("AI3D_SEGMENT_BOUNDARY_REPAIR_MIN_COMPONENT_PIXELS", "8").strip() or "8")
    max_comp_ratio = float(os.getenv("AI3D_SEGMENT_BOUNDARY_REPAIR_MAX_COMPONENT_RATIO", "0.01").strip() or "0.01")
    max_comp_pixels = max(min_comp_pixels, int(binary_mask.size * max_comp_ratio))

    repaired = binary_mask.copy()
    kept_pixels = 0
    kept_regions = 0
    for component in sorted(_collect_components(additions), key=lambda item: int(item["area"])):
        comp_area = int(component["area"])
        if comp_area < min_comp_pixels:
            continue
        if bool(component["touches_border"]):
            continue
        if comp_area > max_comp_pixels:
            continue
        if kept_pixels + comp_area > max_add_pixels:
            continue
        for cy, cx in component["coords"]:
            repaired[cy, cx] = True
        kept_pixels += comp_area
        kept_regions += 1

    if kept_pixels <= 0:
        return binary_mask, 0, 0
    return repaired, kept_pixels, kept_regions


@lru_cache(maxsize=4)
def _rembg_session(model_name: str):
    from rembg import new_session

    return new_session(model_name=model_name)


def _build_result(
    *,
    provider: str,
    work_dir: Path,
    rgb_image: Image.Image,
    mask_image: Image.Image,
    background_rgb: list[int],
    report_name: str,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    mask_image = mask_image.convert("L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(5))
    mask_image = mask_image.filter(ImageFilter.MedianFilter(5))
    mask_image = mask_image.filter(ImageFilter.MinFilter(3))

    cleaned_mask = np.asarray(mask_image) > 127
    cleaned_mask, hole_pixels, hole_regions = _fill_internal_holes(cleaned_mask)
    cleaned_mask, boundary_pixels, boundary_regions = _boundary_gap_repair(cleaned_mask)
    mask_image = Image.fromarray((cleaned_mask.astype(np.uint8) * 255), mode="L")
    height, width = cleaned_mask.shape
    foreground_ratio = float(cleaned_mask.mean())
    bbox = _mask_bbox(cleaned_mask)
    hints: list[str] = []

    if foreground_ratio < 0.12:
        hints.append("small_foreground_ratio")
    if bbox and _touches_border(bbox, width, height):
        hints.append("occlusion_detected")
    if hole_pixels > 0:
        hints.append("segmentation_holes_filled")
    if boundary_pixels > 0:
        hints.append("segmentation_boundary_repaired")

    extraction_confident = bbox is not None and 0.01 < foreground_ratio < 0.92
    if not extraction_confident:
        cleaned_mask = np.ones((height, width), dtype=bool)
        mask_image = Image.fromarray((cleaned_mask.astype(np.uint8) * 255), mode="L")
        bbox = {
            "left": 0,
            "top": 0,
            "right": width,
            "bottom": height,
            "width": width,
            "height": height,
        }

    foreground_image = rgb_image.convert("RGBA")
    foreground_image.putalpha(mask_image)

    mask_path = work_dir / "mask.png"
    foreground_path = work_dir / "foreground.png"
    report_path = work_dir / report_name
    mask_image.save(mask_path)
    foreground_image.save(foreground_path)

    result = {
        "provider": provider,
        "foreground_extracted": extraction_confident,
        "mask_path": str(mask_path),
        "foreground_path": str(foreground_path),
        "bbox": bbox,
        "foreground_ratio": foreground_ratio,
        "background_rgb": background_rgb,
        "segmentation_holes_filled": bool(hole_pixels > 0),
        "segmentation_holes_filled_pixels": hole_pixels,
        "segmentation_holes_filled_regions": hole_regions,
        "segmentation_boundary_repaired": bool(boundary_pixels > 0),
        "segmentation_boundary_repaired_pixels": boundary_pixels,
        "segmentation_boundary_repaired_regions": boundary_regions,
        "hints": sorted(set(hints)),
        "report_path": str(report_path),
    }
    if provider_metadata:
        result.update(provider_metadata)
    write_json(report_path, result)
    return result


def extract_with_rembg(
    input_image: Path,
    work_dir: Path,
    *,
    model_name: str | None = None,
) -> dict[str, Any]:
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    resolved_model_name = (model_name or os.getenv("AI3D_FOREGROUND_REMBG_MODEL", "u2netp")).strip() or "u2netp"

    try:
        from rembg import remove
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("rembg is not installed in the current runtime environment.") from exc

    with Image.open(input_image) as source_image:
        rgb_image = source_image.convert("RGB")

    session = _rembg_session(resolved_model_name)
    output = remove(rgb_image, session=session, only_mask=True, post_process_mask=True)
    if isinstance(output, bytes):
        mask_image = Image.open(io.BytesIO(output)).convert("L")
    elif isinstance(output, Image.Image):
        mask_image = output.convert("L")
    else:
        mask_image = Image.fromarray(np.asarray(output).astype(np.uint8)).convert("L")

    image_array = np.asarray(rgb_image).astype(np.float32)
    border_width = max(4, min(rgb_image.size[1], rgb_image.size[0]) // 32)
    border_samples = np.concatenate(
        [
            image_array[:border_width, :, :].reshape(-1, 3),
            image_array[-border_width:, :, :].reshape(-1, 3),
            image_array[:, :border_width, :].reshape(-1, 3),
            image_array[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    background_rgb = [int(round(value)) for value in np.median(border_samples, axis=0).tolist()]

    return _build_result(
        provider="rembg",
        work_dir=work_dir,
        rgb_image=rgb_image,
        mask_image=mask_image,
        background_rgb=background_rgb,
        report_name="foreground_model_report.json",
        provider_metadata={
            "foreground_model": "rembg",
            "foreground_model_name": resolved_model_name,
        },
    )
