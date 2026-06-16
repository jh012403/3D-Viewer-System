from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipelines.common.reliability import PipelineStageError, classify_image_failure, reason_to_user_message, sanitize_error_message
from pipelines.image_to_3d.recon_heads import get_reconstruction_head
from pipelines.image_to_3d.reconstruction_head import ReconstructionResult


@dataclass(slots=True)
class ReconstructionExecution:
    result: ReconstructionResult
    metadata: dict[str, Any]
    raw_mesh_path: Path
    primary_wrapper_log_path: Path | None


def run_reconstruction(
    *,
    input_image: Path,
    multiview_info: dict[str, Any],
    work_dir: Path,
    output_dir: Path,
    object_name: str,
    requested_head: str,
    requested_head_chain: list[str],
    image_quality_mode: str,
    pipeline_profile: str,
) -> ReconstructionExecution:
    reconstruction_attempts: list[dict[str, object]] = []
    last_exception: Exception | None = None

    def _availability_reason(attempts: list[dict[str, object]]) -> str:
        blob = " ".join(
            str(issue).lower()
            for attempt in attempts
            for issue in (attempt.get("issues") or [])
        )
        if any(
            token in blob
            for token in (
                "runtime_module_unavailable",
                "hf_asset_unavailable",
                "repo_dirty",
                "repo_status_probe_failed",
            )
        ):
            return "trellis_official_runtime_unavailable"
        return "reconstruction_head_unavailable"

    for head_name in requested_head_chain:
        head_work_dir = (work_dir / head_name).expanduser().resolve()
        head_work_dir.mkdir(parents=True, exist_ok=True)
        reconstruction_head = get_reconstruction_head(head_name)
        availability = reconstruction_head.availability()
        attempt_record: dict[str, object] = {
            "head": head_name,
            "available": bool(availability.get("available")),
            "issues": availability.get("issues") or [],
            "availability": availability,
        }
        if not availability.get("available"):
            attempt_record["status"] = "skipped_unavailable"
            reconstruction_attempts.append(attempt_record)
            continue

        try:
            reconstruction_result = reconstruction_head.reconstruct(
                input_image=input_image,
                multiview_info=multiview_info,
                work_dir=head_work_dir,
                output_dir=output_dir,
                object_name=object_name,
            )
            raw_mesh_path = reconstruction_result.mesh_path
            if not raw_mesh_path.exists():
                raise PipelineStageError(
                    "object_mesh_failed",
                    "obj_missing",
                    reason_to_user_message("obj_missing"),
                    f"Reconstruction head '{reconstruction_result.used_head}' returned a missing mesh path: {raw_mesh_path}",
                )
            primary_wrapper_log_path = None
            if reconstruction_result.log_paths:
                primary_wrapper_log_path = Path(next(iter(reconstruction_result.log_paths.values()))).expanduser().resolve()

            attempt_record.update(
                {
                    "status": "completed",
                    "mesh_path": str(raw_mesh_path),
                    "used_head": reconstruction_result.used_head,
                    "multiview_source": reconstruction_result.multiview_source,
                    "log_paths": reconstruction_result.log_paths,
                }
            )
            reconstruction_attempts.append(attempt_record)

            raw_outputs = reconstruction_result.raw_outputs or {}
            reconstruction_head_metadata = {
                **reconstruction_result.to_metadata(),
                "requested": requested_head,
                "requested_quality_mode": image_quality_mode,
                "pipeline_profile": pipeline_profile,
                "status": "completed" if head_name == requested_head_chain[0] else "fallback_success",
                "available": True,
                "availability": availability,
                "fallback_chain": requested_head_chain[1:],
                "attempted_heads": reconstruction_attempts,
                "resolved_backend": reconstruction_result.resolved_backend or reconstruction_result.used_head,
                "mesh_backend": (
                    reconstruction_result.mesh_backend
                    or reconstruction_result.to_metadata().get("mesh_backend")
                    or reconstruction_result.used_head
                ),
                "mesh_backend_configured": raw_outputs.get("mesh_backend_configured"),
                "mesh_backend_chain": raw_outputs.get("mesh_backend_chain"),
                "mesh_backend_attempts": raw_outputs.get("mesh_backend_attempts"),
                "fallback_used": head_name != requested_head_chain[0],
            }
            return ReconstructionExecution(
                result=reconstruction_result,
                metadata=reconstruction_head_metadata,
                raw_mesh_path=raw_mesh_path,
                primary_wrapper_log_path=primary_wrapper_log_path,
            )
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            stage_error = classify_image_failure(exc)
            attempt_record.update(
                {
                    "status": "failed",
                    "reason": stage_error.reason,
                    "error": stage_error.detail or sanitize_error_message(exc),
                }
            )
            reconstruction_attempts.append(attempt_record)

    unavailable_attempts = [
        attempt for attempt in reconstruction_attempts if attempt.get("status") == "skipped_unavailable"
    ]
    if reconstruction_attempts and len(unavailable_attempts) == len(reconstruction_attempts):
        unavailable_reason = _availability_reason(unavailable_attempts)
        raise PipelineStageError(
            "object_mesh_failed",
            unavailable_reason,
            reason_to_user_message(unavailable_reason),
            f"Requested head chain {requested_head_chain} is unavailable: {reconstruction_attempts}",
        )
    if last_exception is not None:
        raise last_exception
    raise PipelineStageError(
        "object_mesh_failed",
        "reconstruction_head_unavailable",
        reason_to_user_message("reconstruction_head_unavailable"),
        f"Requested head chain {requested_head_chain} did not produce a mesh.",
    )
