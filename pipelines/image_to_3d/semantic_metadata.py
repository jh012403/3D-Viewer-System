from __future__ import annotations

import json
import os
import re
import shlex
import string
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from pipelines.common.env import build_runtime_env
from pipelines.common.io import write_json


ALLOWED_CATEGORIES = {
    "chair",
    "sneaker",
    "snack_package",
    "dinosaur",
    "small_prop",
    "toy",
    "bottle",
    "box",
    "bag",
    "human_head",
    "unknown",
}

SYNONYM_MAP: dict[str, tuple[str, ...]] = {
    "chair": ("chair", "seat", "stool", "armchair", "bench"),
    "sneaker": ("sneaker", "shoe", "trainer", "running shoe", "footwear"),
    "snack_package": ("snack", "chips", "package", "packet", "pouch", "wrapper", "bag of"),
    "dinosaur": ("dinosaur", "t-rex", "trex", "tyrannosaurus", "raptor", "triceratops"),
    "small_prop": ("prop", "object", "figurine", "decor", "ornament"),
    "toy": ("toy", "doll", "figure", "plush", "model"),
    "bottle": ("bottle", "can", "container", "jar", "cup"),
    "box": ("box", "carton", "cube", "crate"),
    "bag": ("bag", "backpack", "handbag", "sack", "tote"),
    "human_head": ("human", "person", "face", "portrait", "head", "bust", "selfie", "man", "woman"),
}

CATEGORY_LABELS = {
    "chair": "Furniture",
    "sneaker": "Footwear",
    "snack_package": "Packaging",
    "dinosaur": "Animal Prop",
    "small_prop": "Small Prop",
    "toy": "Toy",
    "bottle": "Container",
    "box": "Container",
    "bag": "Accessory",
    "human_head": "Character Prop",
    "unknown": "Uncategorized Prop",
}

MATERIAL_HINTS = {
    "chair": ["wood", "fabric", "painted surface"],
    "sneaker": ["fabric", "rubber", "synthetic"],
    "snack_package": ["plastic wrapper", "printed packaging"],
    "dinosaur": ["bone", "fossil", "matte porous surface"],
    "small_prop": ["mixed material"],
    "toy": ["plastic", "painted surface"],
    "bottle": ["plastic", "glass", "metal"],
    "box": ["cardboard", "paper"],
    "bag": ["fabric", "leather", "synthetic"],
    "human_head": ["skin", "hair", "fabric"],
    "unknown": ["mixed material"],
}

DCC_TAGS = {
    "chair": ["background_prop", "furniture", "set_dressing"],
    "sneaker": ["background_prop", "wardrobe", "small_prop"],
    "snack_package": ["background_prop", "packaging", "set_dressing"],
    "dinosaur": ["background_prop", "creature_prop", "museum"],
    "small_prop": ["background_prop", "set_dressing"],
    "toy": ["background_prop", "toy", "set_dressing"],
    "bottle": ["background_prop", "container", "set_dressing"],
    "box": ["background_prop", "container", "set_dressing"],
    "bag": ["background_prop", "accessory", "set_dressing"],
    "human_head": ["character_head", "portrait_scan", "lookdev_test", "experimental"],
    "unknown": ["background_prop", "uncategorized"],
}

DISPLAY_CATEGORY_LABELS = {
    "chair": "Chair",
    "sneaker": "Sneaker",
    "snack_package": "Snack Package",
    "dinosaur": "Dinosaur",
    "small_prop": "Small Prop",
    "toy": "Toy",
    "bottle": "Bottle",
    "box": "Box",
    "bag": "Bag",
    "human_head": "Human Head",
    "unknown": "Generated Prop",
}

DISPLAY_DEFAULTS = {
    "human_head": {
        "type": "Portrait Head",
        "visual": "Single-image human head reconstruction with visible facial features.",
        "material": "Skin, hair, and fabric surfaces for preview lookdev.",
        "usage": "Lookdev test, portrait scan preview, non-hero character placeholder.",
    },
    "dinosaur": {
        "type": "Dinosaur Fossil",
        "visual": "Fossilized skull or skeletal museum specimen.",
        "material": "Aged bone or matte fossil surface.",
        "usage": "Museum scene, set dressing, background creature prop.",
    },
    "chair": {
        "type": "Chair",
        "visual": "Recognizable furniture shape for interior set dressing.",
        "material": "Wood, fabric, painted or worn surface.",
        "usage": "Interior scene, layout prop, background furniture.",
    },
    "sneaker": {
        "type": "Sneaker",
        "visual": "Low-profile footwear shape with layered panels.",
        "material": "Fabric, rubber, synthetic surface.",
        "usage": "Wardrobe prop, room dressing, product layout.",
    },
    "snack_package": {
        "type": "Snack Package",
        "visual": "Printed package shape with compact shelf-ready silhouette.",
        "material": "Plastic wrapper or printed packaging.",
        "usage": "Store shelf, desk clutter, kitchen set dressing.",
    },
    "unknown": {
        "type": "Generated Prop",
        "visual": "Object silhouette suitable for background placement.",
        "material": "Mixed material surface.",
        "usage": "Background prop, set dressing, previz layout.",
    },
}


