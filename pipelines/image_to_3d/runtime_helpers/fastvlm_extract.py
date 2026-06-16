from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

IMAGE_TOKEN_INDEX = -200
DEFAULT_IMAGE_TOKEN = "<image>"
DEFAULT_IM_START_TOKEN = "<im_start>"
DEFAULT_IM_END_TOKEN = "<im_end>"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract semantic asset metadata with FastVLM.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-prompt", default="")
    parser.add_argument("--allowed-categories", default="")
    parser.add_argument("--model-id", default=os.getenv("FASTVLM_MODEL_ID", "apple/FastVLM-0.5B"))
    parser.add_argument("--revision", default=os.getenv("FASTVLM_REVISION", ""))
    parser.add_argument("--device", default=os.getenv("FASTVLM_DEVICE", "cuda"))
    parser.add_argument("--dtype", default=os.getenv("FASTVLM_DTYPE", "float16"))
    parser.add_argument("--max-new-tokens", type=int, default=int(os.getenv("FASTVLM_MAX_NEW_TOKENS", "512")))
    parser.add_argument("--temperature", type=float, default=float(os.getenv("FASTVLM_TEMPERATURE", "0.0")))
    parser.add_argument("--top-p", type=float, default=float(os.getenv("FASTVLM_TOP_P", "1.0")))
    parser.add_argument("--num-beams", type=int, default=int(os.getenv("FASTVLM_NUM_BEAMS", "1")))
    parser.add_argument("--check-runtime", action="store_true")
    return parser.parse_args()


