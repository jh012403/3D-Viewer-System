#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python - <<'PY'
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


PROJECT_ROOT = Path.cwd()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
IMAGE_FILE = Path(os.getenv("IMAGE_FILE", str(PROJECT_ROOT / "assets" / "mock" / "sample_input.jpg"))).resolve()
IMAGE_RUNS = int(os.getenv("IMAGE_RUNS", "3"))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL_SEC", "2"))
TIMEOUT_SEC = float(os.getenv("TIMEOUT_SEC", "1200"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_url(path: str) -> str:
    return f"{BACKEND_URL}{path}"


def request_json(path: str, *, method: str = "GET", payload: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    req = request.Request(build_url(path), data=payload, method=method, headers=headers or {})
    with request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def encode_multipart(job_type: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----ai3d-boundary-{uuid.uuid4().hex}"
    content_type = "image/jpeg"
    body = b"".join(
        [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\n{job_type}\r\n".encode("utf-8"),
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"{file_path.name}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return body, boundary


def upload(job_type: str, file_path: Path) -> dict:
    body, boundary = encode_multipart(job_type, file_path)
    return request_json(
        "/api/upload",
        method="POST",
        payload=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def create_job(job_id: str, job_type: str) -> dict:
    return request_json(
        "/api/jobs",
        method="POST",
        payload=json.dumps({"job_id": job_id, "type": job_type}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def get_job(job_id: str) -> dict:
    return request_json(f"/api/jobs/{job_id}")


def get_result(job_id: str) -> dict | None:
    try:
        return request_json(f"/api/jobs/{job_id}/result")
    except error.HTTPError as exc:
        return {"http_error": exc.code, "detail": exc.read().decode("utf-8")}


def wait_for_job(job_id: str) -> dict:
    started = time.perf_counter()
    while True:
        job = get_job(job_id)
        if job["status"] in {"completed", "failed"}:
            return job
        if time.perf_counter() - started > TIMEOUT_SEC:
            raise TimeoutError(f"Timed out waiting for {job_id} after {TIMEOUT_SEC} seconds.")
        time.sleep(POLL_INTERVAL_SEC)


def run_case(job_type: str, file_path: Path, run_index: int) -> dict:
    started = time.perf_counter()
    upload_payload = upload(job_type, file_path)
    create_job(upload_payload["job_id"], upload_payload["type"])
    job = wait_for_job(upload_payload["job_id"])
    duration_sec = round(time.perf_counter() - started, 3)
    result = get_result(upload_payload["job_id"]) if job["status"] == "completed" else None
    quality = {}
    if isinstance(result, dict):
        quality = result.get("quality") or result.get("metadata", {}).get("quality") or {}

    return {
        "job_type": job_type,
        "run_index": run_index,
        "job_id": upload_payload["job_id"],
        "status": job["status"],
        "duration_sec": duration_sec,
        "stage": job.get("stage"),
        "reason": job.get("reason"),
        "quality_status": job.get("quality_status") or quality.get("status"),
        "error": job.get("error"),
        "input_file": str(file_path),
        "result": result,
    }


def main() -> int:
    report_dir = PROJECT_ROOT / "storage" / "test_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    if not IMAGE_FILE.exists():
        raise FileNotFoundError(f"Image sample not found: {IMAGE_FILE}")

    request_json("/health")

    report = {
        "started_at": now_iso(),
        "backend_url": BACKEND_URL,
        "image_runs": IMAGE_RUNS,
        "runs": [],
    }

    for index in range(1, IMAGE_RUNS + 1):
        run = run_case("image_to_3d", IMAGE_FILE, index)
        report["runs"].append(run)
        print(f"[image {index}/{IMAGE_RUNS}] {run['job_id']} -> {run['status']} / {run['stage']} / {run['quality_status']}")

    report["completed_at"] = now_iso()
    report_path = report_dir / f"repeatability_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Repeatability report written to {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Repeatability test failed: {exc}", file=sys.stderr)
        raise
PY
