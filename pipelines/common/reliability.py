from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipelines.common.io import ensure_dir, write_json


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_stage() -> tuple[str, float]:
    return utcnow_iso(), time.perf_counter()


def sanitize_error_message(error: Exception | str | None, limit: int = 240) -> str | None:
    if error is None:
        return None
    text = str(error).strip().splitlines()[0].strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def write_exception_trace(stage_logs_dir: Path, stage: str, error: Exception) -> Path:
    stage_logs_dir = ensure_dir(stage_logs_dir)
    trace_path = stage_logs_dir / f"{stage}.trace.txt"
    trace_path.write_text(
        "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        encoding="utf-8",
    )
    return trace_path


def write_stage_log(
    stage_logs_dir: Path,
    *,
    stage: str,
    status: str,
    started_at: str,
    started_perf: float,
    input_path: str | None,
    output_path: str | None,
    reason: str | None = None,
    error: str | None = None,
    trace_path: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    ended_at = utcnow_iso()
    payload: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "start_time": started_at,
        "end_time": ended_at,
        "duration_sec": round(time.perf_counter() - started_perf, 3),
        "input_path": input_path,
        "output_path": output_path,
        "reason": reason,
        "error": error,
        "error_trace": str(trace_path) if trace_path else None,
    }
    if extra:
        payload.update(extra)
    return write_json(ensure_dir(stage_logs_dir) / f"{stage}.json", payload)


def reason_to_user_message(reason: str) -> str:
    messages = {
        "image_preprocess_failed": "The uploaded image could not be normalized into a clean object-centered input.",
        "foreground_extraction_failed": "Foreground extraction failed before the image could be normalized.",
        "foreground_provider_fallback_used": "The preferred foreground model was unavailable, so the pipeline used a heuristic fallback.",
        "multiview_prior_failed": "The image pipeline failed while preparing the multiview prior handoff.",
        "multiview_generation_failed": "The multi-view prior stage failed before reconstruction could start.",
        "multiview_fallback_used": "The preferred multi-view prior failed, so the pipeline fell back to the single-view path.",
        "reconstruction_head_unavailable": "The selected reconstruction head is not available in the current runtime environment.",
        "trellis_official_runtime_unavailable": "TRELLIS.2 official runtime is not ready. Required CUDA extensions or gated model assets are missing, so the service is refusing to run a degraded fallback.",
        "reconstruction_runtime_error": "The reconstruction backend failed while generating the object mesh.",
        "hunyuan3d_runtime_error": "Hunyuan3D failed while generating the object mesh.",
        "trellis_runtime_error": "TRELLIS.2 failed while generating the object mesh.",
        "obj_missing": "The reconstruction stage finished, but no mesh file was produced.",
        "mesh_cleanup_failed": "The raw object mesh was produced, but cleanup failed before the final GLB export.",
        "asset_metadata_failed": "The object mesh was produced, but semantic metadata extraction failed.",
        "material_package_failed": "The object mesh was produced, but PBR material packaging failed.",
        "mesh_conversion_failed": "The generated OBJ mesh could not be converted into a GLB file.",
        "thumbnail_render_failed": "The thumbnail renderer failed for the generated mesh.",
        "quality_failed": "The pipeline completed, but the quality checks marked the output as unreliable.",
        "poor_reconstruction": "The mesh was generated, but the reconstructed geometry is still too weak for a reliable high-quality result.",
    }
    return messages.get(reason, "The pipeline failed for an unknown reason.")


@dataclass(slots=True)
class PipelineStageError(RuntimeError):
    stage: str
    reason: str
    user_message: str
    detail: str | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.user_message)


def classify_image_failure(error: Exception) -> PipelineStageError:
    message = (sanitize_error_message(error) or "").lower()
    if (
        "runtime_module_unavailable" in message
        or "hf_asset_unavailable" in message
        or "repo_dirty" in message
        or "strict official runtime" in message
    ):
        reason = "trellis_official_runtime_unavailable"
    elif "selected reconstruction head" in message or "runtime not available" in message or "reconstruction head is not available" in message:
        reason = "reconstruction_head_unavailable"
    elif "trellis" in message:
        reason = "trellis_runtime_error"
    elif "hunyuan3d" in message or "hunyuan 3d" in message:
        reason = "hunyuan3d_runtime_error"
    elif "preprocess" in message or "normalized" in message or "foreground" in message:
        reason = "image_preprocess_failed"
    elif "multiview prior" in message:
        reason = "multiview_prior_failed"
    elif "cleanup" in message:
        reason = "mesh_cleanup_failed"
    elif "without generating an obj" in message or "missing obj path" in message or "missing obj" in message:
        reason = "obj_missing"
    elif "obj -> glb conversion failed" in message or "conversion failed" in message:
        reason = "mesh_conversion_failed"
    elif "thumbnail" in message:
        reason = "thumbnail_render_failed"
    else:
        reason = "reconstruction_runtime_error"
    return PipelineStageError("object_mesh_failed", reason, reason_to_user_message(reason), sanitize_error_message(error))
