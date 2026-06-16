from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from backend.app.core.config import get_settings
from backend.app.schemas.job import (
    JobCreateRequest,
    JobExportListResponse,
    JobExportResponse,
    JobRecord,
    JobResultResponse,
    JobType,
    SegmentationCandidatesResponse,
    SegmentationPromptRequest,
    SegmentationTextPromptRequest,
    UploadResponse,
)
from backend.app.services.job_service import JobService

router = APIRouter(prefix="/api")
job_service = JobService()


@router.get("/demo-assets/trellis")
def list_trellis_demo_assets() -> dict[str, object]:
    settings = get_settings()
    examples_dir = settings.project_root / "assets" / "trellis_demo_ready"
    items: list[dict[str, object]] = []
    if examples_dir.exists():
        for path in sorted(examples_dir.glob("*.webp")):
            if not path.is_file():
                continue
            relative = Path("trellis_demo_ready") / path.name
            items.append(
                {
                    "id": path.stem,
                    "file_name": path.name,
                    "url": f"/assets/{relative.as_posix()}",
                    "size_bytes": path.stat().st_size,
                    "source": "trellis2_official_example_ready",
                }
            )
    return {
        "source": "assets/trellis_demo_ready",
        "count": len(items),
        "items": items,
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_file(type: JobType = Form(...), file: UploadFile = File(...)) -> UploadResponse:
    return await job_service.handle_upload(type, file)


@router.post("/jobs", response_model=JobRecord)
def create_job(request: JobCreateRequest) -> JobRecord:
    return job_service.create_job(request)


@router.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    return job_service.get_job(job_id)


@router.get("/jobs/{job_id}/segmentation-candidates", response_model=SegmentationCandidatesResponse)
def get_segmentation_candidates(job_id: str) -> SegmentationCandidatesResponse:
    return job_service.get_segmentation_candidates(job_id)


@router.post("/jobs/{job_id}/segmentation-prompt", response_model=SegmentationCandidatesResponse)
def create_segmentation_prompt(job_id: str, request: SegmentationPromptRequest) -> SegmentationCandidatesResponse:
    return job_service.create_segmentation_prompt(job_id, request)


@router.post("/jobs/{job_id}/segmentation-text-prompt", response_model=SegmentationCandidatesResponse)
def create_segmentation_text_prompt(
    job_id: str,
    request: SegmentationTextPromptRequest,
) -> SegmentationCandidatesResponse:
    return job_service.create_segmentation_text_prompt(job_id, request)


@router.post("/jobs/{job_id}/segmentation-candidates/{candidate_id}/enhance", response_model=SegmentationCandidatesResponse)
def enhance_segmentation_candidate(job_id: str, candidate_id: str) -> SegmentationCandidatesResponse:
    return job_service.enhance_segmentation_candidate(job_id, candidate_id)


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
def get_job_result(job_id: str) -> JobResultResponse:
    return job_service.get_result(job_id)


@router.get("/jobs/{job_id}/exports", response_model=JobExportListResponse)
def list_job_exports(job_id: str) -> JobExportListResponse:
    return job_service.list_exports(job_id)


@router.post("/jobs/{job_id}/exports/{export_format}", response_model=JobExportResponse)
def create_job_export(job_id: str, export_format: str) -> JobExportResponse:
    return job_service.create_export(job_id, export_format)
