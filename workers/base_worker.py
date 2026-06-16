from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from pipelines.common.env import build_runtime_env

from backend.app.core.config import get_settings
from backend.app.core.job_store import JobStore
from backend.app.schemas.job import JobRecord, JobType


class BaseWorker:
    def __init__(self, job_type: JobType, pipeline_module: str) -> None:
        self.settings = get_settings()
        self.store = JobStore(self.settings)
        self.job_type = job_type
        self.pipeline_module = pipeline_module

    def build_command(self, job: JobRecord) -> list[str]:
        mode = "mock" if self.settings.mock_mode else "real"
        command = [
            sys.executable,
            "-m",
            self.pipeline_module,
            "--job-id",
            job.job_id,
            "--input-file",
            job.input_file,
            "--output-dir",
            job.output_dir,
            "--preview-dir",
            job.preview_dir,
            "--temp-dir",
            job.temp_dir,
            "--mode",
            mode,
        ]
        if job.type == "image_to_3d":
            requested_head = str(job.options.get("requested_reconstruction_head") or "").strip()
            image_quality_mode = str(job.options.get("image_quality_mode") or "").strip()
            sam2_candidate_id = str(job.options.get("sam2_candidate_id") or "").strip()
            source_prompt = str(job.options.get("source_prompt") or "").strip()
            if requested_head:
                command.extend(["--requested-reconstruction-head", requested_head])
            if image_quality_mode:
                command.extend(["--image-quality-mode", image_quality_mode])
            if sam2_candidate_id:
                command.extend(["--sam2-candidate-id", sam2_candidate_id])
            if source_prompt:
                command.extend(["--source-prompt", source_prompt])
        return command

    def write_worker_log(self, job: JobRecord, stdout: str, stderr: str) -> Path:
        log_path = Path(job.temp_dir) / "worker.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        if stdout:
            payload.append("STDOUT\n" + stdout.strip())
        if stderr:
            payload.append("STDERR\n" + stderr.strip())
        if not payload:
            payload.append("Worker completed without console output.")
        log_path.write_text("\n\n".join(payload) + "\n", encoding="utf-8")
        return log_path

    def metadata_path_for_job(self, job: JobRecord) -> Path:
        return self.store.metadata_file(job.job_id, job.type)

    def load_metadata_summary(self, job: JobRecord) -> dict:
        metadata_path = self.metadata_path_for_job(job)
        if not metadata_path.exists():
            return {}
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    def user_error_message(self, job: JobRecord, error: Exception) -> str:
        metadata = self.load_metadata_summary(job)
        if metadata.get("user_message"):
            return str(metadata["user_message"])
        return str(error).strip().splitlines()[0].strip() or "The pipeline failed."

    def process_job(self, job: JobRecord) -> None:
        command = self.build_command(job)
        run_env = build_runtime_env()
        completed = subprocess.run(
            command,
            cwd=self.settings.project_root,
            capture_output=True,
            text=True,
            env=run_env,
        )
        self.write_worker_log(job, completed.stdout, completed.stderr)
        metadata = self.load_metadata_summary(job)
        if completed.returncode != 0:
            fallback = completed.stderr.strip() or completed.stdout.strip() or f"Pipeline exited with code {completed.returncode}."
            raise RuntimeError(metadata.get("user_message") or fallback)

        metadata_path = self.metadata_path_for_job(job)

        result_files = self.store.build_result_files(job.job_id, job.type)
        missing = [
            path
            for path in (result_files.mesh_path, result_files.metadata_path, result_files.thumbnail_path)
            if not Path(path).exists()
        ]
        if missing:
            raise RuntimeError(f"Pipeline finished but required artifacts are missing: {', '.join(missing)}")
        self.store.mark_completed(job.job_id, result_files)

    def run(self, once: bool = False) -> None:
        while True:
            job = self.store.claim_next_job(self.job_type)
            if job:
                try:
                    self.process_job(job)
                except Exception as exc:  # noqa: BLE001
                    self.store.mark_failed(job.job_id, self.user_error_message(job, exc))
            if once:
                return
            if not job:
                time.sleep(self.settings.worker_poll_interval_seconds)


def build_arg_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--once", action="store_true", help="Process at most one queued job.")
    return parser
