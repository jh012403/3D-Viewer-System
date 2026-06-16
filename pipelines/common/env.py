from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None


def _ensure_pipeline_cache_env(env: dict[str, str] | os._Environ[str]) -> dict[str, str]:
    """Ensure numba/pymatting-friendly cache variables are available.

    These directories are intentionally writable temp paths to avoid
    "no locator available" failures in constrained runtime environments.
    """
    env = dict(env)
    cache_root = Path(
        env.get("AI3D_RUNTIME_CACHE_DIR")
        or env.get("AI3D_RUNTIME_CACHE_ROOT")
        or "/tmp/ai3d_cache"
    ).expanduser()
    hf_home = Path(
        env.get("HF_HOME")
        or (Path.home() / ".cache" / "huggingface")
    ).expanduser()
    hf_hub_cache = Path(
        env.get("HUGGINGFACE_HUB_CACHE")
        or (hf_home / "hub")
    ).expanduser()
    numba_cache = Path(env.get("NUMBA_CACHE_DIR") or (cache_root / "numba")).expanduser()
    xdg_cache = Path(env.get("XDG_CACHE_HOME") or (cache_root / "xdg")).expanduser()

    env["AI3D_RUNTIME_CACHE_ROOT"] = str(cache_root)
    env["HF_HOME"] = str(hf_home)
    env["HUGGINGFACE_HUB_CACHE"] = str(hf_hub_cache)
    env["NUMBA_CACHE_DIR"] = str(numba_cache)
    env["XDG_CACHE_HOME"] = str(xdg_cache)
    env.setdefault("HOME", str(Path.home()))

    for path in (cache_root, hf_home, hf_hub_cache, numba_cache, xdg_cache):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Non-fatal here; callers can inspect logs if cache creation fails.
            pass
    return env


def build_runtime_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return a copy of environment values with image-frontend cache defaults."""
    return _ensure_pipeline_cache_env(dict(base_env or os.environ))


@lru_cache
def load_project_env() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    if load_dotenv is not None:
        load_dotenv(env_path, override=True)
    elif env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _ensure_pipeline_cache_env(os.environ)
    return project_root
