from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.env import load_project_env
from pipelines.common.io import ensure_dir, write_json


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sv3d_repo_dir() -> Path | None:
    configured = os.getenv("SV3D_REPO_DIR", "").strip()
    if not configured:
        return None
    return Path(configured).expanduser().resolve()


def _sv3d_command_parts() -> list[str]:
    command = os.getenv("SV3D_CMD", "").strip()
    if not command:
        raise RuntimeError(
            "SV3D provider was requested but SV3D_CMD is empty. "
            "Set SV3D_CMD (and optional SV3D_REPO_DIR) or use a different MULTIVIEW_PROVIDER."
        )
    return shlex.split(command)


def _append_named_arg(command: list[str], env_name: str, default: str, value: str) -> None:
    arg_name = os.getenv(env_name, default).strip()
    if arg_name:
        command.extend([arg_name, value])


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _set_named_arg(command: list[str], arg_name: str, value: str) -> list[str]:
    if not arg_name:
        return list(command)
    result: list[str] = []
    index = 0
    while index < len(command):
        part = command[index]
        if part == arg_name:
            index += 2
            continue
        result.append(part)
        index += 1
    result.extend([arg_name, value])
    return result


def _is_cuda_oom(stderr: str) -> bool:
    lowered = (stderr or "").lower()
    markers = (
        "cuda out of memory",
        "outofmemoryerror",
        "cudnn_status_alloc_failed",
        "cuda error: out of memory",
    )
    return any(marker in lowered for marker in markers)


def _build_sv3d_command(input_image: Path, work_dir: Path, views_dir: Path, output_video: Path) -> list[str]:
    command = [*_sv3d_command_parts()]
    _append_named_arg(command, "SV3D_INPUT_ARG", "--input_path", str(input_image))
    _append_named_arg(command, "SV3D_OUTPUT_DIR_ARG", "--output_folder", str(work_dir))
    _append_named_arg(command, "SV3D_FRAMES_DIR_ARG", "--frames-dir", str(views_dir))
    _append_named_arg(command, "SV3D_OUTPUT_VIDEO_ARG", "--output-video", str(output_video))
    _append_named_arg(
        command,
        "SV3D_NUM_VIEWS_ARG",
        "--num-views",
        os.getenv("MULTIVIEW_VIEW_COUNT", "16").strip() or "16",
    )

    version = os.getenv("SV3D_VERSION", "").strip()
    if version:
        _append_named_arg(command, "SV3D_VERSION_ARG", "--version", version)

    num_steps = os.getenv("SV3D_NUM_STEPS", "").strip()
    if num_steps:
        _append_named_arg(command, "SV3D_NUM_STEPS_ARG", "--num_steps", num_steps)

    decoding_t = os.getenv("SV3D_DECODING_T", "").strip()
    if decoding_t:
        _append_named_arg(command, "SV3D_DECODING_T_ARG", "--decoding_t", decoding_t)

    device = os.getenv("SV3D_DEVICE", "").strip()
    if device:
        _append_named_arg(command, "SV3D_DEVICE_ARG", "--device", device)

    seed = os.getenv("SV3D_SEED", "").strip()
    if seed:
        _append_named_arg(command, "SV3D_SEED_ARG", "--seed", seed)

    extra_args = os.getenv("SV3D_EXTRA_ARGS", "").strip()
    if extra_args:
        command.extend(shlex.split(extra_args))
    return command


def _collect_view_paths(frames_dir: Path) -> list[Path]:
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    return sorted(path for path in frames_dir.glob("*") if path.suffix.lower() in image_exts)


