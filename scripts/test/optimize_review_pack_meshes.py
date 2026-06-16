#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from pipelines.image_to_3d.mesh_optimize import MeshOptimizeConfig, optimize_mesh


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply mesh optimization to every backend result in a review pack.")
    parser.add_argument("--source-review-root", required=True, help="Path to source review pack directory.")
    parser.add_argument("--target-review-root", required=True, help="Path to target optimized review pack directory.")
    parser.add_argument("--resolution", type=int, default=220, help="Voxel resolution for optimization.")
    parser.add_argument("--close-iterations", type=int, default=2, help="Binary closing iterations.")
    parser.add_argument("--open-iterations", type=int, default=1, help="Binary opening iterations.")
    parser.add_argument("--humphrey-iterations", type=int, default=4, help="Humphrey smoothing iterations.")
    parser.add_argument("--min-component-face-ratio", type=float, default=0.03, help="Component filtering threshold.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite target directory if it already exists.")
    return parser.parse_args()


def load_summary(path: Path) -> dict[str, Any]:
    summary_path = path / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"summary.json not found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    source = Path(args.source_review_root).expanduser().resolve()
    target = Path(args.target_review_root).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"source review pack not found: {source}")

    if target.exists():
        if not args.overwrite:
            raise SystemExit(f"target already exists: {target}. Use --overwrite to replace it.")
        shutil.rmtree(target)

    shutil.copytree(source, target)
    summary = load_summary(target)
    optimization_reports: list[dict[str, Any]] = []
    logs_root = target / "_optimization_logs"
    logs_root.mkdir(parents=True, exist_ok=True)

    config = MeshOptimizeConfig(
        resolution=args.resolution,
        close_iterations=args.close_iterations,
        open_iterations=args.open_iterations,
        humphrey_iterations=args.humphrey_iterations,
        min_component_face_ratio=args.min_component_face_ratio,
    )

    for sample in summary.get("samples", []):
        sample_name = str(sample.get("sample_name", "sample"))
        for result in sample.get("results", []):
            backend = str(result.get("backend", "backend"))
            mesh_rel = str(result.get("mesh", "")).strip()
            if not mesh_rel:
                continue
            mesh_path = target / mesh_rel
            if not mesh_path.exists():
                continue

            mesh_before_path = mesh_path.with_name("mesh_before_optimize.glb")
            if not mesh_before_path.exists():
                shutil.copy2(mesh_path, mesh_before_path)

            work_dir = logs_root / sample_name / backend
            try:
                report = optimize_mesh(mesh_before_path, mesh_path, work_dir, config=config)
                result["optimize_status"] = "optimized"
                result["mesh_before_optimize"] = str(mesh_before_path.relative_to(target))
                result["optimize_report"] = str((work_dir / "mesh_optimize_report.json").relative_to(target))
                result["optimized_vertices"] = report.get("optimized_vertices")
                result["optimized_faces"] = report.get("optimized_faces")
                result["source_vertices"] = report.get("source_vertices")
                result["source_faces"] = report.get("source_faces")
                optimization_reports.append(
                    {
                        "sample_name": sample_name,
                        "backend": backend,
                        "mesh": mesh_rel,
                        "status": "optimized",
                        "report": report,
                    }
                )
                print(f"[optimized] sample={sample_name} backend={backend}")
            except Exception as exc:  # noqa: BLE001
                result["optimize_status"] = "failed"
                result["optimize_error"] = str(exc)
                optimization_reports.append(
                    {
                        "sample_name": sample_name,
                        "backend": backend,
                        "mesh": mesh_rel,
                        "status": "failed",
                        "error": str(exc),
                    }
                )
                print(f"[failed] sample={sample_name} backend={backend} error={exc}")

    summary["postprocess"] = {
        "mesh_optimization": {
            "enabled": True,
            "config": {
                "resolution": config.resolution,
                "close_iterations": config.close_iterations,
                "open_iterations": config.open_iterations,
                "humphrey_iterations": config.humphrey_iterations,
                "min_component_face_ratio": config.min_component_face_ratio,
            },
            "report_count": len(optimization_reports),
            "logs_root": str(logs_root.relative_to(target)),
        }
    }

    summary_path = target / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (target / "optimization_summary.json").write_text(json.dumps(optimization_reports, indent=2), encoding="utf-8")
    print(f"optimized review pack: {target}")
    print(f"summary: {summary_path}")
    print(f"optimization_summary: {target / 'optimization_summary.json'}")


if __name__ == "__main__":
    main()

