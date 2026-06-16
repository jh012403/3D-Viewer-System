from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import imageio.v2 as imageio
import numpy as np


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run official Stability SV3D sampling and export multiview frames."
    )
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--output-video", required=True)
    parser.add_argument("--num-views", type=int, default=21)
    parser.add_argument("--repo-dir", default="")
    parser.add_argument("--version", default="sv3d_p")
    parser.add_argument("--num-steps", "--num_steps", dest="num_steps", type=int, default=30)
    parser.add_argument("--decoding-t", "--decoding_t", dest="decoding_t", type=int, default=2)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--extra-args", default="")
    return parser.parse_args()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_repo_dir() -> Path:
    configured = os.getenv("SV3D_REPO_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (_project_root() / ".runtime" / "generative-models").resolve()


def _pick_generated_video(output_dir: Path) -> Path:
    candidates = sorted(
        [
            path
            for path in output_dir.rglob("*.mp4")
            if path.is_file()
        ],
        key=lambda path: path.stat().st_size,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"SV3D did not generate any .mp4 under {output_dir}")
    return candidates[0]


def _extract_frames(video_path: Path, frames_dir: Path, num_views: int) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    reader = imageio.get_reader(str(video_path))
    frames = []
    try:
        for frame in reader:
            frames.append(frame)
    finally:
        reader.close()

    if not frames:
        raise RuntimeError(f"No frames decoded from generated video: {video_path}")

    num_views = max(1, int(num_views))
    if len(frames) <= num_views:
        indices = list(range(len(frames)))
    else:
        indices = np.linspace(0, len(frames) - 1, num_views).round().astype(int).tolist()

    selected_paths: list[Path] = []
    for index, frame_idx in enumerate(indices):
        out_path = frames_dir / f"view_{index:03d}.png"
        imageio.imwrite(out_path, frames[frame_idx])
        selected_paths.append(out_path)
    return selected_paths


def main() -> None:
    args = _parse_args()
    repo_dir = Path(args.repo_dir).expanduser().resolve() if args.repo_dir else _default_repo_dir()
    if not repo_dir.exists():
        raise RuntimeError(f"SV3D repo dir not found: {repo_dir}")

    output_dir = Path(args.output_dir).expanduser().resolve()
    frames_dir = Path(args.frames_dir).expanduser().resolve()
    output_video = Path(args.output_video).expanduser().resolve()
    input_image = Path(args.input_image).expanduser().resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    output_video.parent.mkdir(parents=True, exist_ok=True)

    script_path = repo_dir / "scripts" / "sampling" / "simple_video_sample.py"
    if not script_path.exists():
        raise RuntimeError(f"SV3D sampling script not found: {script_path}")

    command = [
        sys.executable,
        str(script_path),
        "--input_path",
        str(input_image),
        "--version",
        str(args.version),
        "--output_folder",
        str(output_dir),
        "--num_steps",
        str(args.num_steps),
        "--decoding_t",
        str(args.decoding_t),
        "--seed",
        str(args.seed),
        "--device",
        str(args.device),
    ]
    if args.extra_args.strip():
        command.extend(shlex.split(args.extra_args.strip()))

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "").strip()
    repo_str = str(repo_dir)
    env["PYTHONPATH"] = f"{repo_str}:{pythonpath}" if pythonpath else repo_str

    completed = subprocess.run(
        command,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        env=env,
    )

    log_path = output_dir / "sv3d_helper.log"
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
        raise RuntimeError(f"SV3D sampling failed with exit code {completed.returncode}. See {log_path}")

    generated_video = _pick_generated_video(output_dir)
    shutil.copyfile(generated_video, output_video)
    selected_paths = _extract_frames(generated_video, frames_dir, args.num_views)

    payload = {
        "repo_dir": str(repo_dir),
        "input_image": str(input_image),
        "generated_video": str(generated_video),
        "output_video": str(output_video),
        "frames_dir": str(frames_dir),
        "num_views_requested": int(args.num_views),
        "num_views_exported": len(selected_paths),
        "view_paths": [str(path) for path in selected_paths],
        "version": args.version,
        "num_steps": int(args.num_steps),
        "decoding_t": int(args.decoding_t),
        "seed": int(args.seed),
        "device": args.device,
        "log_path": str(log_path),
    }
    (output_dir / "sv3d_helper_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
