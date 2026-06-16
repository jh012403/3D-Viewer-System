from __future__ import annotations

import argparse
import os
from pathlib import Path

from pipelines.common.context import PipelineContext, PipelineMode
from pipelines.common.env import load_project_env
from pipelines.image_to_3d.pipeline import ImageTo3DPipeline


def resolve_mode(explicit_mode: str | None) -> PipelineMode:
    if explicit_mode:
        return explicit_mode  # type: ignore[return-value]
    mock_enabled = os.getenv("AI3D_MOCK_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
    return "mock" if mock_enabled else "real"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the image-to-3D pipeline.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--preview-dir", required=True)
    parser.add_argument("--temp-dir", required=True)
    parser.add_argument("--mode", choices=["mock", "real"])
    parser.add_argument("--requested-reconstruction-head")
    parser.add_argument("--image-quality-mode", choices=["high_quality"])
    parser.add_argument("--sam2-candidate-id")
    parser.add_argument("--source-prompt")
    return parser


def main() -> None:
    load_project_env()
    args = build_parser().parse_args()
    ctx = PipelineContext(
        job_id=args.job_id,
        input_file=Path(args.input_file),
        output_dir=Path(args.output_dir),
        preview_dir=Path(args.preview_dir),
        temp_dir=Path(args.temp_dir),
        mode=resolve_mode(args.mode),
        requested_reconstruction_head=args.requested_reconstruction_head,
        image_quality_mode=args.image_quality_mode,
        job_options={
            "requested_reconstruction_head": args.requested_reconstruction_head,
            "image_quality_mode": args.image_quality_mode,
            "sam2_candidate_id": args.sam2_candidate_id,
            "source_prompt": args.source_prompt,
        },
    )
    ImageTo3DPipeline().run(ctx)


if __name__ == "__main__":
    main()
