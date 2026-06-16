from __future__ import annotations

import json
import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw


def _pad_bytes(data: bytes, pad_byte: bytes = b" ") -> bytes:
    padding = (-len(data)) % 4
    if padding == 0:
        return data
    return data + (pad_byte * padding)


def _build_glb_bytes() -> bytes:
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []

    faces = [
        ((0, 0, 1), [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]),
        ((0, 0, -1), [(1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)]),
        ((-1, 0, 0), [(-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)]),
        ((1, 0, 0), [(1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)]),
        ((0, 1, 0), [(-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)]),
        ((0, -1, 0), [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)]),
    ]

    for face_index, (normal, verts) in enumerate(faces):
        start = face_index * 4
        for vertex in verts:
            positions.extend(vertex)
            normals.extend(normal)
        indices.extend([start, start + 1, start + 2, start, start + 2, start + 3])

    position_bytes = struct.pack(f"<{len(positions)}f", *positions)
    normal_bytes = struct.pack(f"<{len(normals)}f", *normals)
    index_bytes = struct.pack(f"<{len(indices)}H", *indices)
    binary_blob = _pad_bytes(position_bytes, b"\x00") + _pad_bytes(normal_bytes, b"\x00") + _pad_bytes(index_bytes, b"\x00")

    position_length = len(_pad_bytes(position_bytes, b"\x00"))
    normal_length = len(_pad_bytes(normal_bytes, b"\x00"))
    index_offset = position_length + normal_length

    gltf = {
        "asset": {"version": "2.0", "generator": "ai-3d-service-mock"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "name": "mock_cube",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1},
                        "indices": 2,
                        "material": 0,
                    }
                ],
            }
        ],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.2, 0.75, 0.76, 1.0],
                    "metallicFactor": 0.1,
                    "roughnessFactor": 0.8,
                }
            }
        ],
        "buffers": [{"byteLength": len(binary_blob)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": position_length, "byteLength": len(normal_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(index_bytes), "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 24,
                "type": "VEC3",
                "max": [1, 1, 1],
                "min": [-1, -1, -1],
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": 24,
                "type": "VEC3",
            },
            {
                "bufferView": 2,
                "componentType": 5123,
                "count": 36,
                "type": "SCALAR",
            },
        ],
    }

    json_bytes = _pad_bytes(json.dumps(gltf, separators=(",", ":")).encode("utf-8"))
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary_blob)
    header = struct.pack("<4sII", b"glTF", 2, total_length)
    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_chunk = struct.pack("<I4s", len(binary_blob), b"BIN\x00") + binary_blob
    return header + json_chunk + bin_chunk


def write_mock_object_glb(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_build_glb_bytes())
    return path


def write_mock_scene_obj(path: Path) -> Path:
    obj_text = """# mock scene mesh
v -2.0 0.0 -2.0
v 2.0 0.0 -2.0
v 2.0 0.0 2.0
v -2.0 0.0 2.0
v -1.0 1.6 -1.0
v 1.0 1.6 -1.0
v 1.0 1.6 1.0
v -1.0 1.6 1.0
v 0.0 2.4 0.0
f 1 2 3
f 1 3 4
f 5 6 7
f 5 7 8
f 1 2 6
f 1 6 5
f 2 3 7
f 2 7 6
f 3 4 8
f 3 8 7
f 4 1 5
f 4 5 8
f 5 6 9
f 6 7 9
f 7 8 9
f 8 5 9
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj_text, encoding="utf-8")
    return path


def write_mock_ply(path: Path) -> Path:
    ply = """ply
format ascii 1.0
element vertex 5
property float x
property float y
property float z
end_header
0 0 0
1 0 0
0 1 0
0 0 1
1 1 1
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ply, encoding="utf-8")
    return path


def write_thumbnail(path: Path, title: str, subtitle: str, accent: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 960, 720
    image = Image.new("RGB", (width, height), color=(9, 18, 28))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        blend = y / max(height - 1, 1)
        color = (
            int(9 + (accent[0] - 9) * blend * 0.7),
            int(18 + (accent[1] - 18) * blend * 0.7),
            int(28 + (accent[2] - 28) * blend * 0.7),
        )
        draw.line((0, y, width, y), fill=color)

    draw.rounded_rectangle((60, 60, width - 60, height - 60), radius=36, outline=(242, 245, 247), width=4)
    draw.text((100, 110), title, fill=(255, 255, 255))
    draw.text((100, 180), subtitle, fill=(220, 230, 232))

    center_x, center_y = width // 2, height // 2 + 40
    radius = 120
    points = []
    for idx in range(6):
        angle = math.pi / 3 * idx
        points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    draw.polygon(points, outline=(255, 255, 255), fill=(accent[0], accent[1], accent[2]))

    image.save(path, format="PNG")
    return path


def write_frame(path: Path, index: int) -> Path:
    accent = (240, 147, 43 + (index * 8) % 150)
    return write_thumbnail(path, f"Frame {index:03d}", "Mock extracted frame", accent)