def _collect_view_paths_recursive(work_dir: Path) -> list[Path]:
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    blocked_names = {"multiview_grid.png", "mask.png"}
    candidates = []
    for path in sorted(work_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in image_exts:
            continue
        if path.name.lower() in blocked_names:
            continue
        candidates.append(path)
    return candidates


def _collect_video_paths_recursive(work_dir: Path) -> list[Path]:
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    return sorted(path for path in work_dir.rglob("*") if path.is_file() and path.suffix.lower() in video_exts)


def _extract_video_frames(video_path: Path, frames_dir: Path) -> list[Path]:
    frame_pattern = frames_dir / "view_%03d.png"
    command = ["ffmpeg", "-y", "-i", str(video_path), str(frame_pattern)]
    completed = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
    if completed.returncode != 0:
        raise RuntimeError(
            f"Failed to extract frames from {video_path} (exit code {completed.returncode}). "
            f"ffmpeg stderr: {completed.stderr.strip()}"
        )
    return _collect_view_paths(frames_dir)


def _build_montage(view_paths: list[Path], output_path: Path) -> None:
    if not view_paths:
        raise RuntimeError("Cannot build montage without view images.")
    selected = view_paths[:12]
    images = [Image.open(path).convert("RGB") for path in selected]
    width, height = images[0].size
    columns = min(4, len(images))
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * width, rows * height), color=(0, 0, 0))
    for index, image in enumerate(images):
        row = index // columns
        col = index % columns
        canvas.paste(image, (col * width, row * height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def _pairwise_metrics(view_paths: list[Path]) -> dict[str, float]:
    sampled = view_paths[: min(len(view_paths), 12)]
    arrays = []
    for path in sampled:
        with Image.open(path) as image:
            rgb = image.convert("RGB").resize((128, 128))
            arrays.append(np.asarray(rgb, dtype=np.float32) / 255.0)

    if len(arrays) < 2:
        return {
            "pairwise_mean_abs_diff_mean": 0.0,
            "pairwise_mean_abs_diff_min": 0.0,
            "pairwise_mean_abs_diff_max": 0.0,
        }

    values = [
        float(np.mean(np.abs(arrays[left] - arrays[right])))
        for left, right in combinations(range(len(arrays)), 2)
    ]
    return {
        "pairwise_mean_abs_diff_mean": round(float(np.mean(values)), 6),
        "pairwise_mean_abs_diff_min": round(float(np.min(values)), 6),
        "pairwise_mean_abs_diff_max": round(float(np.max(values)), 6),
    }


def _generate_sv3d_multiview(input_image: Path, work_dir: Path) -> dict[str, Any]:
    repo_dir = _sv3d_repo_dir()
    if repo_dir is not None and not repo_dir.exists():
        raise RuntimeError(f"SV3D_REPO_DIR does not exist: {repo_dir}")

    views_dir = ensure_dir(work_dir / "views")
    output_video = work_dir / "sv3d_orbit.mp4"
    command = _build_sv3d_command(input_image, work_dir, views_dir, output_video)
    log_path = work_dir / "multiview_wrapper.log"
    attempts: list[dict[str, Any]] = []

    def _run_attempt(run_command: list[str], *, name: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            run_command,
            cwd=repo_dir if repo_dir is not None else None,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        attempts.append(
            {
                "attempt": name,
                "command": " ".join(shlex.quote(part) for part in run_command),
                "return_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        )
        return completed

    completed = _run_attempt(command, name="primary")
    used_oom_retry = False
    if completed.returncode != 0 and _is_cuda_oom(completed.stderr) and _bool_env("SV3D_OOM_RETRY_ENABLED", True):
        retry_command = list(command)
        retry_num_steps = os.getenv("SV3D_OOM_RETRY_NUM_STEPS", "12").strip()
        retry_decoding_t = os.getenv("SV3D_OOM_RETRY_DECODING_T", "1").strip()
        retry_version = os.getenv("SV3D_OOM_RETRY_VERSION", "sv3d_u").strip()
        retry_device = os.getenv("SV3D_OOM_RETRY_DEVICE", os.getenv("SV3D_DEVICE", "cuda").strip() or "cuda").strip()

        retry_command = _set_named_arg(
            retry_command,
            os.getenv("SV3D_NUM_STEPS_ARG", "--num_steps").strip() or "--num_steps",
            retry_num_steps,
        )
        retry_command = _set_named_arg(
            retry_command,
            os.getenv("SV3D_DECODING_T_ARG", "--decoding_t").strip() or "--decoding_t",
            retry_decoding_t,
        )
        retry_command = _set_named_arg(
            retry_command,
            os.getenv("SV3D_VERSION_ARG", "--version").strip() or "--version",
            retry_version,
        )
        retry_command = _set_named_arg(
            retry_command,
            os.getenv("SV3D_DEVICE_ARG", "--device").strip() or "--device",
            retry_device,
        )

        retry_completed = _run_attempt(retry_command, name="oom_retry")
        if retry_completed.returncode == 0:
            used_oom_retry = True
            completed = retry_completed
        else:
            completed = retry_completed

    log_blocks = []
    for item in attempts:
        log_blocks.extend(
            [
                f"ATTEMPT: {item['attempt']}",
                "COMMAND\n" + item["command"],
                "STDOUT\n" + (item["stdout"] or "(empty)"),
                "STDERR\n" + (item["stderr"] or "(empty)"),
            ]
        )
    log_path.write_text("\n\n".join(log_blocks) + "\n", encoding="utf-8")

    if completed.returncode != 0:
        raise RuntimeError(
            f"SV3D generation failed with exit code {completed.returncode}. "
            f"See {log_path}. Last attempt: {attempts[-1]['attempt']}."
        )

    view_paths = _collect_view_paths(views_dir)
    if not view_paths and output_video.exists():
        view_paths = _extract_video_frames(output_video, views_dir)

    if not view_paths:
        recursive_videos = _collect_video_paths_recursive(work_dir)
        if recursive_videos:
            view_paths = _extract_video_frames(recursive_videos[0], views_dir)

    if not view_paths:
        recursive_candidates = _collect_view_paths_recursive(work_dir)
        for index, candidate in enumerate(recursive_candidates):
            destination = views_dir / f"view_{index:03d}{candidate.suffix.lower()}"
            shutil.copyfile(candidate, destination)
            view_paths.append(destination)

    if not view_paths:
        raise RuntimeError(
            f"SV3D command finished without any view frames under {views_dir} or {work_dir}. See {log_path}."
        )

    grid_path = work_dir / "multiview_grid.png"
    _build_montage(view_paths, grid_path)
    summary = {
        "provider": "sv3d",
        "input_image": str(input_image),
        "output_dir": str(work_dir),
        "grid_path": str(grid_path),
        "views_dir": str(views_dir),
        "view_paths": [str(path) for path in view_paths],
        "num_views": len(view_paths),
        "video_path": str(output_video) if output_video.exists() else None,
        "metrics": _pairwise_metrics(view_paths),
        "log_path": str(log_path),
        "sv3d_attempts": [
            {"attempt": item["attempt"], "return_code": item["return_code"]}
            for item in attempts
        ],
        "sv3d_oom_retry_used": used_oom_retry,
    }
    write_json(work_dir / "multiview_summary.json", summary)
    return summary


def generate_multiview_images(input_image: Path, work_dir: Path, *, provider: str | None = None) -> dict[str, Any]:
    load_project_env()
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    provider_name = (provider or os.getenv("MULTIVIEW_PROVIDER", "zero123plus").strip() or "zero123plus")

    if provider_name == "sv3d":
        return _generate_sv3d_multiview(input_image, work_dir)

    # Hunyuan-only production policy: keep SV3D path available, and use
    # deterministic passthrough for any other requested provider.
    return create_passthrough_multiview(
        input_image,
        work_dir,
        reason=f"provider_not_supported:{provider_name}",
    )


def create_passthrough_multiview(input_image: Path, work_dir: Path, *, reason: str | None = None) -> dict[str, Any]:
    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    passthrough_path = work_dir / "multiview_input.png"
    shutil.copyfile(input_image, passthrough_path)
    payload = {
        "enabled": False,
        "active": False,
        "mode": "passthrough",
        "status": "future_hook",
        "input_path": str(input_image),
        "output_path": str(passthrough_path),
        "output_dir": str(work_dir),
        "view_paths": [str(passthrough_path)],
        "num_views": 1,
        "fallback_used": reason is not None,
        "fallback_reason": reason,
        "provider_requested": os.getenv("MULTIVIEW_PROVIDER", "disabled").strip() or "disabled",
        "provider_used": "passthrough",
    }
    write_json(work_dir / "multiview_prior.json", payload)
    return payload
