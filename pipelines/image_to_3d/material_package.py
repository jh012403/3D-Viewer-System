from __future__ import annotations

import base64
import io
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance

from pipelines.common.io import ensure_dir, write_json


def _read_glb(glb_path: Path) -> tuple[dict[str, Any], bytes]:
    data = glb_path.read_bytes()
    if len(data) < 20:
        raise RuntimeError(f"GLB file is too small: {glb_path}")
    magic, version, _length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2:
        raise RuntimeError(f"Unsupported GLB header: {glb_path}")

    json_chunk: bytes | None = None
    binary_chunk = b""
    offset = 12
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == b"JSON":
            json_chunk = chunk
        elif chunk_type == b"BIN\x00":
            binary_chunk = chunk

    if json_chunk is None:
        raise RuntimeError(f"GLB JSON chunk is missing: {glb_path}")
    return json.loads(json_chunk.rstrip(b" \t\r\n\x00").decode("utf-8")), binary_chunk


def _buffer_view_bytes(gltf: dict[str, Any], binary_chunk: bytes, buffer_view_index: int) -> bytes:
    buffer_view = gltf.get("bufferViews", [])[buffer_view_index]
    offset = int(buffer_view.get("byteOffset", 0))
    length = int(buffer_view.get("byteLength", 0))
    return binary_chunk[offset : offset + length]


def _texture_source_index(gltf: dict[str, Any], texture_index: int) -> int | None:
    textures = gltf.get("textures") or []
    if texture_index < 0 or texture_index >= len(textures):
        return None
    texture = textures[texture_index]
    extensions = texture.get("extensions") or {}
    webp = extensions.get("EXT_texture_webp") or {}
    if "source" in webp:
        return int(webp["source"])
    if "source" in texture:
        return int(texture["source"])
    return None


def _image_bytes(gltf: dict[str, Any], binary_chunk: bytes, image_index: int) -> bytes | None:
    images = gltf.get("images") or []
    if image_index < 0 or image_index >= len(images):
        return None
    image = images[image_index]
    if "bufferView" in image:
        return _buffer_view_bytes(gltf, binary_chunk, int(image["bufferView"]))
    uri = str(image.get("uri") or "")
    if uri.startswith("data:") and "," in uri:
        return base64.b64decode(uri.split(",", 1)[1])
    return None


def _texture_image(gltf: dict[str, Any], binary_chunk: bytes, texture_info: dict[str, Any] | None) -> Image.Image | None:
    if not isinstance(texture_info, dict) or "index" not in texture_info:
        return None
    source_index = _texture_source_index(gltf, int(texture_info["index"]))
    if source_index is None:
        return None
    payload = _image_bytes(gltf, binary_chunk, source_index)
    if not payload:
        return None
    with Image.open(io.BytesIO(payload)) as image:
        return image.convert("RGBA")


