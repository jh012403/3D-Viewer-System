from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from pipelines.image_to_3d.foreground_model_wrapper import _build_result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract foreground mask with official SAM2 automatic mask generation.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sam2-repo-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--points-per-side", type=int, default=32)
    parser.add_argument("--pred-iou-thresh", type=float, default=0.65)
    parser.add_argument("--stability-score-thresh", type=float, default=0.80)
    parser.add_argument("--min-mask-area-ratio", type=float, default=0.005)
    parser.add_argument("--max-mask-area-ratio", type=float, default=0.90)
    parser.add_argument("--crop-n-layers", type=int, default=0)
    parser.add_argument("--crop-n-points-downscale-factor", type=int, default=1)
    parser.add_argument("--min-mask-region-area", type=int, default=0)
    parser.add_argument("--adaptive-enabled", type=int, default=1)
    parser.add_argument("--adaptive-trigger-score", type=float, default=0.62)
    parser.add_argument("--adaptive-trigger-min-area-ratio", type=float, default=0.06)
    parser.add_argument("--adaptive-points-per-side", type=int, default=48)
    parser.add_argument("--adaptive-pred-iou-thresh", type=float, default=0.55)
    parser.add_argument("--adaptive-stability-score-thresh", type=float, default=0.72)
    parser.add_argument("--adaptive-crop-n-layers", type=int, default=1)
    parser.add_argument("--adaptive-crop-n-points-downscale-factor", type=int, default=1)
    parser.add_argument("--adaptive-min-mask-region-area", type=int, default=0)
    parser.add_argument("--dump-candidates-dir")
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--selected-candidate-id")
    parser.add_argument("--boxes-json")
    parser.add_argument("--prompt-json")
    return parser.parse_args()


def _touches_border(mask: np.ndarray, margin: int = 4) -> bool:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0 or len(ys) == 0:
        return True
    height, width = mask.shape
    return (
        int(xs.min()) <= margin
        or int(ys.min()) <= margin
        or int(xs.max()) >= (width - margin - 1)
        or int(ys.max()) >= (height - margin - 1)
    )


def _border_touch_count(mask: np.ndarray, margin: int = 4) -> int:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0 or len(ys) == 0:
        return 4
    height, width = mask.shape
    touches_top = int(ys.min()) <= margin
    touches_left = int(xs.min()) <= margin
    touches_right = int(xs.max()) >= (width - margin - 1)
    touches_bottom = int(ys.max()) >= (height - margin - 1)
    return int(touches_top) + int(touches_left) + int(touches_right) + int(touches_bottom)


def _score_mask(
    candidate: dict[str, object],
    *,
    min_mask_area_ratio: float,
    max_mask_area_ratio: float,
) -> float:
    segmentation = np.asarray(candidate.get("segmentation"), dtype=bool)
    if segmentation.size == 0:
        return float("-inf")

    area_ratio = float(segmentation.mean())
    if area_ratio < min_mask_area_ratio or area_ratio > max_mask_area_ratio:
        return float("-inf")

    ys, xs = np.nonzero(segmentation)
    if len(xs) == 0 or len(ys) == 0:
        return float("-inf")

    stability = float(candidate.get("stability_score") or 0.0)
    predicted_iou = float(candidate.get("predicted_iou") or 0.0)
    bbox = candidate.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    bbox_area_ratio = float((float(bbox[2]) * float(bbox[3])) / float(segmentation.shape[0] * segmentation.shape[1]))
    fill_ratio = area_ratio / max(1e-8, bbox_area_ratio)

    # Center prior: in object photos, the target is usually near center.
    centroid_x = float(xs.mean() / segmentation.shape[1])
    centroid_y = float(ys.mean() / segmentation.shape[0])
    center_dist = math.sqrt((centroid_x - 0.5) ** 2 + (centroid_y - 0.5) ** 2)
    center_pref = 1.0 - min(1.0, center_dist / 0.42)

    # Prefer practical object scales while still allowing small objects.
    size_pref = 1.0 - min(1.0, abs(area_ratio - 0.22) / 0.22)
    fill_pref = min(1.0, max(0.0, (fill_ratio - 0.08) / 0.55))
    quality_pref = (0.5 * stability) + (0.5 * predicted_iou)

    border_touch_count = _border_touch_count(segmentation)
    border_penalty = 0.24 * border_touch_count
    # Penalize ultra-thin masks that often correspond to stands/signboards.
    thin_penalty = 0.20 if fill_ratio < 0.12 else 0.0

    score = (
        (0.38 * center_pref)
        + (0.26 * size_pref)
        + (0.14 * fill_pref)
        + (0.22 * quality_pref)
        - border_penalty
        - thin_penalty
    )
    return float(score)


