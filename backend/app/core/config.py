from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    project_root: Path
    storage_root: Path
    uploads_root: Path
    jobs_root: Path
    outputs_root: Path
    previews_root: Path
    temp_root: Path
    backend_host: str
    backend_port: int
    frontend_origin: str
    worker_poll_interval_seconds: int
    mock_mode: bool
    log_level: str


@lru_cache
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env")
    storage_root = project_root / "storage"
    return Settings(
        project_root=project_root,
        storage_root=storage_root,
        uploads_root=storage_root / "uploads",
        jobs_root=storage_root / "jobs",
        outputs_root=storage_root / "outputs",
        previews_root=storage_root / "previews",
        temp_root=storage_root / "temp",
        backend_host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(os.getenv("BACKEND_PORT", "8000")),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        worker_poll_interval_seconds=int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2")),
        mock_mode=_read_bool("AI3D_MOCK_MODE", True),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )
