from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import trimesh


def _split_mesh_components(mesh: trimesh.Trimesh) -> list[trimesh.Trimesh]:
    try:
        pieces = mesh.split(only_watertight=False)
        return [piece for piece in pieces if len(piece.vertices) > 0]
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


def _load_scene(mesh_path: Path) -> tuple[trimesh.Scene | None, str | None]:
    try:
        scene = trimesh.load(mesh_path, force="scene")
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    if not isinstance(scene, trimesh.Scene):
        try:
            scene = scene.scene()
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)
    return scene, None


def _vertex_count(scene: trimesh.Scene) -> int:
    total = 0
    for geometry in scene.geometry.values():
        vertices = getattr(geometry, "vertices", None)
        if vertices is not None:
            total += len(vertices)
    return total


def _bbox_metrics(scene: trimesh.Scene) -> tuple[list[float], float]:
    bounds = scene.bounds
    if bounds is None:
        return [0.0, 0.0, 0.0], 0.0
    extents = (bounds[1] - bounds[0]).tolist()
    volume = float(extents[0] * extents[1] * extents[2]) if all(value > 0 for value in extents) else 0.0
    return [float(value) for value in extents], volume


def _component_metrics(scene: trimesh.Scene, *, fast_path: bool = False) -> tuple[int, float]:
    component_vertex_counts: list[int] = []
    for geometry in scene.geometry.values():
        if not isinstance(geometry, trimesh.Trimesh):
            continue
        if fast_path:
            vertices = getattr(geometry, "vertices", None)
            if vertices is not None and len(vertices) > 0:
                component_vertex_counts.append(len(vertices))
            continue
        pieces = _split_mesh_components(geometry)
        if not pieces:
            pieces = [geometry]
        for piece in pieces:
            vertices = getattr(piece, "vertices", None)
            if vertices is not None and len(vertices) > 0:
                component_vertex_counts.append(len(vertices))

    if not component_vertex_counts:
        return 0, 0.0
    total = sum(component_vertex_counts)
    largest_ratio = float(max(component_vertex_counts) / total) if total else 0.0
    return len(component_vertex_counts), largest_ratio


def _quality_payload(checks: dict[str, bool], metrics: dict[str, Any], errors: dict[str, str]) -> dict[str, Any]:
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "status": "passed" if not failed else "failed",
        "reason": None if not failed else "poor_reconstruction",
        "usable": not failed,
        "checks": checks,
        "metrics": metrics,
        "errors": errors,
        "hints": metrics.pop("quality_hints", []),
        "summary": "All quality checks passed." if not failed else "Failed checks: " + ", ".join(failed),
    }