def _allowed_categories(raw: str) -> list[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or [
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
    ]


def _build_metadata_prompt(source_prompt: str, allowed_categories: list[str]) -> str:
    allowed = ", ".join(allowed_categories)
    prompt_text = source_prompt.strip() or "unknown object"
    return (
        "Analyze this transparent object cutout for a VFX/animation background prop asset. "
        "Return only a valid JSON object, with no markdown and no explanation. "
        f"The user's source prompt is: {json.dumps(prompt_text)}. "
        f"object_category must be exactly one of: {allowed}. "
        "specific_type must be the most specific recognizable subtype or product form, not a repeat of object_category; "
        "for example use Triceratops for a horned dinosaur skull, Tyrannosaurus only when the object clearly appears to be a T-rex, "
        "Dinosaur Fossil when the exact species is uncertain, and Portrait Head for a human face/head. "
        "Do not write placeholder phrases like 'a description of ...'. "
        "All array fields must contain plain short strings, not nested objects. "
        "Use this schema: "
        '{"asset_name": string, "raw_category": string, "object_category": string, '
        '"category": string, "subcategory": string, "specific_type": string, '
        '"description": string, "visual_features": string[], "color_hints": string[], '
        '"material_hints": string[], "recommended_usage": string, "dcc_tags": string[]}.'
    )


def _build_demo_prompt() -> str:
    return os.getenv("FASTVLM_DEMO_PROMPT", "Describe this image in detail.").strip() or "Describe this image in detail."


def _build_qwen_prompt(user_prompt: str, *, use_im_start_end: bool) -> str:
    image_token = DEFAULT_IMAGE_TOKEN
    if use_im_start_end:
        image_token = f"{DEFAULT_IM_START_TOKEN}{DEFAULT_IMAGE_TOKEN}{DEFAULT_IM_END_TOKEN}"
    question = f"{image_token}\n{user_prompt}"
    return (
        "<|im_start|>system\n"
        "You are a helpful assistant.<|im_end|>\n"
        "<|im_start|>user\n"
        f"{question}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def _tokenizer_image_token(prompt: str, tokenizer: Any, return_tensors: str | None = None):
    prompt_chunks = [tokenizer(chunk).input_ids for chunk in prompt.split(DEFAULT_IMAGE_TOKEN)]

    def insert_separator(items: list[list[int]], sep: list[int]) -> list[int]:
        merged: list[int] = []
        for index, item in enumerate(items):
            if index:
                merged.extend(sep)
            merged.extend(item)
        return merged

    input_ids: list[int] = []
    offset = 0
    if prompt_chunks and prompt_chunks[0] and prompt_chunks[0][0] == tokenizer.bos_token_id:
        offset = 1
        input_ids.append(prompt_chunks[0][0])
    chunks = [chunk[offset:] for chunk in prompt_chunks]
    input_ids.extend(insert_separator(chunks, [IMAGE_TOKEN_INDEX]))

    if return_tensors == "pt":
        import torch

        return torch.tensor(input_ids, dtype=torch.long)
    if return_tensors is not None:
        raise ValueError(f"Unsupported tensor type: {return_tensors}")
    return input_ids


def _expand2square(image: Image.Image, background_color: tuple[int, int, int]) -> Image.Image:
    width, height = image.size
    if width == height:
        return image
    side = max(width, height)
    result = Image.new(image.mode, (side, side), background_color)
    result.paste(image, ((side - width) // 2, (side - height) // 2))
    return result


def _process_images(images: list[Image.Image], image_processor: Any, model_cfg: Any):
    image_aspect_ratio = getattr(model_cfg, "image_aspect_ratio", None)
    if image_aspect_ratio == "pad":
        processed = []
        background = tuple(int(value * 255) for value in image_processor.image_mean)
        for image in images:
            padded = _expand2square(image, background)
            processed.append(image_processor.preprocess(padded, return_tensors="pt")["pixel_values"][0])
        import torch

        return torch.stack(processed, dim=0)
    return image_processor(images, return_tensors="pt")["pixel_values"]


def _torch_dtype(torch_module: Any, name: str, device: str):
    value = name.strip().lower()
    if value == "auto":
        return torch_module.float16 if device == "cuda" else torch_module.float32
    if value in {"float16", "fp16", "half"}:
        return torch_module.float16
    if value in {"bfloat16", "bf16"}:
        return torch_module.bfloat16
    if value in {"float32", "fp32", "full"}:
        return torch_module.float32
    raise ValueError(f"Unsupported FASTVLM_DTYPE: {name}")


def _resolve_device(torch_module: Any, requested: str) -> str:
    requested = requested.strip().lower() or "cuda"
    if requested == "cuda" and torch_module.cuda.is_available():
        return "cuda"
    if requested == "mps" and getattr(torch_module.backends, "mps", None) and torch_module.backends.mps.is_available():
        return "mps"
    if requested in {"cpu", "cuda", "mps"}:
        return "cpu"
    return requested


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        value = json.loads(cleaned[start : end + 1])
        if isinstance(value, dict):
            return value
    raise ValueError("FastVLM output did not contain a JSON object")


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("name") or item.get("type") or item.get("description") or "").strip()
                if text:
                    values.append(text)
                continue
            text = str(item).strip()
            if text:
                values.append(text)
        return list(dict.fromkeys(values))
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[,;/]", value) if part.strip()]
        return parts or ([value.strip()] if value.strip() else [])
    return []


def _as_compact_string(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("type") or value.get("description") or "").strip()
    if isinstance(value, list):
        return ", ".join(_as_string_list(value)).strip()
    return str(value or "").strip()


def _sanitize_payload(payload: dict[str, Any], *, allowed_categories: list[str], source_prompt: str) -> dict[str, Any]:
    object_category = str(payload.get("object_category") or payload.get("category") or payload.get("raw_category") or "")
    object_category = object_category.strip().lower().replace(" ", "_")
    if object_category not in set(allowed_categories):
        object_category = "unknown"

    raw_category = str(payload.get("raw_category") or object_category or "unknown").strip() or "unknown"
    asset_name = str(payload.get("asset_name") or source_prompt or object_category or "generated_prop").strip()
    category = str(payload.get("category") or raw_category).strip() or raw_category

    return {
        "asset_name": asset_name,
        "raw_category": raw_category,
        "object_category": object_category,
        "category": category,
        "subcategory": str(payload.get("subcategory") or object_category).strip() or object_category,
        "specific_type": str(payload.get("specific_type") or source_prompt or object_category).strip() or object_category,
        "description": _as_compact_string(payload.get("description")),
        "visual_features": _as_string_list(payload.get("visual_features")),
        "color_hints": _as_string_list(payload.get("color_hints")),
        "material_hints": _as_string_list(payload.get("material_hints")),
        "recommended_usage": _as_compact_string(payload.get("recommended_usage")),
        "dcc_tags": _as_string_list(payload.get("dcc_tags")),
    }


def _fallback_payload_from_text(
    raw_text: str,
    *,
    allowed_categories: list[str],
    source_prompt: str,
    parse_error: Exception,
) -> dict[str, Any]:
    haystack = f"{source_prompt} {raw_text}".lower().replace("-", "_")
    object_category = "unknown"
    for category in allowed_categories:
        if category != "unknown" and category.lower() in haystack:
            object_category = category
            break
    prompt_or_category = source_prompt.strip() or object_category
    return {
        "asset_name": prompt_or_category or "generated_prop",
        "raw_category": prompt_or_category or object_category,
        "object_category": object_category,
        "category": object_category,
        "subcategory": object_category,
        "specific_type": prompt_or_category or object_category,
        "description": raw_text.strip()[:600],
        "visual_features": [],
        "color_hints": [],
        "material_hints": [],
        "recommended_usage": "background prop",
        "dcc_tags": ["background_prop", object_category],
        "vlm_parse_status": "invalid_json_fallback",
        "vlm_parse_error": str(parse_error),
    }


def _load_fastvlm(args: argparse.Namespace):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = _resolve_device(torch, args.device)
    dtype = _torch_dtype(torch, args.dtype, device)
    revision_kwargs = {"revision": args.revision} if args.revision else {}
    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True, **revision_kwargs)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        trust_remote_code=True,
        dtype=dtype,
        low_cpu_mem_usage=True,
        **revision_kwargs,
    )
    model.to(device)
    model.eval()
    return torch, tokenizer, model, device, dtype


def _generate_fastvlm_text(
    *,
    torch: Any,
    tokenizer: Any,
    model: Any,
    device: str,
    image: Image.Image,
    image_tensor: Any,
    prompt_text: str,
    args: argparse.Namespace,
) -> str:
    prompt = _build_qwen_prompt(
        prompt_text,
        use_im_start_end=bool(getattr(model.config, "mm_use_im_start_end", False)),
    )
    input_ids = _tokenizer_image_token(prompt, tokenizer, return_tensors="pt").unsqueeze(0).to(device)

    if tokenizer.pad_token_id is not None:
        model.generation_config.pad_token_id = tokenizer.pad_token_id

    generate_kwargs: dict[str, Any] = {
        "inputs": input_ids,
        "images": image_tensor,
        "image_sizes": [image.size],
        "do_sample": args.temperature > 0,
        "num_beams": args.num_beams,
        "max_new_tokens": args.max_new_tokens,
        "use_cache": True,
    }
    if args.temperature > 0:
        generate_kwargs["temperature"] = args.temperature
        generate_kwargs["top_p"] = args.top_p

    with torch.inference_mode():
        output_ids = model.generate(**generate_kwargs)
    return tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0].strip()


