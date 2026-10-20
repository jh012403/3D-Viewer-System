"""Inspect an actual generated box; add a separate closed bottom cap if needed.

Original generated GLB is never overwritten. UV seams are welded only in the
topology audit copy; existing textured mesh data is retained in the export.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


def run(source, output, report, yaw=0):
    scene = trimesh.load(source, force="scene")
    rows, caps = [], []
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        mesh = scene.geometry[name]
        welded = mesh.copy()
        welded.merge_vertices(merge_tex=True, merge_norm=True)
        edges = welded.edges_sorted
        unique, count = np.unique(edges, axis=0, return_counts=True)
        boundary = unique[count == 1]
        vertices = trimesh.transform_points(welded.vertices, transform)
        low, high = vertices[:, 1].min(), vertices[:, 1].max()
        bottom_edges = boundary[np.all(vertices[boundary, 1] < low + .2 * (high - low), axis=1)]
        row = dict(node=node, watertight_after_seam_weld=bool(welded.is_watertight),
                   boundary_edges=len(boundary), bottom_boundary_edges=len(bottom_edges),
                   vertices=len(vertices), faces=len(mesh.faces))
        if len(bottom_edges):
            floor = np.quantile(vertices[:, 1], .02)
            base = vertices[vertices[:, 1] <= low + .1 * (high - low)][:, [0, 2]]
            outline = base[ConvexHull(base).vertices]
            # A closed, thin prism: both bottom and top fans plus the rim.
            n = len(outline)
            thickness = max(.001, .015 * (high - low))
            points = np.array([[x, floor + dy, z] for dy in (-thickness, 0) for x, z in outline])
            faces = []
            for i in range(1, n - 1):
                faces.extend([[0, i + 1, i], [n, n + i, n + i + 1]])
            for i in range(n):
                j = (i + 1) % n
                faces.extend([[i, j, n + j], [i, n + j, n + i]])
            cap = trimesh.Trimesh(points, faces, process=True)
            trimesh.repair.fix_normals(cap)
            cap.visual = trimesh.visual.ColorVisuals(cap, face_colors=[112, 91, 69, 255])
            assert cap.is_watertight
            caps.append(cap)
            row["cap"] = dict(vertices=len(cap.vertices), faces=len(cap.faces), thickness=thickness)
        rows.append(row)
    for i, cap in enumerate(caps):
        scene.add_geometry(cap, node_name=f"closed_bottom_cap_{i}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if caps:
        scene.export(output)
    else:
        output.write_bytes(source.read_bytes())
    result = dict(source=str(source), output=str(output), meshes=rows,
                  cap_count=len(caps), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  placement_yaw_degrees=yaw,
                  original_preserved=True, note="Closed cap is a separate bottom patch, not a claim of globally repaired topology.")
    (output.parent / "placement-profile.json").write_text(
        json.dumps({"yaw_degrees": yaw, "mesh_sha256": result["output_sha256"]}), encoding="utf-8")
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--yaw", type=float, default=0)
    args = parser.parse_args()
    run(args.source, args.output, args.report, args.yaw)