def _save_png(image: Image.Image, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path.name


def _solid_rgba(color: list[float] | tuple[float, ...] | None, size: tuple[int, int] = (1024, 1024)) -> Image.Image:
    values = color or [1.0, 1.0, 1.0, 1.0]
    rgba = []
    for value in values[:4]:
        if value <= 1.0:
            rgba.append(int(max(0.0, min(1.0, float(value))) * 255))
        else:
            rgba.append(int(max(0, min(255, float(value)))))
    while len(rgba) < 4:
        rgba.append(255)
    return Image.new("RGBA", size, tuple(rgba))


def _factor_list(value: Any, fallback: list[float], length: int) -> list[float]:
    if not isinstance(value, (list, tuple)):
        return list(fallback[:length])
    out: list[float] = []
    for item in list(value)[:length]:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            out.append(fallback[len(out)] if len(out) < len(fallback) else 1.0)
    while len(out) < length:
        out.append(fallback[len(out)] if len(out) < len(fallback) else 1.0)
    return out


def _float_factor(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    if not np.isfinite(number):
        return fallback
    return float(number)


def _hex_from_rgb_factor(values: list[float] | tuple[float, ...]) -> str:
    channels: list[int] = []
    for value in list(values)[:3]:
        channels.append(round(max(0.0, min(1.0, float(value))) * 255))
    while len(channels) < 3:
        channels.append(255)
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _variance(image: Image.Image) -> float:
    arr = np.asarray(image.convert("L"), dtype=np.float32)
    return float(arr.var())


def _contrast(image: Image.Image) -> float:
    arr = np.asarray(image.convert("L"), dtype=np.float32)
    return float(np.percentile(arr, 95) - np.percentile(arr, 5))


def _texture_report(image: Image.Image, *, source: str, has_glb_texture: bool) -> dict[str, Any]:
    rgba = image.convert("RGBA")
    gray = np.asarray(rgba.convert("L"), dtype=np.float32)
    alpha = np.asarray(rgba)[:, :, 3].astype(np.float32)
    variance = _variance(rgba)
    contrast = _contrast(rgba)
    width, height = rgba.size
    if not has_glb_texture:
        detail_level = "generated_or_scalar"
    elif variance < 12.0 and contrast < 18.0:
        detail_level = "flat"
    elif variance > 4200.0 or contrast > 160.0:
        detail_level = "high_contrast_or_baked_lighting"
    else:
        detail_level = "readable"
    return {
        "source": source,
        "hasGlbTexture": bool(has_glb_texture),
        "width": int(width),
        "height": int(height),
        "variance": round(float(variance), 4),
        "contrast": round(float(contrast), 4),
        "alphaCoverage": round(float(np.mean(alpha > 8.0)), 4),
        "detailLevel": detail_level,
        "bakedLightingHint": bool(contrast > 125.0 and float(np.percentile(gray, 5)) < 35.0),
    }


def _roughness_from_base_color(base_color: Image.Image) -> Image.Image:
    gray = base_color.convert("L")
    equalized = ImageEnhance.Contrast(gray).enhance(0.65)
    arr = np.asarray(equalized, dtype=np.float32)
    arr = 210.0 - ((arr - arr.min()) / max(float(arr.max() - arr.min()), 1.0) * 95.0)
    return Image.fromarray(np.clip(arr, 35, 245).astype(np.uint8), mode="L")


def _normal_from_height(base_color: Image.Image, strength: float = 2.0) -> Image.Image:
    height = np.asarray(base_color.convert("L").resize(base_color.size), dtype=np.float32) / 255.0
    grad_y, grad_x = np.gradient(height)
    nx = -grad_x * strength
    ny = -grad_y * strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack(
        [
            (nx / length * 0.5 + 0.5) * 255.0,
            (ny / length * 0.5 + 0.5) * 255.0,
            (nz / length * 0.5 + 0.5) * 255.0,
        ],
        axis=-1,
    )
    return Image.fromarray(np.clip(normal, 0, 255).astype(np.uint8), mode="RGB")


def _extract_channel(image: Image.Image, channel_index: int) -> Image.Image:
    arr = np.asarray(image.convert("RGBA"))
    return Image.fromarray(arr[:, :, channel_index], mode="L")


def build_material_package(
    *,
    glb_path: Path,
    output_path: Path,
    textures_dir: Path,
    scale_normalization: dict[str, Any] | None,
    cleanup_metadata: dict[str, Any] | None,
    viewer_environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    textures_dir = ensure_dir(textures_dir)
    for stale_name in (
        "baseColor.png",
        "baseColor_source.png",
        "roughness.png",
        "roughness_generated.png",
        "metallic.png",
        "normal.png",
        "normal_generated.png",
        "opacity.png",
    ):
        (textures_dir / stale_name).unlink(missing_ok=True)
    gltf, binary_chunk = _read_glb(glb_path)
    material = (gltf.get("materials") or [{}])[0]
    pbr = material.get("pbrMetallicRoughness") or {}
    base_color_factor = _factor_list(pbr.get("baseColorFactor"), [1.0, 1.0, 1.0, 1.0], 4)
    base_color_factor_hex = _hex_from_rgb_factor(base_color_factor)
    roughness_factor = _float_factor(pbr.get("roughnessFactor"), 1.0)
    metallic_factor = _float_factor(pbr.get("metallicFactor"), 1.0)

    base_color = _texture_image(gltf, binary_chunk, pbr.get("baseColorTexture"))
    has_glb_base_color_texture = base_color is not None
    base_color_source = "glb_baseColorTexture"
    if base_color is None:
        base_color = _solid_rgba(pbr.get("baseColorFactor"))
        base_color_source = "baseColorFactor"
    base_color_original_report = _texture_report(
        base_color,
        source=base_color_source,
        has_glb_texture=has_glb_base_color_texture,
    )
    original_base_color_name: str | None = None
    texture_enhancement = {
        "applied": False,
        "strategy": "preserve_trellis_glb",
        "source": "glb_material",
    }
    base_color_final_report = _texture_report(
        base_color,
        source=base_color_source,
        has_glb_texture=has_glb_base_color_texture,
    )
    base_color_name = _save_png(base_color, textures_dir / "baseColor.png")

    metallic_roughness = _texture_image(gltf, binary_chunk, pbr.get("metallicRoughnessTexture"))
    roughness_source = "glb_roughnessFactor"
    metallic_source = "glb_metallicFactor"
    roughness_name: str | None = None
    metallic_name: str | None = None
    metallic_value: float | None = metallic_factor

    if metallic_roughness is not None:
        roughness_map = _extract_channel(metallic_roughness, 1)
        metallic_map = _extract_channel(metallic_roughness, 2)
        if _variance(roughness_map) > 1.0 or _contrast(roughness_map) > 4.0:
            roughness_name = _save_png(roughness_map, textures_dir / "roughness.png")
            roughness_source = "glb_metallicRoughness_green_channel"
        metallic_mean = float(np.asarray(metallic_map, dtype=np.float32).mean())
        metallic_variance = _variance(metallic_map)
        if metallic_variance > 1.0 or metallic_mean > 8.0:
            metallic_name = _save_png(metallic_map, textures_dir / "metallic.png")
            metallic_source = "glb_metallicRoughness_blue_channel"
        else:
            # In glTF PBR, the metallic-roughness texture's blue channel modulates
            # metallicFactor. A uniform black channel means non-metal even when the
            # scalar metallicFactor is left at its glTF default of 1.0.
            metallic_value = 0.0
            metallic_source = "glb_metallicRoughness_blue_channel_uniform_non_metal"

    if roughness_name is None:
        roughness_generated = _roughness_from_base_color(base_color)
        roughness_name = _save_png(roughness_generated, textures_dir / "roughness_generated.png")
        roughness_source = "fallback_from_baseColor_for_package"

    if metallic_name is not None:
        metallic_value = None  # type: ignore[assignment]

    normal_image = _texture_image(gltf, binary_chunk, material.get("normalTexture"))
    normal_source = "glb_normalTexture"
    normal_name: str | None = None
    if normal_image is not None:
        normal_name = _save_png(normal_image, textures_dir / "normal.png")
    else:
        normal_generated = _normal_from_height(base_color)
        normal_name = _save_png(normal_generated, textures_dir / "normal_generated.png")
        normal_source = "height_from_baseColor"

    opacity_name: str | None = None
    opacity_value = 1.0
    alpha = np.asarray(base_color.convert("RGBA"))[:, :, 3]
    alpha_mode = str(material.get("alphaMode") or "OPAQUE").upper()
    alpha_cutoff = float(material.get("alphaCutoff", 0.5) or 0.5)
    transparent_ratio = float(np.mean(alpha < 250))
    alpha_texture_ignored = bool(alpha_mode == "OPAQUE" and transparent_ratio > 0.01)
    if alpha_mode != "OPAQUE":
        opacity_name = _save_png(Image.fromarray(alpha, mode="L"), textures_dir / "opacity.png")
        opacity_value = None  # type: ignore[assignment]

    extensions = material.get("extensions") or {}
    transmission_ext = extensions.get("KHR_materials_transmission") or {}
    ior_ext = extensions.get("KHR_materials_ior") or {}
    subsurface_ext = extensions.get("KHR_materials_subsurface") or {}
    displacement_ext = extensions.get("KHR_materials_displacement") or {}
    transmission_value = _float_factor(transmission_ext.get("transmissionFactor"), 0.0)
    ior_value = _float_factor(ior_ext.get("ior"), 1.5)
    subsurface_weight = _float_factor(
        subsurface_ext.get("subsurfaceFactor", subsurface_ext.get("subsurfaceWeight")),
        0.0,
    )
    subsurface_color = _factor_list(
        subsurface_ext.get("subsurfaceColorFactor", subsurface_ext.get("subsurfaceColor")),
        [1.0, 1.0, 1.0],
        3,
    )
    displacement_scale = _float_factor(displacement_ext.get("scale"), 0.0)

    if roughness_name:
        with Image.open(textures_dir / roughness_name) as roughness_image:
            roughness_variance = round(_variance(roughness_image), 4)
    else:
        roughness_variance = 0.0

    validation = {
        "baseColorVariance": base_color_final_report["variance"],
        "baseColorContrast": base_color_final_report["contrast"],
        "roughnessVariance": roughness_variance,
        "bakedShadowHint": bool(_contrast(base_color) > 120.0),
    }
    viewer_base_tint = base_color_factor_hex if has_glb_base_color_texture else "#ffffff"
    viewer_tint_source = "glb_baseColorFactor" if has_glb_base_color_texture else "solid_baseColorTexture_from_glb_factor"
    environment_presets = []
    if isinstance(viewer_environment, dict):
        environment_presets = list(viewer_environment.get("environmentPresets") or [])
    if not environment_presets:
        environment_presets = [
            {"id": "neutral", "label": "Neutral", "viewerValue": "neutral", "viewerAvailable": True},
            {"id": "legacy", "label": "Studio", "viewerValue": "legacy", "viewerAvailable": True},
        ]
    default_environment = (
        str((viewer_environment or {}).get("defaultEnvironmentPreset") or "").strip()
        if isinstance(viewer_environment, dict)
        else ""
    ) or "neutral"

    payload = {
        "baseColorTexture": f"textures/{base_color_name}",
        "originalBaseColorTexture": f"textures/{original_base_color_name}" if original_base_color_name else None,
        "baseColorSource": base_color_source,
        "baseColorFactor": base_color_factor,
        "baseColorFactorHex": base_color_factor_hex,
        "roughnessTexture": f"textures/{roughness_name}" if roughness_name else None,
        "roughnessValue": roughness_factor,
        "roughnessFactor": roughness_factor,
        "viewerRoughnessValue": roughness_factor,
        "roughnessSource": roughness_source,
        "metallicTexture": f"textures/{metallic_name}" if metallic_name else None,
        "metallicValue": metallic_value,
        "metallicFactor": metallic_factor,
        "viewerMetallicValue": metallic_value if metallic_name is None else metallic_factor,
        "metallicSource": metallic_source,
        "opacityTexture": f"textures/{opacity_name}" if opacity_name else None,
        "opacityValue": opacity_value,
        "opacityFactor": base_color_factor[3],
        "opacitySource": "glb_baseColor_alpha" if opacity_name else (
            "glb_opaque_alpha_ignored" if alpha_texture_ignored else "default_opaque"
        ),
        "normalTexture": f"textures/{normal_name}" if normal_name else None,
        "normalSource": normal_source,
        "alphaMode": alpha_mode,
        "alphaCutoff": alpha_cutoff,
        "alphaCutout": alpha_mode == "MASK",
        "transmissionValue": transmission_value,
        "transmissionSource": "glb_KHR_materials_transmission" if transmission_ext else "default_surface",
        "iorValue": ior_value,
        "iorSource": "glb_KHR_materials_ior" if ior_ext else "default_dielectric",
        "subsurfaceWeight": subsurface_weight,
        "subsurfaceColor": subsurface_color,
        "subsurfaceColorHex": _hex_from_rgb_factor(subsurface_color),
        "subsurfaceSource": "glb_KHR_materials_subsurface" if subsurface_ext else "default_disabled",
        "displacementTexture": None,
        "displacementScale": displacement_scale,
        "displacementSource": "glb_KHR_materials_displacement" if displacement_ext else "not_available_from_glb",
        "viewerBaseTint": viewer_base_tint,
        "viewerTintSource": viewer_tint_source,
        "viewerLightIntensity": 1.72,
        "viewerExposureEV": 0.0,
        "hdriRotationDegrees": 0.0,
        "environmentPreset": default_environment,
        "environmentPresets": environment_presets,
        "viewerSettingsFile": "viewer_settings.json" if viewer_environment else None,
        "viewerEnvironmentPackage": {
            "source": (viewer_environment or {}).get("source") if isinstance(viewer_environment, dict) else None,
            "hdriDir": (viewer_environment or {}).get("hdriDir") if isinstance(viewer_environment, dict) else None,
            "notes": (viewer_environment or {}).get("notes") if isinstance(viewer_environment, dict) else [],
        },
        "colorManagement": {
            "workingSpace": "ACEScg",
            "baseColorColorSpace": "sRGB",
            "dataMapColorSpace": "Linear",
            "displayTransform": "ACES 1.0 SDR Video",
        },
        "channelSoloMaps": {
            "baseColor": f"textures/{base_color_name}",
            "roughness": f"textures/{roughness_name}" if roughness_name else None,
            "metallic": f"textures/{metallic_name}" if metallic_name else None,
            "normal": f"textures/{normal_name}" if normal_name else None,
            "opacity": f"textures/{opacity_name}" if opacity_name else None,
        },
        "studioDefaultsSource": "glb_material_pbr",
        "textureEnhancement": texture_enhancement,
        "textureQuality": {
            "baseColorOriginal": base_color_original_report,
            "baseColorFinal": base_color_final_report,
            "trellisTexturePreserved": bool(has_glb_base_color_texture),
            "trellisTextureAvailable": bool(has_glb_base_color_texture),
            "viewerTintPreservesTexture": bool(
                not has_glb_base_color_texture or viewer_tint_source == "glb_baseColorFactor"
            ),
            "needsHighQualityTexturePass": bool(
                base_color_final_report["detailLevel"] in {"flat", "generated_or_scalar", "high_contrast_or_baked_lighting"}
            ),
        },
        "scaleNormalization": scale_normalization or {},
        "pivotPolicy": (scale_normalization or {}).get("pivot_policy", "bottom_center"),
        "groundAligned": bool((scale_normalization or {}).get("ground_aligned", True)),
        "cleanupApplied": bool(cleanup_metadata),
        "removedSmallComponents": int((cleanup_metadata or {}).get("removed_small_components") or 0),
        "validation": validation,
        "alphaTextureIgnored": alpha_texture_ignored,
    }
    write_json(output_path, payload)
    return payload
