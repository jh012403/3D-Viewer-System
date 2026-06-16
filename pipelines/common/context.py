from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PipelineMode = Literal["mock", "real"]


@dataclass(frozen=True)
class PipelineContext:
    job_id: str
    input_file: Path
    output_dir: Path
    preview_dir: Path
    temp_dir: Path
    mode: PipelineMode
    requested_reconstruction_head: str | None = None
    image_quality_mode: str | None = None
    job_options: dict[str, object] | None = None