def _candidate_pack_sort_key(item: dict[str, object]) -> tuple[float, float, float, float]:
    pass_name = str(item.get("pass_name") or "")
    area_ratio = float(item.get("area_ratio") or 0.0)
    score = float(item.get("score") or 0.0)
    border_touch_count = int(item.get("border_touch_count") or 0)
    pass_bonus = 2.0 if pass_name == "prompt" else 0.0
    practical_size = 1.0 - min(1.0, abs(area_ratio - 0.16) / 0.20)
    background_penalty = 1.2 if area_ratio > 0.22 and border_touch_count >= 2 else 0.0
    priority = pass_bonus + score + (0.55 * practical_size) - (0.35 * border_touch_count) - background_penalty
    return priority, score, area_ratio, -float(border_touch_count)


def _generate_masks(
    *,
    sam2_model: object,
    image_np: np.ndarray,
    device: str,
    points_per_side: int,
    pred_iou_thresh: float,
    stability_score_thresh: float,
    crop_n_layers: int,
    crop_n_points_downscale_factor: int,
    min_mask_region_area: int,
) -> list[dict[str, object]]:
    import torch
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

    mask_generator = SAM2AutomaticMaskGenerator(
        sam2_model,
        points_per_side=points_per_side,
        pred_iou_thresh=pred_iou_thresh,
        stability_score_thresh=stability_score_thresh,
        crop_n_layers=crop_n_layers,
        crop_n_points_downscale_factor=crop_n_points_downscale_factor,
        min_mask_region_area=min_mask_region_area,
    )
    with torch.inference_mode():
        if device.startswith("cuda"):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                masks = mask_generator.generate(image_np)
        else:
            masks = mask_generator.generate(image_np)
    return masks


def _load_guided_boxes(path: str | None, width: int, height: int) -> list[dict[str, object]]:
    if not path:
        return []
    boxes_path = Path(path).expanduser().resolve()
    if not boxes_path.exists():
        return []
    payload = json.loads(boxes_path.read_text(encoding="utf-8"))
    raw_candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(raw_candidates, list):
        return []

    boxes: list[dict[str, object]] = []
    for index, candidate in enumerate(raw_candidates):
        if not isinstance(candidate, dict):
            continue
        raw_box = candidate.get("bbox")
        if not isinstance(raw_box, list) or len(raw_box) != 4:
            continue
        left = max(0.0, min(float(width), float(raw_box[0])))
        top = max(0.0, min(float(height), float(raw_box[1])))
        right = max(0.0, min(float(width), float(raw_box[2])))
        bottom = max(0.0, min(float(height), float(raw_box[3])))
        if right <= left or bottom <= top:
            continue
        boxes.append(
            {
                "detection_id": str(candidate.get("detection_id") or f"box_{index:04d}"),
                "label": str(candidate.get("label") or "object"),
                "bbox": [left, top, right, bottom],
                "source": str(candidate.get("source") or payload.get("provider") or "detector"),
                "detection_score": candidate.get("score"),
            }
        )
    return boxes