@dataclass(frozen=True)
class ScalePivotPolicy:
    category_id: str
    target_dimension: str
    target_size_m: float | None
    pivot_policy: str = "bottom_center"
    ground_alignment: bool = True

    def to_json(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "target_dimension": self.target_dimension,
            "target_size_m": self.target_size_m,
            "pivot_policy": self.pivot_policy,
            "ground_alignment": self.ground_alignment,
        }


POLICIES: dict[str, ScalePivotPolicy] = {
    "chair": ScalePivotPolicy("chair", "height", 1.0),
    "sneaker": ScalePivotPolicy("sneaker", "length", 0.3),
    "snack_package": ScalePivotPolicy("snack_package", "height", 0.25),
    "dinosaur": ScalePivotPolicy("dinosaur", "height", 1.5),
    "small_prop": ScalePivotPolicy("small_prop", "height", 0.2),
    "toy": ScalePivotPolicy("toy", "height", 0.25),
    "bottle": ScalePivotPolicy("bottle", "height", 0.25),
    "box": ScalePivotPolicy("box", "height", 0.3),
    "bag": ScalePivotPolicy("bag", "height", 0.45),
    "human_head": ScalePivotPolicy("human_head", "height", 0.28),
    "unknown": ScalePivotPolicy("unknown", "height", 1.0),
}


def _clean_text(value: str) -> str:
    normalized = value.lower().strip()
    normalized = normalized.translate(str.maketrans({char: " " for char in string.punctuation}))
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_category(*values: str | None) -> dict[str, Any]:
    candidates = [_clean_text(value or "") for value in values if value]
    for candidate in candidates:
        if candidate in ALLOWED_CATEGORIES and candidate != "unknown":
            return {
                "normalized_category_id": candidate,
                "raw_category": candidate,
                "normalization_method": "exact_match",
            }

    joined = " ".join(candidates)
    for category_id, keywords in SYNONYM_MAP.items():
        for keyword in keywords:
            if keyword in joined:
                return {
                    "normalized_category_id": category_id,
                    "raw_category": joined or keyword,
                    "normalization_method": f"keyword:{keyword}",
                }

    return {
        "normalized_category_id": "unknown",
        "raw_category": joined or "unknown",
        "normalization_method": "exact_match" if joined == "unknown" else "fallback_unknown",
    }


def category_policy(category_id: str | None) -> ScalePivotPolicy:
    return POLICIES.get(category_id or "unknown", POLICIES["unknown"])


def _asset_name(source_prompt: str | None, category_id: str) -> str:
    raw = source_prompt or category_id or "generated_prop"
    cleaned = _clean_text(raw)
    slug = "_".join(token for token in cleaned.split()[:5] if token)
    return slug or "generated_prop"


def _image_color_hints(image_path: Path | None) -> list[str]:
    if image_path is None or not image_path.exists():
        return []
    try:
        with Image.open(image_path) as image:
            rgba = image.convert("RGBA").resize((96, 96))
    except Exception:
        return []

    pixels = np.asarray(rgba)
    alpha = pixels[:, :, 3]
    mask = alpha > 16
    if not np.any(mask):
        mask = np.ones(alpha.shape, dtype=bool)

    rgb = pixels[:, :, :3][mask]
    if len(rgb) == 0:
        return []
    mean = rgb.mean(axis=0)
    brightness = float(mean.mean())
    dominant = _name_color(mean)
    hints = [dominant]
    if brightness < 72:
        hints.append("dark")
    elif brightness > 190:
        hints.append("light")
    return list(dict.fromkeys(hints))


