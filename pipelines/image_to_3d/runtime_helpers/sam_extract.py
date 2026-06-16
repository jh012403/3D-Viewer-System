from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from pipelines.image_to_3d.foreground_model_wrapper import _build_result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract a foreground object mask with Segment Anything.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model-type", default="vit_h")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--points-per-side", type=int, default=24)
    parser.add_argument("--pred-iou-thresh", type=float, default=0.86)
    parser.add_argument("--stability-score-thresh", type=float, default=0.92)
    return parser.parse_args()


def _touches_border(mask: np.ndarray, margin: int = 4) -> bool:
    height, width = mask.shape
    ys, xs = np.nonzero(mask)
    if len(xs) == 0 or len(ys) == 0:
        return True
    return (
        int(xs.min()) <= margin
        or int(ys.min()) <= margin
        or int(xs.max()) >= width - margin - 1
        or int(ys.max()) >= height - margin - 1
    )


def _score_mask(candidate: dict[str, object], image_shape: tuple[int, int]) -> float:
    segmentation = np.asarray(candidate.get("segmentation"), dtype=bool)
    if segmentation.size == 0:
        return float("-inf")
    area_ratio = float(segmentation.mean())
    if area_ratio <= 0.005 or area_ratio >= 0.97:
        return float("-inf")

    border_penalty = 0.3 if _touches_border(segmentation) else 0.0
    stability = float(candidate.get("stability_score") or 0.0)
    predicted_iou = float(candidate.get("predicted_iou") or 0.0)
    bbox = candidate.get("bbox") or [0.0, 0.0, float(image_shape[1]), float(image_shape[0])]
    bbox_area_ratio = float((bbox[2] * bbox[3]) / float(image_shape[0] * image_shape[1]))
    compactness_bonus = max(0.0, 0.25 - abs(bbox_area_ratio - area_ratio))
    return area_ratio + stability * 0.35 + predicted_iou * 0.35 + compactness_bonus - border_penalty


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


def main() -> None:
    args = _parse_args()

    from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

    input_image = Path(args.input_image).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(input_image) as source_image:
        rgb_image = source_image.convert("RGB")
    image_np = np.asarray(rgb_image)

    sam_model = sam_model_registry[args.model_type](checkpoint=args.checkpoint)
    sam_model.to(device=args.device)
    mask_generator = SamAutomaticMaskGenerator(
        model=sam_model,
        points_per_side=args.points_per_side,
        pred_iou_thresh=args.pred_iou_thresh,
        stability_score_thresh=args.stability_score_thresh,
    )
    masks = mask_generator.generate(image_np)
    if not masks:
        raise RuntimeError("SAM produced no masks for the input image.")

    best_index = max(range(len(masks)), key=lambda index: _score_mask(masks[index], image_np.shape[:2]))
    best_mask = masks[best_index]
    best_segmentation = np.asarray(best_mask["segmentation"], dtype=np.uint8) * 255
    mask_image = Image.fromarray(best_segmentation, mode="L")

    result = _build_result(
        provider="sam",
        work_dir=output_dir,
        rgb_image=rgb_image,
        mask_image=mask_image,
        background_rgb=_background_rgb(rgb_image),
        report_name="sam_foreground_report.json",
        provider_metadata={
            "foreground_model": "sam",
            "foreground_model_name": args.model_type,
            "sam_checkpoint": str(Path(args.checkpoint).expanduser().resolve()),
            "sam_mask_count": len(masks),
            "sam_selected_index": int(best_index),
            "sam_selected_area": int(best_mask.get("area") or 0),
            "sam_selected_predicted_iou": float(best_mask.get("predicted_iou") or 0.0),
            "sam_selected_stability_score": float(best_mask.get("stability_score") or 0.0),
            "sam_device": args.device,
        },
    )
    summary_path = output_dir / "sam_summary.json"
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
