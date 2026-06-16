from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect semantic object boxes with Florence-2.")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--model-id", default="microsoft/Florence-2-large")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--prompt", default="<OD>")
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--min-area-ratio", type=float, default=0.002)
    parser.add_argument("--max-area-ratio", type=float, default=0.95)
    return parser.parse_args()


def _clip_box(box: list[float], width: int, height: int) -> list[float] | None:
    if len(box) != 4:
        return None
    left = max(0.0, min(float(width), float(box[0])))
    top = max(0.0, min(float(height), float(box[1])))
    right = max(0.0, min(float(width), float(box[2])))
    bottom = max(0.0, min(float(height), float(box[3])))
    if right <= left or bottom <= top:
        return None
    return [left, top, right, bottom]


def main() -> None:
    args = _parse_args()
    input_image = Path(args.input_image).expanduser().resolve()
    output_json = Path(args.output_json).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)

    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    with Image.open(input_image) as source:
        image = source.convert("RGB")
    width, height = image.size

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        device = "cpu"
    dtype = torch.float16 if device.startswith("cuda") else torch.float32

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        trust_remote_code=True,
        torch_dtype=dtype,
    ).to(device)
    processor = AutoProcessor.from_pretrained(args.model_id, trust_remote_code=True)

    inputs = processor(text=args.prompt, images=image, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.inference_mode():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
            do_sample=False,
        )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(generated_text, task=args.prompt, image_size=(width, height))
    payload = parsed.get(args.prompt) if isinstance(parsed, dict) else None
    if not isinstance(payload, dict):
        payload = {}

    boxes = payload.get("bboxes") or []
    labels = payload.get("labels") or []
    scores = payload.get("scores") or []
    image_area = max(1.0, float(width * height))

    candidates: list[dict[str, object]] = []
    for index, raw_box in enumerate(boxes):
        box = _clip_box([float(value) for value in raw_box], width, height)
        if box is None:
            continue
        area_ratio = ((box[2] - box[0]) * (box[3] - box[1])) / image_area
        if area_ratio < args.min_area_ratio or area_ratio > args.max_area_ratio:
            continue
        label = str(labels[index]) if index < len(labels) else "object"
        score = float(scores[index]) if index < len(scores) else None
        candidates.append(
            {
                "detection_id": f"florence2_{index:04d}",
                "label": label,
                "bbox": box,
                "area_ratio": float(area_ratio),
                "score": score,
                "source": "florence2",
            }
        )

    candidates = sorted(candidates, key=lambda item: float(item["area_ratio"]), reverse=True)[: args.max_candidates]
    output_json.write_text(
        json.dumps(
            {
                "provider": "florence2",
                "model_id": args.model_id,
                "prompt": args.prompt,
                "image_size": [width, height],
                "candidates": candidates,
                "raw_text": generated_text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
