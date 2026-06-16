from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.image_to_3d.foreground_model_wrapper import _build_result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract foreground mask with official SAM3 text-prompt image segmentation.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sam3-repo-dir", required=True)
    parser.add_argument("--model-id", default="facebook/sam3")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--text-prompt", required=True)
    parser.add_argument("--text-prompt-alias", action="append", default=[])
    parser.add_argument("--confidence-threshold", type=float, default=0.5)
    parser.add_argument("--fallback-confidence-threshold", type=float)
    parser.add_argument("--merge-mode", choices=["best", "union"], default="best")
    parser.add_argument("--dump-candidates-dir")
    parser.add_argument("--max-candidates", type=int, default=1)
    return parser.parse_args()


def _as_numpy(value: object) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if str(getattr(value, "dtype", "")) in {"torch.bfloat16", "torch.float16"} and hasattr(value, "float"):
        value = value.float()
    if hasattr(value, "cpu"):
        value = value.cpu()
    return np.asarray(value)


def _normalize_mask(mask: object, height: int, width: int) -> np.ndarray:
    array = _as_numpy(mask)
    array = np.squeeze(array)
    if array.ndim != 2:
        raise RuntimeError(f"Unexpected SAM3 mask shape: {array.shape}")
    mask_bool = array > 0
    if mask_bool.shape != (height, width):
        mask_image = Image.fromarray((mask_bool.astype(np.uint8) * 255), mode="L")
        mask_image = mask_image.resize((width, height), Image.Resampling.NEAREST)
        mask_bool = np.asarray(mask_image) > 127
    return mask_bool


def _bbox_from_mask(mask_bool: np.ndarray) -> list[float]:
    ys, xs = np.nonzero(mask_bool)
    if len(xs) == 0 or len(ys) == 0:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        float(xs.min()),
        float(ys.min()),
        float(xs.max() - xs.min() + 1),
        float(ys.max() - ys.min() + 1),
    ]


def _border_touch_count(mask_bool: np.ndarray, margin: int = 4) -> int:
    ys, xs = np.nonzero(mask_bool)
    if len(xs) == 0 or len(ys) == 0:
        return 4
    height, width = mask_bool.shape
    return int(ys.min() <= margin) + int(xs.min() <= margin) + int(xs.max() >= width - margin - 1) + int(ys.max() >= height - margin - 1)


