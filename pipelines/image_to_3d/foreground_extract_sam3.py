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
    command = os.getenv("SAM3_CMD", "").strip()
    return shlex.split(command) if command else []


def _repo_dir() -> Path | None:
    raw = os.getenv("SAM3_REPO_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    candidate = (_project_root() / ".runtime" / "sam3").resolve()
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


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _prompt_aliases(prompt: str) -> list[str]:
    if not _bool_env("SAM3_TEXT_PROMPT_EXPANSION", True):
        return []
    cleaned = " ".join(prompt.lower().replace("-", " ").replace("_", " ").split())
    aliases: list[str] = []
    if any(token in cleaned for token in ("dinosaur", "dino", "t rex", "trex", "tyrannosaurus", "triceratops")):
        aliases.extend(
            [
                "dinosaur fossil",
                "dinosaur bones",
                "dinosaur skeleton",
                "dinosaur skull",
                "fossil skull",
                "fossil skeleton",
                "museum fossil",
                "animal skull fossil",
                "horned dinosaur skull",
                "horned fossil skull",
                "ceratopsian fossil skull",
                "triceratops skull",
                "triceratops fossil",
                "triceratops horridus",
                "ceratopsian skull",
            ]
        )
    if "skull" in cleaned and "fossil skull" not in aliases:
        aliases.append("fossil skull")
    if "skeleton" in cleaned and "fossil skeleton" not in aliases:
        aliases.append("fossil skeleton")

    ordered: list[str] = []
    seen = {cleaned}
    for alias in aliases:
        key = " ".join(alias.lower().split())
        if key and key not in seen:
            ordered.append(alias)
            seen.add(key)
    return ordered[: int(os.getenv("SAM3_TEXT_PROMPT_ALIAS_LIMIT", "12").strip() or "12")]


def sam3_foreground_contract() -> dict[str, Any]:
    command = _command_parts()
    repo_dir = _repo_dir()
    helper_script = _project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "sam3_extract.py"
    issues: list[str] = []
    if not command:
        issues.append("command_missing")
    elif not _command_available(command):
        issues.append(f"command_not_found:{command[0]}")
    if repo_dir is None:
        issues.append("repo_missing")
    elif not repo_dir.exists():
        issues.append(f"repo_not_found:{repo_dir}")
    if not helper_script.exists():
        issues.append(f"helper_missing:{helper_script}")

    return {
        "provider": "sam3",
        "available": not issues,
        "command": command,
        "repo_dir": str(repo_dir) if repo_dir else None,
        "model_id": os.getenv("SAM3_MODEL_ID", "facebook/sam3").strip() or "facebook/sam3",
        "device": os.getenv("SAM3_DEVICE", "cuda").strip() or "cuda",
        "issues": issues,
        "summary": "SAM3 text-prompt foreground extraction via official SAM3 image processor.",
    }


def extract_with_sam3(
    input_image: Path,
    work_dir: Path,
    *,
    text_prompt: str,
    dump_candidates_dir: Path | None = None,
    max_candidates: int = 1,
    confidence_threshold: float | None = None,
    merge_mode: str | None = None,
    reset_candidates_dir: bool = True,
) -> dict[str, Any]:
    load_project_env()
    contract = sam3_foreground_contract()
    if not contract["available"]:
        raise RuntimeError(f"SAM3 runtime not available: {', '.join(contract['issues'])}")

    prompt = text_prompt.strip()
    if not prompt:
        raise RuntimeError("SAM3 text prompt is empty.")

    input_image = input_image.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())
    helper_script = _project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "sam3_extract.py"

    threshold = (
        float(confidence_threshold)
        if confidence_threshold is not None
        else float(os.getenv("SAM3_CONFIDENCE_THRESHOLD", "0.5").strip() or "0.5")
    )
    resolved_merge_mode = (merge_mode or os.getenv("SAM3_MERGE_MODE", "best")).strip().lower() or "best"

    command = [
        *contract["command"],
        str(helper_script),
        "--input-image",
        str(input_image),
        "--output-dir",
        str(work_dir),
        "--sam3-repo-dir",
        str(contract["repo_dir"]),
        "--model-id",
        str(contract["model_id"]),
        "--device",
        str(contract["device"]),
        "--text-prompt",
        prompt,
        "--confidence-threshold",
        str(threshold),
        "--merge-mode",
        resolved_merge_mode,
    ]
    fallback_threshold = float(os.getenv("SAM3_FALLBACK_CONFIDENCE_THRESHOLD", "0.25").strip() or "0.25")
    if fallback_threshold < threshold:
        command.extend(["--fallback-confidence-threshold", str(fallback_threshold)])
    for alias in _prompt_aliases(prompt):
        command.extend(["--text-prompt-alias", alias])
    if dump_candidates_dir is not None:
        if reset_candidates_dir:
            shutil.rmtree(dump_candidates_dir.expanduser().resolve(), ignore_errors=True)
        command.extend(["--dump-candidates-dir", str(dump_candidates_dir.expanduser().resolve())])
        command.extend(["--max-candidates", str(max(1, int(max_candidates)))])

    env = os.environ.copy()
    project_root = str(_project_root())
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{project_root}:{current_pythonpath}" if current_pythonpath else project_root
    pythonpath_overlay = os.getenv("SAM3_PYTHONPATH", "").strip()
    if pythonpath_overlay:
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{pythonpath_overlay}:{current_pythonpath}" if current_pythonpath else pythonpath_overlay

    token = os.getenv("SAM3_HF_TOKEN", "").strip()
    if token:
        env.setdefault("HF_TOKEN", token)
        env.setdefault("HUGGING_FACE_HUB_TOKEN", token)
    hf_home = os.getenv("SAM3_HF_HOME", "").strip() or os.getenv("HF_HOME", "").strip()
    if not hf_home:
        # Backend dev scripts set XDG_CACHE_HOME to a temp cache, which makes
        # huggingface_hub miss the user's normal `hf auth login` token unless
        # HF_HOME is pinned back to the account cache.
        hf_home = str(Path.home() / ".cache" / "huggingface")
    env.setdefault("HF_HOME", hf_home)
    env.setdefault("HUGGINGFACE_HUB_CACHE", str(Path(hf_home).expanduser() / "hub"))

    completed = subprocess.run(
        command,
        cwd=_project_root(),
        capture_output=True,
        text=True,
        env=env,
    )

    log_path = work_dir / "sam3_foreground.log"
    log_path.write_text(
        _format_log(command, completed.stdout, completed.stderr, title="ATTEMPT sam3_text") + "\n",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"SAM3 foreground extraction failed with exit code {completed.returncode}. See {log_path}.")

    summary_path = work_dir / "sam3_summary.json"
    if not summary_path.exists():
        raise RuntimeError(f"SAM3 foreground extraction finished without writing {summary_path}.")

    result = json.loads(summary_path.read_text(encoding="utf-8"))
    result.setdefault("provider", "sam3")
    result["log_path"] = str(log_path)
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
