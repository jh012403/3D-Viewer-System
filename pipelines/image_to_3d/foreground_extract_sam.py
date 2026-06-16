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
    command = (
        os.getenv("SAM2_FOREGROUND_CMD", "").strip()
        or os.getenv("SAM_FOREGROUND_CMD", "").strip()
    )
    return shlex.split(command) if command else []


def _repo_dir() -> Path | None:
    raw = os.getenv("SAM2_REPO_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    candidate = (_project_root() / ".runtime" / "sam2").resolve()
    if candidate.exists():
        return candidate
    return None


def _command_available(parts: list[str]) -> bool:
    if not parts:
        return False
    executable = parts[0]
    if "/" in executable or executable.startswith("."):
        return Path(executable).expanduser().exists()
    return shutil.which(executable) is not None


def _replace_cli_value(command: list[str], flag: str, value: str) -> None:
    try:
        index = command.index(flag)
    except ValueError:
        command.extend([flag, value])
        return
    if index + 1 < len(command):
        command[index + 1] = value
    else:
        command.append(value)


def _is_cuda_oom(stderr: str) -> bool:
    lowered = stderr.lower()
    return "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered


def _format_log(command: list[str], stdout: str, stderr: str, *, title: str = "") -> str:
    sections = []
    if title:
        sections.append(title)
    sections.extend(
        [
            "COMMAND\n" + " ".join(shlex.quote(part) for part in command),
            "STDOUT\n" + (stdout.strip() or "(empty)"),
            "STDERR\n" + (stderr.strip() or "(empty)"),
        ]
    )
    return "\n\n".join(sections)


def _default_checkpoint_candidates(repo_dir: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if repo_dir is not None:
        candidates.extend(
            [
                repo_dir / "checkpoints" / "sam2.1_hiera_tiny.pt",
                repo_dir / "checkpoints" / "sam2.1_hiera_small.pt",
                repo_dir / "checkpoints" / "sam2.1_hiera_base_plus.pt",
                repo_dir / "checkpoints" / "sam2.1_hiera_large.pt",
            ]
        )
    return [path.expanduser().resolve() for path in candidates]


def _checkpoint_path(repo_dir: Path | None) -> Path | None:
    explicit = (
        os.getenv("SAM2_FOREGROUND_CHECKPOINT", "").strip()
        or os.getenv("SAM_FOREGROUND_CHECKPOINT", "").strip()
    )
    if explicit:
        return Path(explicit).expanduser().resolve()
    for candidate in _default_checkpoint_candidates(repo_dir):
        if candidate.exists():
            return candidate
    return None


def _config_name() -> str:
    return os.getenv("SAM2_FOREGROUND_CONFIG", "configs/sam2.1/sam2.1_hiera_t.yaml").strip() or "configs/sam2.1/sam2.1_hiera_t.yaml"


def sam_foreground_contract() -> dict[str, Any]:
    command = _command_parts()
    repo_dir = _repo_dir()
    checkpoint = _checkpoint_path(repo_dir)
    helper_script = _project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "sam2_extract.py"
    issues: list[str] = []
    if not command:
        issues.append("command_missing")
    elif not _command_available(command):
        issues.append(f"command_not_found:{command[0]}")
    if repo_dir is None:
        issues.append("repo_missing")
    elif not repo_dir.exists():
        issues.append(f"repo_not_found:{repo_dir}")
    if checkpoint is None:
        issues.append("checkpoint_missing")
    elif not checkpoint.exists():
        issues.append(f"checkpoint_not_found:{checkpoint}")
    if not helper_script.exists():
        issues.append(f"helper_missing:{helper_script}")

    return {
        "provider": "sam2",
        "available": not issues,
        "command": command,
        "repo_dir": str(repo_dir) if repo_dir else None,
        "checkpoint": str(checkpoint) if checkpoint else None,
        "config": _config_name(),
        "device": (
            os.getenv("SAM2_FOREGROUND_DEVICE", "").strip()
            or os.getenv("SAM_FOREGROUND_DEVICE", "cuda").strip()
            or "cuda"
        ),
        "issues": issues,
        "summary": "SAM2-backed foreground extraction via official automatic mask generation.",
    }


def extract_with_sam(
    input_image: Path,
    work_dir: Path,
    *,
    selected_candidate_id: str | None = None,
    dump_candidates_dir: Path | None = None,
    boxes_json: Path | None = None,
    prompt_json: Path | None = None,
    max_candidates: int = 0,
    reset_candidates_dir: bool = True,
) -> dict[str, Any]:
    load_project_env()
    contract = sam_foreground_contract()
    if not contract["available"]:
        raise RuntimeError(f"SAM2 runtime not available: {', '.join(contract['issues'])}")

    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    helper_script = _project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "sam2_extract.py"
    if not helper_script.exists():
        raise RuntimeError(f"SAM2 helper script is missing: {helper_script}")

    command = [
        *contract["command"],
        str(helper_script),
        "--input-image",
        str(input_image),
        "--output-dir",
        str(work_dir),
        "--sam2-repo-dir",
        str(contract["repo_dir"]),
        "--checkpoint",
        str(contract["checkpoint"]),
        "--config",
        str(contract["config"]),
        "--device",
        str(contract["device"]),
        "--points-per-side",
        (
            os.getenv("SAM2_FOREGROUND_POINTS_PER_SIDE", "").strip()
            or os.getenv("SAM_FOREGROUND_POINTS_PER_SIDE", "32").strip()
            or "32"
        ),
        "--pred-iou-thresh",
        (
            os.getenv("SAM2_FOREGROUND_PRED_IOU_THRESH", "").strip()
            or os.getenv("SAM_FOREGROUND_PRED_IOU_THRESH", "0.65").strip()
            or "0.65"
        ),
        "--stability-score-thresh",
        (
            os.getenv("SAM2_FOREGROUND_STABILITY_SCORE_THRESH", "").strip()
            or os.getenv("SAM_FOREGROUND_STABILITY_SCORE_THRESH", "0.80").strip()
            or "0.80"
        ),
        "--min-mask-area-ratio",
        os.getenv("SAM2_FOREGROUND_MIN_AREA_RATIO", "0.005").strip() or "0.005",
        "--max-mask-area-ratio",
        os.getenv("SAM2_FOREGROUND_MAX_AREA_RATIO", "0.90").strip() or "0.90",
        "--crop-n-layers",
        os.getenv("SAM2_FOREGROUND_CROP_N_LAYERS", "0").strip() or "0",
        "--crop-n-points-downscale-factor",
        os.getenv("SAM2_FOREGROUND_CROP_N_POINTS_DOWNSCALE", "1").strip() or "1",
        "--min-mask-region-area",
        os.getenv("SAM2_FOREGROUND_MIN_MASK_REGION_AREA", "0").strip() or "0",
        "--adaptive-enabled",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_ENABLED", "1").strip() or "1",
        "--adaptive-trigger-score",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_TRIGGER_SCORE", "0.62").strip() or "0.62",
        "--adaptive-trigger-min-area-ratio",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_TRIGGER_MIN_AREA_RATIO", "0.06").strip() or "0.06",
        "--adaptive-points-per-side",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_POINTS_PER_SIDE", "48").strip() or "48",
        "--adaptive-pred-iou-thresh",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_PRED_IOU_THRESH", "0.55").strip() or "0.55",
        "--adaptive-stability-score-thresh",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_STABILITY_SCORE_THRESH", "0.72").strip() or "0.72",
        "--adaptive-crop-n-layers",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_CROP_N_LAYERS", "1").strip() or "1",
        "--adaptive-crop-n-points-downscale-factor",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_CROP_N_POINTS_DOWNSCALE", "1").strip() or "1",
        "--adaptive-min-mask-region-area",
        os.getenv("SAM2_FOREGROUND_ADAPTIVE_MIN_MASK_REGION_AREA", "0").strip() or "0",
    ]
    if selected_candidate_id:
        command.extend(["--selected-candidate-id", selected_candidate_id])
    if boxes_json is not None:
        command.extend(["--boxes-json", str(boxes_json.expanduser().resolve())])
    if prompt_json is not None:
        command.extend(["--prompt-json", str(prompt_json.expanduser().resolve())])
    if dump_candidates_dir is not None:
        if reset_candidates_dir:
            shutil.rmtree(dump_candidates_dir.expanduser().resolve(), ignore_errors=True)
        command.extend(["--dump-candidates-dir", str(dump_candidates_dir.expanduser().resolve())])
        command.extend(["--max-candidates", str(max(0, int(max_candidates)))])

    env = os.environ.copy()
    project_root = str(_project_root())
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}:{current_pythonpath}" if current_pythonpath else project_root
    pythonpath_overlay = (
        os.getenv("SAM2_FOREGROUND_PYTHONPATH", "").strip()
        or os.getenv("SAM_FOREGROUND_PYTHONPATH", "").strip()
    )
    if pythonpath_overlay:
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{pythonpath_overlay}:{current_pythonpath}" if current_pythonpath else pythonpath_overlay
        )

    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    completed = subprocess.run(
        command,
        cwd=_project_root(),
        capture_output=True,
        text=True,
        env=env,
    )

    log_path = work_dir / "sam_foreground.log"
    log_body = _format_log(command, completed.stdout, completed.stderr, title="ATTEMPT primary")

    if completed.returncode != 0 and _is_cuda_oom(completed.stderr):
        safe_command = list(command)
        _replace_cli_value(safe_command, "--points-per-side", os.getenv("SAM2_FOREGROUND_OOM_POINTS_PER_SIDE", "24"))
        _replace_cli_value(safe_command, "--crop-n-layers", "0")
        _replace_cli_value(safe_command, "--adaptive-enabled", "0")
        _replace_cli_value(safe_command, "--adaptive-points-per-side", os.getenv("SAM2_FOREGROUND_OOM_POINTS_PER_SIDE", "24"))
        _replace_cli_value(safe_command, "--adaptive-crop-n-layers", "0")
        retry = subprocess.run(
            safe_command,
            cwd=_project_root(),
            capture_output=True,
            text=True,
            env=env,
        )
        log_body += "\n\nRETRY_REASON\ncuda_oom_safe_sam2_candidate_pass"
        log_body += "\n\n" + _format_log(safe_command, retry.stdout, retry.stderr, title="ATTEMPT oom_safe")
        completed = retry
        command = safe_command

    log_path.write_text(log_body + "\n", encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"SAM2 foreground extraction failed with exit code {completed.returncode}. See {log_path}.")

    summary_path = work_dir / "sam2_summary.json"
    if not summary_path.exists():
        raise RuntimeError(f"SAM2 foreground extraction finished without writing {summary_path}.")

    result = json.loads(summary_path.read_text(encoding="utf-8"))
    result.setdefault("provider", "sam2")
    result["log_path"] = str(log_path)
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
