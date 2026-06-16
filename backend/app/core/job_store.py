from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import fcntl
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.core.config import Settings, get_settings
from backend.app.schemas.job import JobRecord, JobResultFiles, JobType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def locked_file(path: Path) -> Iterator[Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        yield handle
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class JobStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.ensure_storage_layout()

    def ensure_storage_layout(self) -> None:
        for root in (
            self.settings.uploads_root,
            self.settings.jobs_root,
            self.settings.outputs_root,
            self.settings.previews_root,
            self.settings.temp_root,
        ):
            root.mkdir(parents=True, exist_ok=True)

    def reserve_job_id(self) -> str:
        sequence_path = self.settings.jobs_root / ".sequence"
        with locked_file(sequence_path) as handle:
            raw = handle.read().strip()
            current = int(raw) if raw else 0
            next_value = current + 1
            handle.seek(0)
            handle.truncate()
            handle.write(str(next_value))
        return f"job_{next_value:06d}"

    def upload_dir(self, job_id: str) -> Path:
        return self.settings.uploads_root / job_id

    def job_dir(self, job_id: str) -> Path:
        return self.settings.jobs_root / job_id

    def output_dir(self, job_id: str) -> Path:
        return self.settings.outputs_root / job_id

    def preview_dir(self, job_id: str) -> Path:
        return self.settings.previews_root / job_id

    def temp_dir(self, job_id: str) -> Path:
        return self.settings.temp_root / job_id

    def job_file(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def upload_manifest_file(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "upload.json"

    def metadata_file(self, job_id: str, job_type: JobType) -> Path:
        return self.output_dir(job_id) / "object_metadata.json"

    def save_image_upload(self, job_id: str, source_path: Path) -> Path:
        destination_dir = self.upload_dir(job_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        try:
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                rgba = image.convert("RGBA")
                alpha = rgba.getchannel("A")
                has_alpha_cutout = alpha.getextrema()[0] < 255
                if has_alpha_cutout:
                    destination_path = destination_dir / "input_image.png"
                    rgba.save(destination_path, format="PNG")
                else:
                    destination_path = destination_dir / "input_image.jpg"
                    image.convert("RGB").save(destination_path, format="JPEG", quality=95, subsampling=0)
        except UnidentifiedImageError as exc:
            raise ValueError("Uploaded file is not a valid image.") from exc
        return destination_path

    def write_upload_manifest(self, job_id: str, job_type: JobType, input_file: Path, filename: str) -> None:
        manifest_path = self.upload_manifest_file(job_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": job_id,
            "type": job_type,
            "input_file": str(input_file),
            "filename": filename,
            "created_at": utcnow().isoformat(),
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def read_upload_manifest(self, job_id: str) -> dict[str, Any]:
        manifest_path = self.upload_manifest_file(job_id)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Upload manifest not found for {job_id}.")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def create_job(self, job_id: str, job_type: JobType, options: dict[str, Any] | None = None) -> JobRecord:
        if self.job_file(job_id).exists():
            return self.get_job(job_id)

        manifest = self.read_upload_manifest(job_id)
        if manifest["type"] != job_type:
            raise ValueError("Uploaded asset type does not match the requested job type.")

        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir(job_id).mkdir(parents=True, exist_ok=True)
        self.preview_dir(job_id).mkdir(parents=True, exist_ok=True)
        self.temp_dir(job_id).mkdir(parents=True, exist_ok=True)

        now = utcnow()
        record = JobRecord(
            job_id=job_id,
            type=job_type,
            status="queued",
            input_file=manifest["input_file"],
            output_dir=str(self.output_dir(job_id)),
            requested_head_chain=None,
            fallback_chain=None,
            backend_policy=None,
            resolved_backend=None,
            mesh_backend=None,
            fallback_used=None,
            options=options or {},
            preview_dir=str(self.preview_dir(job_id)),
            temp_dir=str(self.temp_dir(job_id)),
            error=None,
            stage=None,
            reason=None,
            quality_status=None,
            quality={},
            created_at=now,
            updated_at=now,
            result=None,
        )
        self.job_file(job_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def get_job(self, job_id: str) -> JobRecord:
        job_path = self.job_file(job_id)
        if not job_path.exists():
            recovered = self.recover_job_from_outputs(job_id)
            if recovered is None:
                raise FileNotFoundError(f"Job {job_id} not found.")
            self.save_job(recovered)
            return recovered
        return JobRecord.model_validate_json(job_path.read_text(encoding="utf-8"))

    def recover_job_from_outputs(self, job_id: str) -> JobRecord | None:
        output_dir = self.output_dir(job_id)
        preview_dir = self.preview_dir(job_id)
        temp_dir = self.temp_dir(job_id)

        image_metadata = output_dir / "object_metadata.json"
        job_type: JobType | None = None
        metadata_path: Path | None = None
        if image_metadata.exists():
            job_type = "image_to_3d"
            metadata_path = image_metadata

        if job_type is None or metadata_path is None:
            return None

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        input_file = str(metadata.get("input_file") or "")

        if not input_file:
            manifest_path = self.upload_manifest_file(job_id)
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                input_file = str(manifest.get("input_file") or "")

        mesh_exists = False
        try:
            result_files = self.build_result_files(job_id, job_type)
            mesh_exists = Path(result_files.mesh_path).exists()
        except Exception:  # noqa: BLE001
            result_files = None

        metadata_status = str(metadata.get("status") or "").strip().lower()
        if metadata_status in {"queued", "running", "completed", "failed"}:
            status_value = metadata_status
        else:
            status_value = "completed" if mesh_exists else "failed"

        metadata_updated_at = metadata_path.stat().st_mtime
        created_at = datetime.fromtimestamp(metadata_updated_at, tz=timezone.utc)
        updated_at = datetime.fromtimestamp(metadata_updated_at, tz=timezone.utc)

        return JobRecord(
            job_id=job_id,
            type=job_type,
            status=status_value,  # type: ignore[arg-type]
            input_file=input_file,
            output_dir=str(output_dir),
            requested_head_chain=None,
            fallback_chain=None,
            backend_policy=str(metadata.get("backend_policy")) if metadata.get("backend_policy") is not None else None,
            resolved_backend=str(metadata.get("resolved_backend")) if metadata.get("resolved_backend") is not None else None,
            mesh_backend=str(metadata.get("mesh_backend")) if metadata.get("mesh_backend") is not None else None,
            fallback_used=bool(metadata.get("fallback_used")) if "fallback_used" in metadata else None,
            options={},
            error=str(metadata.get("user_message") or metadata.get("error") or "") or None,
            stage=str(metadata.get("stage") or "") or None,
            reason=str(metadata.get("reason") or "") or None,
            quality_status=str(metadata.get("quality_status") or "") or None,
            quality=metadata.get("quality") or {},
            preview_dir=str(preview_dir),
            temp_dir=str(temp_dir),
            created_at=created_at,
            updated_at=updated_at,
            result=result_files if status_value == "completed" else None,
        )

    def save_job(self, record: JobRecord) -> JobRecord:
        record.updated_at = utcnow()
        with locked_file(self.job_file(record.job_id)) as handle:
            handle.seek(0)
            handle.truncate()
            handle.write(record.model_dump_json(indent=2))
        return record

    def read_metadata_summary(self, job_id: str, job_type: JobType) -> dict[str, Any]:
        metadata_path = self.metadata_file(job_id, job_type)
        if not metadata_path.exists():
            return {}
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def enrich_job_record(self, record: JobRecord) -> JobRecord:
        metadata = self.read_metadata_summary(record.job_id, record.type)
        if not metadata:
            return record
        enriched = record.model_copy(deep=True)
        enriched.stage = metadata.get("stage")
        enriched.reason = metadata.get("reason")
        enriched.quality = metadata.get("quality") or {}
        enriched.quality_status = metadata.get("quality_status") or enriched.quality.get("status")
        enriched.resolved_backend = metadata.get("resolved_backend") or enriched.resolved_backend
        enriched.mesh_backend = metadata.get("mesh_backend") or enriched.mesh_backend
        requested_chain = metadata.get("requested_head_chain")
        if requested_chain is not None:
            if isinstance(requested_chain, str):
                enriched.requested_head_chain = [requested_chain]
            else:
                enriched.requested_head_chain = list(requested_chain)
        backend_policy = metadata.get("backend_policy")
        if backend_policy is not None:
            enriched.backend_policy = str(backend_policy)
        fallback_chain = metadata.get("fallback_chain")
        if fallback_chain is not None:
            if isinstance(fallback_chain, str):
                enriched.fallback_chain = [fallback_chain]
            else:
                enriched.fallback_chain = list(fallback_chain)
        if "fallback_used" in metadata:
            enriched.fallback_used = bool(metadata.get("fallback_used"))
        if enriched.status == "failed" and metadata.get("user_message"):
            enriched.error = metadata["user_message"]
        return enriched

    def claim_next_job(self, job_type: JobType) -> JobRecord | None:
        job_files = sorted(self.settings.jobs_root.glob("job_*/job.json"))
        for job_path in job_files:
            with locked_file(job_path) as handle:
                raw = handle.read().strip()
                if not raw:
                    continue
                record = JobRecord.model_validate_json(raw)
                if record.type != job_type or record.status != "queued":
                    continue
                record.status = "running"
                record.updated_at = utcnow()
                handle.seek(0)
                handle.truncate()
                handle.write(record.model_dump_json(indent=2))
                return record
        return None

    def mark_completed(self, job_id: str, result: JobResultFiles | None = None) -> JobRecord:
        record = self.get_job(job_id)
        record.status = "completed"
        record.error = None
        record.result = result
        return self.save_job(record)

    def mark_failed(self, job_id: str, error: str) -> JobRecord:
        record = self.get_job(job_id)
        record.status = "failed"
        record.error = error
        return self.save_job(record)

    def build_result_files(self, job_id: str, job_type: JobType) -> JobResultFiles:
        viewer_type = "object_viewer"
        mesh_name = "object_mesh.glb"
        metadata_name = "object_metadata.json"
        material_name = "material.json"
        asset_metadata_name = "metadata.json"
        thumbnail_name = "object_thumbnail.png"

        mesh_path = self.output_dir(job_id) / mesh_name
        metadata_path = self.output_dir(job_id) / metadata_name
        material_path = self.output_dir(job_id) / material_name
        asset_metadata_path = self.output_dir(job_id) / asset_metadata_name
        thumbnail_path = self.preview_dir(job_id) / thumbnail_name

        return JobResultFiles(
            viewer_type=viewer_type,
            mesh_path=str(mesh_path),
            mesh_url=f"/storage/outputs/{job_id}/{mesh_name}",
            metadata_path=str(metadata_path),
            metadata_url=f"/storage/outputs/{job_id}/{metadata_name}",
            material_path=str(material_path),
            material_url=f"/storage/outputs/{job_id}/{material_name}" if material_path.exists() else None,
            asset_metadata_path=str(asset_metadata_path),
            asset_metadata_url=f"/storage/outputs/{job_id}/{asset_metadata_name}" if asset_metadata_path.exists() else None,
            thumbnail_path=str(thumbnail_path),
            thumbnail_url=f"/storage/previews/{job_id}/{thumbnail_name}",
        )
