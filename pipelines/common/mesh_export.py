from __future__ import annotations

import os
import json
import shutil
import subprocess
import textwrap
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import trimesh
from trimesh.exchange.obj import export_obj


@dataclass(frozen=True)
class MeshExportSpec:
    format: str
    label: str
    extension: str
    mime_type: str
    tool_hint: str
    note: str
    package: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class MeshExportResult:
    format: str
    label: str
    file_name: str
    path: Path
    mime_type: str
    tool_hint: str
    note: str
    generated: bool


EXPORT_SPECS: dict[str, MeshExportSpec] = {
    "glb": MeshExportSpec(
        format="glb",
        label="GLB",
        extension=".glb",
        mime_type="model/gltf-binary",
        tool_hint="웹 뷰어, Blender, Unity, Unreal",
        note="텍스처가 포함된 기본 결과 파일입니다.",
    ),
    "gltf": MeshExportSpec(
        format="gltf",
        label="glTF",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="three.js, Babylon.js, 웹/게임 엔진",
        note="gltf, bin, texture 파일을 ZIP으로 묶어 제공합니다.",
        package=True,
    ),
    "obj": MeshExportSpec(
        format="obj",
        label="OBJ",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="Blender, Maya, Cinema 4D, Unity",
        note="obj, mtl, texture 파일을 함께 묶은 호환 패키지입니다.",
        package=True,
    ),
    "fbx": MeshExportSpec(
        format="fbx",
        label="FBX",
        extension=".fbx",
        mime_type="application/octet-stream",
        tool_hint="Maya, 3ds Max, Unity, Unreal",
        note="DCC/게임 엔진에서 쓰기 좋은 교환 포맷입니다.",
    ),
    "stl": MeshExportSpec(
        format="stl",
        label="STL",
        extension=".stl",
        mime_type="model/stl",
        tool_hint="Cura, PrusaSlicer, Bambu Studio",
        note="3D 프린팅용 geometry 포맷입니다. 색상과 텍스처는 포함되지 않습니다.",
    ),
    "3mf": MeshExportSpec(
        format="3mf",
        label="3MF",
        extension=".3mf",
        mime_type="model/3mf",
        tool_hint="Bambu Studio, PrusaSlicer, OrcaSlicer",
        note="3D 프린팅 툴에서 쓰기 좋은 패키지형 geometry 포맷입니다.",
    ),
    "usdz": MeshExportSpec(
        format="usdz",
        label="USDZ",
        extension=".usdz",
        mime_type="model/vnd.usdz+zip",
        tool_hint="Apple Quick Look, Reality Composer",
        note="USDZ는 USD 변환 도구가 서버에 설치되면 활성화할 수 있습니다.",
        enabled=False,
    ),
    "web": MeshExportSpec(
        format="web",
        label="Web Package",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="Web viewer, sharing, lightweight review",
        note="Canonical GLB with textures, material.json, metadata.json, and thumbnail.",
        package=True,
    ),
    "blender": MeshExportSpec(
        format="blender",
        label="Blender Package",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="Blender GLB import workflow",
        note="Blender-friendly GLB package with sidecar PBR and semantic metadata.",
        package=True,
    ),
    "maya": MeshExportSpec(
        format="maya",
        label="Maya Package",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="Maya + Arnold import helper",
        note="FBX, textures, material.json, metadata.json, thumbnail, and import_asset.py.",
        package=True,
    ),
    "unreal": MeshExportSpec(
        format="unreal",
        label="Unreal Package",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="Unreal static mesh import",
        note="FBX-centered package with PBR sidecars for engine import setup.",
        package=True,
    ),
    "alembic": MeshExportSpec(
        format="alembic",
        label="Alembic Package",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="VFX geometry cache handoff",
        note="ABC geometry with texture/material/metadata sidecars.",
        package=True,
    ),
    "obj_legacy": MeshExportSpec(
        format="obj_legacy",
        label="OBJ Legacy Package",
        extension=".zip",
        mime_type="application/zip",
        tool_hint="Legacy DCC mesh exchange",
        note="OBJ/MTL package with PBR sidecar material metadata.",
        package=True,
    ),
}


class MeshExportError(RuntimeError):
    pass


def _blender_binary() -> str | None:
    configured = os.getenv("BLENDER_BIN")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.exists():
            return str(configured_path)
    project_root = Path(__file__).resolve().parents[2]
    bundled = project_root / ".runtime" / "blender" / "blender-4.3.2-linux-x64" / "blender"
    if bundled.exists():
        return str(bundled)
    return shutil.which("blender")


