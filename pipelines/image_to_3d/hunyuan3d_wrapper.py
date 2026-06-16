from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipelines.common.env import build_runtime_env, load_project_env
from pipelines.common.io import ensure_dir, write_json


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_dir() -> Path:
    configured = os.getenv("HUNYUAN3D_REPO_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (_project_root() / ".runtime" / "Hunyuan3D-2").resolve()


def _helper_script() -> Path:
    return (_project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "hunyuan3d_generate.py").resolve()


def _command_parts() -> list[str]:
    command = os.getenv("HUNYUAN3D_CMD", "conda run -n instantmesh-run python").strip()
    return shlex.split(command)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _string_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _command_available(parts: list[str]) -> bool:
    if not parts:
        return False
    executable = parts[0]
    if "/" in executable or executable.startswith("."):
        return Path(executable).expanduser().exists()
    return shutil.which(executable) is not None


def _python_runtime_probe(parts: list[str]) -> list[str]:
    if not parts:
        return ["empty_command"]

    probe = subprocess.run(
        [
            *parts,
            "-c",
            (
                "import importlib.util as u;"
                "mods=['torch','hy3dgen','trimesh'];"
                "missing=[m for m in mods if u.find_spec(m) is None];"
                "print(','.join(missing))"
            ),
        ],
        capture_output=True,
        text=True,
        env=build_runtime_env(os.environ.copy()),
    )
    if probe.returncode != 0:
        stderr = (probe.stderr or "").strip() or "probe_failed"
        return [f"python_probe_failed:{stderr}"]
    missing = (probe.stdout or "").strip()
    if missing:
        return [f"missing_python_modules:{missing}"]
    return []


def hunyuan3d_contract() -> dict[str, Any]:
    repo_dir = _repo_dir()
    helper = _helper_script()
    command = _command_parts()
    issues: list[str] = []
    if not repo_dir.exists():
        issues.append(f"repo_missing:{repo_dir}")
    if not helper.exists():
        issues.append(f"helper_missing:{helper}")
    if not _command_available(command):
        issues.append(f"command_missing:{command[0] if command else 'empty'}")
    if not issues:
        issues.extend(_python_runtime_probe(command))

    return {
        "head": "hunyuan3d",
        "available": not issues,
        "repo_dir": str(repo_dir),
        "helper_script": str(helper),
        "command": command,
        "model_path": _string_env("HUNYUAN3D_MODEL_PATH", "tencent/Hunyuan3D-2mini"),
        "subfolder": _string_env("HUNYUAN3D_SUBFOLDER", "hunyuan3d-dit-v2-mini-turbo"),
        "device": _string_env("HUNYUAN3D_DEVICE", "cuda"),
        "num_inference_steps": _int_env("HUNYUAN3D_NUM_INFERENCE_STEPS", 28),
        "guidance_scale": _float_env("HUNYUAN3D_GUIDANCE_SCALE", 5.5),
        "octree_resolution": _int_env("HUNYUAN3D_OCTREE_RESOLUTION", 320),
        "mc_algo": _string_env("HUNYUAN3D_MC_ALGO", "mc"),
        "enable_flashvdm": _bool_env("HUNYUAN3D_ENABLE_FLASHVDM", True),
        "enable_postprocess": _bool_env("HUNYUAN3D_ENABLE_POSTPROCESS", True),
        "enable_tex": _bool_env("HUNYUAN3D_ENABLE_TEX", False),
        "low_vram_mode": _bool_env("HUNYUAN3D_LOW_VRAM_MODE", True),
        "issues": issues,
        "summary": "Hunyuan3D-2 image-to-mesh runtime wrapper (SAM/normalized image input).",
    }


def run_hunyuan3d(
    *,
    input_image: Path,
    work_dir: Path,
    output_dir: Path,
    object_name: str,
) -> dict[str, Any]:
    load_project_env()
    contract = hunyuan3d_contract()
    if not contract["available"]:
        issues = ", ".join(contract["issues"])
        raise RuntimeError(f"Hunyuan3D runtime not available: {issues}")

    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    output_dir = ensure_dir(output_dir.expanduser().resolve())
    repo_dir = Path(str(contract["repo_dir"]))
    helper_script = Path(str(contract["helper_script"]))
    output_mesh_path = work_dir / "hunyuan3d_raw.obj"
    summary_path = work_dir / "hunyuan3d_summary.json"
    runtime_log_path = work_dir / "hunyuan3d_runtime.log"
    wrapper_log_path = work_dir / "hunyuan3d_wrapper.log"

    command = [
        *_command_parts(),
        str(helper_script),
        "--input-image",
        str(input_image),
        "--output-mesh",
        str(output_mesh_path),
        "--summary-path",
        str(summary_path),
        "--runtime-log",
        str(runtime_log_path),
        "--model-path",
        str(contract["model_path"]),
        "--subfolder",
        str(contract["subfolder"]),
        "--device",
        str(contract["device"]),
        "--num-inference-steps",
        str(contract["num_inference_steps"]),
        "--guidance-scale",
        str(contract["guidance_scale"]),
        "--octree-resolution",
        str(contract["octree_resolution"]),
        "--mc-algo",
        str(contract["mc_algo"]),
        "--seed",
        str(_int_env("HUNYUAN3D_SEED", 1234)),
        "--max-faces",
        str(_int_env("HUNYUAN3D_MAX_FACES", 120000)),
    ]
    if bool(contract["enable_flashvdm"]):
        command.append("--enable-flashvdm")
    if bool(contract["enable_postprocess"]):
        command.append("--enable-postprocess")
    if bool(contract["enable_tex"]):
        command.extend(["--enable-tex", "--tex-model-path", _string_env("HUNYUAN3D_TEX_MODEL_PATH", "tencent/Hunyuan3D-2")])
    if bool(contract["low_vram_mode"]):
        command.append("--low-vram")

    extra_args = os.getenv("HUNYUAN3D_EXTRA_ARGS", "").strip()
    if extra_args:
        command.extend(shlex.split(extra_args))

    completed = subprocess.run(
        command,
        cwd=repo_dir,
        capture_output=True,
        text=True,
        env=build_runtime_env(os.environ.copy()),
    )
    wrapper_log_path.write_text(
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
        raise RuntimeError(f"Hunyuan3D reconstruction failed with exit code {completed.returncode}. See {wrapper_log_path}.")

    summary_payload: dict[str, Any] = {}
    if summary_path.exists():
        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary_payload = {"status": "invalid_summary_json"}

    mesh_path = Path(str(summary_payload.get("output_mesh") or output_mesh_path)).expanduser().resolve()
    if not mesh_path.exists():
        raise RuntimeError(f"Hunyuan3D finished without exporting a mesh under {work_dir}.")

    payload = {
        "head": "hunyuan3d",
        "input_image": str(input_image),
        "mesh_path": str(mesh_path),
        "mesh_backend": "hunyuan3d",
        "resolved_backend": "hunyuan3d",
        "object_name": object_name,
        "log_paths": {
            "wrapper": str(wrapper_log_path),
            "runtime": str(runtime_log_path),
        },
        "summary_path": str(summary_path),
        "summary": summary_payload,
        "raw_outputs": summary_payload,
    }
    write_json(work_dir / "hunyuan3d_wrapper_summary.json", payload)
    return payload


def _run() -> None:
    parser = argparse.ArgumentParser(description="Hunyuan3D wrapper helper.")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--input-image", type=str)
    args = parser.parse_args()

    load_project_env()
    contract = hunyuan3d_contract()
    if args.debug and args.input_image:
        result = run_hunyuan3d(
            input_image=Path(args.input_image),
            work_dir=Path(".runtime/hunyuan3d_debug"),
            output_dir=Path(".runtime/hunyuan3d_debug_output"),
            object_name="debug_hunyuan3d",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(json.dumps(contract, indent=2, ensure_ascii=False))
    if not contract.get("available", False):
        raise SystemExit(1)


if __name__ == "__main__":
    _run()
