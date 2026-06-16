from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


IMAGE_QUALITY_MODE_TO_HEAD = {
    "high_quality": "trellis",
    "auto": "trellis",
}

"""Image reconstruction policy constants."""
PRODUCTION_BACKEND_POLICY = "production_trellis_only_v1"
AUTO_HQ_CHAIN = ["trellis"]


_HEAD_ALIASES = {
    "trellis2": "trellis",
    "trellis_2": "trellis",
    "hunyuan": "hunyuan3d",
    "hunyuan_3d": "hunyuan3d",
    "hunyuan3d_2": "hunyuan3d",
}


def normalize_head_name(name: str | None) -> str:
    normalized = (name or "").strip().lower().replace("-", "_")
    normalized = _HEAD_ALIASES.get(normalized, normalized)
    if normalized in {"hq", "high_quality", "auto", "fast", "auto_hq"}:
        return "trellis"
    if normalized in {"trellis", "trellis2"}:
        return "trellis"
    if normalized in {"hunyuan3d", "hunyuan"}:
        return "hunyuan3d"
    # Force all unknown/legacy heads to trellis to keep a single
    # deterministic production path.
    return "trellis"


def normalize_image_quality_mode(mode: str | None) -> str | None:
    normalized = (mode or "").strip().lower().replace("-", "_")
    if not normalized:
        return None
    if normalized in {"high", "hq", "quality", "highquality", "high_quality", "auto", "fast"}:
        return "high_quality"
    return None


def resolve_image_quality_mode(explicit_mode: str | None = None, requested_head: str | None = None) -> str:
    normalized_mode = normalize_image_quality_mode(explicit_mode)
    if normalized_mode in IMAGE_QUALITY_MODE_TO_HEAD:
        return normalized_mode

    normalized_head = normalize_head_name(requested_head or "")
    if normalized_head in {"trellis", "hunyuan3d"}:
        return "high_quality"

    env_mode = normalize_image_quality_mode(os.getenv("AI3D_IMAGE_QUALITY_MODE", "high_quality"))
    if env_mode in IMAGE_QUALITY_MODE_TO_HEAD:
        return env_mode
    return "high_quality"


def resolve_requested_reconstruction_head(
    explicit_head: str | None = None,
    image_quality_mode: str | None = None,
) -> str:
    if explicit_head:
        return normalize_head_name(explicit_head)

    normalized_mode = normalize_image_quality_mode(image_quality_mode)
    if normalized_mode in IMAGE_QUALITY_MODE_TO_HEAD:
        return IMAGE_QUALITY_MODE_TO_HEAD[normalized_mode]

    env_mode = normalize_image_quality_mode(os.getenv("AI3D_IMAGE_QUALITY_MODE", ""))
    if env_mode in IMAGE_QUALITY_MODE_TO_HEAD:
        return IMAGE_QUALITY_MODE_TO_HEAD[env_mode]

    return normalize_head_name(os.getenv("IMAGE_RECON_HEAD", "trellis"))


def resolve_reconstruction_head_chain(requested_head: str | None) -> list[str]:
    _ = normalize_head_name(requested_head)
    return list(AUTO_HQ_CHAIN)


@dataclass(slots=True)
class ReconstructionResult:
    mesh_path: Path
    requested_head: str
    used_head: str
    multiview_source: str | None = None
    mesh_backend: str | None = None
    resolved_backend: str | None = None
    log_paths: dict[str, str] = field(default_factory=dict)
    raw_outputs: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def head_name(self) -> str:
        return self.used_head

    def to_metadata(self) -> dict[str, Any]:
        return {
            "requested": self.requested_head,
            "used": self.used_head,
            "resolved_backend": self.resolved_backend,
            "mesh_backend": self.mesh_backend or self.resolved_backend,
            "status": "completed",
            "mesh_path": str(self.mesh_path),
            "multiview_source": self.multiview_source,
            "log_paths": self.log_paths,
            "raw_outputs": self.raw_outputs,
            "notes": self.notes,
        }


class ReconstructionHead(ABC):
    name: str

    @abstractmethod
    def availability(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def reconstruct(
        self,
        *,
        input_image: Path,
        multiview_info: dict[str, Any],
        work_dir: Path,
        output_dir: Path,
        object_name: str,
    ) -> ReconstructionResult:
        raise NotImplementedError