def evaluate_image_quality(
    mesh_path: Path,
    thumbnail_path: Path,
    *,
    image_preprocess: dict[str, Any] | None = None,
    preprocess_hints: list[str] | None = None,
    multiview_info: dict[str, Any] | None = None,
    reconstruction_head_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mesh_path = mesh_path.expanduser().resolve()
    thumbnail_path = thumbnail_path.expanduser().resolve()

    checks = {
        "mesh_exists": mesh_path.exists(),
        "mesh_non_empty": mesh_path.exists() and mesh_path.stat().st_size > 0,
        "thumbnail_exists": thumbnail_path.exists(),
        "mesh_loadable": False,
        "bbox_valid": False,
        "vertex_count_ok": False,
        "component_count_ok": False,
        "largest_component_ratio_ok": False,
        "bbox_tightness_ok": True,
        "silhouette_consistency_ok": True,
        "view_count_ok": True,
        "view_diversity_ok": True,
    }
    metrics: dict[str, Any] = {
        "mesh_size_bytes": mesh_path.stat().st_size if mesh_path.exists() else 0,
        "quality_hints": [],
    }
    errors: dict[str, str] = {}
    precomputed_mesh_stats = (
        ((reconstruction_head_info or {}).get("raw_outputs") or {}).get("trellis_summary") or {}
    ).get("mesh_stats")

    if mesh_path.exists() and isinstance(precomputed_mesh_stats, dict):
        vertex_count = int(precomputed_mesh_stats.get("vertex_count") or 0)
        face_count = int(precomputed_mesh_stats.get("face_count") or 0)
        bbox_extents = [float(value) for value in (precomputed_mesh_stats.get("bbox_size") or [0.0, 0.0, 0.0])]
        bbox_valid = bool(precomputed_mesh_stats.get("bbox_valid"))
        bbox_volume = float(np.prod(bbox_extents)) if bbox_valid and bbox_extents else 0.0
        checks["mesh_loadable"] = True
        checks["bbox_valid"] = bbox_valid
        checks["vertex_count_ok"] = vertex_count > 0
        checks["component_count_ok"] = True
        checks["largest_component_ratio_ok"] = True
        metrics["vertex_count"] = vertex_count
        metrics["face_count"] = face_count
        metrics["bbox_extents"] = bbox_extents
        metrics["bbox_volume"] = bbox_volume
        metrics["component_count"] = 1
        metrics["largest_component_ratio"] = 1.0
        if bbox_extents:
            positive_extents = [value for value in bbox_extents if value > 0]
            max_extent = max(positive_extents) if positive_extents else 0.0
            min_extent = min(positive_extents) if positive_extents else 0.0
            thickness_ratio = float(min_extent / max_extent) if max_extent > 0 else 0.0
            metrics["bbox_thickness_ratio"] = thickness_ratio
            if 0 < thickness_ratio < 0.08:
                metrics["quality_hints"].append("geometry_slab_like")
        metrics["quality_hints"].append("precomputed_mesh_stats_used")
    elif mesh_path.exists():
        scene, load_error = _load_scene(mesh_path)
        if load_error:
            errors["mesh_loadable"] = load_error
        elif scene is not None:
            fast_component_metrics = mesh_path.suffix.lower() in {".glb", ".gltf"}
            checks["mesh_loadable"] = True
            vertex_count = _vertex_count(scene)
            bbox_extents, bbox_volume = _bbox_metrics(scene)
            component_count, largest_component_ratio = _component_metrics(scene, fast_path=fast_component_metrics)
            checks["bbox_valid"] = bbox_volume > 0
            checks["vertex_count_ok"] = vertex_count > 0
            checks["component_count_ok"] = component_count <= 4
            checks["largest_component_ratio_ok"] = largest_component_ratio >= 0.75
            metrics["vertex_count"] = vertex_count
            metrics["bbox_extents"] = bbox_extents
            metrics["bbox_volume"] = bbox_volume
            metrics["component_count"] = component_count
            metrics["largest_component_ratio"] = largest_component_ratio
            metrics["component_metric_mode"] = "geometry_fast_path" if fast_component_metrics else "split_components"
            if bbox_extents:
                positive_extents = [value for value in bbox_extents if value > 0]
                max_extent = max(positive_extents) if positive_extents else 0.0
                min_extent = min(positive_extents) if positive_extents else 0.0
                thickness_ratio = float(min_extent / max_extent) if max_extent > 0 else 0.0
                metrics["bbox_thickness_ratio"] = thickness_ratio
                if 0 < thickness_ratio < 0.08:
                    metrics["quality_hints"].append("geometry_slab_like")
            if component_count > 1 or largest_component_ratio < 0.85:
                metrics["quality_hints"].append("geometry_fragmented")
            if component_count > 1 or largest_component_ratio < 0.75:
                metrics["quality_hints"].append("fragmented_shape")

    preprocess_hints = preprocess_hints or []
    image_preprocess = image_preprocess or {}
    crop_fill_ratio = float(image_preprocess.get("crop_fill_ratio") or 0.0)
    normalized_foreground_ratio = float(image_preprocess.get("normalized_foreground_ratio") or 0.0)
    metrics["crop_fill_ratio"] = crop_fill_ratio
    metrics["normalized_foreground_ratio"] = normalized_foreground_ratio
    if crop_fill_ratio > 0:
        checks["bbox_tightness_ok"] = 0.08 <= crop_fill_ratio <= 0.95
        if crop_fill_ratio < 0.08:
            metrics["quality_hints"].append("bbox_too_loose")
        elif crop_fill_ratio > 0.95:
            metrics["quality_hints"].append("bbox_too_tight")
    if "complex_background_detected" in preprocess_hints:
        metrics["quality_hints"].append("background_complexity_high")
    if {"small_foreground_ratio", "occlusion_detected"} & set(preprocess_hints):
        metrics["quality_hints"].append("single_view_ambiguity_high")
    if "foreground_provider_fallback_used" in preprocess_hints:
        metrics["quality_hints"].append("foreground_provider_fallback_used")

    multiview_info = multiview_info or {}
    if multiview_info:
        num_views = int(multiview_info.get("num_views") or 0)
        metrics["multiview_num_views"] = num_views
        metrics["multiview_enabled"] = bool(multiview_info.get("enabled"))
        metrics["multiview_active"] = bool(multiview_info.get("active"))
        view_metrics = multiview_info.get("view_metrics") or {}
        silhouette_metrics = multiview_info.get("silhouette_metrics") or {}
        metrics["multiview_pairwise_mean_abs_diff_mean"] = view_metrics.get("pairwise_mean_abs_diff_mean")
        metrics["silhouette_consistency_score"] = silhouette_metrics.get("consistency_score")
        metrics["silhouette_coverage_std"] = silhouette_metrics.get("coverage_std")
        if multiview_info.get("active"):
            checks["view_count_ok"] = num_views >= 4
            pairwise_mean = float(view_metrics.get("pairwise_mean_abs_diff_mean") or 0.0)
            checks["view_diversity_ok"] = pairwise_mean >= 0.02
            if not checks["view_diversity_ok"]:
                metrics["quality_hints"].append("view_diversity_low")
            consistency_score = float(silhouette_metrics.get("consistency_score") or 0.0)
            coverage_std = float(silhouette_metrics.get("coverage_std") or 0.0)
            checks["silhouette_consistency_ok"] = consistency_score >= 0.4 and coverage_std <= 0.22
            if not checks["silhouette_consistency_ok"]:
                metrics["quality_hints"].append("silhouette_consistency_low")
        if multiview_info.get("multiview_fallback"):
            metrics["quality_hints"].append("multiview_fallback_used")
    reconstruction_head_info = reconstruction_head_info or {}
    if reconstruction_head_info:
        metrics["recon_head_used"] = reconstruction_head_info.get("used")
        metrics["recon_head_requested"] = reconstruction_head_info.get("requested")
    metrics["quality_hints"] = sorted(set(metrics["quality_hints"]))

    return _quality_payload(checks, metrics, errors)
