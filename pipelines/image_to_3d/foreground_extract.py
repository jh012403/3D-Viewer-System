from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from pipelines.common.io import ensure_dir, write_json
from pipelines.image_to_3d.foreground_extract_sam import extract_with_sam
from pipelines.image_to_3d.foreground_model_wrapper import extract_with_rembg


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


def _extract_with_heuristic(input_image: Path, work_dir: Path) -> dict[str, Any]:
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())

    with Image.open(input_image) as source_image:
        rgb_image = source_image.convert("RGB")

    image_array = np.asarray(rgb_image).astype(np.float32)
    height, width, _channels = image_array.shape
    border_width = max(4, min(height, width) // 32)
    border_samples = np.concatenate(
        [
            image_array[:border_width, :, :].reshape(-1, 3),
            image_array[-border_width:, :, :].reshape(-1, 3),
            image_array[:, :border_width, :].reshape(-1, 3),
            image_array[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    background_rgb = np.median(border_samples, axis=0)
    border_distances = np.linalg.norm(border_samples - background_rgb, axis=1)

    color_distance = np.linalg.norm(image_array - background_rgb, axis=2)
    saturation = image_array.max(axis=2) - image_array.min(axis=2)
    score = color_distance + saturation * 0.35

    threshold = max(float(np.percentile(border_distances, 95) + 18.0), 24.0)
    mask = score > threshold
    mask_image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    mask_image = mask_image.filter(ImageFilter.MaxFilter(5))
    mask_image = mask_image.filter(ImageFilter.MedianFilter(5))
    mask_image = mask_image.filter(ImageFilter.MinFilter(3))

    cleaned_mask = np.asarray(mask_image) > 0
    foreground_ratio = float(cleaned_mask.mean())
    bbox = _mask_bbox(cleaned_mask)

    hints: list[str] = []
    background_complexity = float(border_distances.std())
    if background_complexity > 18.0:
        hints.append("complex_background_detected")
    if foreground_ratio < 0.12:
        hints.append("small_foreground_ratio")
    if bbox and _touches_border(bbox, width, height):
        hints.append("occlusion_detected")

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

    rgba_image = rgb_image.convert("RGBA")
    foreground_image = rgba_image.copy()
    foreground_image.putalpha(mask_image)

    mask_path = work_dir / "mask.png"
    foreground_path = work_dir / "foreground.png"
    report_path = work_dir / "foreground_report.json"
    mask_image.save(mask_path)
    foreground_image.save(foreground_path)

    result = {
        "provider": "heuristic",
        "foreground_extracted": extraction_confident,
        "mask_path": str(mask_path),
        "foreground_path": str(foreground_path),
        "bbox": bbox,
        "foreground_ratio": foreground_ratio,
        "background_rgb": [int(round(value)) for value in background_rgb.tolist()],
        "background_complexity": round(background_complexity, 4),
        "score_threshold": round(threshold, 4),
        "hints": sorted(set(hints)),
        "report_path": str(report_path),
    }
    write_json(report_path, result)
    return result


def _requested_provider(explicit_mode: str | None) -> str:
    requested = (explicit_mode or os.getenv("AI3D_FOREGROUND_PROVIDER", "auto")).strip().lower()
    if requested == "sam":
        requested = "sam2"
    if requested in {"", "default"}:
        return "auto"
    if requested not in {"auto", "heuristic", "rembg", "sam2"}:
        return "auto"
    return requested


def _fallback_sequence() -> list[str]:
    raw = os.getenv("AI3D_FOREGROUND_PROVIDER_FALLBACK_CHAIN", "rembg,heuristic").strip()
    sequence: list[str] = []
    for item in raw.split(","):
        provider = item.strip().lower()
        if provider == "sam":
            provider = "sam2"
        if provider in {"sam2", "rembg", "heuristic"} and provider not in sequence:
            sequence.append(provider)
    if "heuristic" not in sequence:
        sequence.append("heuristic")
    return sequence


def extract_foreground(
    input_image: Path,
    work_dir: Path,
    mode: str | None = None,
    *,
    selected_candidate_id: str | None = None,
) -> dict[str, Any]:
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    requested = _requested_provider(mode)
    fallback_sequence = _fallback_sequence()
    strict_sam2 = os.getenv("AI3D_SAM2_STRICT", "true").strip().lower() in {"1", "true", "yes", "on"}

    attempts: list[dict[str, Any]] = []

    def with_common_metadata(result: dict[str, Any], *, provider_requested: str, provider_used: str, fallback_used: bool) -> dict[str, Any]:
        merged = dict(result)
        merged["provider_requested"] = provider_requested
        merged["provider_used"] = provider_used
        merged["provider_fallback_used"] = fallback_used
        merged["provider_attempts"] = attempts
        hints = list(merged.get("hints") or [])
        if fallback_used:
            hints.append("foreground_provider_fallback_used")
        merged["hints"] = sorted(set(hints))
        report_path = Path(str(merged["report_path"])).expanduser().resolve()
        write_json(report_path, merged)
        return merged

    provider_sequence: list[str]
    if requested == "auto":
        provider_sequence = ["sam2", *[provider for provider in fallback_sequence if provider != "sam2"]]
    elif requested == "sam2":
        if strict_sam2:
            provider_sequence = ["sam2"]
        else:
            provider_sequence = ["sam2", *[provider for provider in fallback_sequence if provider != "sam2"]]
    elif requested == "rembg":
        provider_sequence = ["rembg", *[provider for provider in fallback_sequence if provider != "rembg"]]
    else:
        provider_sequence = ["heuristic"]

    for index, provider in enumerate(provider_sequence):
        if provider == "heuristic":
            result = _extract_with_heuristic(input_image, work_dir)
            attempts.append({"provider": provider, "status": "completed"})
            return with_common_metadata(
                result,
                provider_requested=requested,
                provider_used="heuristic",
                fallback_used=index > 0,
            )

        if provider == "sam2":
            try:
                result = extract_with_sam(
                    input_image,
                    work_dir / "sam",
                    selected_candidate_id=selected_candidate_id,
                )
            except Exception as exc:  # noqa: BLE001
                attempts.append({"provider": provider, "status": "failed", "error": str(exc)})
                if requested == "sam2" and strict_sam2:
                    raise RuntimeError(f"SAM2 strict mode: segmentation failed ({exc}).") from exc
                continue

            if result.get("foreground_extracted"):
                attempts.append({"provider": provider, "status": "completed"})
                provider_used = str(result.get("provider") or "sam2")
                return with_common_metadata(
                    result,
                    provider_requested=requested,
                    provider_used=provider_used,
                    fallback_used=index > 0,
                )

            attempts.append(
                {
                    "provider": provider,
                    "status": "low_confidence",
                    "error": "SAM returned a low-confidence mask. Falling back to the next foreground provider.",
                }
            )
            if requested == "sam2" and strict_sam2:
                raise RuntimeError("SAM2 strict mode: generated mask was low-confidence.")
            continue

        try:
            result = extract_with_rembg(input_image, work_dir / "rembg")
        except Exception as exc:  # noqa: BLE001
            attempts.append({"provider": provider, "status": "failed", "error": str(exc)})
            continue

        if result.get("foreground_extracted"):
            attempts.append({"provider": provider, "status": "completed"})
            return with_common_metadata(
                result,
                provider_requested=requested,
                provider_used="rembg",
                fallback_used=index > 0,
            )

        attempts.append(
            {
                "provider": provider,
                "status": "low_confidence",
                "error": "Foreground model returned a low-confidence mask. Falling back to heuristic extraction.",
            }
        )

    if requested == "sam2" and strict_sam2:
        raise RuntimeError("SAM2 strict mode: segmentation did not produce a valid mask.")

    result = _extract_with_heuristic(input_image, work_dir)
    attempts.append({"provider": "heuristic", "status": "completed"})
    return with_common_metadata(
        result,
        provider_requested=requested,
        provider_used="heuristic",
        fallback_used=requested != "heuristic",
    )
