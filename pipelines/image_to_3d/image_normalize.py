from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.io import ensure_dir, write_json


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _expand_square_bbox(
    bbox: dict[str, int],
    image_width: int,
    image_height: int,
    margin_ratio: float = 0.14,
) -> tuple[int, int, int, int]:
    box_width = bbox["width"]
    box_height = bbox["height"]
    center_x = bbox["left"] + box_width / 2.0
    center_y = bbox["top"] + box_height / 2.0
    side = max(box_width, box_height)
    side = max(side * (1.0 + margin_ratio * 2.0), min(image_width, image_height) * 0.28)
    half_side = side / 2.0

    left = int(round(center_x - half_side))
    top = int(round(center_y - half_side))
    right = int(round(center_x + half_side))
    bottom = int(round(center_y + half_side))

    if left < 0:
        right += -left
        left = 0
    if top < 0:
        bottom += -top
        top = 0
    if right > image_width:
        left -= right - image_width
        right = image_width
    if bottom > image_height:
        top -= bottom - image_height
        bottom = image_height

    left = max(left, 0)
    top = max(top, 0)
    right = min(right, image_width)
    bottom = min(bottom, image_height)
    return left, top, right, bottom


def normalize_image_for_reconstruction(
    input_image: Path,
    foreground_result: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    target_size = _env_int("AI3D_IMAGE_NORMALIZE_SIZE", 1024)

    with Image.open(input_image) as image:
        rgb_image = image.convert("RGB")

    mask_path = Path(str(foreground_result["mask_path"])).expanduser().resolve()
    with Image.open(mask_path) as mask_image:
        mask = mask_image.convert("L")

    width, height = rgb_image.size
    bbox = foreground_result.get("bbox") or {
        "left": 0,
        "top": 0,
        "right": width,
        "bottom": height,
        "width": width,
        "height": height,
    }

    if not foreground_result.get("foreground_extracted") and bbox["width"] == width and bbox["height"] == height:
        fallback_side = int(round(min(width, height) * 0.9))
        center_x = width // 2
        center_y = height // 2
        crop_box = (
            max(center_x - fallback_side // 2, 0),
            max(center_y - fallback_side // 2, 0),
            min(center_x + fallback_side // 2, width),
            min(center_y + fallback_side // 2, height),
        )
        hints = list(foreground_result.get("hints") or [])
        hints.append("center_crop_fallback_applied")
        foreground_result = {**foreground_result, "hints": hints}
    else:
        crop_box = _expand_square_bbox(bbox, width, height)
    crop_width = crop_box[2] - crop_box[0]
    crop_height = crop_box[3] - crop_box[1]
    cropped_rgb = rgb_image.crop(crop_box)
    cropped_mask = mask.crop(crop_box)
    trellis_input_rgb_path = work_dir / "trellis_input_rgb.png"
    cropped_rgb.save(trellis_input_rgb_path)

    canvas_side = max(crop_width, crop_height)
    background_rgb = tuple(int(channel) for channel in foreground_result.get("background_rgb", [243, 244, 246]))
    background_mode = "solid"
    square_canvas = Image.new("RGB", (canvas_side, canvas_side), background_rgb)
    square_mask = Image.new("L", (canvas_side, canvas_side), 0)

    offset_x = (canvas_side - crop_width) // 2
    offset_y = (canvas_side - crop_height) // 2
    square_canvas.paste(cropped_rgb, (offset_x, offset_y))
    square_mask.paste(cropped_mask, (offset_x, offset_y))

    normalized_image = square_canvas.resize((target_size, target_size), Image.Resampling.LANCZOS)
    normalized_mask = square_mask.resize((target_size, target_size), Image.Resampling.LANCZOS)
    normalized_foreground = normalized_image.convert("RGBA")
    normalized_foreground.putalpha(normalized_mask)

    normalized_input_path = work_dir / "normalized_input.png"
    normalized_mask_path = work_dir / "normalized_mask.png"
    normalized_foreground_path = work_dir / "normalized_foreground.png"
    report_path = work_dir / "normalization_report.json"
    normalized_image.save(normalized_input_path)
    normalized_mask.save(normalized_mask_path)
    normalized_foreground.save(normalized_foreground_path)

    original_ratio = width / height if height else 1.0
    foreground_ratio = float(foreground_result.get("foreground_ratio") or 0.0)
    bbox_area = float(bbox["width"] * bbox["height"])
    crop_area = float(max(crop_width, 1) * max(crop_height, 1))
    crop_fill_ratio = float(bbox_area / crop_area) if crop_area > 0 else 0.0
    normalized_mask_array = np.asarray(normalized_mask, dtype=np.uint8)
    normalized_foreground_ratio = float((normalized_mask_array > 127).mean())
    hints = list(foreground_result.get("hints") or [])
    if original_ratio > 1.8 or original_ratio < 0.56:
        hints.append("extreme_aspect_ratio")
    if foreground_ratio < 0.08:
        hints.append("small_foreground_ratio")
    if crop_fill_ratio < 0.08:
        hints.append("bbox_too_loose")
    if crop_fill_ratio > 0.94:
        hints.append("bbox_too_tight")

    result = {
        "normalized_input_path": str(normalized_input_path),
        "normalized_mask_path": str(normalized_mask_path),
        "normalized_foreground_path": str(normalized_foreground_path),
        "trellis_input_rgb_path": str(trellis_input_rgb_path),
        "crop_applied": crop_box != (0, 0, width, height),
        "crop_box": {
            "left": crop_box[0],
            "top": crop_box[1],
            "right": crop_box[2],
            "bottom": crop_box[3],
        },
        "normalized_size": [target_size, target_size],
        "background_mode": background_mode,
        "foreground_ratio": foreground_ratio,
        "crop_fill_ratio": round(crop_fill_ratio, 6),
        "normalized_foreground_ratio": round(normalized_foreground_ratio, 6),
        "original_size": [width, height],
        "original_aspect_ratio": round(original_ratio, 4),
        "hints": sorted(set(hints)),
        "report_path": str(report_path),
    }
    write_json(report_path, result)
    return result