def _run_hf_fastvlm(args: argparse.Namespace) -> dict[str, Any]:
    allowed = _allowed_categories(args.allowed_categories)
    torch, tokenizer, model, device, dtype = _load_fastvlm(args)

    if args.check_runtime:
        return {
            "vlm_backend": "huggingface_transformers",
            "vlm_model": args.model_id,
            "vlm_runtime_check": "ok",
            "vlm_device": device,
            "vlm_dtype": str(dtype).replace("torch.", ""),
        }

    image_path = Path(args.image).expanduser().resolve()
    image = Image.open(image_path).convert("RGB")
    image_processor = model.get_vision_tower().image_processor
    image_tensor = _process_images([image], image_processor, model.config).to(device=device, dtype=dtype)

    demo_prompt = _build_demo_prompt()
    demo_text = _generate_fastvlm_text(
        torch=torch,
        tokenizer=tokenizer,
        model=model,
        device=device,
        image=image,
        image_tensor=image_tensor,
        prompt_text=demo_prompt,
        args=args,
    )

    metadata_prompt = _build_metadata_prompt(args.source_prompt, allowed)
    raw_text = _generate_fastvlm_text(
        torch=torch,
        tokenizer=tokenizer,
        model=model,
        device=device,
        image=image,
        image_tensor=image_tensor,
        prompt_text=metadata_prompt,
        args=args,
    )
    try:
        parsed_payload = _extract_json(raw_text)
        payload = _sanitize_payload(parsed_payload, allowed_categories=allowed, source_prompt=args.source_prompt)
        payload["vlm_parse_status"] = "json"
    except Exception as exc:  # noqa: BLE001
        payload = _fallback_payload_from_text(
            raw_text,
            allowed_categories=allowed,
            source_prompt=args.source_prompt,
            parse_error=exc,
        )
    payload.update(
        {
            "vlm_backend": "huggingface_transformers",
            "vlm_model": args.model_id,
            "vlm_device": device,
            "vlm_dtype": str(dtype).replace("torch.", ""),
            "vlm_raw_text": raw_text[:4000],
            "fastvlm_demo_prompt": demo_prompt,
            "fastvlm_demo_text": demo_text,
        }
    )
    return payload


def main() -> int:
    args = _parse_args()
    try:
        payload = _run_hf_fastvlm(args)
    except Exception as exc:  # noqa: BLE001
        print(f"FastVLM extraction failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
