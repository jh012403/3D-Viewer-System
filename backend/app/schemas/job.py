from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


JobType = Literal["image_to_3d"]
JobStatus = Literal["queued", "running", "completed", "failed"]
ViewerType = Literal["object_viewer"]


class UploadResponse(BaseModel):
    job_id: str
    type: JobType
    input_file: str
    filename: str


class JobCreateRequest(BaseModel):
    job_id: str
    type: JobType
    options: dict[str, Any] = Field(default_factory=dict)


class SegmentationCandidate(BaseModel):
    candidate_id: str
    pass_name: str
    label: str | None = None
    source: str | None = None
    bbox: list[float] | None = None
    detection_score: float | None = None
    score: float
    area_ratio: float
    predicted_iou: float
    stability_score: float
    border_touch_count: int
    segmented_url: str
    segmented_preview_url: str | None = None
    mask_url: str
    overlay_url: str


class SegmentationCandidatesResponse(BaseModel):
    job_id: str
    type: JobType
    input_url: str
    selected_candidate_id: str | None = None
    candidates: list[SegmentationCandidate] = Field(default_factory=list)


class SegmentationPromptPoint(BaseModel):
    x: float
    y: float
    label: int = 1


class SegmentationPromptRequest(BaseModel):
    points: list[SegmentationPromptPoint] = Field(default_factory=list)
    box: list[float] | None = None


class SegmentationTextPromptRequest(BaseModel):
    prompt: str
    confidence_threshold: float | None = None
    merge_mode: Literal["best", "union"] = "best"


class JobResultFiles(BaseModel):
    viewer_type: ViewerType | None = None
    mesh_path: str
    mesh_url: str
    metadata_path: str
    metadata_url: str
    material_path: str | None = None
    material_url: str | None = None
    asset_metadata_path: str | None = None
    asset_metadata_url: str | None = None
    thumbnail_path: str | None = None
    thumbnail_url: str | None = None
    preview_path: str | None = None
    preview_url: str | None = None

    @model_validator(mode="after")
    def normalize_legacy_fields(self) -> "JobResultFiles":
        if self.thumbnail_path is None and self.preview_path is not None:
            self.thumbnail_path = self.preview_path
        if self.thumbnail_url is None and self.preview_url is not None:
            self.thumbnail_url = self.preview_url

        if self.viewer_type is None:
            self.viewer_type = "object_viewer"
        return self


class JobRecord(BaseModel):
    job_id: str
    type: JobType
    status: JobStatus
    input_file: str
    output_dir: str
    requested_head_chain: list[str] | None = None
    fallback_chain: list[str] | None = None
    backend_policy: str | None = None
    resolved_backend: str | None = None
    mesh_backend: str | None = None
    fallback_used: bool | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    stage: str | None = None
    reason: str | None = None
    quality_status: str | None = None
    quality: dict = Field(default_factory=dict)
    preview_dir: str
    temp_dir: str
    created_at: datetime
    updated_at: datetime
    result: JobResultFiles | None = None


class JobResultResponse(BaseModel):
    job_id: str
    type: JobType
    viewer_type: ViewerType
    mesh_url: str | None
    thumbnail_url: str
    material_url: str | None = None
    asset_metadata_url: str | None = None
    stage: str | None = None
    reason: str | None = None
    quality_status: str | None = None
    quality: dict = Field(default_factory=dict)
    job: JobRecord
    metadata: dict = Field(default_factory=dict)
    material: dict = Field(default_factory=dict)
    asset_metadata: dict = Field(default_factory=dict)


class JobExportItem(BaseModel):
    format: str
    label: str
    file_name: str | None = None
    url: str | None = None
    mime_type: str
    tool_hint: str
    note: str
    available: bool = True
    generated: bool = False
    reason: str | None = None


class JobExportListResponse(BaseModel):
    job_id: str
    exports: list[JobExportItem] = Field(default_factory=list)


class JobExportResponse(JobExportItem):
    job_id: str
