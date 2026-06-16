from __future__ import annotations

import os
import json
import shutil
from pathlib import Path

from pipelines.common.context import PipelineContext
from pipelines.common.io import ensure_dir, write_json
from pipelines.common.mock_assets import write_mock_object_glb, write_thumbnail
from pipelines.common.quality_gate import evaluate_image_quality
from pipelines.common.reliability import (
    PipelineStageError,
    classify_image_failure,
    reason_to_user_message,
    sanitize_error_message,
    start_stage,
    utcnow_iso,
    write_exception_trace,
    write_stage_log,
)
from pipelines.common.thumbnail import generate_thumbnail
from pipelines.image_to_3d.material_package import build_material_package
from pipelines.image_to_3d.mesh_cleanup import cleanup_mesh
from pipelines.image_to_3d.multiview_generator import run_multiview_generation
from pipelines.image_to_3d.preprocess import segment_foreground, normalize_image
from pipelines.image_to_3d.reconstruction import run_reconstruction
from pipelines.image_to_3d.reconstruction_head import (
    PRODUCTION_BACKEND_POLICY,
    resolve_image_quality_mode,
    resolve_reconstruction_head_chain,
    resolve_requested_reconstruction_head,
)
from pipelines.image_to_3d.semantic_metadata import build_asset_metadata, normalize_category
from pipelines.image_to_3d.viewer_environment import build_viewer_environment_package


