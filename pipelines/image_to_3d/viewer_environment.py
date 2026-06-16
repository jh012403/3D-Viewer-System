from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.io import ensure_dir, write_json


TRELLIS_HDRI_PRESETS = (
    ("forest", "HDRI Forest", "forest.exr"),
    ("sunset", "HDRI Sunset", "sunset.exr"),
    ("courtyard", "HDRI Courtyard", "courtyard.exr"),
    ("studio", "HDRI Studio", "studio.exr"),
    ("city", "HDRI City", "city.exr"),
    ("interior", "HDRI Interior", "interior.exr"),
    ("night", "HDRI Night", "night.exr"),
    ("sunrise", "HDRI Sunrise", "sunrise.exr"),
)

BUILTIN_ENVIRONMENT_PRESETS = (
    {
        "id": "neutral",
        "label": "Neutral",
        "viewerValue": "neutral",
        "kind": "model_viewer_builtin",
        "viewerAvailable": True,
    },
    {
        "id": "legacy",
        "label": "Studio",
        "viewerValue": "legacy",
        "kind": "model_viewer_builtin",
        "viewerAvailable": True,
    },
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _trellis_repo_dir() -> Path:
    configured = os.getenv("TRELLIS_REPO_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (_project_root() / ".runtime" / "TRELLIS.2").resolve()


def _read_exr_rgb(path: Path) -> tuple[np.ndarray | None, str | None]:
    os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
    try:
        import cv2
    except Exception as exc:  # noqa: BLE001
        return None, f"opencv_unavailable:{type(exc).__name__}:{exc}"

    try:
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    except Exception as exc:  # noqa: BLE001
        return None, f"exr_read_failed:{type(exc).__name__}:{exc}"
    if image is None:
        return None, "exr_read_failed:empty_image"

    if image.ndim == 2:
        rgb = np.stack([image, image, image], axis=-1)
    else:
        channels = image[:, :, :3]
        rgb = cv2.cvtColor(channels, cv2.COLOR_BGR2RGB)
    return np.asarray(rgb, dtype=np.float32), None


def _tonemap_exr(rgb: np.ndarray, *, max_width: int = 1024) -> Image.Image:
    data = np.nan_to_num(rgb, nan=0.0, posinf=0.0, neginf=0.0)
    data = np.maximum(data, 0.0)
    positive = data[data > 0.0]
    scale = float(np.percentile(positive, 99.5)) if positive.size else 1.0
    scale = max(scale, 1e-6)
    ldr = np.clip(data / scale, 0.0, 1.0)
    ldr = np.power(ldr, 1.0 / 2.2)
    image = Image.fromarray((ldr * 255.0).astype(np.uint8), mode="RGB")
    if image.width > max_width:
        height = max(1, round(image.height * (max_width / image.width)))
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
    return image


def _write_environment_pngs(src: Path, out_png: Path, preview_png: Path) -> tuple[bool, str | None]:
    rgb, error = _read_exr_rgb(src)
    if rgb is None:
        return False, error

    try:
        image = _tonemap_exr(rgb)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_png, format="PNG")
        preview = image.resize((320, max(1, round(image.height * (320 / image.width)))), Image.Resampling.LANCZOS)
        preview.save(preview_png, format="PNG")
    except Exception as exc:  # noqa: BLE001
        return False, f"png_conversion_failed:{type(exc).__name__}:{exc}"
    return True, None


def build_viewer_environment_package(output_dir: Path) -> dict[str, Any]:
    """Copy TRELLIS.2 HDRI assets and create browser-friendly environment presets.

    The EXR files are kept for DCC/package fidelity. Tonemapped PNG versions are
    generated for the web viewer because browser-side viewers are more reliable
    with regular image URLs than with OpenEXR files.
    """

    output_dir = ensure_dir(output_dir)
    hdri_dir = ensure_dir(output_dir / "hdri")
    trellis_hdri_dir = _trellis_repo_dir() / "assets" / "hdri"
    presets: list[dict[str, Any]] = [dict(item) for item in BUILTIN_ENVIRONMENT_PRESETS]
    copied: list[str] = []
    notes: list[str] = []

    license_src = trellis_hdri_dir / "license.txt"
    if license_src.exists():
        shutil.copy2(license_src, hdri_dir / "license.txt")

    for preset_id, label, file_name in TRELLIS_HDRI_PRESETS:
        src = trellis_hdri_dir / file_name
        if not src.exists():
            notes.append(f"missing_hdri:{file_name}")
            continue

        dest_exr = hdri_dir / file_name
        shutil.copy2(src, dest_exr)
        copied.append(f"hdri/{file_name}")

        png_name = f"{preset_id}.png"
        preview_name = f"{preset_id}_preview.png"
        converted, error = _write_environment_pngs(src, hdri_dir / png_name, hdri_dir / preview_name)
        if converted:
            copied.extend([f"hdri/{png_name}", f"hdri/{preview_name}"])
        elif error:
            notes.append(f"{preset_id}:{error}")

        presets.append(
            {
                "id": preset_id,
                "label": label,
                "kind": "trellis2_official_hdri",
                "sourceFile": f"hdri/{file_name}",
                "viewerValue": f"hdri/{png_name}" if converted else None,
                "previewImage": f"hdri/{preview_name}" if converted else None,
                "viewerAvailable": bool(converted),
                "dccReady": True,
            }
        )

    default_id = "forest" if any(item.get("id") == "forest" and item.get("viewerAvailable") for item in presets) else "neutral"
    payload = {
        "source": "trellis2_official_assets",
        "hdriDir": "hdri",
        "viewerSettingsFile": "viewer_settings.json",
        "defaultEnvironmentPreset": default_id,
        "environmentPresets": presets,
        "copiedFiles": copied,
        "notes": notes,
    }
    write_json(output_dir / "viewer_settings.json", payload)
    return payload