def _name_color(rgb: np.ndarray) -> str:
    r, g, b = [float(value) for value in rgb[:3]]
    if max(r, g, b) - min(r, g, b) < 18:
        if r < 70:
            return "black"
        if r > 205:
            return "white"
        return "gray"
    if r > g and r > b:
        return "red" if g < 120 else "orange"
    if g > r and g > b:
        return "green"
    if b > r and b > g:
        return "blue"
    if r > 150 and g > 130 and b < 110:
        return "yellow"
    return "mixed color"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dcc_tags(vlm_value: Any, category_id: str) -> list[str]:
    tags = list(DCC_TAGS.get(category_id, DCC_TAGS["unknown"]))
    for raw_tag in _as_list(vlm_value):
        cleaned = _clean_text(raw_tag).replace(" ", "_")
        if not cleaned:
            continue
        if len(cleaned) > 40 or len(cleaned.split("_")) > 4:
            continue
        tags.append(cleaned)
    return list(dict.fromkeys(tags))


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        return _first_text(value[0]) if value else ""
    if isinstance(value, dict):
        return str(value.get("name") or value.get("type") or value.get("description") or "").strip()
    return str(value or "").strip()


def _is_generic_metadata_text(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return (
        not text
        or text.startswith("a description of")
        or text.startswith("detailed description")
        or "typically to be displayed" in text
        or "showcasing its anatomy" in text
    )


def _display_default(category_id: str, key: str) -> str:
    defaults = DISPLAY_DEFAULTS.get(category_id) or DISPLAY_DEFAULTS["unknown"]
    return defaults[key]


def _refine_specific_type(category_id: str, *values: Any) -> str:
    joined = " ".join(_first_text(value) for value in values).lower()
    if category_id == "human_head":
        candidate = _first_text(values[0] if values else "").strip()
        generic = {"human", "person", "face", "head", "portrait", "human head", "human_head"}
        if not _is_generic_metadata_text(candidate) and _clean_text(candidate) not in generic:
            return candidate
        if re.search(r"bust|shoulders|neck", joined):
            return "Head And Shoulders"
        return _display_default(category_id, "type")

    if category_id == "dinosaur":
        if "triceratops" in joined:
            return "Triceratops"
        if re.search(r"ceratopsian|ceratops|frill|horned dinosaur|three horn", joined):
            return "Ceratopsian"
        if re.search(r"\bhorn|horns|skull", joined):
            return "Horned Dinosaur"
        if re.search(r"tyrannosaurus|t[\s_-]?rex", joined):
            return "Tyrannosaurus"
        if "velociraptor" in joined or "raptor" in joined:
            return "Velociraptor"
        candidate = _first_text(values[0] if values else "").strip()
        if not _is_generic_metadata_text(candidate) and _clean_text(candidate) not in {category_id, "dinosaur"}:
            return candidate
        if re.search(r"fossil|skeleton|skeletal|bone", joined):
            return "Dinosaur Fossil"
        return _display_default(category_id, "type")

    candidate = _first_text(values[0] if values else "").strip()
    if not _is_generic_metadata_text(candidate) and _clean_text(candidate) != category_id:
        return candidate
    return _display_default(category_id, "type")


def _display_summary(category_id: str, value: Any, fallback_key: str) -> str:
    text = _first_text(value)
    word_count = len([token for token in text.split() if token])
    if _is_generic_metadata_text(text) or (fallback_key != "material" and word_count < 3):
        return _display_default(category_id, fallback_key)
    return re.sub(r"\s+", " ", text).strip()


def _read_candidate_metadata(temp_dir: Path, candidate_id: str | None) -> dict[str, Any]:
    if not candidate_id:
        return {}
    safe_id = candidate_id.strip()
    if not safe_id or "/" in safe_id or "\\" in safe_id or safe_id.startswith("."):
        return {}
    metadata_path = temp_dir / "sam2_candidates" / "candidates" / safe_id / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fastvlm_helper_script() -> Path:
    return (_project_root() / "pipelines" / "image_to_3d" / "runtime_helpers" / "fastvlm_extract.py").resolve()


def _fastvlm_args(image_path: Path, source_prompt: str) -> list[str] | None:
    legacy_command = os.getenv("FASTVLM_METADATA_CMD", "").strip()
    if legacy_command:
        command = shlex.split(legacy_command)
    else:
        command = shlex.split(os.getenv("FASTVLM_CMD", "conda run -n trellis2 python").strip())
        if not command:
            command = [sys.executable]
        command.append(str(_fastvlm_helper_script()))

    args = command + [
        "--image",
        str(image_path),
        "--source-prompt",
        source_prompt,
        "--allowed-categories",
        ",".join(sorted(ALLOWED_CATEGORIES)),
    ]
    model_id = os.getenv("FASTVLM_MODEL_ID", "").strip()
    if model_id:
        args += ["--model-id", model_id]
    revision = os.getenv("FASTVLM_REVISION", "").strip()
    if revision:
        args += ["--revision", revision]
    device = os.getenv("FASTVLM_DEVICE", "").strip()
    if device:
        args += ["--device", device]
    dtype = os.getenv("FASTVLM_DTYPE", "").strip()
    if dtype:
        args += ["--dtype", dtype]
    max_new_tokens = os.getenv("FASTVLM_MAX_NEW_TOKENS", "").strip()
    if max_new_tokens:
        args += ["--max-new-tokens", max_new_tokens]
    temperature = os.getenv("FASTVLM_TEMPERATURE", "").strip()
    if temperature:
        args += ["--temperature", temperature]
    top_p = os.getenv("FASTVLM_TOP_P", "").strip()
    if top_p:
        args += ["--top-p", top_p]
    num_beams = os.getenv("FASTVLM_NUM_BEAMS", "").strip()
    if num_beams:
        args += ["--num-beams", num_beams]
    return args


def _run_fastvlm_if_configured(image_path: Path | None, source_prompt: str) -> dict[str, Any]:
    if image_path is None or not image_path.exists():
        return {"vlm_status": "fallback_no_cutout_for_fastvlm"}

    args = _fastvlm_args(image_path, source_prompt)
    if not args:
        return {"vlm_status": "fallback_no_fastvlm_cmd"}

    timeout = int(os.getenv("FASTVLM_TIMEOUT_SEC", "900").strip() or "900")
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=build_runtime_env(os.environ.copy()),
        )
    except Exception as exc:  # noqa: BLE001
        return {"vlm_status": "fallback_fastvlm_exception", "vlm_error": str(exc)}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return {
            "vlm_status": "fallback_fastvlm_failed",
            "vlm_error": detail[-1] if detail else f"exit_code_{completed.returncode}",
        }

    raw = (completed.stdout or "").strip()
    try:
        return {**json.loads(raw), "vlm_status": "fastvlm_completed"}
    except json.JSONDecodeError:
        for line in reversed(raw.splitlines()):
            try:
                return {**json.loads(line), "vlm_status": "fastvlm_completed"}
            except json.JSONDecodeError:
                continue
    return {"vlm_status": "fallback_fastvlm_invalid_json"}


