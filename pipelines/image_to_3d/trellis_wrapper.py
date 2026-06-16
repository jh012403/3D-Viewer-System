from __future__ import annotations

import argparse
import json
import os
import random
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipelines.common.env import build_runtime_env, load_project_env
from pipelines.common.io import ensure_dir, write_json


MAX_SEED = 2_147_483_647


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _repo_dir() -> Path:
    configured = os.getenv("TRELLIS_REPO_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (_project_root() / ".runtime" / "TRELLIS.2").resolve()


def _helper_script() -> Path:
    return (_project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "trellis_generate.py").resolve()


def _command_parts() -> list[str]:
    command = os.getenv("TRELLIS_CMD", "conda run -n trellis2 python").strip()
    return shlex.split(command)


def _strict_official_mode() -> bool:
    return _bool_env("TRELLIS_STRICT_OFFICIAL_MODE", True)


def _require_clean_repo() -> bool:
    return _bool_env("TRELLIS_REQUIRE_CLEAN_REPO", True)


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


def _effective_seed(contract: dict[str, Any]) -> int:
    seed = int(contract.get("seed") or 0)
    if bool(contract.get("randomize_seed")):
        return random.randrange(0, MAX_SEED)
    return max(0, min(MAX_SEED, seed))


def _command_available(parts: list[str]) -> bool:
    if not parts:
        return False
    executable = parts[0]
    if "/" in executable or executable.startswith("."):
        return Path(executable).expanduser().exists()
    return shutil.which(executable) is not None


def _runtime_env(repo_dir: Path) -> dict[str, str]:
    env = build_runtime_env(os.environ.copy())
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    repo_pythonpath = str(repo_dir)
    if existing_pythonpath:
        env["PYTHONPATH"] = f"{repo_pythonpath}:{existing_pythonpath}"
    else:
        env["PYTHONPATH"] = repo_pythonpath
    return env


def _runtime_backend_contract() -> dict[str, str]:
    attention_backend = _string_env("ATTN_BACKEND", "flash_attn")
    sparse_attention_backend = _string_env(
        "SPARSE_ATTN_BACKEND",
        os.getenv("ATTN_BACKEND", "").strip() or "flash_attn",
    )
    sparse_conv_backend = _string_env("SPARSE_CONV_BACKEND", "flex_gemm")
    return {
        "attention_backend": attention_backend,
        "sparse_attention_backend": sparse_attention_backend,
        "sparse_conv_backend": sparse_conv_backend,
    }


def _sanitize_probe_text(text: str) -> str:
    return " ".join(text.strip().split())[:240]


def _required_runtime_modules() -> list[str]:
    backends = _runtime_backend_contract()
    required = ["torch", "trellis2", "PIL", "o_voxel", "cumesh", "nvdiffrast"]
    sparse_conv_backend = backends["sparse_conv_backend"]
    sparse_attention_backend = backends["sparse_attention_backend"]
    attention_backend = backends["attention_backend"]

    if sparse_conv_backend == "flex_gemm":
        required.append("flex_gemm")
    elif sparse_conv_backend == "spconv":
        required.append("spconv")

    if sparse_attention_backend in {"flash_attn", "flash_attn_3"} or attention_backend in {"flash_attn", "flash_attn_3"}:
        required.append("flash_attn")
    elif sparse_attention_backend == "xformers" or attention_backend == "xformers":
        required.append("xformers")

    ordered: list[str] = []
    for module_name in required:
        if module_name not in ordered:
            ordered.append(module_name)
    return ordered


def _expected_runtime_versions() -> dict[str, str]:
    return {
        "torch": "2.6.0+cu124",
        "torchvision": "0.21.0+cu124",
        "transformers": "4.57.3",
        "timm": "1.0.22",
        "trimesh": "4.10.1",
        "imageio": "2.37.2",
        "flash_attn": "2.7.3",
    }


def _repo_clean_probe(repo_dir: Path) -> list[str]:
    if not _require_clean_repo():
        return []
    probe = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        stderr = _sanitize_probe_text(probe.stderr or "git_status_failed")
        return [f"repo_status_probe_failed:{stderr}"]
    dirty = [line.strip() for line in (probe.stdout or "").splitlines() if line.strip()]
    if dirty:
        sample = "; ".join(dirty[:5])
        return [f"repo_dirty:{sample}"]
    return []


def _python_runtime_probe(parts: list[str], repo_dir: Path) -> list[str]:
    if not parts:
        return ["empty_command"]

    required_modules = _required_runtime_modules()
    expected_versions = _expected_runtime_versions()
    script = f"""
import importlib
import json

mods = {required_modules!r}
expected_versions = {expected_versions!r}
issues = []
for mod in mods:
    try:
        importlib.import_module(mod)
    except Exception as exc:
        issues.append(f"runtime_module_unavailable:{{mod}}:{{type(exc).__name__}}:{{exc}}")

if not issues:
    version_targets = [
        ("torch", "torch"),
        ("torchvision", "torchvision"),
        ("transformers", "transformers"),
        ("timm", "timm"),
        ("trimesh", "trimesh"),
        ("imageio", "imageio"),
        ("flash_attn", "flash_attn"),
    ]
    for label, mod_name in version_targets:
        try:
            module = importlib.import_module(mod_name)
            actual = getattr(module, "__version__", "")
            expected = expected_versions.get(label, "")
            if expected and actual != expected:
                issues.append(f"runtime_version_mismatch:{{label}}:{{expected}}:{{actual}}")
        except Exception as exc:
            issues.append(f"runtime_version_probe_failed:{{label}}:{{type(exc).__name__}}:{{exc}}")

if not issues:
    try:
        from transformers import DINOv3ViTModel
        model = DINOv3ViTModel.from_pretrained("facebook/dinov3-vitb16-pretrain-lvd1689m")
        if not hasattr(model, "layer"):
            issues.append("dinov3_layout_mismatch:missing_model_layer")
    except Exception as exc:
        issues.append(f"dinov3_probe_failed:{{type(exc).__name__}}:{{exc}}")
print(json.dumps(issues))
"""
    probe = subprocess.run(
        [
            *parts,
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        cwd=repo_dir,
        env=_runtime_env(repo_dir),
    )
    if probe.returncode != 0:
        stderr = _sanitize_probe_text((probe.stderr or "").strip() or "probe_failed")
        return [f"python_probe_failed:{stderr}"]
    try:
        issues = json.loads((probe.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        stdout = _sanitize_probe_text(probe.stdout or "invalid_python_probe_output")
        return [f"invalid_python_probe_output:{stdout}"]
    return [_sanitize_probe_text(str(item)) for item in issues if str(item).strip()]


def _hf_access_probe(parts: list[str], repo_dir: Path, model_path: str) -> list[str]:
    if not parts:
        return ["empty_command"]

    checks = [
        (model_path, "pipeline.json"),
        ("facebook/dinov3-vitl16-pretrain-lvd1689m", "config.json"),
        ("briaai/RMBG-2.0", "config.json"),
    ]
    script = f"""
import json
from huggingface_hub import hf_hub_download

checks = {checks!r}
issues = []
for repo_id, filename in checks:
    try:
        hf_hub_download(repo_id, filename)
    except Exception as exc:
        issues.append(f"hf_asset_unavailable:{{repo_id}}:{{filename}}:{{type(exc).__name__}}:{{exc}}")
print(json.dumps(issues))
"""
    probe = subprocess.run(
        [
            *parts,
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        cwd=repo_dir,
        env=_runtime_env(repo_dir),
    )
    if probe.returncode != 0:
        stderr = _sanitize_probe_text((probe.stderr or "").strip() or "hf_probe_failed")
        return [f"hf_probe_failed:{stderr}"]
    try:
        issues = json.loads((probe.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        stdout = _sanitize_probe_text(probe.stdout or "invalid_hf_probe_output")
        return [f"invalid_hf_probe_output:{stdout}"]
    return [_sanitize_probe_text(str(item)) for item in issues if str(item).strip()]


def _strict_official_issues(parts: list[str], repo_dir: Path, model_path: str) -> list[str]:
    issues: list[str] = []
    issues.extend(_repo_clean_probe(repo_dir))
    issues.extend(_python_runtime_probe(parts, repo_dir))
    issues.extend(_hf_access_probe(parts, repo_dir, model_path))
    return issues


def trellis_contract() -> dict[str, Any]:
    repo_dir = _repo_dir()
    helper = _helper_script()
    command = _command_parts()
    model_path = _string_env("TRELLIS_MODEL_PATH", "microsoft/TRELLIS.2-4B")
    issues: list[str] = []
    if not repo_dir.exists():
        issues.append(f"repo_missing:{repo_dir}")
    if not helper.exists():
        issues.append(f"helper_missing:{helper}")
    if not _command_available(command):
        issues.append(f"command_missing:{command[0] if command else 'empty'}")
    if not issues and _strict_official_mode():
        issues.extend(_repo_clean_probe(repo_dir))
        issues.extend(_python_runtime_probe(command, repo_dir))
        issues.extend(_hf_access_probe(command, repo_dir, model_path))
    elif not issues:
        issues.extend(_python_runtime_probe(command, repo_dir))

    return {
        "head": "trellis",
        "available": not issues,
        "repo_dir": str(repo_dir),
        "helper_script": str(helper),
        "command": command,
        "model_path": model_path,
        "device": _string_env("TRELLIS_DEVICE", "cuda"),
        "resolution": _string_env("TRELLIS_RESOLUTION", "1024"),
        "seed": _int_env("TRELLIS_SEED", 0),
        "randomize_seed": _bool_env("TRELLIS_RANDOMIZE_SEED", True),
        "mesh_simplify_faces": _int_env("TRELLIS_MESH_SIMPLIFY_FACES", 16777216),
        "low_vram_mode": _bool_env("TRELLIS_LOW_VRAM_MODE", True),
        "oom_retry_enabled": _bool_env("TRELLIS_OOM_RETRY_ENABLED", True),
        "oom_retry_resolution": _string_env("TRELLIS_OOM_RETRY_RESOLUTION", "512"),
        "strict_official_mode": _strict_official_mode(),
        "require_clean_repo": _require_clean_repo(),
        "official_backends": _runtime_backend_contract(),
        "expected_runtime_versions": _expected_runtime_versions(),
        "required_runtime_modules": _required_runtime_modules(),
        "issues": issues,
        "summary": "TRELLIS.2 strict official runtime wrapper. No internal fallbacks or runtime patches are allowed.",
    }


def _trellis_oom_retry_requested(completed: subprocess.CompletedProcess[str], summary_path: Path) -> bool:
    text_parts = [completed.stdout or "", completed.stderr or ""]
    if summary_path.exists():
        try:
            text_parts.append(summary_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    text = "\n".join(text_parts).lower()
    return (
        "out of memory" in text
        or "cuda error" in text and "error code: 2" in text
        or "cuda out of memory" in text
    )


def _build_trellis_command(
    *,
    contract: dict[str, Any],
    helper_script: Path,
    input_image: Path,
    output_mesh_path: Path,
    summary_path: Path,
    runtime_log_path: Path,
    resolution: str,
) -> list[str]:
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
        "--device",
        str(contract["device"]),
        "--resolution",
        str(resolution),
        "--seed",
        str(contract["effective_seed"]),
        "--mesh-simplify-faces",
        str(contract["mesh_simplify_faces"]),
    ]
    if bool(contract["low_vram_mode"]):
        command.append("--low-vram")

    extra_args = os.getenv("TRELLIS_EXTRA_ARGS", "").strip()
    if extra_args:
        command.extend(shlex.split(extra_args))
    return command


def _write_attempt_log(wrapper_log_path: Path, attempts: list[dict[str, Any]]) -> None:
    sections: list[str] = []
    for attempt in attempts:
        sections.extend(
            [
                f"ATTEMPT {attempt['label']}",
                "COMMAND\n" + " ".join(shlex.quote(part) for part in attempt["command"]),
                "STDOUT\n" + (str(attempt.get("stdout") or "").strip() or "(empty)"),
                "STDERR\n" + (str(attempt.get("stderr") or "").strip() or "(empty)"),
            ]
        )
    wrapper_log_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def run_trellis(
    *,
    input_image: Path,
    work_dir: Path,
    output_dir: Path,
    object_name: str,
) -> dict[str, Any]:
    load_project_env()
    contract = trellis_contract()
    if not contract["available"]:
        issues = ", ".join(contract["issues"])
        raise RuntimeError(f"TRELLIS runtime not available: {issues}")
    contract = {
        **contract,
        "effective_seed": _effective_seed(contract),
        "seed_policy": "randomized_official_default"
        if bool(contract.get("randomize_seed"))
        else "fixed_user_seed",
    }

    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    output_dir = ensure_dir(output_dir.expanduser().resolve())
    repo_dir = Path(str(contract["repo_dir"]))
    helper_script = Path(str(contract["helper_script"]))
    output_mesh_path = work_dir / "trellis_raw.glb"
    summary_path = work_dir / "trellis_summary.json"
    runtime_log_path = work_dir / "trellis_runtime.log"
    wrapper_log_path = work_dir / "trellis_wrapper.log"

    attempts: list[dict[str, Any]] = []
    attempt_specs = [
        {
            "label": f"primary_{contract['resolution']}",
            "resolution": str(contract["resolution"]),
            "output_mesh_path": output_mesh_path,
            "summary_path": summary_path,
            "runtime_log_path": runtime_log_path,
        }
    ]
    retry_resolution = str(contract.get("oom_retry_resolution") or "").strip()
    if (
        bool(contract.get("oom_retry_enabled"))
        and retry_resolution
        and retry_resolution != str(contract["resolution"])
    ):
        attempt_specs.append(
            {
                "label": f"oom_retry_{retry_resolution}",
                "resolution": retry_resolution,
                "output_mesh_path": work_dir / f"trellis_raw_retry_{retry_resolution}.glb",
                "summary_path": work_dir / f"trellis_summary_retry_{retry_resolution}.json",
                "runtime_log_path": work_dir / f"trellis_runtime_retry_{retry_resolution}.log",
            }
        )

    completed: subprocess.CompletedProcess[str] | None = None
    final_spec = attempt_specs[0]
    for index, spec in enumerate(attempt_specs):
        command = _build_trellis_command(
            contract=contract,
            helper_script=helper_script,
            input_image=input_image,
            output_mesh_path=Path(spec["output_mesh_path"]),
            summary_path=Path(spec["summary_path"]),
            runtime_log_path=Path(spec["runtime_log_path"]),
            resolution=str(spec["resolution"]),
        )
        completed = subprocess.run(
            command,
            cwd=repo_dir,
            capture_output=True,
            text=True,
            env=_runtime_env(repo_dir),
        )
        attempt = {
            "label": spec["label"],
            "resolution": spec["resolution"],
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "summary_path": str(spec["summary_path"]),
            "runtime_log_path": str(spec["runtime_log_path"]),
            "output_mesh_path": str(spec["output_mesh_path"]),
        }
        attempts.append(attempt)
        _write_attempt_log(wrapper_log_path, attempts)
        final_spec = spec
        if completed.returncode == 0:
            break
        if index == 0 and len(attempt_specs) > 1 and _trellis_oom_retry_requested(completed, Path(spec["summary_path"])):
            continue
        break

    assert completed is not None
    if completed.returncode != 0:
        raise RuntimeError(f"TRELLIS reconstruction failed with exit code {completed.returncode}. See {wrapper_log_path}.")

    output_mesh_path = Path(final_spec["output_mesh_path"])
    summary_path = Path(final_spec["summary_path"])
    runtime_log_path = Path(final_spec["runtime_log_path"])
    summary_payload: dict[str, Any] = {}
    if summary_path.exists():
        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary_payload = {"status": "invalid_summary_json"}

    mesh_path = Path(str(summary_payload.get("output_mesh") or output_mesh_path)).expanduser().resolve()
    if not mesh_path.exists():
        raise RuntimeError(f"TRELLIS finished without exporting a mesh under {work_dir}.")

    payload = {
        "head": "trellis",
        "input_image": str(input_image),
        "mesh_path": str(mesh_path),
        "mesh_backend": "trellis",
        "resolved_backend": "trellis",
        "object_name": object_name,
        "log_paths": {
            "wrapper": str(wrapper_log_path),
            "runtime": str(runtime_log_path),
        },
        "summary_path": str(summary_path),
        "summary": summary_payload,
        "raw_outputs": summary_payload,
        "attempts": [
            {
                "label": attempt["label"],
                "resolution": attempt["resolution"],
                "returncode": attempt["returncode"],
                "summary_path": attempt["summary_path"],
                "runtime_log_path": attempt["runtime_log_path"],
                "output_mesh_path": attempt["output_mesh_path"],
            }
            for attempt in attempts
        ],
        "oom_retry_used": len(attempts) > 1 and attempts[-1]["returncode"] == 0,
        "seed": contract["seed"],
        "randomize_seed": contract["randomize_seed"],
        "effective_seed": contract["effective_seed"],
        "seed_policy": contract["seed_policy"],
    }
    write_json(work_dir / "trellis_wrapper_summary.json", payload)
    return payload


def _run() -> None:
    parser = argparse.ArgumentParser(description="TRELLIS wrapper helper.")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--input-image", type=str)
    args = parser.parse_args()

    load_project_env()
    contract = trellis_contract()
    if args.debug and args.input_image:
        result = run_trellis(
            input_image=Path(args.input_image),
            work_dir=Path(".runtime/trellis_debug"),
            output_dir=Path(".runtime/trellis_debug_output"),
            object_name="debug_trellis",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(json.dumps(contract, indent=2, ensure_ascii=False))
    if not contract.get("available", False):
        raise SystemExit(1)


if __name__ == "__main__":
    _run()