def _spec_with_runtime_availability(spec: MeshExportSpec) -> MeshExportSpec:
    if spec.format == "fbx" and _blender_binary() is None:
        return replace(
            spec,
            enabled=False,
            note="FBX 변환에는 서버에 Blender CLI가 필요합니다.",
        )
    if spec.format in {"maya", "unreal", "alembic"} and _blender_binary() is None:
        return replace(
            spec,
            enabled=False,
            note="이 DCC 패키지를 만들려면 서버에 Blender CLI가 필요합니다.",
        )
    return spec


def list_export_specs() -> list[MeshExportSpec]:
    return [_spec_with_runtime_availability(spec) for spec in EXPORT_SPECS.values()]


def _export_fbx_with_blender(source_mesh: Path, output_path: Path) -> Path:
    blender = _blender_binary()
    if blender is None:
        raise MeshExportError("FBX 변환에는 서버에 Blender CLI가 필요합니다.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = textwrap.dedent(
        """
        import bpy
        import sys
        from pathlib import Path

        source = Path(sys.argv[sys.argv.index("--") + 1])
        target = Path(sys.argv[sys.argv.index("--") + 2])

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        bpy.ops.import_scene.gltf(filepath=str(source))
        mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
        if not mesh_objects:
            raise RuntimeError("Imported scene has no objects")

        # glTF is Y-up, Blender is Z-up, and Maya is Y-up. If the FBX exporter
        # stores that conversion only as pre/post rotations, Maya can display
        # object exports lying on the grid. Flatten the imported hierarchy and
        # bake the axis conversion into the FBX data for a Maya-friendly file.
        for obj in mesh_objects:
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
            obj.select_set(False)

        for obj in list(bpy.context.scene.objects):
            if obj.type != "MESH":
                bpy.data.objects.remove(obj, do_unlink=True)

        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objects[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.export_scene.fbx(
            filepath=str(target),
            use_selection=True,
            path_mode="COPY",
            embed_textures=True,
            add_leaf_bones=False,
            bake_anim=False,
            axis_forward="-Z",
            axis_up="Y",
            bake_space_transform=True,
        )
        """
    )
    command = [
        blender,
        "--background",
        "--factory-startup",
        "--python-expr",
        script,
        "--",
        str(source_mesh),
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise MeshExportError(f"FBX 변환에 실패했습니다: {details[-800:]}")
    return output_path


def _export_abc_with_blender(source_mesh: Path, output_path: Path) -> Path:
    blender = _blender_binary()
    if blender is None:
        raise MeshExportError("Alembic 변환에는 서버에 Blender CLI가 필요합니다.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = textwrap.dedent(
        """
        import bpy
        import sys
        from pathlib import Path

        source = Path(sys.argv[sys.argv.index("--") + 1])
        target = Path(sys.argv[sys.argv.index("--") + 2])

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()
        bpy.ops.import_scene.gltf(filepath=str(source))
        mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
        if not mesh_objects:
            raise RuntimeError("Imported scene has no mesh objects")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in mesh_objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_objects[0]
        bpy.ops.wm.alembic_export(
            filepath=str(target),
            selected=True,
            start=1,
            end=1,
            flatten=True,
            visible_objects_only=False,
            renderable_only=False,
        )
        """
    )
    command = [
        blender,
        "--background",
        "--factory-startup",
        "--python-expr",
        script,
        "--",
        str(source_mesh),
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise MeshExportError(f"Alembic 변환에 실패했습니다: {details[-800:]}")
    return output_path


def _safe_scene(source_mesh: Path) -> trimesh.Scene:
    scene = trimesh.load(source_mesh, force="scene")
    if not isinstance(scene, trimesh.Scene):
        scene = trimesh.Scene(scene)
    if not scene.geometry:
        raise MeshExportError("3D 모델 안에 변환할 geometry가 없습니다.")
    return scene


def _write_bytes(path: Path, payload: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_bytes(payload)
    return path


def _write_zip(path: Path, files: dict[str, bytes | str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            archive.writestr(name, data)
    return path


def _export_gltf_zip(scene: trimesh.Scene, output_path: Path) -> Path:
    exported = scene.export(file_type="gltf")
    if not isinstance(exported, dict):
        raise MeshExportError("glTF 변환 결과가 패키지 형태가 아닙니다.")
    files: dict[str, bytes | str] = {}
    for name, payload in exported.items():
        files[str(name)] = payload
    return _write_zip(output_path, files)


def _export_obj_zip(scene: trimesh.Scene, output_path: Path, *, base_name: str) -> Path:
    obj_text, assets = export_obj(
        scene,
        include_normals=True,
        include_color=True,
        include_texture=True,
        return_texture=True,
        mtl_name=f"{base_name}.mtl",
        header="PRISM Scan export",
    )
    files: dict[str, bytes | str] = {f"{base_name}.obj": obj_text}
    for name, payload in assets.items():
        files[str(name)] = payload
    return _write_zip(output_path, files)


def _maya_import_script() -> str:
    return r'''from __future__ import annotations

import json
import os

import maya.cmds as cmds


def _root():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _texture(root, rel_path):
    if not rel_path:
        return None
    return os.path.join(root, rel_path.replace("/", os.sep))


def _connect_file(path, target_attr, color_space="sRGB"):
    if not path or not os.path.exists(path):
        return None
    file_node = cmds.shadingNode("file", asTexture=True)
    cmds.setAttr(file_node + ".fileTextureName", path, type="string")
    try:
        cmds.setAttr(file_node + ".colorSpace", color_space, type="string")
    except Exception:
        pass
    if target_attr.endswith(".baseColor"):
        cmds.connectAttr(file_node + ".outColor", target_attr, force=True)
    else:
        cmds.connectAttr(file_node + ".outAlpha", target_attr, force=True)
    return file_node


def _set_attr_if_exists(node, attr, value):
    try:
        if cmds.attributeQuery(attr, node=node, exists=True):
            cmds.setAttr(node + "." + attr, value)
            return True
    except Exception:
        pass
    return False


def _set_color_if_exists(node, attr, value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return False
    try:
        if cmds.attributeQuery(attr, node=node, exists=True):
            cmds.setAttr(node + "." + attr, float(value[0]), float(value[1]), float(value[2]), type="double3")
            return True
    except Exception:
        pass
    return False


def _mesh_transforms():
    meshes = cmds.ls(type="mesh", long=True) or []
    transforms = []
    for shape in meshes:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        transforms.extend(parents)
    return list(dict.fromkeys(transforms))


def import_asset(mode="auto"):
    root = _root()
    material_path = os.path.join(root, "material.json")
    metadata_path = os.path.join(root, "metadata.json")
    fbx_path = os.path.join(root, "model.fbx")
    abc_path = os.path.join(root, "model.abc")

    if mode == "auto":
        mode = "fbx" if os.path.exists(fbx_path) else "abc"

    before = set(cmds.ls(assemblies=True, long=True) or [])
    if mode == "fbx" and os.path.exists(fbx_path):
        cmds.file(fbx_path, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace="ai3d")
    elif mode == "abc" and os.path.exists(abc_path):
        cmds.AbcImport(abc_path, mode="import")
    else:
        raise RuntimeError("No model.fbx or model.abc found next to import_asset.py")
    after = set(cmds.ls(assemblies=True, long=True) or [])
    imported_roots = list(after - before) or (cmds.ls(assemblies=True, long=True) or [])

    material = _read_json(material_path) if os.path.exists(material_path) else {}
    shader = cmds.shadingNode("aiStandardSurface", asShader=True, name="AI3D_aiStandardSurface")
    shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")
    cmds.connectAttr(shader + ".outColor", shading_group + ".surfaceShader", force=True)

    _connect_file(_texture(root, material.get("baseColorTexture")), shader + ".baseColor", "sRGB")
    _connect_file(_texture(root, material.get("roughnessTexture")), shader + ".specularRoughness", "Raw")
    _connect_file(_texture(root, material.get("metallicTexture")), shader + ".metalness", "Raw")
    if material.get("metallicTexture") is None and material.get("metallicValue") is not None:
        cmds.setAttr(shader + ".metalness", float(material.get("metallicValue") or 0.0))
    if material.get("roughnessTexture") is None and material.get("roughnessValue") is not None:
        cmds.setAttr(shader + ".specularRoughness", float(material.get("roughnessValue") or 0.8))
    _connect_file(_texture(root, material.get("opacityTexture")), shader + ".opacity", "Raw")
    _set_attr_if_exists(shader, "transmission", float(material.get("transmissionValue") or 0.0))
    _set_attr_if_exists(shader, "specularIOR", float(material.get("iorValue") or 1.5))
    _set_attr_if_exists(shader, "subsurface", float(material.get("subsurfaceWeight") or 0.0))
    _set_color_if_exists(shader, "subsurfaceColor", material.get("subsurfaceColor") or [1.0, 1.0, 1.0])

    normal_path = _texture(root, material.get("normalTexture"))
    if normal_path and os.path.exists(normal_path):
        file_node = _connect_file(normal_path, shader + ".normalCamera", "Raw")
        if file_node:
            normal_node = cmds.shadingNode("aiNormalMap", asUtility=True)
            cmds.disconnectAttr(file_node + ".outAlpha", shader + ".normalCamera")
            cmds.connectAttr(file_node + ".outColor", normal_node + ".input", force=True)
            cmds.connectAttr(normal_node + ".outValue", shader + ".normalCamera", force=True)

    transforms = _mesh_transforms()
    if transforms:
        cmds.sets(transforms, edit=True, forceElement=shading_group)

    metadata = _read_json(metadata_path) if os.path.exists(metadata_path) else {}
    attr_map = {
        "FastVLM_AssetName": metadata.get("asset_name"),
        "FastVLM_Category": metadata.get("category"),
        "FastVLM_Subcategory": metadata.get("subcategory"),
        "FastVLM_Tags": ", ".join(metadata.get("dcc_tags") or []),
        "FastVLM_SourcePrompt": metadata.get("source_prompt"),
        "Generation_Model": metadata.get("generation_model"),
        "Asset_Usage": metadata.get("recommended_usage"),
        "Normalized_Category_ID": metadata.get("normalized_category_id"),
    }
    for node in imported_roots:
        for attr, value in attr_map.items():
            if value is None:
                continue
            if not cmds.attributeQuery(attr, node=node, exists=True):
                cmds.addAttr(node, longName=attr, dataType="string")
            cmds.setAttr(f"{node}.{attr}", str(value), type="string")
    return imported_roots


if __name__ == "__main__":
    import_asset()
'''


def _sidecar_files(
    *,
    material_path: Path | None,
    metadata_path: Path | None,
    thumbnail_path: Path | None,
    textures_dir: Path | None,
    hdri_dir: Path | None = None,
    viewer_settings_path: Path | None = None,
) -> dict[str, bytes | str]:
    files: dict[str, bytes | str] = {}
    if textures_dir and textures_dir.exists():
        for texture in sorted(textures_dir.iterdir()):
            if texture.is_file():
                files[f"textures/{texture.name}"] = texture.read_bytes()
    if hdri_dir and hdri_dir.exists():
        for item in sorted(hdri_dir.iterdir()):
            if item.is_file():
                files[f"hdri/{item.name}"] = item.read_bytes()
    if material_path and material_path.exists():
        files["material.json"] = material_path.read_text(encoding="utf-8")
    if metadata_path and metadata_path.exists():
        files["metadata.json"] = metadata_path.read_text(encoding="utf-8")
    if viewer_settings_path and viewer_settings_path.exists():
        files["viewer_settings.json"] = viewer_settings_path.read_text(encoding="utf-8")
    if thumbnail_path and thumbnail_path.exists():
        files["thumbnail.png"] = thumbnail_path.read_bytes()
    return files


def export_asset_package(
    source_mesh: Path,
    output_dir: Path,
    fmt: str,
    *,
    material_path: Path | None,
    metadata_path: Path | None,
    thumbnail_path: Path | None,
    textures_dir: Path | None,
    hdri_dir: Path | None = None,
    viewer_settings_path: Path | None = None,
    base_name: str = "object_mesh",
) -> MeshExportResult:
    normalized = fmt.strip().lower()
    spec = _spec_with_runtime_availability(EXPORT_SPECS.get(normalized)) if EXPORT_SPECS.get(normalized) else None
    if spec is None or normalized not in {"web", "blender", "maya", "unreal", "alembic", "obj_legacy"}:
        raise MeshExportError(f"지원하지 않는 DCC 패키지입니다: {fmt}")
    if not spec.enabled:
        raise MeshExportError(spec.note)

    source_mesh = source_mesh.expanduser().resolve()
    if not source_mesh.exists():
        raise MeshExportError("원본 3D 파일을 찾을 수 없습니다.")

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_base_name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in base_name).strip("_") or "object_mesh"
    output_path = output_dir / f"{safe_base_name}.{normalized}.zip"
    build_dir = output_dir / "_package_build" / normalized
    build_dir.mkdir(parents=True, exist_ok=True)

    files = _sidecar_files(
        material_path=material_path,
        metadata_path=metadata_path,
        thumbnail_path=thumbnail_path,
        textures_dir=textures_dir,
        hdri_dir=hdri_dir,
        viewer_settings_path=viewer_settings_path,
    )
    canonical_model = {
        "maya": "model.fbx",
        "unreal": "model.fbx",
        "alembic": "model.abc",
        "obj_legacy": "model.obj",
    }.get(normalized, "model.glb")
    manifest = {
        "format": normalized,
        "canonical_model": canonical_model,
        "material": "material.json" if "material.json" in files else None,
        "metadata": "metadata.json" if "metadata.json" in files else None,
        "viewer_settings": "viewer_settings.json" if "viewer_settings.json" in files else None,
        "hdri": sorted(name for name in files if name.startswith("hdri/")),
    }

    if normalized in {"web", "blender"}:
        files["model.glb"] = source_mesh.read_bytes()
    elif normalized in {"maya", "unreal"}:
        fbx_path = _export_fbx_with_blender(source_mesh, build_dir / "model.fbx")
        files["model.fbx"] = fbx_path.read_bytes()
        if normalized == "maya":
            files["import_asset.py"] = _maya_import_script()
    elif normalized == "alembic":
        abc_path = _export_abc_with_blender(source_mesh, build_dir / "model.abc")
        files["model.abc"] = abc_path.read_bytes()
        files["import_asset.py"] = _maya_import_script()
    elif normalized == "obj_legacy":
        scene = _safe_scene(source_mesh)
        obj_text, assets = export_obj(
            scene,
            include_normals=True,
            include_color=True,
            include_texture=True,
            return_texture=True,
            mtl_name="model.mtl",
            header="PRISM Scan OBJ legacy package",
        )
        files["model.obj"] = obj_text
        for name, payload in assets.items():
            files[str(name).replace(safe_base_name, "model")] = payload

    files["package_manifest.json"] = json.dumps(manifest, indent=2)
    _write_zip(output_path, files)

    return MeshExportResult(
        format=spec.format,
        label=spec.label,
        file_name=output_path.name,
        path=output_path,
        mime_type=spec.mime_type,
        tool_hint=spec.tool_hint,
        note=spec.note,
        generated=True,
    )


def export_mesh_format(source_mesh: Path, output_dir: Path, fmt: str, *, base_name: str = "object_mesh") -> MeshExportResult:
    normalized = fmt.strip().lower()
    raw_spec = EXPORT_SPECS.get(normalized)
    spec = _spec_with_runtime_availability(raw_spec) if raw_spec else None
    if spec is None:
        raise MeshExportError(f"지원하지 않는 출력 포맷입니다: {fmt}")
    if not spec.enabled:
        raise MeshExportError(spec.note)

    source_mesh = source_mesh.expanduser().resolve()
    if not source_mesh.exists():
        raise MeshExportError("원본 3D 파일을 찾을 수 없습니다.")

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_base_name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in base_name).strip("_")
    if not safe_base_name:
        safe_base_name = "object_mesh"
    output_path = output_dir / f"{safe_base_name}.{normalized}{spec.extension if spec.package else ''}"
    if normalized not in {"glb", "fbx"} and output_path.exists() and output_path.stat().st_size > 0:
        return MeshExportResult(
            format=spec.format,
            label=spec.label,
            file_name=output_path.name,
            path=output_path,
            mime_type=spec.mime_type,
            tool_hint=spec.tool_hint,
            note=spec.note,
            generated=False,
        )

    if normalized == "glb":
        target = source_mesh
    elif normalized == "fbx":
        target = _export_fbx_with_blender(source_mesh, output_path)
    else:
        scene = _safe_scene(source_mesh)
        if normalized == "gltf":
            target = _export_gltf_zip(scene, output_path)
        elif normalized == "obj":
            target = _export_obj_zip(scene, output_path, base_name=safe_base_name)
        elif normalized == "stl":
            target = _write_bytes(output_path, scene.export(file_type="stl"))
        elif normalized == "3mf":
            try:
                target = _write_bytes(output_path, scene.export(file_type="3mf"))
            except ModuleNotFoundError as exc:
                raise MeshExportError("3MF 변환에는 lxml 패키지가 필요합니다.") from exc
        else:
            raise MeshExportError(f"아직 변환기가 연결되지 않은 포맷입니다: {fmt}")

    if target != source_mesh and (not target.exists() or target.stat().st_size <= 0):
        raise MeshExportError(f"{spec.label} 파일 생성에 실패했습니다.")

    if normalized == "glb":
        # Keep the canonical result path. Do not duplicate the main mesh.
        target = source_mesh
    elif target != output_path:
        shutil.copy2(target, output_path)
        target = output_path

    return MeshExportResult(
        format=spec.format,
        label=spec.label,
        file_name=target.name,
        path=target,
        mime_type=spec.mime_type,
        tool_hint=spec.tool_hint,
        note=spec.note,
        generated=True,
    )


def export_result_to_payload(result: MeshExportResult, url: str) -> dict[str, Any]:
    return {
        "format": result.format,
        "label": result.label,
        "file_name": result.file_name,
        "url": url,
        "mime_type": result.mime_type,
        "tool_hint": result.tool_hint,
        "note": result.note,
        "generated": result.generated,
        "available": True,
    }
