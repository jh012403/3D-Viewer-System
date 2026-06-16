from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines.image_to_3d.image_normalize import normalize_image_for_reconstruction


def normalize_image(
    input_image: Path,
    foreground_result: dict[str, Any],
    work_dir: Path,
) -> dict[str, Any]:
    """Normalize a foreground-extracted image into a canonical square GLB-friendly input.

    The pipeline keeps this adapter thin so we can evolve the
    normalization strategy while preserving compatibility with existing
    callers and metadata shape.
    """
    payload = normalize_image_for_reconstruction(input_image, foreground_result, work_dir)
    payload["normalized"] = True
    return payload