def _load_prompt(path: str | None, width: int, height: int) -> dict[str, object] | None:
    if not path:
        return None
    prompt_path = Path(path).expanduser().resolve()
    if not prompt_path.exists():
        return None
    payload = json.loads(prompt_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None

    points: list[list[float]] = []
    labels: list[int] = []
    for point in payload.get("points") or []:
        if not isinstance(point, dict):
            continue
        x = max(0.0, min(float(width - 1), float(point.get("x", 0.0))))
        y = max(0.0, min(float(height - 1), float(point.get("y", 0.0))))
        label = int(point.get("label", 1))
        points.append([x, y])
        labels.append(1 if label > 0 else 0)

    box: list[float] | None = None
    raw_box = payload.get("box")
    if isinstance(raw_box, list) and len(raw_box) == 4:
        left = max(0.0, min(float(width - 1), float(raw_box[0])))
        top = max(0.0, min(float(height - 1), float(raw_box[1])))
        right = max(0.0, min(float(width - 1), float(raw_box[2])))
        bottom = max(0.0, min(float(height - 1), float(raw_box[3])))
        if right > left and bottom > top:
            box = [left, top, right, bottom]

    if not points and box is None:
        return None
    return {
        "points": points,
        "labels": labels,
        "box": box,
        "source": str(payload.get("source") or "user_prompt"),
    }


def _generate_masks_from_boxes(
    *,
    sam2_model: object,
    image_np: np.ndarray,
    boxes: list[dict[str, object]],
    device: str,
) -> list[dict[str, object]]:
    import torch
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    predictor = SAM2ImagePredictor(sam2_model)
    with torch.inference_mode():
        if device.startswith("cuda"):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                predictor.set_image(image_np)
                return _predict_box_masks(predictor, boxes)
        predictor.set_image(image_np)
        return _predict_box_masks(predictor, boxes)


def _generate_masks_from_prompt(
    *,
    sam2_model: object,
    image_np: np.ndarray,
    prompt: dict[str, object],
    device: str,
) -> list[dict[str, object]]:
    import torch
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    predictor = SAM2ImagePredictor(sam2_model)
    with torch.inference_mode():
        if device.startswith("cuda"):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                predictor.set_image(image_np)
                return _predict_prompt_masks(predictor, prompt)
        predictor.set_image(image_np)
        return _predict_prompt_masks(predictor, prompt)


def _predict_prompt_masks(predictor: object, prompt: dict[str, object]) -> list[dict[str, object]]:
    points = np.asarray(prompt.get("points") or [], dtype=np.float32)
    labels = np.asarray(prompt.get("labels") or [], dtype=np.int32)
    box_payload = prompt.get("box")
    box = np.asarray(box_payload, dtype=np.float32) if isinstance(box_payload, list) else None
    point_coords = points if points.size else None
    point_labels = labels if labels.size else None
    masks, scores, _logits = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        box=box,
        multimask_output=True,
    )
    if masks is None or len(masks) == 0:
        return []

    masks_out: list[dict[str, object]] = []
    score_array = np.asarray(scores, dtype=np.float32).reshape(-1)
    for index, mask_item in enumerate(masks):
        mask = np.asarray(mask_item, dtype=bool)
        ys, xs = np.nonzero(mask)
        if len(xs) == 0 or len(ys) == 0:
            continue
        left = float(xs.min())
        top = float(ys.min())
        width = float(xs.max() - xs.min() + 1)
        height = float(ys.max() - ys.min() + 1)
        score = float(score_array[index]) if index < score_array.size else 0.0
        masks_out.append(
            {
                "segmentation": mask,
                "area": int(mask.sum()),
                "bbox": [left, top, width, height],
                "predicted_iou": score,
                "stability_score": score,
                "label": "selected object",
                "source": prompt.get("source") or "user_prompt",
            }
        )
    return masks_out


def _predict_box_masks(predictor: object, boxes: list[dict[str, object]]) -> list[dict[str, object]]:
    masks_out: list[dict[str, object]] = []
    for box_info in boxes:
        box = np.asarray(box_info["bbox"], dtype=np.float32)
        masks, scores, _logits = predictor.predict(box=box, multimask_output=True)
        if masks is None or len(masks) == 0:
            continue
        score_array = np.asarray(scores, dtype=np.float32).reshape(-1)
        best_idx = int(score_array.argmax()) if score_array.size else 0
        mask = np.asarray(masks[best_idx], dtype=bool)
        score = float(score_array[best_idx]) if score_array.size else 0.0
        left, top, right, bottom = [float(value) for value in box.tolist()]
        masks_out.append(
            {
                "segmentation": mask,
                "area": int(mask.sum()),
                "bbox": [left, top, max(0.0, right - left), max(0.0, bottom - top)],
                "predicted_iou": score,
                "stability_score": score,
                "label": box_info.get("label"),
                "source": box_info.get("source"),
                "detection_id": box_info.get("detection_id"),
                "detection_score": box_info.get("detection_score"),
            }
        )
    return masks_out


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


def _candidate_id(pass_name: str, index: int) -> str:
    return f"{pass_name}_{index:04d}"


def _apply_mask_rgba(rgb_image: Image.Image, mask_bool: np.ndarray) -> Image.Image:
    mask_image = Image.fromarray((mask_bool.astype(np.uint8) * 255), mode="L")
    rgba = rgb_image.convert("RGBA")
    rgba.putalpha(mask_image)
    return rgba


