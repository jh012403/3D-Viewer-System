from __future__ import annotations

import os
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.io import ensure_dir, write_json
from pipelines.image_to_3d.multiview_wrapper import create_passthrough_multiview, generate_multiview_images

_MULTIVIEW_PROVIDER_ALIASES = {
    "sv3d": "sv3d",
    "sv3d_p": "sv3d",
    "sv3d_u": "sv3d",
}


def _is_strict_mode() -> bool:
    return os.getenv("MULTIVIEW_STRICT", "false").strip().lower() in {"1", "true", "yes", "on"}


def normalize_multiview_provider(name: str | None) -> str:
    normalized = (name or "").strip().lower().replace(" ", "").replace("-", "_")
    if not normalized:
        return "sv3d"
    normalized = normalized.replace("__", "_")
    return _MULTIVIEW_PROVIDER_ALIASES.get(normalized, "sv3d")


def _requested_provider(explicit_provider: str | None = None) -> str:
    requested = explicit_provider or os.getenv("MULTIVIEW_PROVIDER", "sv3d")
    return normalize_multiview_provider(requested)


def _actual_runtime_provider(requested_provider: str) -> tuple[str, str | None]:
    if requested_provider == "sv3d":
        if os.getenv("SV3D_CMD", "").strip():
            return "sv3d", None
        return "sv3d", "sv3d_runtime_unavailable"
    return "sv3d", f"provider_not_supported:{requested_provider}"


