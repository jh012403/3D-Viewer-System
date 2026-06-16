from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import trimesh
import trimesh.voxel.ops as voxel_ops
from scipy import ndimage

from pipelines.common.io import ensure_dir, write_json


@dataclass
class MeshOptimizeConfig:
    resolution: int = 200
    close_iterations: int = 2
    open_iterations: int = 1
    humphrey_alpha: float = 0.08
    humphrey_beta: float = 0.4
    humphrey_iterations: int = 4
    min_component_face_ratio: float = 0.03


def _sanitize(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    cleaned = mesh.copy()
    try:
        if hasattr(cleaned, "nondegenerate_faces"):
            mask = cleaned.nondegenerate_faces()
            if len(mask) == len(cleaned.faces):
                cleaned.update_faces(mask)
    except Exception:
        pass
    try:
        if hasattr(cleaned, "unique_faces"):
            mask = cleaned.unique_faces()
            if len(mask) == len(cleaned.faces):
                cleaned.update_faces(mask)
    except Exception:
        pass

    try:
        cleaned.remove_unreferenced_vertices()
    except Exception:
        pass
    return cleaned


def _load_as_mesh(mesh_path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(mesh_path, force="scene")
    if isinstance(loaded, trimesh.Trimesh):
        return _sanitize(loaded)
    if isinstance(loaded, trimesh.Scene):
        geometry = [g.copy() for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not geometry:
            raise RuntimeError(f"No trimesh geometry found in scene: {mesh_path}")
        merged = trimesh.util.concatenate(geometry)
        return _sanitize(merged)
    raise RuntimeError(f"Unsupported mesh payload: {type(loaded).__name__}")


def _filter_components(mesh: trimesh.Trimesh, min_face_ratio: float) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    parts = [p for p in mesh.split(only_watertight=False) if len(p.faces) > 0 and len(p.vertices) > 0]
    if not parts:
        return mesh, {
            "component_count_before": 0,
            "component_count_after": 0,
            "kept_component_faces": [],
        }

    face_counts = [len(p.faces) for p in parts]
    max_faces = max(face_counts)
    threshold = max(16, int(max_faces * min_face_ratio))
    kept = [p for p in parts if len(p.faces) >= threshold]
    if not kept:
        kept = [parts[int(np.argmax(face_counts))]]

    combined = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]
    return _sanitize(combined), {
        "component_count_before": len(parts),
        "component_count_after": len(kept),
        "kept_component_faces": [len(p.faces) for p in kept],
        "component_threshold_faces": threshold,
    }


def _voxel_refine(mesh: trimesh.Trimesh, cfg: MeshOptimizeConfig) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    extents = np.asarray(mesh.extents, dtype=np.float64)
    max_extent = float(np.max(extents)) if extents.size else 0.0
    if not np.isfinite(max_extent) or max_extent <= 1e-8:
        raise RuntimeError("Invalid mesh extent for voxel refine.")

    resolution = max(int(cfg.resolution), 64)
    pitch = max_extent / float(resolution)
    voxel = mesh.voxelized(pitch=pitch)
    matrix = np.asarray(voxel.matrix, dtype=bool)
    if matrix.size == 0 or int(matrix.sum()) == 0:
        raise RuntimeError("Voxelization produced an empty occupancy grid.")

    closed = ndimage.binary_closing(matrix, iterations=max(cfg.close_iterations, 0))
    opened = ndimage.binary_opening(closed, iterations=max(cfg.open_iterations, 0))
    filled = ndimage.binary_fill_holes(opened)
    if int(filled.sum()) == 0:
        raise RuntimeError("Morphology removed all occupied voxels.")

    refined = voxel_ops.matrix_to_marching_cubes(filled, pitch=float(pitch))
    refined.apply_translation(voxel.translation)
    refined = _sanitize(refined)

    return refined, {
        "voxel_resolution": resolution,
        "voxel_pitch": float(pitch),
        "voxel_shape": list(map(int, matrix.shape)),
        "occupied_before": int(matrix.sum()),
        "occupied_after": int(filled.sum()),
        "voxel_translation": [float(x) for x in np.asarray(voxel.translation).tolist()],
    }


def _match_scale_and_center(source: trimesh.Trimesh, target: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    src = source.copy()
    out = target.copy()
    src_center = np.asarray(src.bounding_box.centroid, dtype=np.float64)
    out_center = np.asarray(out.bounding_box.centroid, dtype=np.float64)
    src_extent = float(np.max(np.asarray(src.extents, dtype=np.float64)))
    out_extent = float(np.max(np.asarray(out.extents, dtype=np.float64)))
    scale = 1.0
    if np.isfinite(src_extent) and np.isfinite(out_extent) and out_extent > 1e-9:
        scale = src_extent / out_extent
        out.apply_scale(scale)
    out_center = np.asarray(out.bounding_box.centroid, dtype=np.float64)
    out.apply_translation(src_center - out_center)
    return out, {
        "scale_to_source": float(scale),
        "source_center": [float(v) for v in src_center.tolist()],
        "target_center_after": [float(v) for v in np.asarray(out.bounding_box.centroid, dtype=np.float64).tolist()],
    }


def optimize_mesh(
    input_mesh_path: Path,
    output_mesh_path: Path,
    work_dir: Path,
    config: MeshOptimizeConfig | None = None,
) -> dict[str, Any]:
    cfg = config or MeshOptimizeConfig()
    input_mesh_path = input_mesh_path.expanduser().resolve()
    output_mesh_path = output_mesh_path.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())

    source_mesh = _load_as_mesh(input_mesh_path)
    source_mesh = _sanitize(source_mesh)
    filtered_mesh, component_meta = _filter_components(source_mesh, cfg.min_component_face_ratio)
    voxel_mesh, voxel_meta = _voxel_refine(filtered_mesh, cfg)
    voxel_mesh = _sanitize(voxel_mesh)

    try:
        trimesh.smoothing.filter_humphrey(
            voxel_mesh,
            alpha=cfg.humphrey_alpha,
            beta=cfg.humphrey_beta,
            iterations=cfg.humphrey_iterations,
        )
        smoothing_applied = True
    except Exception:
        smoothing_applied = False
    voxel_mesh = _sanitize(voxel_mesh)

    refined_mesh, fit_meta = _match_scale_and_center(filtered_mesh, voxel_mesh)
    refined_mesh = _sanitize(refined_mesh)

    scene = trimesh.Scene(geometry={"optimized_mesh": refined_mesh})
    output_mesh_path.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output_mesh_path)

    report = {
        "status": "optimized",
        "input_mesh_path": str(input_mesh_path),
        "output_mesh_path": str(output_mesh_path),
        "source_vertices": int(len(source_mesh.vertices)),
        "source_faces": int(len(source_mesh.faces)),
        "optimized_vertices": int(len(refined_mesh.vertices)),
        "optimized_faces": int(len(refined_mesh.faces)),
        "component_filter": component_meta,
        "voxel_refine": voxel_meta,
        "fit_to_source": fit_meta,
        "smoothing_applied": smoothing_applied,
        "source_bbox_extents": [float(v) for v in np.asarray(source_mesh.extents, dtype=np.float64).tolist()],
        "optimized_bbox_extents": [float(v) for v in np.asarray(refined_mesh.extents, dtype=np.float64).tolist()],
    }
    write_json(work_dir / "mesh_optimize_report.json", report)
    return report