def _background_rgb(rgb_image: Image.Image) -> list[int]:
    image_array = np.asarray(rgb_image).astype(np.float32)
    height, width, _ = image_array.shape
    border_width = max(4, min(height, width) // 32)
    border_samples = np.concatenate(
        [
            image_array[:border_width, :, :].reshape(-1, 3),
            image_array[-border_width:, :, :].reshape(-1, 3),
            image_array[:, :border_width, :].reshape(-1, 3),
            image_array[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    return [int(round(value)) for value in np.median(border_samples, axis=0).tolist()]


def _apply_mask_rgba(rgb_image: Image.Image, mask_bool: np.ndarray) -> Image.Image:
    mask_image = Image.fromarray((mask_bool.astype(np.uint8) * 255), mode="L")
    rgba = rgb_image.convert("RGBA")
    rgba.putalpha(mask_image)
    return rgba


def _overlay_image(rgb_image: Image.Image, mask_bool: np.ndarray) -> Image.Image:
    base = np.asarray(rgb_image.convert("RGB")).astype(np.float32)
    tint = np.zeros_like(base)
    tint[..., 0] = 255.0
    tint[..., 1] = 55.0
    tint[..., 2] = 35.0
    alpha = mask_bool.astype(np.float32) * 0.48
    composed = np.clip((1.0 - alpha[..., None]) * base + alpha[..., None] * tint, 0.0, 255.0).astype(np.uint8)
    return Image.fromarray(composed, mode="RGB")


def _preview_image(image: Image.Image, *, max_side: int = 960) -> Image.Image:
    preview = image.copy()
    width, height = preview.size
    longest_side = max(width, height)
    if longest_side > max_side:
        scale = max_side / float(longest_side)
        preview = preview.resize(
            (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
            Image.Resampling.LANCZOS,
        )
    return preview


def _candidate_id(index: int) -> str:
    return f"sam3_text_{index:04d}"


def _write_candidate_pack(
    *,
    dump_dir: Path,
    rgb_image: Image.Image,
    candidates: list[dict[str, Any]],
    max_candidates: int,
) -> list[dict[str, Any]]:
    dump_dir.mkdir(parents=True, exist_ok=True)
    selected_candidates = sorted(
        candidates,
        key=lambda item: float(item.get("quality_score") or item.get("score") or 0.0),
        reverse=True,
    )
    selected_candidates = selected_candidates[: max(1, int(max_candidates))]

    packs: list[dict[str, Any]] = []
    for pack_index, candidate in enumerate(selected_candidates):
        index = int(candidate.get("index") or 0)
        candidate_id = _candidate_id(pack_index)
        candidate_dir = dump_dir / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)

        mask_bool = np.asarray(candidate["segmentation"], dtype=bool)
        mask_path = candidate_dir / "mask.png"
        segmented_path = candidate_dir / "segmented.png"
        segmented_preview_path = candidate_dir / "segmented_preview.png"
        overlay_path = candidate_dir / "overlay.png"
        metadata_path = candidate_dir / "metadata.json"

        Image.fromarray((mask_bool.astype(np.uint8) * 255), mode="L").save(mask_path)
        segmented_image = _apply_mask_rgba(rgb_image, mask_bool)
        segmented_image.save(segmented_path)
        _preview_image(segmented_image).save(segmented_preview_path)
        _overlay_image(rgb_image, mask_bool).save(overlay_path)

        payload = {
            "candidate_id": candidate_id,
            "pass_name": "sam3_text",
            "index": index,
            "label": candidate.get("label"),
            "source": "sam3_text_prompt",
            "text_prompt": candidate.get("text_prompt"),
            "bbox": candidate.get("bbox"),
            "detection_score": float(candidate.get("score") or 0.0),
            "score": float(candidate.get("score") or 0.0),
            "quality_score": float(candidate.get("quality_score") or candidate.get("score") or 0.0),
            "area_ratio": float(candidate.get("area_ratio") or 0.0),
            "border_touch_count": int(candidate.get("border_touch_count") or 0),
            "predicted_iou": float(candidate.get("score") or 0.0),
            "stability_score": float(candidate.get("score") or 0.0),
            "mask_path": str(mask_path),
            "segmented_path": str(segmented_path),
            "segmented_preview_path": str(segmented_preview_path),
            "overlay_path": str(overlay_path),
        }
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        packs.append(payload)

    (dump_dir / "candidates_summary.json").write_text(json.dumps({"candidates": packs}, indent=2), encoding="utf-8")
    return packs


def _extract_instances(
    *,
    output: dict[str, object],
    image_size: tuple[int, int],
    text_prompt: str,
    confidence_threshold: float,
) -> list[dict[str, Any]]:
    width, height = image_size
    masks = output.get("masks")
    if masks is None:
        return []
    masks_array = list(masks)
    score_values = _as_numpy(output.get("scores", [])).reshape(-1).tolist()

    candidates: list[dict[str, Any]] = []
    for index, mask_item in enumerate(masks_array):
        score = float(score_values[index]) if index < len(score_values) else 0.0
        if score < confidence_threshold:
            continue
        mask_bool = _normalize_mask(mask_item, height, width)
        if not mask_bool.any():
            continue
        quality_score = _candidate_quality_score(
            confidence=score,
            area_ratio=float(mask_bool.mean()),
            border_touch_count=_border_touch_count(mask_bool),
            text_prompt=text_prompt,
        )
        candidates.append(
            {
                "index": index,
                "segmentation": mask_bool,
                "area": int(mask_bool.sum()),
                "area_ratio": float(mask_bool.mean()),
                "bbox": _bbox_from_mask(mask_bool),
                "score": score,
                "quality_score": quality_score,
                "border_touch_count": _border_touch_count(mask_bool),
                "label": f"{text_prompt} ({score:.2f})",
                "text_prompt": text_prompt,
            }
        )
    return candidates


def _candidate_quality_score(
    *,
    confidence: float,
    area_ratio: float,
    border_touch_count: int,
    text_prompt: str,
) -> float:
    """Rank masks for object cutouts, not just detector confidence.

    SAM3 sometimes returns a high-confidence but overly broad mask for a vague
    prompt. A small amount of geometry-aware scoring helps the more specific
    fallback prompts win on cluttered museum/product photos.
    """

    score = float(confidence)
    if area_ratio < 0.015:
        score -= 0.28
    elif area_ratio < 0.035:
        score -= 0.12
    elif 0.08 <= area_ratio <= 0.58:
        score += 0.04
    elif area_ratio > 0.72:
        score -= 0.18
    elif area_ratio > 0.62:
        score -= 0.08

    score -= min(4, int(border_touch_count)) * 0.045

    prompt = text_prompt.lower()
    if any(token in prompt for token in ("fossil", "skull", "skeleton", "bones", "triceratops", "ceratopsian", "horned")):
        score += 0.055
    if any(token in prompt for token in ("thing", "object", "item")):
        score -= 0.04
    return float(score)


def _union_candidate(candidates: list[dict[str, Any]], text_prompt: str) -> dict[str, Any]:
    union_mask = np.zeros_like(np.asarray(candidates[0]["segmentation"], dtype=bool))
    scores: list[float] = []
    for candidate in candidates:
        union_mask |= np.asarray(candidate["segmentation"], dtype=bool)
        scores.append(float(candidate.get("score") or 0.0))
    score = max(scores) if scores else 0.0
    return {
        "index": 0,
        "segmentation": union_mask,
        "area": int(union_mask.sum()),
        "area_ratio": float(union_mask.mean()),
        "bbox": _bbox_from_mask(union_mask),
        "score": score,
        "quality_score": _candidate_quality_score(
            confidence=score,
            area_ratio=float(union_mask.mean()),
            border_touch_count=_border_touch_count(union_mask),
            text_prompt=text_prompt,
        ),
        "border_touch_count": _border_touch_count(union_mask),
        "label": f"{text_prompt} ({score:.2f})",
        "text_prompt": text_prompt,
    }


def _load_sam3_model(model_id: str, device: str) -> object:
    from sam3.model_builder import build_sam3_image_model

    checkpoint_candidate = Path(model_id).expanduser() if model_id else None
    if checkpoint_candidate and checkpoint_candidate.exists():
        return build_sam3_image_model(checkpoint_path=str(checkpoint_candidate.resolve()), device=device)
    return build_sam3_image_model(device=device)


def main() -> None:
    args = _parse_args()
    input_image = Path(args.input_image).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    sam3_repo_dir = Path(args.sam3_repo_dir).expanduser().resolve()
    if not sam3_repo_dir.exists():
        raise RuntimeError(f"SAM3 repo not found: {sam3_repo_dir}")

    sys.path.insert(0, str(sam3_repo_dir))

    import torch

    from sam3.model.sam3_image_processor import Sam3Processor

    with Image.open(input_image) as source_image:
        rgb_image = source_image.convert("RGB")

    model = _load_sam3_model(args.model_id, args.device)
    primary_threshold = float(args.confidence_threshold)
    fallback_threshold = (
        float(args.fallback_confidence_threshold)
        if args.fallback_confidence_threshold is not None
        else primary_threshold
    )
    processor_threshold = min(primary_threshold, fallback_threshold)

    processor = Sam3Processor(
        model,
        device=args.device,
        confidence_threshold=float(processor_threshold),
    )
    autocast_context = (
        torch.autocast(device_type="cuda", dtype=torch.bfloat16)
        if str(args.device).startswith("cuda")
        else nullcontext()
    )

    prompt_sequence = []
    for prompt in [args.text_prompt, *(args.text_prompt_alias or [])]:
        prompt = str(prompt or "").strip()
        if prompt and prompt.lower() not in {item.lower() for item in prompt_sequence}:
            prompt_sequence.append(prompt)

    attempts: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    with autocast_context:
        inference_state = processor.set_image(rgb_image)
        for prompt_index, prompt in enumerate(prompt_sequence):
            threshold = primary_threshold if prompt_index == 0 else fallback_threshold
            output = processor.set_text_prompt(state=inference_state, prompt=prompt)
            prompt_candidates = _extract_instances(
                output=output,
                image_size=rgb_image.size,
                text_prompt=prompt,
                confidence_threshold=float(threshold),
            )
            attempts.append(
                {
                    "prompt": prompt,
                    "confidence_threshold": float(threshold),
                    "candidate_count": int(len(prompt_candidates)),
                    "best_score": float(max((candidate.get("score") or 0.0 for candidate in prompt_candidates), default=0.0)),
                    "best_quality_score": float(
                        max((candidate.get("quality_score") or 0.0 for candidate in prompt_candidates), default=0.0)
                    ),
                }
            )
            if prompt_candidates:
                candidates.extend(prompt_candidates)

    if not candidates:
        tried = ", ".join(item["prompt"] for item in attempts) or args.text_prompt
        raise RuntimeError(
            f"SAM3 produced no masks above confidence threshold after trying: {tried}."
        )

    selected_prompt = str(
        max(candidates, key=lambda item: float(item.get("quality_score") or item.get("score") or 0.0)).get("text_prompt")
        or args.text_prompt
    )
    selected_threshold = next(
        (
            float(item["confidence_threshold"])
            for item in attempts
            if str(item.get("prompt", "")).lower() == selected_prompt.lower()
        ),
        primary_threshold,
    )

    if args.merge_mode == "union":
        selected_prompt_candidates = [
            candidate
            for candidate in candidates
            if str(candidate.get("text_prompt", "")).lower() == selected_prompt.lower()
        ]
        candidates_for_result = [_union_candidate(selected_prompt_candidates or candidates, selected_prompt)]
    else:
        candidates_for_result = sorted(
            candidates,
            key=lambda item: float(item.get("quality_score") or item.get("score") or 0.0),
            reverse=True,
        )

    best_candidate = candidates_for_result[0]
    candidate_packs: list[dict[str, Any]] = []
    if args.dump_candidates_dir:
        candidate_packs = _write_candidate_pack(
            dump_dir=Path(args.dump_candidates_dir).expanduser().resolve(),
            rgb_image=rgb_image,
            candidates=candidates_for_result,
            max_candidates=int(args.max_candidates),
        )

    best_mask = np.asarray(best_candidate["segmentation"], dtype=bool)
    mask_image = Image.fromarray((best_mask.astype(np.uint8) * 255), mode="L")
    result = _build_result(
        provider="sam3",
        work_dir=output_dir,
        rgb_image=rgb_image,
        mask_image=mask_image,
        background_rgb=_background_rgb(rgb_image),
        report_name="sam3_foreground_report.json",
        provider_metadata={
            "foreground_model": "sam3",
            "foreground_model_name": "sam3_text_prompt",
            "sam3_repo_dir": str(sam3_repo_dir),
            "sam3_model_id": args.model_id,
            "sam3_text_prompt": args.text_prompt,
            "sam3_effective_text_prompt": selected_prompt,
            "sam3_text_prompt_aliases": args.text_prompt_alias or [],
            "sam3_text_prompt_attempts": attempts,
            "sam3_prompt_fallback_used": selected_prompt != args.text_prompt,
            "sam3_confidence_threshold": float(primary_threshold),
            "sam3_effective_confidence_threshold": float(selected_threshold),
            "sam3_fallback_confidence_threshold": float(fallback_threshold),
            "sam3_merge_mode": args.merge_mode,
            "sam3_mask_count": int(len(candidates)),
            "sam3_selected_candidate_id": str(candidate_packs[0]["candidate_id"]) if candidate_packs else _candidate_id(int(best_candidate["index"])),
            "sam3_selected_score": float(best_candidate.get("score") or 0.0),
            "sam3_selected_quality_score": float(best_candidate.get("quality_score") or best_candidate.get("score") or 0.0),
            "sam3_selected_area": int(best_candidate.get("area") or 0),
            "sam3_selected_area_ratio": float(best_candidate.get("area_ratio") or 0.0),
            "sam3_device": args.device,
            "sam3_candidates": candidate_packs,
        },
    )
    summary_path = output_dir / "sam3_summary.json"
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "selected": result.get("sam3_selected_candidate_id")}))


if __name__ == "__main__":
    main()