class ImageTo3DPipeline:
    def run(self, ctx: PipelineContext) -> None:
        requested_reconstruction_head = resolve_requested_reconstruction_head(
            ctx.requested_reconstruction_head,
            ctx.image_quality_mode,
        )
        image_quality_mode = resolve_image_quality_mode(ctx.image_quality_mode, requested_reconstruction_head)
        pipeline_profile = "high_quality"
        requested_head_chain = resolve_reconstruction_head_chain(requested_reconstruction_head)
        trellis_direct_input_enabled = (
            len(requested_head_chain) > 0
            and requested_head_chain[0] == "trellis"
            and os.getenv("AI3D_TRELLIS_DIRECT_INPUT", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        skip_multiview_prior = (
            os.getenv("AI3D_SKIP_MULTIVIEW_FOR_DIRECT_RECON", "true").strip().lower() in {"1", "true", "yes", "on"}
            and len(requested_head_chain) > 0
            and requested_head_chain[0] in {"hunyuan3d", "trellis"}
        )
        pipeline_stages = ["trellis_direct_input"] if trellis_direct_input_enabled else ["foreground_extract", "image_normalize"]
        pipeline_stages.append("asset_metadata")
        if not skip_multiview_prior:
            pipeline_stages.append("multiview_generation")
        pipeline_stages.extend(["reconstruction", "mesh_cleanup", "material_package"])
        backend_policy = PRODUCTION_BACKEND_POLICY
        foreground_provider_mode = os.getenv("AI3D_HIGH_QUALITY_FOREGROUND_PROVIDER", "sam").strip().lower() or "sam"
        selected_candidate_id = str((ctx.job_options or {}).get("sam2_candidate_id") or "").strip() or None
        image_dir = ensure_dir(ctx.temp_dir / "image")
        multiview_dir = ensure_dir(ctx.temp_dir / "multiview")
        work_dir = ensure_dir(ctx.temp_dir / "reconstruction")
        cleanup_dir = ensure_dir(ctx.temp_dir / "mesh_cleanup")
        stage_logs_dir = ensure_dir(ctx.temp_dir / "stage_logs")
        mesh_path = ctx.output_dir / "object_mesh.glb"
        preview_path = ctx.preview_dir / "object_thumbnail.png"
        metadata_path = ctx.output_dir / "object_metadata.json"
        asset_metadata_path = ctx.output_dir / "metadata.json"
        material_path = ctx.output_dir / "material.json"
        textures_dir = ctx.output_dir / "textures"
        viewer_settings_path = ctx.output_dir / "viewer_settings.json"
        hdri_dir = ctx.output_dir / "hdri"

        raw_mesh_path: Path | None = None
        normalized_input_path: Path | None = None
        multiview_input_path: Path | None = None
        reconstruction_input_path: Path | None = None
        foreground_result: dict[str, object] | None = None
        normalization_result: dict[str, object] | None = None
        primary_wrapper_log_path: Path | None = None
        thumbnail_status = "not_started"
        conversion_status = "not_started"
        stage_log_paths: dict[str, str] = {}
        stage_timers: dict[str, tuple[str, float]] = {}
        quality: dict[str, object] = {"status": "not_evaluated", "checks": {}, "summary": "Quality gate has not run yet."}
        preprocess_hints: list[str] = []
        raw_mesh_archive_path: Path | None = None
        image_preprocess: dict[str, object] = {
            "pipeline_profile": pipeline_profile,
            "foreground_provider_requested": None,
            "foreground_provider_used": None,
            "foreground_provider_fallback_used": False,
            "foreground_extracted": False,
            "crop_applied": False,
            "background_mode": "unknown",
            "sam_used": False,
            "segmentation_area_ratio": 0.0,
            "segmentation_components": 0,
            "segmentation_attempt": None,
            "segmentation_valid": False,
            "normalized": False,
            "hints": preprocess_hints,
        }
        multiview_prior: dict[str, object] = {
            "enabled": False,
            "active": False,
            "mode": "not_started",
            "status": "not_started",
        }
        reconstruction_head_metadata: dict[str, object] = {
            "requested": requested_reconstruction_head,
            "requested_quality_mode": image_quality_mode,
            "pipeline_profile": pipeline_profile,
            "used": None,
            "status": "not_started",
            "available": None,
            "issues": [],
            "fallback_chain": requested_head_chain[1:],
            "attempted_heads": [],
            "mesh_path": None,
            "multiview_source": None,
            "log_paths": {},
            "raw_outputs": {},
            "notes": [],
        }
        mesh_cleanup_metadata: dict[str, object] = {
            "largest_component_only": True,
            "removed_small_components": 0,
            "cleanup_status": "not_started",
        }
        asset_metadata: dict[str, object] = {}
        material_package: dict[str, object] = {}
        viewer_environment_package: dict[str, object] = {}

        metadata = {
            "job_id": ctx.job_id,
            "type": "image_to_3d",
            "mode": ctx.mode,
            "requested_mode": image_quality_mode,
            "sam2_candidate_id_requested": selected_candidate_id,
            "requested_reconstruction_head": requested_reconstruction_head,
            "requested_head_chain": requested_head_chain,
            "resolved_backend": None,
            "backend_policy": backend_policy,
            "reconstruction_backend": None,
            "mesh_backend": None,
            "fallback_used": False,
            "fallback_chain": requested_head_chain[1:],
            "image_quality_mode": image_quality_mode,
            "pipeline_profile": pipeline_profile,
            "pipeline": pipeline_stages,
            "input_file": str(ctx.input_file),
            "foreground_file": None,
            "mask_file": None,
            "normalized_input_file": None,
            "multiview_input_file": None,
            "reconstruction_input_file": None,
            "raw_mesh_file": None,
            "obj_file": None,
            "raw_mesh_archive_file": None,
            "mesh_file": str(mesh_path),
            "material_file": str(material_path),
            "asset_metadata_file": str(asset_metadata_path),
            "textures_dir": str(textures_dir),
            "viewer_settings_file": str(viewer_settings_path),
            "hdri_dir": str(hdri_dir),
            "preview_file": str(preview_path),
            "temp_dir": str(ctx.temp_dir),
            "wrapper_log": None,
            "conversion_status": conversion_status,
            "thumbnail_status": thumbnail_status,
            "image_preprocess": image_preprocess,
            "multiview_prior": multiview_prior,
            "reconstruction_head": reconstruction_head_metadata,
            "mesh_cleanup": mesh_cleanup_metadata,
            "asset_metadata": asset_metadata,
            "material_package": material_package,
            "viewer_environment_package": viewer_environment_package,
            "stage": "image_preprocess_running",
            "status": "running",
            "reason": None,
            "user_message": None,
            "quality": quality,
            "quality_status": quality["status"],
            "stage_logs": stage_log_paths,
            "created_at": utcnow_iso(),
        }

        def persist(**updates: object) -> None:
            metadata.update(updates)
            write_json(metadata_path, metadata)

        def _resolve_reconstruction_fields(fields: dict[str, object]) -> tuple[str | None, str | None, str | None, bool]:
            raw_outputs = fields.get("raw_outputs")
            resolved_backend = fields.get("resolved_backend") or fields.get("used") or fields.get("used_head")
            reconstruction_backend = fields.get("reconstruction_backend") or resolved_backend
            mesh_backend = fields.get("mesh_backend")
            if isinstance(raw_outputs, dict):
                mesh_backend = mesh_backend or raw_outputs.get("mesh_backend")

            if mesh_backend is None:
                mesh_backend = resolved_backend

            fallback_used = bool(fields.get("fallback_used"))
            return (
                str(resolved_backend) if resolved_backend else None,
                str(reconstruction_backend) if reconstruction_backend else None,
                str(mesh_backend) if mesh_backend else None,
                fallback_used,
            )

        def _selected_candidate_image(candidate_id: str) -> Path:
            safe_id = candidate_id.strip()
            if not safe_id or "/" in safe_id or "\\" in safe_id or safe_id.startswith("."):
                raise RuntimeError("Invalid object candidate id.")
            candidate_path = (
                ctx.temp_dir
                / "sam2_candidates"
                / "candidates"
                / safe_id
                / "segmented.png"
            ).expanduser().resolve()
            allowed_root = (ctx.temp_dir / "sam2_candidates" / "candidates").expanduser().resolve()
            if allowed_root not in candidate_path.parents:
                raise RuntimeError("Object candidate path resolved outside the candidate directory.")
            if not candidate_path.exists():
                raise RuntimeError(
                    f"Selected object candidate image is missing: {safe_id}. "
                    "Refresh object candidates and start again."
                )
            return candidate_path

        def _source_prompt() -> str:
            raw = str((ctx.job_options or {}).get("source_prompt") or "").strip()
            if raw:
                return raw
            if not selected_candidate_id:
                return ""
            prompt_path = ctx.temp_dir / "sam2_candidates" / "prompt" / "sam3_text_prompt.json"
            if not prompt_path.exists():
                return ""
            try:
                payload = json.loads(prompt_path.read_text(encoding="utf-8"))
            except Exception:
                return ""
            return str(payload.get("prompt") or "").strip()

        def _source_category_id() -> str:
            return str(normalize_category(_source_prompt()).get("normalized_category_id") or "unknown")

        def _trellis_input_contract(image_path: Path, *, selected_object: bool) -> dict[str, object]:
            try:
                from PIL import Image

                with Image.open(image_path) as image:
                    mode = image.mode
                    width, height = image.size
                    rgba = image.convert("RGBA")
                    alpha = rgba.getchannel("A")
                    alpha_min, alpha_max = alpha.getextrema()
                    hist = alpha.histogram()
                    total = max(1, sum(hist))
                    alpha_coverage = float(sum(hist[9:]) / total)
                    has_alpha_cutout = alpha_min < 255
            except Exception as exc:  # noqa: BLE001
                return {
                    "status": "unreadable",
                    "path": str(image_path),
                    "error": sanitize_error_message(exc),
                }
            status = (
                "official_like_alpha_masked_object"
                if has_alpha_cutout
                else "alpha_free_original_official_rembg_required"
            )
            return {
                "status": status,
                "path": str(image_path),
                "source": "selected_object_cutout" if selected_object else "original_upload",
                "mode": mode,
                "size": [int(width), int(height)],
                "has_alpha_cutout": bool(has_alpha_cutout),
                "alpha_coverage": round(alpha_coverage, 4),
                "official_trellis_preprocess": True,
            }

        def fail_stage(stage_name: str, error: Exception, *, input_path: str | None, output_path: str | None) -> None:
            stage_error = error if isinstance(error, PipelineStageError) else classify_image_failure(error)
            trace_path = write_exception_trace(stage_logs_dir, stage_name, error)
            started_at, started_perf = stage_timers[stage_name]
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage=stage_name,
                status="failed",
                started_at=started_at,
                started_perf=started_perf,
                input_path=input_path,
                output_path=output_path,
                reason=stage_error.reason,
                error=stage_error.detail or sanitize_error_message(error),
                trace_path=trace_path,
                extra={"mode": ctx.mode},
            )
            stage_log_paths[stage_name] = str(stage_log_path)
            resolved_backend, reconstruction_backend, mesh_backend, fallback_used = _resolve_reconstruction_fields(
                reconstruction_head_metadata
            )
            persist(
                raw_mesh_file=str(raw_mesh_path) if raw_mesh_path else None,
                obj_file=str(raw_mesh_path) if raw_mesh_path and raw_mesh_path.suffix.lower() == ".obj" else None,
                raw_mesh_archive_file=str(raw_mesh_archive_path) if raw_mesh_archive_path else None,
                normalized_input_file=str(normalized_input_path) if normalized_input_path else None,
                multiview_input_file=str(multiview_input_path) if multiview_input_path else None,
                reconstruction_input_file=str(reconstruction_input_path) if reconstruction_input_path else None,
                wrapper_log=str(primary_wrapper_log_path) if primary_wrapper_log_path and primary_wrapper_log_path.exists() else None,
                conversion_status=conversion_status,
                thumbnail_status=thumbnail_status,
                image_preprocess=image_preprocess,
                multiview_prior=multiview_prior,
                reconstruction_head=reconstruction_head_metadata,
                requested_mode=image_quality_mode,
                resolved_backend=resolved_backend,
                reconstruction_backend=reconstruction_backend,
                mesh_backend=mesh_backend,
                fallback_used=fallback_used,
                mesh_cleanup=mesh_cleanup_metadata,
                asset_metadata=asset_metadata,
                material_package=material_package,
                viewer_environment_package=viewer_environment_package,
                stage=stage_error.stage,
                status="failed",
                reason=stage_error.reason,
                user_message=stage_error.user_message,
                quality_status=quality["status"],
                quality=quality,
                stage_logs=stage_log_paths,
            )
            raise RuntimeError(stage_error.user_message) from error

            persist()

        stage_timers["image_preprocess"] = start_stage()
        persist(stage="image_preprocess_running", status="running", reason=None, user_message=None)
        try:
            if trellis_direct_input_enabled:
                selected_candidate_path = _selected_candidate_image(selected_candidate_id) if selected_candidate_id else None
                normalized_input_path = selected_candidate_path or ctx.input_file.expanduser().resolve()
                multiview_input_path = normalized_input_path
                reconstruction_input_path = normalized_input_path
                trellis_input_contract = _trellis_input_contract(
                    reconstruction_input_path,
                    selected_object=bool(selected_candidate_path),
                )
                preprocess_hints = sorted(
                    set(
                        preprocess_hints
                        + [
                            "trellis_official_direct_input",
                            "object_selection_input" if selected_candidate_path else "original_input",
                            "trellis_official_alpha_masked_input"
                            if trellis_input_contract.get("has_alpha_cutout")
                            else "trellis_official_rembg_required",
                        ]
                    )
                )
                image_preprocess = {
                    "pipeline_profile": pipeline_profile,
                    "foreground_provider_requested": "user_selected_object" if selected_candidate_path else None,
                    "foreground_provider_used": "object_candidate" if selected_candidate_path else None,
                    "foreground_provider_fallback_used": False,
                    "foreground_extracted": bool(selected_candidate_path),
                    "crop_applied": False,
                    "background_mode": "selected_object_rgba" if selected_candidate_path else "original",
                    "sam_used": bool(selected_candidate_path),
                    "object_candidate_id": selected_candidate_id,
                    "object_candidate_image": str(selected_candidate_path) if selected_candidate_path else None,
                    "segmentation_area_ratio": 0.0,
                    "segmentation_components": 0,
                    "segmentation_attempt": "user_selected_candidate" if selected_candidate_path else "skipped",
                    "segmentation_valid": True,
                    "normalized": False,
                    "direct_input_enabled": True,
                    "trellis_input_file": str(reconstruction_input_path),
                    "trellis_input_strategy": (
                        "selected_object_image_to_trellis_official_preprocess"
                        if selected_candidate_path
                        else "direct_original_input_to_trellis_official_preprocess"
                    ),
                    "trellis_input_alpha_free": not bool(selected_candidate_path),
                    "trellis_input_contract": trellis_input_contract,
                    "hints": preprocess_hints,
                }
            else:
                foreground_result = segment_foreground(
                    ctx.input_file,
                    image_dir,
                    mode=foreground_provider_mode,
                    selected_candidate_id=selected_candidate_id,
                )
                normalization_result = normalize_image(ctx.input_file, foreground_result, image_dir)
                preprocess_hints = sorted(
                    set((foreground_result.get("hints") or []) + (normalization_result.get("hints") or []))
                )
                image_preprocess = {
                    "pipeline_profile": pipeline_profile,
                    "foreground_provider_requested": foreground_result.get("provider_requested"),
                    "foreground_provider_used": foreground_result.get("provider_used") or foreground_result.get("provider"),
                    "foreground_provider_fallback_used": bool(foreground_result.get("provider_fallback_used")),
                    "foreground_provider_attempts": foreground_result.get("provider_attempts") or [],
                    "foreground_model": foreground_result.get("foreground_model"),
                    "foreground_model_name": foreground_result.get("foreground_model_name"),
                    "foreground_extracted": bool(foreground_result.get("foreground_extracted")),
                    "crop_applied": bool(normalization_result.get("crop_applied")),
                    "background_mode": normalization_result.get("background_mode"),
                    "foreground_ratio": normalization_result.get("foreground_ratio"),
                    "background_complexity": foreground_result.get("background_complexity"),
                    "bbox": foreground_result.get("bbox"),
                    "bbox_ratio": foreground_result.get("segmentation_area_ratio"),
                    "crop_box": normalization_result.get("crop_box"),
                    "normalized_size": normalization_result.get("normalized_size"),
                    "crop_fill_ratio": normalization_result.get("crop_fill_ratio"),
                    "normalized_foreground_ratio": normalization_result.get("normalized_foreground_ratio"),
                    "normalized_foreground_file": normalization_result.get("normalized_foreground_path"),
                    "sam_used": bool(foreground_result.get("sam_used")),
                    "segmentation_area_ratio": foreground_result.get("segmentation_area_ratio"),
                    "segmentation_components": foreground_result.get("segmentation_components"),
                    "segmentation_attempt": foreground_result.get("segmentation_attempt"),
                    "segmentation_valid": foreground_result.get("segmentation_valid"),
                    "segmentation_fallback_reason": foreground_result.get("segmentation_fallback_reason"),
                    "segmentation_holes_filled": foreground_result.get("segmentation_holes_filled"),
                    "segmentation_holes_filled_pixels": foreground_result.get("segmentation_holes_filled_pixels"),
                    "segmentation_holes_filled_regions": foreground_result.get("segmentation_holes_filled_regions"),
                    "segmentation_boundary_repaired": foreground_result.get("segmentation_boundary_repaired"),
                    "segmentation_boundary_repaired_pixels": foreground_result.get("segmentation_boundary_repaired_pixels"),
                    "segmentation_boundary_repaired_regions": foreground_result.get("segmentation_boundary_repaired_regions"),
                    "sam2_mask_count": foreground_result.get("sam2_mask_count"),
                    "sam2_mask_count_adaptive": foreground_result.get("sam2_mask_count_adaptive"),
                    "sam2_candidate_count_total": foreground_result.get("sam2_candidate_count_total"),
                    "sam2_adaptive_enabled": foreground_result.get("sam2_adaptive_enabled"),
                    "sam2_adaptive_triggered": foreground_result.get("sam2_adaptive_triggered"),
                    "sam2_selected_pass": foreground_result.get("sam2_selected_pass"),
                    "sam2_selected_index": foreground_result.get("sam2_selected_index"),
                    "sam2_selected_score": foreground_result.get("sam2_selected_score"),
                    "sam2_primary_best_score": foreground_result.get("sam2_primary_best_score"),
                    "sam2_primary_best_area_ratio": foreground_result.get("sam2_primary_best_area_ratio"),
                    "sam2_selected_predicted_iou": foreground_result.get("sam2_selected_predicted_iou"),
                    "sam2_selected_stability_score": foreground_result.get("sam2_selected_stability_score"),
                    "sam2_selected_border_touch_count": foreground_result.get("sam2_selected_border_touch_count"),
                    "sam2_selected_candidate_id": foreground_result.get("sam2_selected_candidate_id"),
                    "normalized": bool(normalization_result.get("normalized")),
                    "hints": preprocess_hints,
                }
                normalized_input_path = Path(str(normalization_result["normalized_input_path"])).expanduser().resolve()
                multiview_input_path = Path(
                    str(normalization_result.get("normalized_foreground_path") or normalization_result["normalized_input_path"])
                ).expanduser().resolve()
                reconstruction_input_path = multiview_input_path

                if requested_head_chain and requested_head_chain[0] == "trellis":
                    reconstruction_input_path = Path(
                        str(
                            normalization_result.get("trellis_input_rgb_path")
                            or normalization_result["normalized_input_path"]
                        )
                    ).expanduser().resolve()
                    image_preprocess["trellis_input_file"] = str(reconstruction_input_path)
                    image_preprocess["trellis_input_strategy"] = "sam2_bbox_rgb_crop_to_trellis_official_preprocess"
                    image_preprocess["trellis_input_alpha_free"] = True
                    preprocess_hints = sorted(set(preprocess_hints + ["trellis_official_preprocess_enabled"]))
                    image_preprocess["hints"] = preprocess_hints
        except Exception as exc:  # noqa: BLE001
            fail_stage(
                "image_preprocess",
                PipelineStageError(
                    "object_mesh_failed",
                    "image_preprocess_failed",
                    reason_to_user_message("image_preprocess_failed"),
                    sanitize_error_message(exc),
                ),
                input_path=str(ctx.input_file),
                output_path=str(image_dir),
            )
        else:
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage="image_preprocess",
                status="completed",
                started_at=stage_timers["image_preprocess"][0],
                started_perf=stage_timers["image_preprocess"][1],
                input_path=str(ctx.input_file),
                output_path=str(normalized_input_path),
                extra={"hints": preprocess_hints, "mode": ctx.mode},
            )
            stage_log_paths["image_preprocess"] = str(stage_log_path)
            persist(
                foreground_file=str(foreground_result["foreground_path"]) if foreground_result else None,
                mask_file=str(foreground_result["mask_path"]) if foreground_result else None,
                normalized_input_file=None if trellis_direct_input_enabled else str(normalized_input_path) if normalized_input_path else None,
                multiview_input_file=str(multiview_input_path) if multiview_input_path else None,
                reconstruction_input_file=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                image_preprocess=image_preprocess,
                sam_used=bool(foreground_result.get("sam_used")) if foreground_result else False,
                segmentation_area_ratio=foreground_result.get("segmentation_area_ratio") if foreground_result else None,
                segmentation_components=foreground_result.get("segmentation_components") if foreground_result else None,
                normalized=bool(normalization_result.get("normalized")) if normalization_result else False,
                stage="image_preprocess_completed",
                status="running",
                stage_logs=stage_log_paths,
            )

        stage_timers["asset_metadata"] = start_stage()
        persist(stage="asset_metadata_running", status="running", reason=None, user_message=None)
        try:
            metadata_input_path = (
                Path(str(image_preprocess.get("object_candidate_image"))).expanduser().resolve()
                if image_preprocess.get("object_candidate_image")
                else reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file
            )
            asset_metadata = build_asset_metadata(
                output_path=asset_metadata_path,
                cutout_image_path=metadata_input_path,
                temp_dir=ctx.temp_dir,
                source_prompt=_source_prompt(),
                candidate_id=selected_candidate_id,
                segmentation_model="sam3" if selected_candidate_id and selected_candidate_id.startswith("sam3") else "sam",
                generation_model="trellis2",
            )
        except Exception as exc:  # noqa: BLE001
            fail_stage(
                "asset_metadata",
                PipelineStageError(
                    "object_mesh_failed",
                    "asset_metadata_failed",
                    reason_to_user_message("asset_metadata_failed"),
                    sanitize_error_message(exc),
                ),
                input_path=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                output_path=str(asset_metadata_path),
            )
        else:
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage="asset_metadata",
                status="completed",
                started_at=stage_timers["asset_metadata"][0],
                started_perf=stage_timers["asset_metadata"][1],
                input_path=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                output_path=str(asset_metadata_path),
                extra={"asset_metadata": asset_metadata},
            )
            stage_log_paths["asset_metadata"] = str(stage_log_path)
            persist(
                asset_metadata=asset_metadata,
                asset_metadata_file=str(asset_metadata_path),
                category_policy={"source": "sam3_text_prompt", "normalized_category_id": _source_category_id()},
                stage="asset_metadata_completed",
                status="running",
                stage_logs=stage_log_paths,
            )

        if skip_multiview_prior:
            stage_timers["multiview_prior"] = start_stage()
            multiview_prior = {
                "enabled": False,
                "active": False,
                "mode": "direct_input_only",
                "status": "skipped_for_direct_recon",
                "requested_provider": os.getenv("MULTIVIEW_PROVIDER", "").strip() or None,
                "provider_used": None,
                "multiview_fallback": False,
                "multiview_fallback_reason": None,
                "notes": ["Skipped multiview generation: direct image -> reconstruction backend policy."],
            }
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage="multiview_prior",
                status="completed",
                started_at=stage_timers["multiview_prior"][0],
                started_perf=stage_timers["multiview_prior"][1],
                input_path=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                output_path=None,
                extra={"mode": ctx.mode, "pipeline_profile": pipeline_profile, "multiview_prior": multiview_prior},
            )
            stage_log_paths["multiview_prior"] = str(stage_log_path)
            persist(multiview_prior=multiview_prior, stage="image_preprocess_completed", status="running")
        else:
            stage_timers["multiview_prior"] = start_stage()
            persist(stage="multiview_prior_running", status="running", reason=None, user_message=None)
            try:
                multiview_prior = run_multiview_generation(
                    reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file, multiview_dir
                )
            except Exception as exc:  # noqa: BLE001
                fail_stage(
                    "multiview_prior",
                    PipelineStageError(
                        "object_mesh_failed",
                        "multiview_prior_failed",
                        reason_to_user_message("multiview_prior_failed"),
                        sanitize_error_message(exc),
                    ),
                    input_path=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                    output_path=str(multiview_dir),
                )
            else:
                stage_log_path = write_stage_log(
                    stage_logs_dir,
                    stage="multiview_prior",
                    status="completed",
                    started_at=stage_timers["multiview_prior"][0],
                    started_perf=stage_timers["multiview_prior"][1],
                    input_path=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                    output_path=str(multiview_prior.get("montage_path") or multiview_prior.get("output_path")),
                    extra={"mode": ctx.mode, "pipeline_profile": pipeline_profile, "multiview_prior": multiview_prior},
                )
                stage_log_paths["multiview_prior"] = str(stage_log_path)
                multiview_prior = {
                    **multiview_prior,
                    "mode": "high_quality_only",
                    "status": multiview_prior.get("status"),
                }
                persist(multiview_prior=multiview_prior, stage="image_preprocess_completed", status="running")

        stage_timers["object_mesh"] = start_stage()
        persist(stage="object_mesh_running", status="running", reason=None, user_message=None)
        try:
            if ctx.mode == "mock":
                raw_mesh_path = work_dir / "mock_raw.glb"
                write_mock_object_glb(raw_mesh_path)
                conversion_status = "mock"
                reconstruction_head_metadata = {
                    **reconstruction_head_metadata,
                    "used": "mock",
                    "resolved_backend": "mock",
                    "reconstruction_backend": "mock",
                    "mesh_backend": "mock",
                    "fallback_used": False,
                    "status": "mock_passthrough",
                    "available": True,
                    "mesh_path": str(raw_mesh_path),
                    "multiview_source": "mock",
                    "pipeline_profile": pipeline_profile,
                }
            else:
                execution = run_reconstruction(
                    input_image=reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file,
                    multiview_info=multiview_prior,
                    work_dir=work_dir,
                    output_dir=ctx.output_dir,
                    object_name=ctx.job_id,
                    requested_head=requested_reconstruction_head,
                    requested_head_chain=requested_head_chain,
                    image_quality_mode=image_quality_mode,
                    pipeline_profile=pipeline_profile,
                )
                raw_mesh_path = execution.raw_mesh_path
                primary_wrapper_log_path = execution.primary_wrapper_log_path
                reconstruction_head_metadata = execution.metadata
        except Exception as exc:  # noqa: BLE001
            fail_stage(
                "object_mesh",
                exc,
                input_path=str(multiview_prior.get("views_dir") or reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                output_path=str(work_dir),
            )
        else:
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage="object_mesh",
                status="completed",
                started_at=stage_timers["object_mesh"][0],
                started_perf=stage_timers["object_mesh"][1],
                input_path=str(multiview_prior.get("views_dir") or reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                output_path=str(raw_mesh_path or mesh_path),
                extra={
                    "mode": ctx.mode,
                    "pipeline_profile": pipeline_profile,
                    "raw_mesh_file": str(raw_mesh_path) if raw_mesh_path else None,
                    "multiview_active": bool(multiview_prior.get("active")),
                    "multiview_fallback": bool(multiview_prior.get("multiview_fallback")),
                    "requested_head_chain": requested_head_chain,
                    "reconstruction_head": reconstruction_head_metadata,
                },
            )
            stage_log_paths["object_mesh"] = str(stage_log_path)
            resolved_backend, reconstruction_backend, mesh_backend, fallback_used = _resolve_reconstruction_fields(
                reconstruction_head_metadata
            )
            persist(
                requested_mode=image_quality_mode,
                resolved_backend=resolved_backend,
                reconstruction_backend=reconstruction_backend,
                mesh_backend=mesh_backend,
                fallback_used=fallback_used,
                raw_mesh_file=str(raw_mesh_path) if raw_mesh_path else None,
                obj_file=str(raw_mesh_path) if raw_mesh_path and raw_mesh_path.suffix.lower() == ".obj" else None,
                raw_mesh_archive_file=str(raw_mesh_archive_path) if raw_mesh_archive_path else None,
                reconstruction_input_file=str(reconstruction_input_path or multiview_input_path or normalized_input_path or ctx.input_file),
                wrapper_log=str(primary_wrapper_log_path) if primary_wrapper_log_path and primary_wrapper_log_path.exists() else None,
                reconstruction_head=reconstruction_head_metadata,
                stage="object_mesh_completed",
                status="running",
                stage_logs=stage_log_paths,
            )

        stage_timers["mesh_cleanup"] = start_stage()
        persist(stage="mesh_cleanup_running", status="running", reason=None, user_message=None)
        try:
            if ctx.mode == "mock":
                mesh_cleanup_metadata = cleanup_mesh(
                    Path(raw_mesh_path),
                    mesh_path,
                    cleanup_dir,
                    category_id=_source_category_id(),
                )
                mesh_cleanup_metadata["cleanup_status"] = "mock_" + str(
                    mesh_cleanup_metadata.get("cleanup_status") or "success"
                )
                thumbnail_status = "generated"
                write_thumbnail(preview_path, "AI 3D Service", "Mock object mesh preview", (37, 171, 182))
            else:
                mesh_cleanup_metadata = cleanup_mesh(
                    Path(raw_mesh_path),
                    mesh_path,
                    cleanup_dir,
                    category_id=_source_category_id(),
                )
                conversion_status = "success"
                if raw_mesh_path is not None:
                    raw_mesh_archive_path = ctx.output_dir / ("object_raw" + raw_mesh_path.suffix.lower())
                    if not raw_mesh_path.suffix:
                        raw_mesh_archive_path = ctx.output_dir / "object_raw.obj"
                    try:
                        shutil.copy2(raw_mesh_path, raw_mesh_archive_path)
                    except Exception as exc:  # noqa: BLE001
                        mesh_cleanup_metadata.setdefault("notes", [])
                        if isinstance(mesh_cleanup_metadata["notes"], list):
                            mesh_cleanup_metadata["notes"].append(f"raw_mesh_archive_copy_failed: {exc}")
                try:
                    generate_thumbnail(mesh_path, preview_path)
                    thumbnail_status = "generated"
                except Exception as exc:  # noqa: BLE001
                    fallback_image = next(iter(sorted(work_dir.rglob("images/*.png"))), None)
                    fallback_note = "generated generic thumbnail"
                    if fallback_image is not None:
                        preview_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(fallback_image, preview_path)
                        fallback_note = f"copied {fallback_image}"
                        thumbnail_status = f"fallback:image_copy: {exc}"
                    else:
                        write_thumbnail(preview_path, "AI 3D Service", "Preview generated by fallback", (37, 171, 182))
                        thumbnail_status = f"fallback: {exc}"
                    (cleanup_dir / "thumbnail.log").write_text(
                        f"Thumbnail rendering failed.\nMesh: {mesh_path}\nError: {exc}\nFallback: {fallback_note}.\n",
                        encoding="utf-8",
                    )
        except Exception as exc:  # noqa: BLE001
            fail_stage(
                "mesh_cleanup",
                PipelineStageError(
                    "object_mesh_failed",
                    "mesh_cleanup_failed",
                    reason_to_user_message("mesh_cleanup_failed"),
                    sanitize_error_message(exc),
                ),
                input_path=str(raw_mesh_path or mesh_path),
                output_path=str(mesh_path),
            )
        else:
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage="mesh_cleanup",
                status="completed",
                started_at=stage_timers["mesh_cleanup"][0],
                started_perf=stage_timers["mesh_cleanup"][1],
                input_path=str(raw_mesh_path or mesh_path),
                output_path=str(mesh_path),
                extra={"mode": ctx.mode, "mesh_cleanup": mesh_cleanup_metadata},
            )
            stage_log_paths["mesh_cleanup"] = str(stage_log_path)
            persist(
                conversion_status=conversion_status,
                thumbnail_status=thumbnail_status,
                mesh_cleanup=mesh_cleanup_metadata,
                stage="object_mesh_completed",
                status="running",
                stage_logs=stage_log_paths,
            )

        stage_timers["material_package"] = start_stage()
        persist(stage="material_package_running", status="running", reason=None, user_message=None)
        try:
            viewer_environment_package = build_viewer_environment_package(ctx.output_dir)
            material_package = build_material_package(
                glb_path=mesh_path,
                output_path=material_path,
                textures_dir=textures_dir,
                scale_normalization=mesh_cleanup_metadata.get("scale_normalization")
                if isinstance(mesh_cleanup_metadata, dict)
                else None,
                cleanup_metadata=mesh_cleanup_metadata,
                viewer_environment=viewer_environment_package,
            )
        except Exception as exc:  # noqa: BLE001
            fail_stage(
                "material_package",
                PipelineStageError(
                    "object_mesh_failed",
                    "material_package_failed",
                    reason_to_user_message("material_package_failed"),
                    sanitize_error_message(exc),
                ),
                input_path=str(mesh_path),
                output_path=str(material_path),
            )
        else:
            stage_log_path = write_stage_log(
                stage_logs_dir,
                stage="material_package",
                status="completed",
                started_at=stage_timers["material_package"][0],
                started_perf=stage_timers["material_package"][1],
                input_path=str(mesh_path),
                output_path=str(material_path),
                extra={"material_package": material_package},
            )
            stage_log_paths["material_package"] = str(stage_log_path)
            persist(
                material_file=str(material_path),
                textures_dir=str(textures_dir),
                viewer_settings_file=str(viewer_settings_path),
                hdri_dir=str(hdri_dir),
                material_package=material_package,
                viewer_environment_package=viewer_environment_package,
                stage="material_package_completed",
                status="running",
                stage_logs=stage_log_paths,
            )

        quality_started_at, quality_started_perf = start_stage()
        quality = evaluate_image_quality(
            mesh_path,
            preview_path,
            image_preprocess=image_preprocess,
            preprocess_hints=preprocess_hints,
            multiview_info=multiview_prior,
            reconstruction_head_info=reconstruction_head_metadata,
        )
        quality_log_path = write_stage_log(
            stage_logs_dir,
            stage="quality_gate",
            status="completed",
            started_at=quality_started_at,
            started_perf=quality_started_perf,
            input_path=str(mesh_path),
            output_path=str(preview_path),
            reason=quality.get("reason") if quality["status"] == "failed" else None,
            error=quality["summary"] if quality["status"] == "failed" else None,
            extra={"quality_status": quality["status"]},
        )
        stage_log_paths["quality_gate"] = str(quality_log_path)

        resolved_backend, reconstruction_backend, mesh_backend, fallback_used = _resolve_reconstruction_fields(
            reconstruction_head_metadata
        )
        persist(
            requested_mode=image_quality_mode,
            resolved_backend=resolved_backend,
            reconstruction_backend=reconstruction_backend,
            mesh_backend=mesh_backend,
            fallback_used=fallback_used,
            raw_mesh_file=str(raw_mesh_path) if raw_mesh_path else None,
            obj_file=str(raw_mesh_path) if raw_mesh_path and raw_mesh_path.suffix.lower() == ".obj" else None,
            raw_mesh_archive_file=str(raw_mesh_archive_path) if raw_mesh_archive_path else None,
            normalized_input_file=str(normalized_input_path) if normalized_input_path else None,
            multiview_input_file=str(multiview_input_path) if multiview_input_path else None,
            wrapper_log=str(primary_wrapper_log_path) if primary_wrapper_log_path and primary_wrapper_log_path.exists() else None,
            conversion_status=conversion_status,
            thumbnail_status=thumbnail_status,
            image_preprocess=image_preprocess,
            multiview_prior=multiview_prior,
            reconstruction_head=reconstruction_head_metadata,
            mesh_cleanup=mesh_cleanup_metadata,
            asset_metadata=asset_metadata,
            material_package=material_package,
            viewer_environment_package=viewer_environment_package,
            material_file=str(material_path),
            asset_metadata_file=str(asset_metadata_path),
            textures_dir=str(textures_dir),
            viewer_settings_file=str(viewer_settings_path),
            hdri_dir=str(hdri_dir),
            stage="object_mesh_completed",
            status="completed",
            reason=quality.get("reason") if quality["status"] == "failed" else None,
            user_message=reason_to_user_message(str(quality.get("reason"))) if quality["status"] == "failed" else None,
            quality=quality,
            quality_status=quality["status"],
            stage_logs=stage_log_paths,
        )
