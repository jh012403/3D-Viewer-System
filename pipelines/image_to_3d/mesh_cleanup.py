from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh

from pipelines.common.io import ensure_dir, write_json
from pipelines.image_to_3d.semantic_metadata import category_policy


def _split_mesh_components(mesh: trimesh.Trimesh) -> list[trimesh.Trimesh]:
    try:
        pieces = mesh.split(only_watertight=False)
        return [piece for piece in pieces if len(piece.vertices) > 0 and len(piece.faces) > 0]
    except ImportError:
        faces = np.asarray(mesh.faces)
        if len(faces) == 0:
            return []

        vertex_to_faces: dict[int, list[int]] = {}
        for face_index, face in enumerate(faces):
            for vertex in face.tolist():
                vertex_to_faces.setdefault(int(vertex), []).append(face_index)

        visited = np.zeros(len(faces), dtype=bool)
        components: list[list[int]] = []
        for face_index in range(len(faces)):
            if visited[face_index]:
                continue
            queue = [face_index]
            visited[face_index] = True
            component: list[int] = []
            while queue:
                current = queue.pop()
                component.append(current)
                for vertex in faces[current].tolist():
                    for neighbor in vertex_to_faces.get(int(vertex), []):
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            queue.append(neighbor)
            components.append(component)

        return [
            mesh.submesh([np.array(component, dtype=np.int64)], append=True, repair=False)
            for component in components
        ]


def _split_components(scene: trimesh.Scene) -> list[trimesh.Trimesh]:
    components: list[trimesh.Trimesh] = []
    for geometry in scene.geometry.values():
        if not isinstance(geometry, trimesh.Trimesh):
            continue
        pieces = _split_mesh_components(geometry)
        if not pieces:
            pieces = [geometry]
        for piece in pieces:
            if len(piece.vertices) == 0 or len(piece.faces) == 0:
                continue
            components.append(piece.copy())
    return components


