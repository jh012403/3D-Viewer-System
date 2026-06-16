#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python - "$@" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pipelines.common.env import load_project_env
from pipelines.image_to_3d.recon_heads import get_reconstruction_head
from pipelines.image_to_3d.reconstruction_head import normalize_head_name, resolve_reconstruction_head_chain


ROOT = Path.cwd()
REPORTS_DIR = ROOT / "storage" / "test_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
load_project_env()

requested_samples = [Path(arg).expanduser().resolve() for arg in sys.argv[1:]]
default_samples = [
    ROOT / "storage" / "uploads" / "job_000046" / "input_image.jpg",
    ROOT / "storage" / "uploads" / "job_000049" / "input_image.jpg",
    ROOT / "storage" / "uploads" / "job_000050" / "input_image.jpg",
]
samples = requested_samples or [path.resolve() for path in default_samples if path.exists()]
heads = [
    head
    for head in os.getenv("IMAGE_RECON_BENCHMARK_HEADS", "trellis").split()
    if head.strip()
]
heads = sorted({normalize_head_name(head) for head in heads})
timestamp = time.strftime("%Y%m%d_%H%M%S")
report_path = REPORTS_DIR / f"image_recon_benchmark_{timestamp}.json"
records: list[dict[str, object]] = []


def sample_label(path: Path) -> str:
    mapping = {
        "job_000049": "cake",
        "job_000050": "museum",
        "job_000046": "character",
    }
    return mapping.get(path.parent.name, path.stem)


def read_metadata(metadata_path: Path) -> dict:
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def describe_shape(summary: dict[str, object]) -> str:
    if summary.get("quality_status") != "passed":
        return "failed"
    if summary.get("bbox_valid") is False:
        return "invalid_bbox"
    component_count = summary.get("component_count")
    if isinstance(component_count, int) and component_count > 1:
        return "fragmented"
    component_ratio = summary.get("largest_component_ratio")
    if isinstance(component_ratio, (float, int)) and float(component_ratio) < 0.75:
        return "fragmented"
    quality_hints = summary.get("quality_hints", [])
    if any("slab" in str(item).lower() for item in quality_hints):
        return "slab_like"
    return "shape_preserved"


for sample in samples:
    if not sample.exists():
        records.append(
            {
                "sample_name": sample.stem,
                "sample_path": str(sample),
                "head_name": None,
                "status": "missing_sample",
                "reason": "sample_not_found",
            }
        )
        continue

    for head_name in heads:
        normalized_head = normalize_head_name(head_name)
        chain = resolve_reconstruction_head_chain(normalized_head)
        per_head = {candidate: get_reconstruction_head(candidate).availability() for candidate in chain}
        availability = {
            "head": normalized_head,
            "available": any(result.get("available") for result in per_head.values()),
            "chain": chain,
            "per_head": per_head,
            "issues": [
                f"{candidate}:{','.join(result.get('issues') or [])}"
                for candidate, result in per_head.items()
                if not result.get("available")
            ],
        }
        record: dict[str, object] = {
            "sample_name": sample_label(sample),
            "sample_path": str(sample),
            "head_name": normalized_head,
            "availability": availability,
        }
        if not availability.get("available"):
            record.update(
                {
                    "status": "skipped_unavailable",
                    "runtime_sec": None,
                    "reason": "runtime_unavailable",
                    "issues": availability.get("issues") or [],
                }
            )
            records.append(record)
            continue

        job_id = f"bench_{sample_label(sample)}_{normalized_head}_{time.strftime('%H%M%S')}"
        output_dir = ROOT / "storage" / "outputs" / job_id
        preview_dir = ROOT / "storage" / "previews" / job_id
        temp_dir = ROOT / "storage" / "temp" / job_id
        metadata_path = output_dir / "object_metadata.json"
        env = os.environ.copy()
        env["AI3D_MOCK_MODE"] = "false"
        env["IMAGE_RECON_HEAD"] = normalized_head
        image_quality_mode = "high_quality"

        started = time.perf_counter()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pipelines.image_to_3d.cli",
                "--job-id",
                job_id,
                "--input-file",
                str(sample),
                "--output-dir",
                str(output_dir),
                "--preview-dir",
                str(preview_dir),
                "--temp-dir",
                str(temp_dir),
                "--mode",
                "real",
                "--requested-reconstruction-head",
                normalized_head,
                "--image-quality-mode",
                image_quality_mode,
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        runtime_sec = round(time.perf_counter() - started, 3)
        metadata = read_metadata(metadata_path)
        quality = metadata.get("quality") or {}
        quality_checks = quality.get("checks") or {}
        quality_metrics = quality.get("metrics") or {}
        status = "completed" if completed.returncode == 0 and metadata.get("status") == "completed" else "failed"
        record.update(
            {
                "job_id": job_id,
                "status": status,
                "runtime_sec": runtime_sec,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "metadata_path": str(metadata_path) if metadata_path.exists() else None,
                "stage": metadata.get("stage"),
                "reason": metadata.get("reason"),
                "quality_status": metadata.get("quality_status"),
                "quality_hints": quality.get("hints") or quality_metrics.get("quality_hints") or [],
                "mesh_file_size": quality_metrics.get("mesh_size_bytes"),
                "component_count": quality_metrics.get("component_count"),
                "largest_component_ratio": quality_metrics.get("largest_component_ratio"),
                "bbox_valid": quality_checks.get("bbox_valid"),
                "viewer_load_success": quality_checks.get("mesh_loadable"),
                "reconstruction_head": metadata.get("reconstruction_head"),
            }
        )
        reconstruction_head = metadata.get("reconstruction_head") or {}
        record["requested_reconstruction_head"] = metadata.get("requested_reconstruction_head") or normalized_head
        record["resolved_backend"] = reconstruction_head.get("used") or metadata.get("resolved_backend") or metadata.get("reconstruction_head", {}).get("used")
        record["fallback_used"] = reconstruction_head.get("fallback_used", False)
        record["mesh_backend"] = reconstruction_head.get("mesh_backend") or metadata.get("mesh_backend")
        record["attempted_heads"] = [
            attempt.get("head")
            for attempt in (reconstruction_head.get("attempted_heads") or [])
            if isinstance(attempt, dict) and attempt.get("head")
        ]
        record["shape_quality_summary"] = describe_shape(record)
        records.append(record)

report = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "heads": heads,
    "samples": [str(sample) for sample in samples],
    "records": records,
}
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Wrote benchmark report to {report_path}")
PY