def _mask_from_view(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    rgba_array = np.asarray(rgba)
    alpha = rgba_array[:, :, 3]
    if int(alpha.max()) > 0:
        return alpha > 12

    rgb = rgba_array[:, :, :3].astype(np.float32)
    corners = np.concatenate(
        [
            rgb[:8, :8, :].reshape(-1, 3),
            rgb[:8, -8:, :].reshape(-1, 3),
            rgb[-8:, :8, :].reshape(-1, 3),
            rgb[-8:, -8:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    background = np.median(corners, axis=0)
    distances = np.linalg.norm(rgb - background, axis=2)
    return distances > 18.0


def _bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _silhouette_metrics(view_paths: list[Path]) -> dict[str, float]:
    if not view_paths:
        return {}

    coverages: list[float] = []
    bbox_areas: list[float] = []
    center_offsets: list[tuple[float, float]] = []
    masks: list[np.ndarray] = []

    for path in view_paths:
        mask = _mask_from_view(path)
        masks.append(mask)
        height, width = mask.shape
        total_area = float(height * width) if height and width else 1.0
        coverage = float(mask.mean())
        bbox = _bbox_from_mask(mask)
        bbox_area = 0.0
        center_offset_x = 0.0
        center_offset_y = 0.0
        if bbox is not None:
            left, top, right, bottom = bbox
            bbox_area = float((right - left) * (bottom - top)) / total_area
            center_offset_x = (((left + right) / 2.0) / max(width, 1)) - 0.5
            center_offset_y = (((top + bottom) / 2.0) / max(height, 1)) - 0.5
        coverages.append(coverage)
        bbox_areas.append(bbox_area)
        center_offsets.append((center_offset_x, center_offset_y))

    pairwise_overlap: list[float] = []
    for left, right in combinations(range(len(masks)), 2):
        union = np.logical_or(masks[left], masks[right]).sum()
        if union <= 0:
            continue
        intersection = np.logical_and(masks[left], masks[right]).sum()
        pairwise_overlap.append(float(intersection / union))

    coverage_mean = float(np.mean(coverages))
    coverage_std = float(np.std(coverages))
    bbox_area_mean = float(np.mean(bbox_areas))
    bbox_area_std = float(np.std(bbox_areas))
    center_offset_mean = float(np.mean([abs(x) + abs(y) for x, y in center_offsets]))
    overlap_mean = float(np.mean(pairwise_overlap)) if pairwise_overlap else 1.0
    consistency_score = max(
        0.0,
        1.0
        - min(1.0, coverage_std * 3.0)
        - min(1.0, bbox_area_std * 2.5)
        - min(1.0, center_offset_mean * 2.0),
    )

    return {
        "coverage_mean": round(coverage_mean, 6),
        "coverage_std": round(coverage_std, 6),
        "bbox_area_mean": round(bbox_area_mean, 6),
        "bbox_area_std": round(bbox_area_std, 6),
        "center_offset_mean": round(center_offset_mean, 6),
        "pairwise_overlap_mean": round(overlap_mean, 6),
        "consistency_score": round(consistency_score, 6),
    }


class MultiViewGenerator:
    def __init__(self, *, enabled: bool | None = None, provider: str | None = None) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else os.getenv("MULTIVIEW_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.provider_requested = _requested_provider(provider)

    def generate(self, input_image_path: Path, output_dir: Path) -> dict[str, Any]:
        input_image_path = input_image_path.expanduser().resolve()
        output_dir = ensure_dir(output_dir.expanduser().resolve())

        if not self.enabled:
            payload = create_passthrough_multiview(input_image_path, output_dir, reason="disabled")
            payload.update(
                {
                    "enabled": False,
                    "requested_provider": self.provider_requested,
                    "provider_requested": self.provider_requested,
                    "status": "disabled_passthrough",
                    "silhouette_metrics": _silhouette_metrics([Path(str(path)) for path in payload.get("view_paths") or []]),
                }
            )
            write_json(output_dir / "multiview_prior.json", payload)
            return payload

        runtime_provider, runtime_fallback_reason = _actual_runtime_provider(self.provider_requested)
        strict_mode = _is_strict_mode()
        if strict_mode and runtime_fallback_reason is not None:
            raise RuntimeError(
                f"Strict multiview mode is enabled (MULTIVIEW_STRICT=true), "
                f"but provider `{self.provider_requested}` is unavailable: {runtime_fallback_reason}"
            )
        try:
            summary = generate_multiview_images(input_image_path, output_dir / "generated", provider=runtime_provider)
        except Exception as exc:  # noqa: BLE001
            if strict_mode:
                raise
            payload = create_passthrough_multiview(input_image_path, output_dir, reason=str(exc))
            payload.update(
                {
                    "enabled": True,
                    "active": False,
                    "mode": "single_view_fallback",
                    "requested_provider": self.provider_requested,
                    "provider_requested": self.provider_requested,
                    "provider_runtime": runtime_provider,
                    "provider_used": "passthrough",
                    "status": "fallback_passthrough",
                    "multiview_fallback": True,
                    "multiview_fallback_reason": str(exc),
                    "silhouette_metrics": _silhouette_metrics([Path(str(path)) for path in payload.get("view_paths") or []]),
                }
            )
            write_json(output_dir / "multiview_prior.json", payload)
            return payload

        view_paths = [Path(str(path)).expanduser().resolve() for path in summary.get("view_paths") or []]
        silhouette_metrics = _silhouette_metrics(view_paths)
        notes: list[str] = []
        if runtime_fallback_reason:
            notes.append(runtime_fallback_reason)

        payload = {
            "enabled": True,
            "active": True,
            "mode": "multi_view",
            "requested_provider": self.provider_requested,
            "provider_requested": self.provider_requested,
            "provider_runtime": runtime_provider,
            "provider_used": summary.get("provider", runtime_provider),
            "status": "generated",
            "multiview_fallback": runtime_fallback_reason is not None,
            "multiview_fallback_reason": runtime_fallback_reason,
            "input_path": str(input_image_path),
            "output_path": str(summary["grid_path"]),
            "output_dir": str(output_dir / "generated"),
            "views_dir": str(summary["views_dir"]),
            "view_paths": [str(path) for path in view_paths],
            "montage_path": str(summary["grid_path"]),
            "num_views": int(summary.get("num_views") or 0),
            "model": summary.get("provider", runtime_provider),
            "log_path": summary.get("log_path"),
            "view_metrics": summary.get("metrics") or {},
            "silhouette_metrics": silhouette_metrics,
            "notes": notes,
        }
        write_json(output_dir / "multiview_prior.json", payload)
        return payload


def run_multiview_generation(normalized_input_path: Path, work_dir: Path) -> dict[str, Any]:
    return MultiViewGenerator().generate(normalized_input_path, work_dir)