def _write_fastvlm_demo_page(
    *,
    output_path: Path,
    image_path: Path | None,
    source_prompt: str,
    vlm_payload: dict[str, Any],
) -> str:
    page_path = output_path.with_name("fastvlm_result.html")
    image_name = "fastvlm_input.png"
    image_written = False
    if image_path is not None and image_path.exists():
        try:
            with Image.open(image_path) as image:
                image.save(output_path.with_name(image_name), format="PNG")
            image_written = True
        except Exception:
            image_written = False

    demo_text = str(
        vlm_payload.get("fastvlm_demo_text")
        or vlm_payload.get("vlm_raw_text")
        or vlm_payload.get("vlm_error")
        or "FastVLM did not return a demo description."
    ).strip()
    demo_prompt = str(vlm_payload.get("fastvlm_demo_prompt") or "Describe this image in detail.").strip()
    model = str(vlm_payload.get("vlm_model") or os.getenv("FASTVLM_MODEL_ID", "apple/FastVLM-0.5B")).strip()
    status = str(vlm_payload.get("vlm_status") or "unknown").strip()
    image_html = (
        f'<img class="preview" src="{escape(image_name)}" alt="FastVLM input image">'
        if image_written
        else '<div class="preview empty">Input image preview unavailable</div>'
    )
    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>FastVLM Result</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin:0; background:#0b1020; color:#eef4ff; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 56px; }}
    .eyebrow {{ color:#62ddff; font-size:12px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }}
    h1 {{ margin:8px 0 18px; font-size:30px; line-height:1.15; }}
    .grid {{ display:grid; grid-template-columns: minmax(220px, 320px) minmax(0,1fr); gap:18px; align-items:start; }}
    .panel {{ border:1px solid rgba(98,221,255,.2); border-radius:12px; background:rgba(255,255,255,.045); padding:16px; }}
    .preview {{ width:100%; border-radius:10px; background:#151b2d; display:block; }}
    .empty {{ min-height:220px; display:grid; place-items:center; color:#8fa3c6; }}
    dl {{ display:grid; grid-template-columns: 110px minmax(0,1fr); gap:8px 12px; margin:0; color:#b6c4df; font-size:13px; }}
    dt {{ color:#6f85ad; font-weight:800; }}
    dd {{ margin:0; overflow-wrap:anywhere; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; margin:0; font-size:16px; line-height:1.65; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    @media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">FastVLM Demo Output</div>
    <h1>Image Description</h1>
    <div class="grid">
      <section class="panel">
        {image_html}
        <dl style="margin-top:14px">
          <dt>Prompt</dt><dd>{escape(demo_prompt)}</dd>
          <dt>Source</dt><dd>{escape(source_prompt or "-")}</dd>
          <dt>Model</dt><dd>{escape(model)}</dd>
          <dt>Status</dt><dd>{escape(status)}</dd>
        </dl>
      </section>
      <section class="panel">
        <pre>{escape(demo_text)}</pre>
      </section>
    </div>
  </main>
</body>
</html>
"""
    page_path.write_text(html, encoding="utf-8")
    return page_path.name


def build_asset_metadata(
    *,
    output_path: Path,
    cutout_image_path: Path | None,
    temp_dir: Path,
    source_prompt: str | None,
    candidate_id: str | None,
    segmentation_model: str,
    generation_model: str,
) -> dict[str, Any]:
    candidate_metadata = _read_candidate_metadata(temp_dir, candidate_id)
    candidate_label = str(candidate_metadata.get("label") or candidate_metadata.get("text_prompt") or "")
    prompt = (source_prompt or candidate_metadata.get("text_prompt") or "").strip()
    vlm_payload = _run_fastvlm_if_configured(cutout_image_path, prompt)
    vlm_category = str(
        vlm_payload.get("object_category")
        or vlm_payload.get("category")
        or vlm_payload.get("raw_category")
        or ""
    )
    normalized = normalize_category(vlm_category, candidate_label, prompt)
    category_id = str(normalized["normalized_category_id"])
    color_hints = _image_color_hints(cutout_image_path)
    specific_type = _refine_specific_type(
        category_id,
        vlm_payload.get("specific_type"),
        prompt,
        vlm_payload.get("description"),
        vlm_payload.get("visual_features"),
        vlm_payload.get("raw_category"),
    )
    visual_features = vlm_payload.get("visual_features") or color_hints
    material_hints = vlm_payload.get("material_hints") or MATERIAL_HINTS.get(category_id, MATERIAL_HINTS["unknown"])
    recommended_usage = vlm_payload.get("recommended_usage") or "background prop, set dressing, previz, layout blocking"

    payload = {
        "asset_name": _asset_name(prompt, category_id),
        "raw_category": vlm_payload.get("raw_category") or normalized["raw_category"],
        "normalized_category_id": category_id,
        "category": vlm_payload.get("category") or CATEGORY_LABELS.get(category_id, "Uncategorized Prop"),
        "subcategory": vlm_payload.get("subcategory") or category_id.replace("_", " "),
        "specific_type": specific_type,
        "description": vlm_payload.get("description")
        or f"AI-generated background prop asset for {prompt or category_id.replace('_', ' ')}.",
        "visual_features": visual_features,
        "color_hints": vlm_payload.get("color_hints") or color_hints,
        "material_hints": material_hints,
        "recommended_usage": recommended_usage,
        "display_category": DISPLAY_CATEGORY_LABELS.get(category_id, "Generated Prop"),
        "display_type": specific_type,
        "display_visual_summary": _display_summary(category_id, visual_features, "visual"),
        "display_material_summary": _display_summary(category_id, material_hints, "material"),
        "display_usage_summary": _display_summary(category_id, recommended_usage, "usage"),
        "dcc_tags": _dcc_tags(vlm_payload.get("dcc_tags"), category_id),
        "source_prompt": prompt,
        "segmentation_model": segmentation_model,
        "vlm_model": vlm_payload.get("vlm_model")
        or os.getenv("FASTVLM_MODEL_NAME", "").strip()
        or "metadata_fallback_no_fastvlm",
        "vlm_backend": vlm_payload.get("vlm_backend"),
        "vlm_status": vlm_payload.get("vlm_status"),
        "vlm_parse_status": vlm_payload.get("vlm_parse_status"),
        "vlm_device": vlm_payload.get("vlm_device"),
        "vlm_dtype": vlm_payload.get("vlm_dtype"),
        "vlm_raw_text": vlm_payload.get("vlm_raw_text"),
        "fastvlm_demo_prompt": vlm_payload.get("fastvlm_demo_prompt"),
        "fastvlm_demo_text": vlm_payload.get("fastvlm_demo_text"),
        "vlm_error": vlm_payload.get("vlm_error"),
        "vlm_parse_error": vlm_payload.get("vlm_parse_error"),
        "generation_model": generation_model,
        "normalization_method": normalized["normalization_method"],
    }
    payload["fastvlm_result_file"] = _write_fastvlm_demo_page(
        output_path=output_path,
        image_path=cutout_image_path,
        source_prompt=prompt,
        vlm_payload=vlm_payload,
    )
    write_json(output_path, payload)
    return payload
