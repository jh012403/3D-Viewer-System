from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pipelines.image_to_3d.multiview_generator import MultiViewGenerator


class MultiViewPrior:
    def __init__(self) -> None:
        self.enabled = os.getenv("MULTIVIEW_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        self.provider = os.getenv("MULTIVIEW_PROVIDER", "zero123plus").strip().lower() or "zero123plus"
        self.generator = MultiViewGenerator(enabled=self.enabled, provider=self.provider)

    def generate(self, input_image_path: Path, output_dir: Path) -> dict[str, Any]:
        return self.generator.generate(input_image_path, output_dir)


def run_multiview_prior(normalized_input_path: Path, work_dir: Path) -> dict[str, Any]:
    return MultiViewPrior().generate(normalized_input_path, work_dir)