def _sanitize_component(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    sanitized = mesh.copy()
    try:
        if hasattr(sanitized, "nondegenerate_faces"):
            face_mask = sanitized.nondegenerate_faces()
            if len(face_mask) == len(sanitized.faces):
                sanitized.update_faces(face_mask)
        elif hasattr(sanitized, "remove_degenerate_faces"):
            sanitized.remove_degenerate_faces()
    except Exception:
        pass

    try:
        if hasattr(sanitized, "unique_faces"):
            unique_mask = sanitized.unique_faces()
            if len(unique_mask) == len(sanitized.faces):
                sanitized.update_faces(unique_mask)
    except Exception:
        pass

    sanitized.remove_unreferenced_vertices()
    return sanitized


def _apply_weak_smoothing(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, bool]:
    smoothed = mesh.copy()
    try:
        trimesh.smoothing.filter_humphrey(smoothed, alpha=0.05, beta=0.4, iterations=2)
    except Exception:
        return mesh, False
    return smoothed, True


def _scene_from_components(components: list[trimesh.Trimesh]) -> trimesh.Scene:
    geometry = {f"cleaned_mesh_{index:03d}": component for index, component in enumerate(components)}
    return trimesh.Scene(geometry=geometry)


def _dimension_value(extents: np.ndarray, target_dimension: str) -> float:
    if target_dimension == "length":
        return float(max(extents[0], extents[2]))
    if target_dimension == "width":
        return float(extents[0])
    if target_dimension == "depth":
        return float(extents[2])
    return float(extents[1])


def _normalize_scene_transform(scene: trimesh.Scene, category_id: str | None) -> dict[str, Any]:
    bounds = np.asarray(scene.bounds, dtype=np.float64)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all():
        return {
            "category_id": category_id or "unknown",
            "policy_status": "skipped_invalid_bounds",
            "scale_applied": 1.0,
            "ground_aligned": False,
            "pivot_policy": "bottom_center",
        }

    policy = category_policy(category_id)
    extents_before = bounds[1] - bounds[0]
    current_dimension = _dimension_value(extents_before, policy.target_dimension)
    scale_applied = 1.0
    if policy.target_size_m is not None and current_dimension > 0:
        scale_applied = float(policy.target_size_m / current_dimension)

    center_x = float((bounds[0][0] + bounds[1][0]) * 0.5)
    center_z = float((bounds[0][2] + bounds[1][2]) * 0.5)
    bottom_y = float(bounds[0][1])
    scene.apply_translation([-center_x, -bottom_y, -center_z])
    if scale_applied > 0 and np.isfinite(scale_applied):
        scene.apply_scale(scale_applied)

    bounds_after = np.asarray(scene.bounds, dtype=np.float64)
    extents_after = bounds_after[1] - bounds_after[0]
    return {
        "category_id": policy.category_id,
        "target_dimension": policy.target_dimension,
        "target_size_m": policy.target_size_m,
        "pivot_policy": policy.pivot_policy,
        "ground_aligned": policy.ground_alignment,
        "scale_applied": round(scale_applied, 6),
        "bbox_min_before": [round(float(value), 6) for value in bounds[0]],
        "bbox_max_before": [round(float(value), 6) for value in bounds[1]],
        "bbox_extents_before": [round(float(value), 6) for value in extents_before],
        "bbox_min_after": [round(float(value), 6) for value in bounds_after[0]],
        "bbox_max_after": [round(float(value), 6) for value in bounds_after[1]],
        "bbox_extents_after": [round(float(value), 6) for value in extents_after],
    }


def cleanup_mesh(
    raw_mesh_path: Path,
    cleaned_glb_path: Path,
    work_dir: Path,
    *,
    category_id: str | None = None,
) -> dict[str, Any]:
    raw_mesh_path = raw_mesh_path.expanduser().resolve()
    cleaned_glb_path = cleaned_glb_path.expanduser().resolve()
    work_dir = ensure_dir(work_dir.expanduser().resolve())

    scene = trimesh.load(raw_mesh_path, force="scene", process=False)
    if not isinstance(scene, trimesh.Scene):
        scene = scene.scene()

    if raw_mesh_path.suffix.lower() == ".glb":
        geometries = [
            geometry
            for geometry in scene.geometry.values()
            if isinstance(geometry, trimesh.Trimesh) and len(geometry.vertices) > 0 and len(geometry.faces) > 0
        ]
        if not geometries:
            raise RuntimeError(f"Mesh cleanup could not find any valid mesh geometry in {raw_mesh_path}.")

        total_vertices = sum(len(geometry.vertices) for geometry in geometries)
        total_faces = sum(len(geometry.faces) for geometry in geometries)
        largest = max(geometries, key=lambda geometry: (len(geometry.faces), float(geometry.area)))
        largest_vertices = len(largest.vertices)
        largest_area = max(float(largest.area), 1e-9)
        kept_names = []
        for name, geometry in scene.geometry.items():
            if not isinstance(geometry, trimesh.Trimesh) or len(geometry.faces) == 0:
                continue
            keep = (
                geometry is largest
                or (total_faces > 0 and len(geometry.faces) / total_faces >= 0.01)
                or float(geometry.area) / largest_area >= 0.01
            )
            if keep:
                kept_names.append(name)

        removed_small_components = max(len(geometries) - len(kept_names), 0)
        if removed_small_components > 0:
            kept_components = [scene.geometry[name].copy() for name in kept_names]
            cleaned_scene = _scene_from_components(kept_components)
        else:
            cleaned_scene = scene.copy()

        scale_normalization = _normalize_scene_transform(cleaned_scene, category_id)
        extents = scale_normalization.get("bbox_extents_after") or []
        cleaned_glb_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_scene.export(cleaned_glb_path)

        payload = {
            "largest_component_only": len(kept_names) == 1,
            "raw_component_count": len(geometries),
            "removed_small_components": removed_small_components,
            "largest_component_ratio": round(float(largest_vertices / total_vertices) if total_vertices else 1.0, 6),
            "largest_component_vertices": largest_vertices,
            "cleanup_status": "success_glb_scene_transform",
            "weak_smoothing_applied": False,
            "scale_applied": scale_normalization.get("scale_applied", 1.0),
            "bbox_extents": [round(float(value), 6) for value in extents],
            "slab_like_hint": bool(min(extents) / max(extents) < 0.08) if extents and max(extents) > 0 else False,
            "scale_normalization": scale_normalization,
            "cleaned_mesh_path": str(cleaned_glb_path),
            "debug_obj_path": None,
            "notes": [
                "GLB cleanup uses scene-geometry filtering to avoid high-memory component splitting on dense TRELLIS assets.",
            ],
        }
        write_json(work_dir / "mesh_cleanup_report.json", payload)
        return payload

    components = [_sanitize_component(component) for component in _split_components(scene)]
    components = [component for component in components if len(component.vertices) > 0 and len(component.faces) > 0]
    if not components:
        raise RuntimeError(f"Mesh cleanup could not find any valid mesh components in {raw_mesh_path}.")

    components.sort(key=lambda component: (len(component.faces), float(component.area)), reverse=True)
    largest = components[0].copy()
    total_vertices = sum(len(component.vertices) for component in components)
    total_faces = sum(len(component.faces) for component in components)
    largest_vertices = len(largest.vertices)
    min_face_ratio = 0.01 if raw_mesh_path.suffix.lower() == ".glb" else 0.05
    min_area_ratio = 0.01 if raw_mesh_path.suffix.lower() == ".glb" else 0.05
    largest_area = max(float(largest.area), 1e-9)
    kept_components = []
    for index, component in enumerate(components):
        keep = (
            index == 0
            or (total_faces > 0 and len(component.faces) / total_faces >= min_face_ratio)
            or float(component.area) / largest_area >= min_area_ratio
        )
        if keep:
            kept_components.append(component.copy())
    if not kept_components:
        kept_components = [largest]
    removed_small_components = max(len(components) - len(kept_components), 0)

    smoothing_applied = False
    if raw_mesh_path.suffix.lower() != ".glb":
        smoothed_mesh, smoothing_applied = _apply_weak_smoothing(kept_components[0])
        kept_components[0] = smoothed_mesh

    cleaned_scene = _scene_from_components(kept_components)
    scale_normalization = _normalize_scene_transform(cleaned_scene, category_id)
    extents = scale_normalization.get("bbox_extents_after") or []
    cleaned_glb_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_scene.export(cleaned_glb_path)

    debug_obj_path = work_dir / "cleaned_component.obj"
    kept_components[0].export(debug_obj_path)

    payload = {
        "largest_component_only": len(kept_components) == 1,
        "raw_component_count": len(components),
        "removed_small_components": removed_small_components,
        "largest_component_ratio": round(float(largest_vertices / total_vertices) if total_vertices else 1.0, 6),
        "largest_component_vertices": largest_vertices,
        "cleanup_status": "success",
        "weak_smoothing_applied": smoothing_applied,
        "scale_applied": scale_normalization.get("scale_applied", 1.0),
        "bbox_extents": [round(float(value), 6) for value in extents],
        "slab_like_hint": bool(min(extents) / max(extents) < 0.08) if extents and max(extents) > 0 else False,
        "scale_normalization": scale_normalization,
        "cleaned_mesh_path": str(cleaned_glb_path),
        "debug_obj_path": str(debug_obj_path),
    }
    write_json(work_dir / "mesh_cleanup_report.json", payload)
    return payload
