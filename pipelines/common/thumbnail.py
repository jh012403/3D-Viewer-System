from __future__ import annotations

from pathlib import Path

import trimesh


def generate_thumbnail(mesh_path: Path, out_path: Path, resolution: tuple[int, int] = (512, 512)) -> Path:
    scene = trimesh.load(mesh_path, force="scene")
    png = scene.save_image(resolution=resolution)
    if png is None:
        raise RuntimeError(f"trimesh could not render a thumbnail for {mesh_path}.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png)
    return out_path

