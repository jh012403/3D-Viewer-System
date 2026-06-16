#!/usr/bin/env python
from __future__ import annotations

import json
import argparse
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from pipelines.common.env import build_runtime_env, load_project_env


def _env_snapshot() -> dict[str, str | None]:
    snapshot = {
        "NUMBA_CACHE_DIR": os.getenv("NUMBA_CACHE_DIR"),
        "XDG_CACHE_HOME": os.getenv("XDG_CACHE_HOME"),
        "HOME": os.getenv("HOME"),
        "AI3D_RUNTIME_CACHE_ROOT": os.getenv("AI3D_RUNTIME_CACHE_ROOT"),
    }
    numba_cache_dir = Path(snapshot["NUMBA_CACHE_DIR"] or "")
    xdg_cache_dir = Path(snapshot["XDG_CACHE_HOME"] or "")
    snapshot["numba_cache_enabled"] = str(numba_cache_dir.exists())
    snapshot["xdg_cache_enabled"] = str(xdg_cache_dir.exists())
    return snapshot


def _safe_copy(path: Path, target: Path) -> None:
    """Copy source artifact path to an optional canonical target path."""
    if not path.exists():
        return
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(path)


def _build_input_image(sample_image: str | None) -> Path:
    if sample_image:
        image_path = Path(sample_image).expanduser().resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")
        return image_path

    work_dir = Path.cwd() / "storage" / "temp" / "debug_rembg"
    work_dir.mkdir(parents=True, exist_ok=True)
    image_path = work_dir / "debug_input.png"
    if not image_path.exists():
        image = Image.new("RGB", (768, 768), color=(255, 255, 255))
        for x in range(200, 560):
            for y in range(220, 540):
                image.putpixel((x, y), (220, 120, 90))
        image.save(image_path)
    return image_path


def _report(message: str, payload: dict[str, Any] | None = None) -> None:
    print(message)
    if payload:
        for key, value in payload.items():
            print(f"  {key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RemBG + pymatting + numba runtime reproduction helper.")
    parser.add_argument("--input-image", default="", help="Optional image to run background removal on.")
    args = parser.parse_args()

    load_project_env()
    runtime_env = build_runtime_env(dict(os.environ))
    os.environ.update(runtime_env)

    log_dir = Path.cwd() / "storage" / "temp" / "debug_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"rembg_runtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    output_dir = Path.cwd() / "storage" / "temp" / "debug_rembg_out"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "status": "failed",
        "error_type": None,
        "error": None,
        "debug_output_dir": str(output_dir),
    }

    try:
        _report("env", _env_snapshot())
        _report("input", {"sample_image": args.input_image.strip() or "synthetic"})

        _report("import check", {"rembg": "pending", "pymatting": "pending", "numba": "pending"})
        try:
            import rembg  # type: ignore
            import numba  # type: ignore
            import pymatting  # type: ignore
            from PIL import Image  # type: ignore

            _report("import check", {
                "rembg": f"OK ({rembg.__name__})",
                "pymatting": f"OK ({pymatting.__name__})",
                "numba": f"OK ({numba.__name__})",
                "PIL": f"OK ({Image.__name__})",
            })
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"import check failed: {exc}") from exc

        sample_image = _build_input_image(args.input_image.strip() or None)
        output_foreground = output_dir / "debug_foreground.png"
        output_mask = output_dir / "debug_mask.png"

        # Import lazily to avoid import-time noise from optional runtime failures.
        from pipelines.image_to_3d.foreground_model_wrapper import extract_with_rembg

        _report("rembg execution", {"input_image": str(sample_image), "work_dir": str(output_dir)})
        result = extract_with_rembg(sample_image, output_dir)

        if result.get("foreground_path"):
            result_foreground = Path(str(result["foreground_path"]))
            if result_foreground.exists():
                _safe_copy(result_foreground, output_foreground)
        if result.get("mask_path"):
            result_mask = Path(str(result["mask_path"]))
            if result_mask.exists():
                _safe_copy(result_mask, output_mask)

        _report("rembg result", {
            "status": "success",
            "foreground_path": result.get("foreground_path"),
            "mask_path": result.get("mask_path"),
            "foreground_extracted": result.get("foreground_extracted"),
        })
        summary = {
            "status": "success",
            "foreground_path": str(result.get("foreground_path")),
            "mask_path": str(result.get("mask_path")),
            "foreground_extracted": bool(result.get("foreground_extracted")),
            "foreground_exists": output_foreground.exists(),
            "mask_exists": output_mask.exists(),
            "debug_output_dir": str(output_dir),
        }
        log_path.write_text(json.dumps({"status": "success", **summary}, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log_path.write_text(
            "\n".join([
                "rembg execution failed",
                f"{type(exc).__name__}: {exc}",
                "---",
                traceback.format_exc().strip(),
            ])
            + "\n",
            encoding="utf-8",
        )
        summary = {
            "status": "failed",
            "error": str(exc),
            "error_type": type(exc).__name__,
            "debug_output_dir": str(output_dir),
        }
        raise
    finally:
        _report("summary", summary)
        print(f"runtime log: {log_path}")


if __name__ == "__main__":
    main()