def _overlay_image(rgb_image: Image.Image, mask_bool: np.ndarray) -> Image.Image:
    base = np.asarray(rgb_image.convert("RGB")).astype(np.float32)
    overlay = base.copy()
    tint = np.zeros_like(overlay)
    tint[..., 0] = 80.0
    tint[..., 1] = 220.0
    tint[..., 2] = 255.0
    alpha = mask_bool.astype(np.float32) * 0.45
    overlay = (1.0 - alpha[..., None]) * overlay + alpha[..., None] * tint
    composed = np.clip(overlay, 0.0, 255.0).astype(np.uint8)
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


def _write_candidate_pack(
    *,
    dump_dir: Path,
    rgb_image: Image.Image,
    candidates: list[dict[str, object]],
    max_candidates: int,
) -> list[dict[str, object]]:
    dump_dir.mkdir(parents=True, exist_ok=True)

    filtered_candidates = [item for item in candidates if math.isfinite(float(item.get("score") or 0.0))]
    selected_candidates = sorted(
        filtered_candidates,
        key=_candidate_pack_sort_key,
        reverse=True,
    )
    if max_candidates > 0:
        selected_candidates = selected_candidates[:max_candidates]

    packs: list[dict[str, object]] = []
    for candidate in selected_candidates:
        candidate_mask = candidate.get("mask")
        if not isinstance(candidate_mask, dict):
            continue
        segmentation = np.asarray(candidate_mask.get("segmentation"), dtype=bool)
        if segmentation.size == 0:
            continue

        pass_name = str(candidate.get("pass_name") or "primary")
        index = int(candidate.get("index") or 0)
        candidate_id = _candidate_id(pass_name, index)
        candidate_dir = dump_dir / candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)

        mask_path = candidate_dir / "mask.png"
        segmented_path = candidate_dir / "segmented.png"
        segmented_preview_path = candidate_dir / "segmented_preview.png"
        overlay_path = candidate_dir / "overlay.png"
        metadata_path = candidate_dir / "metadata.json"

        Image.fromarray((segmentation.astype(np.uint8) * 255), mode="L").save(mask_path)
        segmented_image = _apply_mask_rgba(rgb_image, segmentation)
        segmented_image.save(segmented_path)
        _preview_image(segmented_image).save(segmented_preview_path)
        _overlay_image(rgb_image, segmentation).save(overlay_path)

        payload = {
            "candidate_id": candidate_id,
            "pass_name": pass_name,
            "index": index,
            "label": candidate.get("label"),
            "source": candidate.get("source"),
            "bbox": candidate.get("bbox"),
            "detection_score": candidate.get("detection_score"),
            "score": float(candidate.get("score") or 0.0),
            "area_ratio": float(candidate.get("area_ratio") or 0.0),
            "border_touch_count": int(candidate.get("border_touch_count") or 0),
            "predicted_iou": float(candidate_mask.get("predicted_iou") or 0.0),
            "stability_score": float(candidate_mask.get("stability_score") or 0.0),
            "mask_path": str(mask_path),
            "segmented_path": str(segmented_path),
            "segmented_preview_path": str(segmented_preview_path),
            "overlay_path": str(overlay_path),
        }
        metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        packs.append(payload)

    summary_path = dump_dir / "candidates_summary.json"
    summary_path.write_text(json.dumps({"candidates": packs}, indent=2), encoding="utf-8")
    return packs


