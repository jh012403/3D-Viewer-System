from __future__ import annotations

from pathlib import Path

import trimesh


def obj_to_glb(obj_path: Path, glb_path: Path) -> Path:
    loaded = trimesh.load(obj_path, force="scene")
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    loaded.export(glb_path)
    return glb_path

