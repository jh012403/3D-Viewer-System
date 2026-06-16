from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.io import ensure_dir, write_json
from pipelines.image_to_3d.foreground_extract import extract_foreground
from pipelines.image_to_3d.foreground_model_wrapper import extract_with_rembg


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _connected_components(binary_mask: np.ndarray) -> int:
    h, w = binary_mask.shape
    if h == 0 or w == 0:
        return 0

    visited = np.zeros((h, w), dtype=bool)
    remaining = np.argwhere(binary_mask)
    count = 0

    for y, x in remaining:
        if visited[y, x]:
            continue
        count += 1
        stack = [(y, x)]
        visited[y, x] = True
        while stack:
            cy, cx = stack.pop()
            ny, nx = cy - 1, cx
            if ny >= 0 and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
            ny = cy + 1
            if ny < h and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
            ny, nx = cy, cx - 1
            if nx >= 0 and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
            ny, nx = cy, cx + 1
            if nx < w and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))

    return count


def _component_areas(binary_mask: np.ndarray) -> list[int]:
    h, w = binary_mask.shape
    if h == 0 or w == 0:
        return []

    visited = np.zeros((h, w), dtype=bool)
    areas: list[int] = []

    for y, x in np.argwhere(binary_mask):
        if visited[y, x]:
            continue
        stack = [(int(y), int(x))]
        visited[y, x] = True
        area = 0
        while stack:
            cy, cx = stack.pop()
            area += 1
            ny, nx = cy - 1, cx
            if ny >= 0 and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
            ny = cy + 1
            if ny < h and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
            ny, nx = cy, cx - 1
            if nx >= 0 and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
            ny, nx = cy, cx + 1
            if nx < w and binary_mask[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                stack.append((ny, nx))
        areas.append(area)

    return areas


def _extract_fallback_to_heuristic(input_image: Path, work_dir: Path, reason: str) -> dict[str, Any]:
    result = extract_foreground(input_image, work_dir / "fallback", mode="heuristic")
    result["provider_requested"] = "heuristic"
    result["provider_used"] = "heuristic"
    result["provider_fallback_used"] = True
    result["segmentation_fallback_reason"] = reason
    return result


def _build_segmented_output(
    result: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    foreground_path = Path(str(result["foreground_path"])).expanduser().resolve()
    mask_path = Path(str(result["mask_path"])).expanduser().resolve()

    segmented_image_path = work_dir / "segmented_image.png"
    mask_output_path = work_dir / "mask.png"

    if foreground_path.exists():
        with Image.open(foreground_path) as foreground_image:
            foreground_image.save(segmented_image_path)

    if mask_path.exists():
        with Image.open(mask_path) as mask_image:
            mask_image.convert("L").save(mask_output_path)

    result["segmented_image_path"] = str(segmented_image_path)
    result["mask_path"] = str(mask_output_path)
    result["normalized_segmentation"] = True
    return result


def _validate_segmentation(mask_path: Path, image_size: tuple[int, int]) -> dict[str, Any]:
    with Image.open(mask_path) as mask_image:
        mask_rgba = np.asarray(mask_image.convert("L")) > 0

    area_ratio = float(mask_rgba.mean()) if mask_rgba.size else 0.0
    image_area = int(image_size[0] * image_size[1])
    component_areas = _component_areas(mask_rgba)
    components_total = len(component_areas)
    max_components = int(os.getenv("AI3D_SEGMENT_MAX_COMPONENTS", "3"))
    min_component_pixels = int(os.getenv("AI3D_SEGMENT_MIN_COMPONENT_PIXELS", "64"))
    min_component_ratio = float(os.getenv("AI3D_SEGMENT_MIN_COMPONENT_RATIO", "0.00005"))
    significant_component_min_pixels = max(min_component_pixels, int(image_area * min_component_ratio))
    significant_components = [area for area in component_areas if area >= significant_component_min_pixels]
    components = len(significant_components)
    largest_component_pixels = max(component_areas) if component_areas else 0
    return {
        "segmentation_area_ratio": area_ratio,
        "segmentation_components": components,
        "segmentation_components_total": components_total,
        "segmentation_components_significant_min_pixels": significant_component_min_pixels,
        "segmentation_largest_component_pixels": largest_component_pixels,
        "segmentation_valid": area_ratio >= 0.005 and components <= max_components,
        "segmentation_area_ok": area_ratio >= 0.005,
        "image_area": image_area,
    }


def segment_foreground(
    input_image: Path,
    work_dir: Path,
    *,
    mode: str | None = None,
    allow_fallback: bool = True,
    selected_candidate_id: str | None = None,
) -> dict[str, Any]:
    """Run object-focused segmentation with optional SAM first and deterministic fallback.

    The function returns a canonical payload containing:
      - segmented_image.png path
      - mask.png path
      - SAM usage + fallback metadata
      - segmentation quality signals used by quality gate / metadata
    """
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())

    requested_mode = (mode or os.getenv("AI3D_HIGH_QUALITY_FOREGROUND_PROVIDER", "sam2")).strip().lower()
    if requested_mode == "sam":
        requested_mode = "sam2"
    use_sam = _env_bool("AI3D_ENABLE_SAM_SEGMENT", True)
    strict_sam2 = _env_bool("AI3D_SAM2_STRICT", True)
    min_area_ratio = float(os.getenv("AI3D_SEGMENT_MIN_AREA_RATIO", "0.005"))

    with Image.open(input_image) as image:
        image_size = image.size

    segmentation_attempt = None
    reason: str | None = None
    result: dict[str, Any] | None = None

    if use_sam and requested_mode in {"sam2", "auto", "adaptive"}:
        try:
            result = extract_foreground(
                input_image,
                work_dir / "sam_segment",
                mode="sam2",
                selected_candidate_id=selected_candidate_id,
            )
            result["provider_requested"] = "sam2"
            result["provider_used"] = (
                "sam2" if result.get("provider_used") in {"sam", "sam2"} else result.get("provider_used") or "sam2"
            )
            result["provider_fallback_used"] = False
            segmentation_attempt = "sam2"
        except Exception as exc:  # noqa: BLE001
            segmentation_attempt = "sam2_failed"
            reason = str(exc)
            if strict_sam2 and requested_mode == "sam2":
                raise RuntimeError(f"SAM2 strict mode is enabled and segmentation failed: {exc}") from exc

    if result is None and allow_fallback:
        if reason:
            # Preserve explicit failures for observability; try model-backed + heuristic fallback.
            try:
                result = extract_foreground(input_image, work_dir / "fallback", mode="heuristic")
                result["provider_requested"] = requested_mode or "auto"
                result["provider_used"] = result.get("provider_used") or "heuristic"
                result["provider_fallback_used"] = True
                result["segmentation_fallback_reason"] = reason
                segmentation_attempt = "heuristic_after_sam2_failure"
            except Exception as fallback_error:  # noqa: BLE001
                # Last chance: direct rembg fallback then one final heuristic.
                try:
                    result = extract_with_rembg(input_image, work_dir / "fallback_rembg")
                    result["provider_requested"] = "sam2"
                    result["provider_used"] = "rembg"
                    result["provider_fallback_used"] = True
                    result["segmentation_fallback_reason"] = f"sam2_failed:{reason};rembg_failed:{fallback_error}"
                    segmentation_attempt = "rembg_after_sam2_failure"
                except Exception as exc:  # noqa: BLE001
                    # Guaranteed hard fallback to deterministic heuristic path.
                    result = _extract_fallback_to_heuristic(input_image, work_dir, reason=f"{reason};{fallback_error};{exc}")
                    segmentation_attempt = "forced_heuristic"

    if result is None:
        result = _extract_fallback_to_heuristic(input_image, work_dir, reason="segmentor_initialization_failed")
        segmentation_attempt = "forced_heuristic"

    segmentation_validation = _validate_segmentation(Path(str(result["mask_path"])), image_size)
    result.update(segmentation_validation)
    result["segmentation_attempt"] = segmentation_attempt
    result["sam_used"] = result.get("provider_used") in {"sam", "sam2"}
    if not result.get("foreground_extracted"):
        result["foreground_extracted"] = bool(segmentation_validation["segmentation_area_ratio"] >= min_area_ratio)

    if not result.get("segmentation_valid"):
        result["segmentation_reason"] = "segmentation_area_or_components_invalid"
        if strict_sam2 and result.get("provider_used") in {"sam", "sam2"}:
            raise RuntimeError(
                "SAM2 strict mode rejected the generated mask due to invalid area/components."
            )
        if allow_fallback and result.get("provider_used") != "heuristic":
            fallback_result = _extract_fallback_to_heuristic(input_image, work_dir / "heuristic_repair", reason=result.get("segmentation_reason", "invalid"))
            fallback_result["provider_requested"] = result.get("provider_requested", requested_mode)
            fallback_result["provider_used"] = "heuristic"
            fallback_result["provider_fallback_used"] = True
            fallback_validation = _validate_segmentation(Path(str(fallback_result["mask_path"])), image_size)
            fallback_result.update(fallback_validation)
            fallback_result["sam_used"] = False
            fallback_result["segmentation_fallback_reason"] = result.get("segmentation_reason")
            fallback_result["segmentation_attempt"] = "heuristic_repair_after_invalid"
            result = fallback_result

    # Write a dedicated normalized segment payload and keep canonical filenames.
    result = _build_segmented_output(result, work_dir)
    result["sam_segment_report_path"] = str(work_dir / "sam_segment_report.json")
    normalized_requested = "sam2" if requested_mode in {"sam", "sam2"} else requested_mode
    result["segmentation_provider_order"] = [normalized_requested, "heuristic"]

    # Keep raw reports lightweight and consistent across downstream consumers.
    report_payload = dict(result)
    report_payload["normalized"] = True
    write_json(work_dir / "sam_segment_report.json", report_payload)
    return report_payload