def main() -> None:
    args = _parse_args()
    input_image = Path(args.input_image).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    sam2_repo_dir = Path(args.sam2_repo_dir).expanduser().resolve()
    checkpoint_path = Path(args.checkpoint).expanduser().resolve()

    if not sam2_repo_dir.exists():
        raise RuntimeError(f"SAM2 repo not found: {sam2_repo_dir}")
    if not checkpoint_path.exists():
        raise RuntimeError(f"SAM2 checkpoint not found: {checkpoint_path}")

    # Keep to official SAM2 usage:
    # from sam2.build_sam import build_sam2
    # from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
    sys.path.insert(0, str(sam2_repo_dir))

    import torch
    from sam2.build_sam import build_sam2

    with Image.open(input_image) as source_image:
        rgb_image = source_image.convert("RGB")
    image_np = np.asarray(rgb_image)
    guided_prompt = _load_prompt(args.prompt_json, rgb_image.size[0], rgb_image.size[1])
    guided_boxes = _load_guided_boxes(args.boxes_json, rgb_image.size[0], rgb_image.size[1])

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"

    sam2_model = build_sam2(args.config, str(checkpoint_path), device=device, apply_postprocessing=False)
    primary_masks = []
    if guided_prompt:
        primary_masks = _generate_masks_from_prompt(
            sam2_model=sam2_model,
            image_np=image_np,
            prompt=guided_prompt,
            device=device,
        )
    elif guided_boxes:
        primary_masks = _generate_masks_from_boxes(
            sam2_model=sam2_model,
            image_np=image_np,
            boxes=guided_boxes,
            device=device,
        )
    if not primary_masks:
        primary_masks = _generate_masks(
            sam2_model=sam2_model,
            image_np=image_np,
            device=device,
            points_per_side=args.points_per_side,
            pred_iou_thresh=args.pred_iou_thresh,
            stability_score_thresh=args.stability_score_thresh,
            crop_n_layers=args.crop_n_layers,
            crop_n_points_downscale_factor=args.crop_n_points_downscale_factor,
            min_mask_region_area=args.min_mask_region_area,
        )

    if not primary_masks:
        raise RuntimeError("SAM2 produced no masks for the input image.")

    candidates: list[dict[str, object]] = []
    for index, mask in enumerate(primary_masks):
        segmentation = np.asarray(mask.get("segmentation"), dtype=bool)
        area_ratio = float(segmentation.mean()) if segmentation.size else 0.0
        score = _score_mask(
            mask,
            min_mask_area_ratio=args.min_mask_area_ratio,
            max_mask_area_ratio=args.max_mask_area_ratio,
        )
        if guided_prompt and not math.isfinite(score):
            score = float(mask.get("predicted_iou") or 0.5)
        candidates.append(
            {
                "pass_name": "prompt" if guided_prompt else ("guided" if guided_boxes else "primary"),
                "index": index,
                "candidate_id": _candidate_id("prompt" if guided_prompt else ("guided" if guided_boxes else "primary"), index),
                "mask": mask,
                "label": mask.get("label"),
                "source": mask.get("source") or ("user_prompt_sam2" if guided_prompt else ("detector_sam2" if guided_boxes else "sam2_auto")),
                "bbox": mask.get("bbox"),
                "detection_score": mask.get("detection_score"),
                "score": float(score),
                "area_ratio": area_ratio,
                "border_touch_count": int(_border_touch_count(segmentation)),
            }
        )

    primary_valid_candidates = [candidate for candidate in candidates if candidate["pass_name"] in {"primary", "guided", "prompt"}]
    best_primary = max(primary_valid_candidates, key=lambda item: float(item["score"]))
    adaptive_enabled = bool(args.adaptive_enabled)
    should_run_adaptive = (not guided_prompt) and adaptive_enabled and (
        float(best_primary["score"]) < float(args.adaptive_trigger_score)
        or float(best_primary["area_ratio"]) < float(args.adaptive_trigger_min_area_ratio)
        or int(best_primary["border_touch_count"]) > 0
    )

    adaptive_masks: list[dict[str, object]] = []
    if should_run_adaptive:
        adaptive_masks = _generate_masks(
            sam2_model=sam2_model,
            image_np=image_np,
            device=device,
            points_per_side=args.adaptive_points_per_side,
            pred_iou_thresh=args.adaptive_pred_iou_thresh,
            stability_score_thresh=args.adaptive_stability_score_thresh,
            crop_n_layers=args.adaptive_crop_n_layers,
            crop_n_points_downscale_factor=args.adaptive_crop_n_points_downscale_factor,
            min_mask_region_area=args.adaptive_min_mask_region_area,
        )
        for index, mask in enumerate(adaptive_masks):
            segmentation = np.asarray(mask.get("segmentation"), dtype=bool)
            area_ratio = float(segmentation.mean()) if segmentation.size else 0.0
            score = _score_mask(
                mask,
                min_mask_area_ratio=args.min_mask_area_ratio,
                max_mask_area_ratio=args.max_mask_area_ratio,
            )
            candidates.append(
                {
                    "pass_name": "adaptive",
                    "index": index,
                    "candidate_id": _candidate_id("adaptive", index),
                    "mask": mask,
                    "label": mask.get("label"),
                    "source": mask.get("source") or "sam2_auto_adaptive",
                    "bbox": mask.get("bbox"),
                    "detection_score": mask.get("detection_score"),
                    "score": float(score),
                    "area_ratio": area_ratio,
                    "border_touch_count": int(_border_touch_count(segmentation)),
                }
            )

    selected_candidate_id = (args.selected_candidate_id or "").strip()
    best_candidate: dict[str, object] | None = None
    if selected_candidate_id:
        for candidate in candidates:
            if str(candidate.get("candidate_id") or "") == selected_candidate_id:
                best_candidate = candidate
                break
        if best_candidate is None:
            raise RuntimeError(
                f"SAM2 selected candidate id '{selected_candidate_id}' was not found. "
                "Refresh candidates and pick a valid object."
            )

    if best_candidate is None:
        best_candidate = max(candidates, key=lambda item: float(item["score"]))
    best_index = int(best_candidate["index"])
    best_mask = best_candidate["mask"]
    if best_mask is None:
        raise RuntimeError("SAM2 failed to find a valid mask within configured area thresholds.")

    candidate_packs: list[dict[str, object]] = []
    dump_candidates_dir = (args.dump_candidates_dir or "").strip()
    if dump_candidates_dir:
        candidate_packs = _write_candidate_pack(
            dump_dir=Path(dump_candidates_dir).expanduser().resolve(),
            rgb_image=rgb_image,
            candidates=candidates,
            max_candidates=int(args.max_candidates),
        )

    segmentation = np.asarray(best_mask["segmentation"], dtype=np.uint8) * 255
    mask_image = Image.fromarray(segmentation, mode="L")

    result = _build_result(
        provider="sam2",
        work_dir=output_dir,
        rgb_image=rgb_image,
        mask_image=mask_image,
        background_rgb=_background_rgb(rgb_image),
        report_name="sam2_foreground_report.json",
        provider_metadata={
            "foreground_model": "sam2",
            "foreground_model_name": "sam2_automatic_mask_generator",
            "sam2_repo_dir": str(sam2_repo_dir),
            "sam2_checkpoint": str(checkpoint_path),
            "sam2_config": args.config,
            "sam2_mask_count": int(len(primary_masks)),
            "sam2_mask_count_adaptive": int(len(adaptive_masks)),
            "sam2_guided_box_count": int(len(guided_boxes)),
            "sam2_guided_mode": bool(guided_boxes or guided_prompt),
            "sam2_prompt_mode": bool(guided_prompt),
            "sam2_prompt_point_count": int(len(guided_prompt.get("points") or [])) if guided_prompt else 0,
            "sam2_prompt_has_box": bool(guided_prompt.get("box")) if guided_prompt else False,
            "sam2_adaptive_enabled": adaptive_enabled,
            "sam2_adaptive_triggered": should_run_adaptive,
            "sam2_adaptive_trigger_score": float(args.adaptive_trigger_score),
            "sam2_adaptive_trigger_min_area_ratio": float(args.adaptive_trigger_min_area_ratio),
            "sam2_candidate_count_total": int(len(candidates)),
            "sam2_selected_index": int(best_index),
            "sam2_selected_candidate_id": str(best_candidate.get("candidate_id") or _candidate_id(str(best_candidate["pass_name"]), best_index)),
            "sam2_selected_pass": str(best_candidate["pass_name"]),
            "sam2_selected_area": int(best_mask.get("area") or 0),
            "sam2_selected_predicted_iou": float(best_mask.get("predicted_iou") or 0.0),
            "sam2_selected_stability_score": float(best_mask.get("stability_score") or 0.0),
            "sam2_selected_score": float(best_candidate["score"]),
            "sam2_selected_border_touching": bool(_touches_border(np.asarray(best_mask["segmentation"], dtype=bool))),
            "sam2_selected_border_touch_count": int(
                _border_touch_count(np.asarray(best_mask["segmentation"], dtype=bool))
            ),
            "sam2_primary_best_score": float(best_primary["score"]),
            "sam2_primary_best_area_ratio": float(best_primary["area_ratio"]),
            "sam2_device": device,
            "sam2_candidates": candidate_packs,
        },
    )
    summary_path = output_dir / "sam2_summary.json"
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    torch.cuda.empty_cache() if torch.cuda.is_available() else None


if __name__ == "__main__":
    main()
