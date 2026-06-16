from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipelines.common.env import load_project_env
from pipelines.common.io import ensure_dir


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _command_parts() -> list[str]:
    command = os.getenv("FLORENCE2_CMD", "").strip()
    if command:
        return shlex.split(command)
    return [os.getenv("PYTHON", "python")]


def _command_available(parts: list[str]) -> bool:
    if not parts:
        return False
    executable = parts[0]
    if "/" in executable or executable.startswith("."):
        return Path(executable).expanduser().exists()
    return shutil.which(executable) is not None


def object_detector_contract() -> dict[str, Any]:
    load_project_env()
    provider = os.getenv("AI3D_OBJECT_DETECTOR_PROVIDER", "none").strip().lower() or "none"
    if provider in {"off", "disabled", "false", "0"}:
        provider = "none"
    command = _command_parts()
    issues: list[str] = []
    if provider not in {"none", "florence2"}:
        issues.append(f"unsupported_provider:{provider}")
    if provider == "florence2" and not _command_available(command):
        issues.append(f"command_not_found:{command[0] if command else '(empty)'}")
    return {
        "provider": provider,
        "available": provider != "none" and not issues,
        "command": command,
        "model_id": os.getenv("FLORENCE2_MODEL_ID", "microsoft/Florence-2-large").strip()
        or "microsoft/Florence-2-large",
        "device": os.getenv("FLORENCE2_DEVICE", "cuda").strip() or "cuda",
        "prompt": os.getenv("FLORENCE2_PROMPT", "<OD>").strip() or "<OD>",
        "issues": issues,
    }


def detect_object_boxes(input_image: Path, work_dir: Path, *, max_candidates: int = 12) -> dict[str, Any]:
    """Return semantic object box proposals for the uploaded image.

    This stage is intentionally independent from TRELLIS.2.  If the detector
    runtime is not configured, callers can fall back to SAM2 automatic masks.
    """
    load_project_env()
    contract = object_detector_contract()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    output_json = work_dir / "object_boxes.json"

    if not contract["available"]:
        payload = {
            "provider": contract["provider"],
            "available": False,
            "issues": contract["issues"],
            "candidates": [],
        }
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    helper_script = _project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "florence2_detect.py"
    command = [
        *contract["command"],
        str(helper_script),
        "--input-image",
        str(input_image.expanduser().resolve()),
        "--output-json",
        str(output_json),
        "--model-id",
        str(contract["model_id"]),
        "--device",
        str(contract["device"]),
        "--prompt",
        str(contract["prompt"]),
        "--max-candidates",
        str(max(1, int(max_candidates))),
        "--min-area-ratio",
        os.getenv("AI3D_OBJECT_DETECTOR_MIN_AREA_RATIO", "0.002").strip() or "0.002",
        "--max-area-ratio",
        os.getenv("AI3D_OBJECT_DETECTOR_MAX_AREA_RATIO", "0.95").strip() or "0.95",
    ]

    env = os.environ.copy()
    project_root = str(_project_root())
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}:{current_pythonpath}" if current_pythonpath else project_root

    completed = subprocess.run(
        command,
        cwd=_project_root(),
        capture_output=True,
        text=True,
        env=env,
    )
    log_path = work_dir / "object_detector.log"
    log_path.write_text(
        "\n\n".join(
            [
                "COMMAND\n" + " ".join(shlex.quote(part) for part in command),
                "STDOUT\n" + (completed.stdout.strip() or "(empty)"),
                "STDERR\n" + (completed.stderr.strip() or "(empty)"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if completed.returncode != 0:
        payload = {
            "provider": contract["provider"],
            "available": False,
            "issues": [f"detector_failed:{completed.returncode}"],
            "log_path": str(log_path),
            "candidates": [],
        }
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    if not output_json.exists():
        payload = {
            "provider": contract["provider"],
            "available": False,
            "issues": ["detector_output_missing"],
            "log_path": str(log_path),
            "candidates": [],
        }
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    payload["available"] = True
    payload["log_path"] = str(log_path)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
