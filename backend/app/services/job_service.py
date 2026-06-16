from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from backend.app.core.job_store import JobStore
from backend.app.schemas.job import (
    JobCreateRequest,
    JobExportItem,
    JobExportListResponse,
    JobExportResponse,
    JobRecord,
    JobResultResponse,
    JobType,
    SegmentationCandidate,
    SegmentationCandidatesResponse,
    SegmentationPromptRequest,
    SegmentationTextPromptRequest,
    UploadResponse,
)


class JobService:
    @staticmethod
    def _expose_internal_model_info() -> bool:
        raw = os.getenv("AI3D_EXPOSE_INTERNAL_MODEL_INFO", "false").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _segment_ui_max_candidates() -> int:
        """0 means keep all segmentation candidates that pass basic quality filters."""
        try:
            return max(0, int(os.getenv("AI3D_SEGMENT_UI_MAX_CANDIDATES", "0")))
        except ValueError:
            return 0

    @staticmethod
    def _segment_use_detector_boxes() -> bool:
        raw = os.getenv("AI3D_SEGMENT_USE_DETECTOR_BOXES", "false").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _segment_candidate_priority(candidate: SegmentationCandidate) -> tuple[float, float, float, float]:
        area_ratio = float(candidate.area_ratio or 0.0)
        score = float(candidate.score or 0.0)
        border_touch_count = int(candidate.border_touch_count or 0)
        pass_name = str(candidate.pass_name or "")
        pass_bonus = 2.0 if pass_name in {"prompt", "sam3_text"} else 0.0
        practical_size = 1.0 - min(1.0, abs(area_ratio - 0.16) / 0.20)
        background_penalty = 1.2 if area_ratio > 0.22 and border_touch_count >= 2 else 0.0
        priority = pass_bonus + score + (0.55 * practical_size) - (0.35 * border_touch_count) - background_penalty
        return priority, score, area_ratio, -float(border_touch_count)

    @classmethod
    def _sanitize_job_record(cls, record: JobRecord) -> JobRecord:
        if cls._expose_internal_model_info():
            return record
        payload = record.model_copy(deep=True)
        payload.requested_head_chain = None
        payload.fallback_chain = None
        payload.backend_policy = None
        payload.resolved_backend = None
        payload.mesh_backend = None
        payload.fallback_used = None
        return payload

    @classmethod
    def _sanitize_metadata(cls, metadata: dict) -> dict:
        if cls._expose_internal_model_info():
            return metadata

        sanitized = dict(metadata or {})
        forbidden_tokens = (
            "backend",
            "model",
            "head",
            "provider",
            "checkpoint",
            "config",
            "repo",
            "instantmesh",
            "wonder3d",
            "triposr",
            "hunyuan",
            "trellis",
            "one2345",
            "sam2_",
        )
        for key in list(sanitized.keys()):
            lowered = key.lower()
            if any(token in lowered for token in forbidden_tokens):
                sanitized.pop(key, None)
        return sanitized

    def _storage_url(self, path: str | Path) -> str:
        resolved = Path(path).expanduser().resolve()
        try:
            relative = resolved.relative_to(self.store.settings.storage_root)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Path is outside storage root: {resolved}",
            ) from exc
        return f"/storage/{relative.as_posix()}"

    def _segmentation_candidate_from_payload(self, candidate: dict) -> SegmentationCandidate | None:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        segmented_path = str(candidate.get("segmented_path") or "")
        segmented_preview_path = str(candidate.get("segmented_preview_path") or "")
        mask_path = str(candidate.get("mask_path") or "")
        overlay_path = str(candidate.get("overlay_path") or "")
        if not candidate_id or not segmented_path or not mask_path or not overlay_path:
            return None
        return SegmentationCandidate(
            candidate_id=candidate_id,
            pass_name=str(candidate.get("pass_name") or "primary"),
            label=str(candidate.get("label") or "") or None,
            source=(str(candidate.get("source") or "") or None)
            if self._expose_internal_model_info()
            else None,
            bbox=candidate.get("bbox") if isinstance(candidate.get("bbox"), list) else None,
            detection_score=(
                float(candidate.get("detection_score"))
                if candidate.get("detection_score") is not None
                else None
            ),
            score=float(candidate.get("score") or 0.0),
            area_ratio=float(candidate.get("area_ratio") or 0.0),
            predicted_iou=float(candidate.get("predicted_iou") or 0.0),
            stability_score=float(candidate.get("stability_score") or 0.0),
            border_touch_count=int(candidate.get("border_touch_count") or 0),
            segmented_url=self._storage_url(segmented_path),
            segmented_preview_url=self._storage_url(segmented_preview_path) if segmented_preview_path else None,
            mask_url=self._storage_url(mask_path),
            overlay_url=self._storage_url(overlay_path),
        )

    def _safe_candidate_dir(self, job_id: str, candidate_id: str) -> Path:
        safe_id = str(candidate_id or "").strip()
        if not safe_id or "/" in safe_id or "\\" in safe_id or safe_id.startswith("."):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid segmentation candidate id.",
            )
        candidates_dir = (self.store.temp_dir(job_id) / "sam2_candidates" / "candidates").expanduser().resolve()
        candidate_dir = (candidates_dir / safe_id).expanduser().resolve()
        if candidates_dir not in candidate_dir.parents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidate path resolved outside candidate directory.",
            )
        return candidate_dir

    def _load_candidate_payload(self, job_id: str, candidate_id: str) -> tuple[dict, Path]:
        candidate_dir = self._safe_candidate_dir(job_id, candidate_id)
        metadata_path = candidate_dir / "metadata.json"
        if not metadata_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segmentation candidate was not found: {candidate_id}",
            )
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Segmentation candidate metadata is invalid: {candidate_id}",
            ) from exc
        return payload, candidate_dir

    def _segmentation_response_from_disk(
        self,
        job_id: str,
        input_file: Path,
        selected_candidate_id: str | None,
    ) -> SegmentationCandidatesResponse:
        candidates_dir = (self.store.temp_dir(job_id) / "sam2_candidates" / "candidates").expanduser().resolve()
        candidates: list[SegmentationCandidate] = []
        if candidates_dir.exists():
            for metadata_path in sorted(candidates_dir.glob("*/metadata.json")):
                try:
                    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                parsed = self._segmentation_candidate_from_payload(payload)
                if parsed is not None:
                    candidates.append(parsed)
        selected_id = selected_candidate_id if selected_candidate_id else None
        candidates = sorted(
            candidates,
            key=lambda candidate: (
                1 if selected_id and candidate.candidate_id == selected_id else 0,
                *self._segment_candidate_priority(candidate),
            ),
            reverse=True,
        )
        return SegmentationCandidatesResponse(
            job_id=job_id,
            type="image_to_3d",
            input_url=self._storage_url(input_file),
            selected_candidate_id=selected_id,
            candidates=candidates,
        )

    @staticmethod
    def _part_enhance_target_size() -> int:
        try:
            return min(2048, max(512, int(os.getenv("AI3D_PART_ENHANCE_TARGET_SIZE", "1024"))))
        except ValueError:
            return 1024

    @staticmethod
    def _part_enhance_fill_ratio() -> float:
        try:
            return min(0.9, max(0.35, float(os.getenv("AI3D_PART_ENHANCE_FILL_RATIO", "0.74"))))
        except ValueError:
            return 0.74

    @staticmethod
    def _part_alpha_blur_radius() -> float:
        try:
            return min(4.0, max(0.0, float(os.getenv("AI3D_PART_ALPHA_BLUR_RADIUS", "1.35"))))
        except ValueError:
            return 1.35

    @staticmethod
    def _smooth_cutout_alpha(mask: "Image.Image", target_size: int, blur_radius: float) -> "Image.Image":
        from PIL import Image, ImageFilter

        binary = mask.point(lambda px: 255 if px > 8 else 0)
        # Remove tiny mask speckles before resizing, then close small stair-step gaps.
        binary = binary.filter(ImageFilter.MedianFilter(size=3))
        binary = binary.filter(ImageFilter.MaxFilter(size=3)).filter(ImageFilter.MinFilter(size=3))

        alpha = binary.resize((target_size, target_size), Image.Resampling.LANCZOS)
        if blur_radius > 0:
            alpha = alpha.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        # Keep the boundary anti-aliased, but clamp almost-empty halos and solid interiors.
        return alpha.point(lambda px: 0 if px < 10 else 255 if px > 245 else px)

    @staticmethod
    def _run_external_sr(input_path: Path, output_path: Path, *, scale: int) -> str | None:
        command_template = os.getenv("AI3D_SR_COMMAND", "").strip()
        try:
            timeout = max(30, int(os.getenv("AI3D_SR_TIMEOUT_SEC", "180")))
        except ValueError:
            timeout = 180
        output_path.unlink(missing_ok=True)
        if command_template:
            command = command_template.format(
                input=str(input_path),
                output=str(output_path),
                scale=str(scale),
            )
            try:
                subprocess.run(command, shell=True, check=True, timeout=timeout)  # noqa: S602
            except Exception:
                pass
            if output_path.exists() and output_path.stat().st_size > 0:
                return "external_sr_command"
            output_path.unlink(missing_ok=True)

        project_root = Path(__file__).resolve().parents[3]
        binary_override = os.getenv("AI3D_REALESRGAN_BIN", "").strip()
        binary = (
            Path(binary_override).expanduser()
            if binary_override
            else project_root / ".runtime" / "realesrgan-ncnn-vulkan" / "realesrgan-ncnn-vulkan"
        )
        if not binary.is_file():
            return None

        model_name = os.getenv("AI3D_REALESRGAN_MODEL", "realesrgan-x4plus").strip() or "realesrgan-x4plus"
        try:
            realesrgan_scale = max(2, min(4, int(os.getenv("AI3D_REALESRGAN_SCALE", "4"))))
        except ValueError:
            realesrgan_scale = 4
        models_dir = binary.parent / "models"
        command = [
            str(binary),
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "-s",
            str(realesrgan_scale),
            "-m",
            str(models_dir),
            "-n",
            model_name,
            "-f",
            "png",
        ]
        try:
            subprocess.run(
                command,
                cwd=binary.parent,
                check=True,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
        except Exception:
            return None
        if output_path.exists() and output_path.stat().st_size > 0:
            return "realesrgan_ncnn_vulkan"
        return None

    def _enhance_part_cutout_image(
        self,
        *,
        input_file: Path,
        mask_path: Path,
        output_dir: Path,
    ) -> dict[str, object]:
        from PIL import Image, ImageFilter, ImageOps

        target_size = self._part_enhance_target_size()
        fill_ratio = self._part_enhance_fill_ratio()
        alpha_blur_radius = self._part_alpha_blur_radius()

        with Image.open(input_file) as source_image:
            source = ImageOps.exif_transpose(source_image).convert("RGB")
        with Image.open(mask_path) as mask_image:
            mask = mask_image.convert("L")

        if mask.size != source.size:
            mask = mask.resize(source.size, Image.Resampling.NEAREST)

        bbox = mask.point(lambda px: 255 if px > 8 else 0).getbbox()
        if bbox is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected cutout mask is empty and cannot be enhanced.",
            )

        left, top, right, bottom = bbox
        object_width = max(1, right - left)
        object_height = max(1, bottom - top)
        object_size = max(object_width, object_height)
        crop_size = int(round(object_size / fill_ratio))
        crop_size = max(crop_size, object_size + 8, 32)

        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        crop_left = int(round(cx - (crop_size / 2.0)))
        crop_top = int(round(cy - (crop_size / 2.0)))
        crop_right = crop_left + crop_size
        crop_bottom = crop_top + crop_size

        src_left = max(0, crop_left)
        src_top = max(0, crop_top)
        src_right = min(source.width, crop_right)
        src_bottom = min(source.height, crop_bottom)
        dst_left = src_left - crop_left
        dst_top = src_top - crop_top

        crop_rgb = Image.new("RGB", (crop_size, crop_size), (0, 0, 0))
        crop_mask = Image.new("L", (crop_size, crop_size), 0)
        crop_rgb.paste(source.crop((src_left, src_top, src_right, src_bottom)), (dst_left, dst_top))
        crop_mask.paste(mask.crop((src_left, src_top, src_right, src_bottom)), (dst_left, dst_top))

        sr_input_path = output_dir / "sr_input_crop.png"
        sr_output_path = output_dir / "sr_output_rgb.png"
        crop_rgb.save(sr_input_path)

        scale = max(1, int(round(target_size / max(1, crop_size))))
        sr_backend = self._run_external_sr(sr_input_path, sr_output_path, scale=max(2, scale))
        if sr_backend:
            with Image.open(sr_output_path) as sr_image:
                rgb_up = sr_image.convert("RGB").resize(
                    (target_size, target_size),
                    Image.Resampling.LANCZOS,
                )
        else:
            rgb_up = crop_rgb.resize((target_size, target_size), Image.Resampling.LANCZOS)
            rgb_up = rgb_up.filter(ImageFilter.UnsharpMask(radius=1.2, percent=135, threshold=3))
            sr_backend = "pil_lanczos_unsharp_fallback"

        alpha_up = self._smooth_cutout_alpha(crop_mask, target_size, alpha_blur_radius)

        transparent_rgb = Image.new("RGB", (target_size, target_size), (0, 0, 0))
        rgb_keep_mask = alpha_up.point(lambda px: 255 if px > 0 else 0)
        rgb_clean = Image.composite(rgb_up, transparent_rgb, rgb_keep_mask)
        enhanced = Image.merge("RGBA", (*rgb_clean.split(), alpha_up))
        enhanced_path = output_dir / "segmented.png"
        preview_path = output_dir / "segmented_preview.png"
        enhanced.save(enhanced_path)
        preview = enhanced.copy()
        preview.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        preview.save(preview_path)

        return {
            "target_size": target_size,
            "fill_ratio": fill_ratio,
            "alpha_blur_radius": alpha_blur_radius,
            "alpha_smoothing": "median_close_lanczos_gaussian",
            "source_bbox": [left, top, right - left, bottom - top],
            "crop_box": [crop_left, crop_top, crop_size, crop_size],
            "sr_backend": sr_backend,
            "used_external_sr": sr_backend != "pil_lanczos_unsharp_fallback",
            "enhanced_path": str(enhanced_path),
            "preview_path": str(preview_path),
        }

    def _load_image_upload(self, job_id: str) -> tuple[dict, Path]:
        try:
            manifest = self.store.read_upload_manifest(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        if manifest.get("type") != "image_to_3d":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Segmentation is only available for image jobs.",
            )

        input_file = Path(str(manifest.get("input_file") or "")).expanduser().resolve()
        if not input_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded image was not found for {job_id}.",
            )
        return manifest, input_file

    @staticmethod
    def _normalize_image_job_options(options: dict[str, object] | None) -> dict[str, object]:
        request_opts = dict(options or {})
        requested_head = str(request_opts.get("requested_reconstruction_head") or "").strip().lower()
        image_quality_mode = str(request_opts.get("image_quality_mode") or "").strip().lower()
        candidate_id = str(request_opts.get("sam2_candidate_id") or "").strip()

        # Image pipeline is now trellis-only in production.
        # Keep this coercion strict so old frontend payloads cannot
        # silently reactivate deprecated reconstruction heads.
        if requested_head != "trellis":
            request_opts["requested_reconstruction_head"] = "trellis"
        if image_quality_mode != "high_quality":
            request_opts["image_quality_mode"] = "high_quality"

        # preserve only valid known keys for image jobs
        if not requested_head and not image_quality_mode:
            request_opts["requested_reconstruction_head"] = "trellis"
            request_opts["image_quality_mode"] = "high_quality"
        if candidate_id:
            request_opts["sam2_candidate_id"] = candidate_id
        elif "sam2_candidate_id" in request_opts:
            request_opts.pop("sam2_candidate_id", None)
        return request_opts

    def __init__(self, store: JobStore | None = None) -> None:
        self.store = store or JobStore()

    async def handle_upload(self, job_type: JobType, upload_file: UploadFile) -> UploadResponse:
        job_id = self.store.reserve_job_id()
        filename = upload_file.filename or "upload.bin"

        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_handle:
            tmp_handle.write(await upload_file.read())
            temp_path = Path(tmp_handle.name)

        try:
            if job_type != "image_to_3d":
                raise ValueError("Only image-to-3D object jobs are supported.")
            saved_path = self.store.save_image_upload(job_id, temp_path)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload processing failed.") from exc
        finally:
            temp_path.unlink(missing_ok=True)

        self.store.write_upload_manifest(job_id, job_type, saved_path, filename)
        return UploadResponse(job_id=job_id, type=job_type, input_file=str(saved_path), filename=filename)

    def create_job(self, request: JobCreateRequest) -> JobRecord:
        try:
            options = request.options
            if request.type == "image_to_3d":
                options = self._normalize_image_job_options(options)
            created = self.store.create_job(request.job_id, request.type, options)
            return self._sanitize_job_record(created)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def get_job(self, job_id: str) -> JobRecord:
        try:
            enriched = self.store.enrich_job_record(self.store.get_job(job_id))
            return self._sanitize_job_record(enriched)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    def get_result(self, job_id: str) -> JobResultResponse:
        job = self.get_job(job_id)
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job {job_id} is not completed yet.",
            )

        result = job.result or self.store.build_result_files(job.job_id, job.type)
        metadata_path = Path(result.metadata_path)
        metadata = {}
        if metadata_path.exists():
            import json

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = self._sanitize_metadata(metadata)

        material = {}
        material_path = Path(result.material_path).expanduser().resolve() if result.material_path else None
        if material_path is not None and material_path.exists():
            material = json.loads(material_path.read_text(encoding="utf-8"))

        asset_metadata = {}
        asset_metadata_path = (
            Path(result.asset_metadata_path).expanduser().resolve() if result.asset_metadata_path else None
        )
        if asset_metadata_path is not None and asset_metadata_path.exists():
            asset_metadata = json.loads(asset_metadata_path.read_text(encoding="utf-8"))

        thumbnail_path = Path(result.thumbnail_path or "")
        if not thumbnail_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Result thumbnail is missing for {job_id}.",
            )

        mesh_path = Path(result.mesh_path)
        mesh_url = result.mesh_url if mesh_path.exists() else None
        job_payload = job.model_copy(deep=True)
        if job_payload.result is None:
            job_payload.result = result
        job_payload = self._sanitize_job_record(job_payload)

        return JobResultResponse(
            job_id=job.job_id,
            type=job.type,
            viewer_type=result.viewer_type,
            mesh_url=mesh_url,
            thumbnail_url=result.thumbnail_url,
            material_url=result.material_url,
            asset_metadata_url=result.asset_metadata_url,
            stage=metadata.get("stage"),
            reason=metadata.get("reason"),
            quality_status=metadata.get("quality_status") or (metadata.get("quality") or {}).get("status"),
            quality=metadata.get("quality") or {},
            job=job_payload,
            metadata=metadata,
            material=material,
            asset_metadata=asset_metadata,
        )

    def _completed_exportable_result(self, job_id: str) -> tuple[JobRecord, object]:
        job = self.get_job(job_id)
        if job.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job {job_id} is not completed yet.",
            )
        if job.type != "image_to_3d":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Additional export formats are not available for this job type.",
            )
        result = job.result or self.store.build_result_files(job.job_id, job.type)
        mesh_path = Path(result.mesh_path)
        if not mesh_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"3D result file is missing for {job_id}.",
            )
        return job, result

    @staticmethod
    def _mesh_has_faces(mesh_path: Path) -> bool:
        try:
            import trimesh

            scene_or_mesh = trimesh.load(mesh_path, force="scene", process=False)
            if isinstance(scene_or_mesh, trimesh.Scene):
                return any(
                    hasattr(geom, "faces") and getattr(geom, "faces", None) is not None and len(geom.faces) > 0
                    for geom in scene_or_mesh.geometry.values()
                )
            return hasattr(scene_or_mesh, "faces") and getattr(scene_or_mesh, "faces", None) is not None and len(scene_or_mesh.faces) > 0
        except Exception:  # noqa: BLE001
            return True

    def list_exports(self, job_id: str) -> JobExportListResponse:
        job, result = self._completed_exportable_result(job_id)
        from pipelines.common.mesh_export import list_export_specs

        mesh_path = Path(result.mesh_path)
        exports_dir = self.store.output_dir(job_id) / "exports"
        base_name = "object_mesh"
        has_faces = self._mesh_has_faces(mesh_path)
        items: list[JobExportItem] = []
        for spec in list_export_specs():
            available = spec.enabled
            reason = None if spec.enabled else "서버 변환 도구가 아직 연결되지 않았습니다."
            if spec.format in {"stl", "3mf"} and not has_faces:
                available = False
                reason = "이 결과는 아직 표면 메쉬가 아니라서 이 포맷으로 내보낼 수 없습니다."
            if spec.format == "glb":
                path = mesh_path
            else:
                path = exports_dir / f"{base_name}.{spec.format}{spec.extension if spec.package else ''}"
            exists = path.exists() and path.stat().st_size > 0
            if spec.format == "fbx":
                # FBX orientation depends on the current DCC export recipe.
                # Regenerate it on demand instead of serving stale cached files.
                exists = False
            items.append(
                JobExportItem(
                    format=spec.format,
                    label=spec.label,
                    file_name=path.name if exists and available else None,
                    url=self._storage_url(path) if exists and available else None,
                    mime_type=spec.mime_type,
                    tool_hint=spec.tool_hint,
                    note=spec.note,
                    available=available,
                    generated=exists,
                    reason=reason,
                )
            )
        return JobExportListResponse(job_id=job_id, exports=items)

    def create_export(self, job_id: str, export_format: str) -> JobExportResponse:
        job, result = self._completed_exportable_result(job_id)
        from pipelines.common.mesh_export import (
            MeshExportError,
            export_asset_package,
            export_mesh_format,
            export_result_to_payload,
        )
        if export_format.strip().lower() in {"stl", "3mf"}:
            if not self._mesh_has_faces(Path(result.mesh_path)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이 결과는 아직 표면 메쉬가 아니라서 이 포맷으로 내보낼 수 없습니다.",
                )

        try:
            normalized_format = export_format.strip().lower()
            if normalized_format in {"web", "blender", "maya", "unreal", "alembic", "obj_legacy"}:
                exported = export_asset_package(
                    Path(result.mesh_path),
                    self.store.output_dir(job_id) / "exports",
                    normalized_format,
                    material_path=Path(result.material_path) if result.material_path else None,
                    metadata_path=Path(result.asset_metadata_path) if result.asset_metadata_path else None,
                    thumbnail_path=Path(result.thumbnail_path) if result.thumbnail_path else None,
                    textures_dir=self.store.output_dir(job_id) / "textures",
                    hdri_dir=self.store.output_dir(job_id) / "hdri",
                    viewer_settings_path=self.store.output_dir(job_id) / "viewer_settings.json",
                    base_name="object_mesh",
                )
            else:
                exported = export_mesh_format(
                    Path(result.mesh_path),
                    self.store.output_dir(job_id) / "exports",
                    export_format,
                    base_name="object_mesh",
                )
        except MeshExportError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export conversion failed: {exc}",
            ) from exc

        payload = export_result_to_payload(exported, self._storage_url(exported.path))
        return JobExportResponse(job_id=job_id, **payload)

    def get_segmentation_candidates(self, job_id: str) -> SegmentationCandidatesResponse:
        _manifest, input_file = self._load_image_upload(job_id)

        work_dir = self.store.temp_dir(job_id) / "sam2_candidates"
        candidates_dir = work_dir / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)

        from pipelines.image_to_3d.foreground_extract_sam import extract_with_sam

        max_candidates = self._segment_ui_max_candidates()

        try:
            boxes_json = None
            if self._segment_use_detector_boxes():
                from pipelines.image_to_3d.object_detection import detect_object_boxes

                detector_limit = max(5, max_candidates * 3) if max_candidates > 0 else 80
                detector_summary = detect_object_boxes(
                    input_file,
                    work_dir / "detector",
                    max_candidates=detector_limit,
                )
                boxes_json = work_dir / "detector" / "object_boxes.json"
                if not detector_summary.get("candidates"):
                    boxes_json = None
            summary = extract_with_sam(
                input_file,
                work_dir,
                dump_candidates_dir=candidates_dir,
                boxes_json=boxes_json,
                max_candidates=max_candidates,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"SAM2 candidate generation failed: {exc}",
            ) from exc

        raw_candidates = summary.get("sam2_candidates") or []
        candidates: list[SegmentationCandidate] = []
        for candidate in raw_candidates:
            parsed = self._segmentation_candidate_from_payload(candidate)
            if parsed is not None:
                candidates.append(parsed)

        candidates = sorted(
            candidates,
            key=self._segment_candidate_priority,
            reverse=True,
        )
        if max_candidates > 0:
            candidates = candidates[:max_candidates]

        selected_candidate_id = str(summary.get("sam2_selected_candidate_id") or "").strip() or None
        if candidates:
            selected_candidate = next(
                (candidate for candidate in candidates if candidate.candidate_id == selected_candidate_id),
                None,
            )
            preferred_large_area = float(os.getenv("AI3D_SEGMENT_SELECTION_LARGE_AREA", "0.08"))
            selected_candidate_is_weak = (
                selected_candidate is None
                or float(selected_candidate.area_ratio) < preferred_large_area
                or int(selected_candidate.border_touch_count or 0) >= 2
                or float(selected_candidate.score or 0.0) < 0.0
            )
            if selected_candidate_is_weak:
                large_candidates = [
                    candidate
                    for candidate in candidates
                    if float(candidate.area_ratio) >= preferred_large_area
                    and int(candidate.border_touch_count or 0) <= 1
                    and float(candidate.score or 0.0) > -0.05
                ]
                if large_candidates:
                    selected_candidate = max(
                        large_candidates,
                        key=self._segment_candidate_priority,
                    )
                    selected_candidate_id = selected_candidate.candidate_id
                elif selected_candidate is None:
                    selected_candidate_id = max(
                        candidates,
                        key=self._segment_candidate_priority,
                    ).candidate_id

        report_path = work_dir / "sam2_candidates_response.json"
        response_payload = SegmentationCandidatesResponse(
            job_id=job_id,
            type="image_to_3d",
            input_url=self._storage_url(input_file),
            selected_candidate_id=selected_candidate_id,
            candidates=candidates,
        )
        report_path.write_text(json.dumps(response_payload.model_dump(), indent=2), encoding="utf-8")
        return response_payload

    def create_segmentation_prompt(
        self,
        job_id: str,
        request: SegmentationPromptRequest,
    ) -> SegmentationCandidatesResponse:
        _manifest, input_file = self._load_image_upload(job_id)
        points = [
            {"x": point.x, "y": point.y, "label": 1 if int(point.label) > 0 else 0}
            for point in request.points
        ]
        box = request.box if isinstance(request.box, list) and len(request.box) == 4 else None
        if not points and box is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one point or one box is required.",
            )

        work_dir = self.store.temp_dir(job_id) / "sam2_candidates"
        prompt_dir = work_dir / "prompt"
        candidates_dir = work_dir / "candidates"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        candidates_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / "prompt.json"
        prompt_path.write_text(
            json.dumps(
                {
                    "source": "user_prompt",
                    "points": points,
                    "box": box,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        from pipelines.image_to_3d.foreground_extract_sam import extract_with_sam

        try:
            summary = extract_with_sam(
                input_file,
                work_dir,
                dump_candidates_dir=candidates_dir,
                prompt_json=prompt_path,
                max_candidates=1,
                reset_candidates_dir=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"SAM2 prompt segmentation failed: {exc}",
            ) from exc

        candidates = []
        for candidate in summary.get("sam2_candidates") or []:
            parsed = self._segmentation_candidate_from_payload(candidate)
            if parsed is not None:
                candidates.append(parsed)

        selected_candidate_id = str(summary.get("sam2_selected_candidate_id") or "").strip() or (
            candidates[0].candidate_id if candidates else None
        )
        if selected_candidate_id and not any(candidate.candidate_id == selected_candidate_id for candidate in candidates):
            selected_candidate_id = candidates[0].candidate_id if candidates else None
        response_payload = SegmentationCandidatesResponse(
            job_id=job_id,
            type="image_to_3d",
            input_url=self._storage_url(input_file),
            selected_candidate_id=selected_candidate_id,
            candidates=candidates,
        )
        (work_dir / "sam2_prompt_response.json").write_text(
            json.dumps(response_payload.model_dump(), indent=2),
            encoding="utf-8",
        )
        return response_payload

    def create_segmentation_text_prompt(
        self,
        job_id: str,
        request: SegmentationTextPromptRequest,
    ) -> SegmentationCandidatesResponse:
        _manifest, input_file = self._load_image_upload(job_id)
        text_prompt = request.prompt.strip()
        if not text_prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text prompt is required.",
            )

        work_dir = self.store.temp_dir(job_id) / "sam2_candidates"
        prompt_dir = work_dir / "prompt"
        candidates_dir = work_dir / "candidates"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        candidates_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompt_dir / "sam3_text_prompt.json"
        prompt_path.write_text(
            json.dumps(
                {
                    "source": "user_text_prompt",
                    "provider": "sam3",
                    "prompt": text_prompt,
                    "confidence_threshold": request.confidence_threshold,
                    "merge_mode": request.merge_mode,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        from pipelines.image_to_3d.foreground_extract_sam3 import extract_with_sam3

        try:
            summary = extract_with_sam3(
                input_file,
                work_dir,
                text_prompt=text_prompt,
                dump_candidates_dir=candidates_dir,
                max_candidates=max(1, self._segment_ui_max_candidates() or 1),
                confidence_threshold=request.confidence_threshold,
                merge_mode=request.merge_mode,
                reset_candidates_dir=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"SAM3 text segmentation failed: {exc}",
            ) from exc

        candidates = []
        for candidate in summary.get("sam3_candidates") or []:
            parsed = self._segmentation_candidate_from_payload(candidate)
            if parsed is not None:
                candidates.append(parsed)

        selected_candidate_id = str(summary.get("sam3_selected_candidate_id") or "").strip() or (
            candidates[0].candidate_id if candidates else None
        )
        if selected_candidate_id and not any(candidate.candidate_id == selected_candidate_id for candidate in candidates):
            selected_candidate_id = candidates[0].candidate_id if candidates else None
        response_payload = SegmentationCandidatesResponse(
            job_id=job_id,
            type="image_to_3d",
            input_url=self._storage_url(input_file),
            selected_candidate_id=selected_candidate_id,
            candidates=candidates,
        )
        (work_dir / "sam3_text_prompt_response.json").write_text(
            json.dumps(response_payload.model_dump(), indent=2),
            encoding="utf-8",
        )
        return response_payload

    def enhance_segmentation_candidate(
        self,
        job_id: str,
        candidate_id: str,
    ) -> SegmentationCandidatesResponse:
        _manifest, input_file = self._load_image_upload(job_id)
        source_payload, source_dir = self._load_candidate_payload(job_id, candidate_id)

        mask_path = Path(str(source_payload.get("mask_path") or source_dir / "mask.png")).expanduser().resolve()
        overlay_path = Path(str(source_payload.get("overlay_path") or source_dir / "overlay.png")).expanduser().resolve()
        if not mask_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mask file is missing for candidate: {candidate_id}",
            )

        source_id = str(source_payload.get("candidate_id") or candidate_id).strip()
        enhanced_id = source_id if source_id.endswith("_enhanced") else f"{source_id}_enhanced"
        enhanced_dir = self._safe_candidate_dir(job_id, enhanced_id)
        enhanced_dir.mkdir(parents=True, exist_ok=True)

        enhance_summary = self._enhance_part_cutout_image(
            input_file=input_file,
            mask_path=mask_path,
            output_dir=enhanced_dir,
        )

        enhanced_mask_path = enhanced_dir / "mask.png"
        enhanced_overlay_path = enhanced_dir / "overlay.png"
        shutil.copyfile(mask_path, enhanced_mask_path)
        if overlay_path.exists():
            shutil.copyfile(overlay_path, enhanced_overlay_path)
        else:
            shutil.copyfile(mask_path, enhanced_overlay_path)

        label = str(source_payload.get("label") or source_id)
        if "enhanced" not in label.lower():
            label = f"{label} · enhanced"
        enhanced_payload = {
            **source_payload,
            "candidate_id": enhanced_id,
            "pass_name": "enhanced_cutout",
            "source": "part_zoom_sr_enhancement",
            "parent_candidate_id": source_id,
            "label": label,
            "score": min(1.0, float(source_payload.get("score") or 0.0) + 0.01),
            "quality_score": min(1.0, float(source_payload.get("quality_score") or source_payload.get("score") or 0.0) + 0.04),
            "mask_path": str(enhanced_mask_path),
            "segmented_path": str(enhance_summary["enhanced_path"]),
            "segmented_preview_path": str(enhance_summary["preview_path"]),
            "overlay_path": str(enhanced_overlay_path),
            "enhancement": {
                "method": "part_zoom_super_resolution",
                "source_candidate_id": source_id,
                **{
                    key: value
                    for key, value in enhance_summary.items()
                    if key not in {"enhanced_path", "preview_path"}
                },
            },
        }
        (enhanced_dir / "metadata.json").write_text(
            json.dumps(enhanced_payload, indent=2),
            encoding="utf-8",
        )

        response_payload = self._segmentation_response_from_disk(
            job_id,
            input_file,
            selected_candidate_id=enhanced_id,
        )
        candidates_summary_path = self.store.temp_dir(job_id) / "sam2_candidates" / "candidates" / "candidates_summary.json"
        candidates_summary_path.parent.mkdir(parents=True, exist_ok=True)
        candidates_summary_path.write_text(
            json.dumps(
                {
                    "selected_candidate_id": enhanced_id,
                    "candidates": [
                        {
                            "candidate_id": candidate.candidate_id,
                            "pass_name": candidate.pass_name,
                            "label": candidate.label,
                            "bbox": candidate.bbox,
                            "score": candidate.score,
                            "area_ratio": candidate.area_ratio,
                            "predicted_iou": candidate.predicted_iou,
                            "stability_score": candidate.stability_score,
                            "border_touch_count": candidate.border_touch_count,
                            "segmented_path": str(
                                self._safe_candidate_dir(job_id, candidate.candidate_id) / "segmented.png"
                            ),
                            "segmented_preview_path": str(
                                self._safe_candidate_dir(job_id, candidate.candidate_id) / "segmented_preview.png"
                            ),
                            "mask_path": str(self._safe_candidate_dir(job_id, candidate.candidate_id) / "mask.png"),
                            "overlay_path": str(self._safe_candidate_dir(job_id, candidate.candidate_id) / "overlay.png"),
                        }
                        for candidate in response_payload.candidates
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return response_payload
