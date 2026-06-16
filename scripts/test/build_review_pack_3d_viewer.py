#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an interactive 3D HTML viewer for an image backend review pack."
    )
    parser.add_argument(
        "--review-root",
        required=True,
        help="Path to storage/review_packs/image_backend_comparison/<timestamp>",
    )
    parser.add_argument(
        "--output",
        default="index_3d.html",
        help="Output HTML filename (inside review-root by default).",
    )
    return parser.parse_args()


def load_summary(review_root: Path) -> dict[str, Any]:
    summary_path = review_root / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"summary.json not found: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))


def load_metadata(review_root: Path, metadata_rel: str) -> dict[str, Any]:
    metadata_path = (review_root / metadata_rel).resolve()
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_existing_path(review_root: Path, raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (review_root / candidate).resolve()
    if candidate.exists():
        return candidate
    return None


def versioned_src(review_root: Path, rel_path: str) -> str:
    resolved = (review_root / rel_path).resolve()
    escaped = html.escape(rel_path)
    if not resolved.exists():
        return escaped
    version = int(resolved.stat().st_mtime_ns)
    return f"{escaped}?v={version}"


def materialize_segmented_input(
    review_root: Path,
    sample_dir_rel: str,
    sample: dict[str, Any],
    results: list[dict[str, Any]],
) -> str | None:
    provided = str(sample.get("sam2_segmented_input_png", "")).strip()
    if provided and (review_root / provided).exists():
        return provided

    destination = (review_root / sample_dir_rel / "sam2_segmented_input.png").resolve()
    for result in results:
        metadata_rel = str(result.get("metadata_path", "")).strip()
        if not metadata_rel:
            continue
        metadata = load_metadata(review_root, metadata_rel)
        image_preprocess = metadata.get("image_preprocess") if isinstance(metadata.get("image_preprocess"), dict) else {}
        candidates = [
            image_preprocess.get("normalized_foreground_file"),
            metadata.get("multiview_input_file"),
            metadata.get("foreground_file"),
            metadata.get("normalized_input_file"),
            metadata.get("mask_file"),
        ]
        for raw_candidate in candidates:
            source = resolve_existing_path(review_root, str(raw_candidate) if raw_candidate else None)
            if source is None:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return str(destination.relative_to(review_root))
    return None


def find_primary_mesh(review_root: Path, results: list[dict[str, Any]]) -> str | None:
    def backend_rank(entry: dict[str, Any]) -> int:
        backend = str(entry.get("backend", "")).lower()
        resolved_backend = str(entry.get("resolved_backend", "")).lower()
        mesh_backend = str(entry.get("mesh_backend", "")).lower()
        merged = " ".join([backend, resolved_backend, mesh_backend])
        if "trellis" in merged:
            return 0
        if "hunyuan" in merged:
            return 1
        return 2

    prioritized = sorted(results, key=backend_rank)
    for result in prioritized:
        mesh_rel = str(result.get("mesh", "")).strip()
        if not mesh_rel:
            continue
        if (review_root / mesh_rel).exists():
            return mesh_rel
    return None


def sort_results_for_display(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def rank(entry: dict[str, Any]) -> tuple[int, str]:
        backend = str(entry.get("backend", "")).lower()
        if "trellis" in backend:
            return (0, backend)
        if "hunyuan" in backend:
            return (1, backend)
        return (9, backend)

    return sorted(results, key=rank)


def card_html(review_root: Path, sample_name: str, result: dict[str, Any]) -> str:
    backend = html.escape(str(result.get("backend", "unknown")))
    status = html.escape(str(result.get("status", "unknown")))
    runtime = html.escape(str(result.get("runtime_sec", "n/a")))
    quality = html.escape(str(result.get("quality_status", "unknown")))
    resolved_backend = html.escape(str(result.get("resolved_backend", "unknown")))
    mesh_backend = html.escape(str(result.get("mesh_backend", "unknown")))

    mesh_rel = str(result.get("mesh", "")).strip()
    mesh_before_rel = str(result.get("mesh_before_optimize", "")).strip()
    metadata_rel = str(result.get("metadata_path", "")).strip()
    screenshot_rel = str(result.get("viewer_screenshot", "")).strip()

    mesh_exists = bool(mesh_rel) and (review_root / mesh_rel).exists()
    mesh_before_exists = bool(mesh_before_rel) and (review_root / mesh_before_rel).exists()
    metadata_exists = bool(metadata_rel) and (review_root / metadata_rel).exists()
    screenshot_exists = bool(screenshot_rel) and (review_root / screenshot_rel).exists()

    links = []
    if mesh_exists:
        links.append(f'<a href="{html.escape(mesh_rel)}" target="_blank" rel="noopener">mesh</a>')
    if mesh_before_exists:
        links.append(
            f'<a href="{html.escape(mesh_before_rel)}" target="_blank" rel="noopener">mesh_before_optimize</a>'
        )
    if metadata_exists:
        links.append(f'<a href="{html.escape(metadata_rel)}" target="_blank" rel="noopener">metadata</a>')
    if screenshot_exists:
        links.append(
            f'<a href="{html.escape(screenshot_rel)}" target="_blank" rel="noopener">viewer_screenshot</a>'
        )
    links_html = " | ".join(links) if links else "no files"

    if mesh_exists:
        viewer_block = f"""
        <div class="viewer-wrap">
          <div class="viewer-label">optimized</div>
          <model-viewer
            src="{versioned_src(review_root, mesh_rel)}"
            camera-controls
            interaction-prompt="none"
            shadow-intensity="0.8"
            exposure="1.0"
            tone-mapping="neutral"
            style="width: 100%; height: 320px; background: #0f172a;">
          </model-viewer>
        </div>
        """
        if mesh_before_exists:
            viewer_block += f"""
            <details class="before-view">
              <summary>show before optimize mesh</summary>
              <div class="viewer-wrap">
                <div class="viewer-label">before optimize</div>
                <model-viewer
                  src="{versioned_src(review_root, mesh_before_rel)}"
                  camera-controls
                  interaction-prompt="none"
                  shadow-intensity="0.8"
                  exposure="1.0"
                  tone-mapping="neutral"
                  style="width: 100%; height: 280px; background: #0f172a;">
                </model-viewer>
              </div>
            </details>
            """
    else:
        viewer_block = '<div class="viewer-missing">mesh file is missing for this backend run</div>'

    return f"""
    <article class="backend-card">
      <header class="backend-header">
        <h3>{backend}</h3>
        <p>{sample_name}</p>
      </header>
      {viewer_block}
      <div class="backend-meta">
        <div><span>status</span><strong>{status}</strong></div>
        <div><span>quality</span><strong>{quality}</strong></div>
        <div><span>runtime_sec</span><strong>{runtime}</strong></div>
        <div><span>resolved_backend</span><strong>{resolved_backend}</strong></div>
        <div><span>mesh_backend</span><strong>{mesh_backend}</strong></div>
      </div>
      <footer class="backend-links">{links_html}</footer>
    </article>
    """


def build_html(summary: dict[str, Any], review_root: Path) -> str:
    generated_at = html.escape(str(summary.get("generated_at", "unknown")))
    sample_sections: list[str] = []

    for sample in summary.get("samples", []):
        sample_name_raw = str(sample.get("sample_name", "sample"))
        sample_name = html.escape(sample_name_raw)
        input_png = str(sample.get("input_png", "")).strip()
        sample_dir_rel = str(Path(input_png).parent) if input_png else sample_name_raw

        input_block = '<div class="focus-missing">input image missing</div>'
        if input_png and (review_root / input_png).exists():
            input_block = (
                f'<img src="{versioned_src(review_root, input_png)}" alt="{sample_name} input" class="input-thumb" loading="lazy" />'
            )

        results = sample.get("results", [])
        ordered_results = sort_results_for_display(results)
        cards = "\n".join(card_html(review_root, sample_name, result) for result in ordered_results)

        segmented_rel = materialize_segmented_input(review_root, sample_dir_rel, sample, ordered_results)
        segmented_block = '<div class="focus-missing">SAM2 segmented input not found</div>'
        if segmented_rel and (review_root / segmented_rel).exists():
            segmented_block = (
                f'<img src="{versioned_src(review_root, segmented_rel)}" alt="{sample_name} SAM2 segmented input" class="focus-image" loading="lazy" />'
            )

        sam2_mask_rel = str(sample.get("sam2_mask_png", "")).strip()
        sam2_mask_block = '<div class="focus-missing">SAM2 mask not found</div>'
        if sam2_mask_rel and (review_root / sam2_mask_rel).exists():
            sam2_mask_block = (
                f'<img src="{versioned_src(review_root, sam2_mask_rel)}" alt="{sample_name} SAM2 mask" class="focus-image qc-image" loading="lazy" />'
            )

        sam2_missing_rel = str(sample.get("sam2_missing_regions_png", "")).strip()
        sam2_missing_block = '<div class="focus-missing">Missing-region diagnostic not found</div>'
        if sam2_missing_rel and (review_root / sam2_missing_rel).exists():
            sam2_missing_block = (
                f'<img src="{versioned_src(review_root, sam2_missing_rel)}" alt="{sample_name} SAM2 missing-region diagnostic" class="focus-image qc-image" loading="lazy" />'
            )

        primary_mesh_rel = find_primary_mesh(review_root, ordered_results)
        primary_block = '<div class="focus-missing">Primary mesh result not found</div>'
        if primary_mesh_rel and (review_root / primary_mesh_rel).exists():
            primary_block = f"""
            <model-viewer
              src="{versioned_src(review_root, primary_mesh_rel)}"
              camera-controls
              interaction-prompt="none"
              shadow-intensity="0.8"
              exposure="1.0"
              tone-mapping="neutral"
              style="width: 100%; height: 380px; background: #0f172a;">
            </model-viewer>
            """

        sample_sections.append(
            f"""
            <section class="sample-section">
              <div class="sample-header">
                <h2>{sample_name}</h2>
                <div class="sample-header-input">{input_block}</div>
              </div>
              <div class="focus-grid">
                <article class="focus-card">
                  <header>SAM2 Segmentation Input</header>
                  {segmented_block}
                </article>
                <article class="focus-card">
                  <header>SAM2 Mask + Missing Regions</header>
                  <div class="qc-grid">
                    <div class="qc-item">
                      <p class="qc-title">Binary mask</p>
                      {sam2_mask_block}
                    </div>
                    <div class="qc-item">
                      <p class="qc-title">Removed/internal-hole regions (red)</p>
                      {sam2_missing_block}
                    </div>
                  </div>
                </article>
                <article class="focus-card">
                  <header>Primary Reconstruction Result</header>
                  {primary_block}
                </article>
              </div>
              <div class="card-grid">
                {cards}
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Image Backend 3D Review Pack</title>
    <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
    <style>
      :root {{
        --bg: #0b1020;
        --panel: #121a2f;
        --panel-soft: #0f172a;
        --text: #e2e8f0;
        --muted: #94a3b8;
        --line: #26324a;
        --accent: #22d3ee;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        font-family: "Segoe UI", "Noto Sans KR", sans-serif;
        color: var(--text);
        background: radial-gradient(circle at top left, #16213f 0%, var(--bg) 55%);
      }}
      .page {{
        max-width: 1480px;
        margin: 0 auto;
        padding: 24px 20px 40px;
      }}
      .top {{
        margin-bottom: 24px;
      }}
      .top h1 {{
        margin: 0;
        font-size: 28px;
      }}
      .top p {{
        margin: 8px 0 0;
        color: var(--muted);
      }}
      .sample-section {{
        margin: 28px 0 40px;
        padding: 18px;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: rgba(11, 16, 32, 0.76);
      }}
      .sample-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 14px;
      }}
      .sample-header h2 {{
        margin: 0;
        font-size: 22px;
      }}
      .sample-header-input {{
        width: 180px;
        display: flex;
        justify-content: flex-end;
      }}
      .focus-image {{
        width: 100%;
        max-width: 420px;
        height: 220px;
        object-fit: contain;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: #0f172a;
      }}
      .input-thumb {{
        width: 160px;
        height: 96px;
        object-fit: cover;
        border-radius: 8px;
        border: 1px solid var(--line);
      }}
      .focus-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(260px, 1fr));
        gap: 14px;
        margin-bottom: 16px;
      }}
      .focus-card {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: #101b35;
        padding: 10px;
      }}
      .focus-card header {{
        font-size: 14px;
        font-weight: 600;
        color: #7dd3fc;
        margin-bottom: 8px;
      }}
      .qc-grid {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
      }}
      .qc-item {{
        display: flex;
        flex-direction: column;
        gap: 6px;
      }}
      .qc-title {{
        margin: 0;
        color: #9fb6d8;
        font-size: 12px;
      }}
      .qc-image {{
        height: 180px;
      }}
      .focus-missing {{
        min-height: 220px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px dashed #36507a;
        border-radius: 10px;
        color: #94a3b8;
        background: #0b162f;
        padding: 12px;
        text-align: center;
      }}
      .card-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
        gap: 14px;
      }}
      .backend-card {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel);
        overflow: hidden;
      }}
      .backend-header {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 12px;
        background: linear-gradient(135deg, #111a33 0%, #0f2033 100%);
        border-bottom: 1px solid var(--line);
      }}
      .backend-header h3 {{
        margin: 0;
        font-size: 18px;
        color: var(--accent);
      }}
      .backend-header p {{
        margin: 0;
        color: var(--muted);
        font-size: 12px;
      }}
      .backend-meta {{
        display: grid;
        grid-template-columns: repeat(2, minmax(120px, 1fr));
        gap: 8px;
        padding: 10px 12px;
      }}
      .backend-meta div {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 10px;
        border-bottom: 1px dashed #253353;
        padding-bottom: 4px;
      }}
      .backend-meta span {{
        color: var(--muted);
        font-size: 12px;
      }}
      .backend-meta strong {{
        font-size: 12px;
        text-align: right;
      }}
      .backend-links {{
        padding: 10px 12px 12px;
        color: var(--muted);
        font-size: 13px;
      }}
      .viewer-wrap {{
        border-bottom: 1px solid var(--line);
      }}
      .viewer-label {{
        font-size: 12px;
        color: var(--muted);
        padding: 8px 12px 6px;
        background: rgba(11, 18, 36, 0.75);
      }}
      .before-view {{
        border-top: 1px solid var(--line);
      }}
      .before-view summary {{
        cursor: pointer;
        padding: 8px 12px;
        color: #7dd3fc;
        font-size: 13px;
        list-style: none;
      }}
      .before-view summary::-webkit-details-marker {{
        display: none;
      }}
      .backend-links a {{
        color: #7dd3fc;
        text-decoration: none;
      }}
      .backend-links a:hover {{
        text-decoration: underline;
      }}
      .viewer-missing {{
        height: 360px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fda4af;
        background: var(--panel-soft);
      }}
      @media (max-width: 900px) {{
        .sample-header {{
          flex-direction: column;
          align-items: flex-start;
        }}
        .focus-grid {{
          grid-template-columns: 1fr;
        }}
        .qc-image {{
          height: 220px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <header class="top">
        <h1>Image Backend 3D Review</h1>
        <p>Generated at {generated_at}. Each sample highlights SAM2 segmented input and primary mesh result first.</p>
      </header>
      {"".join(sample_sections)}
    </main>
  </body>
</html>
"""


def main() -> None:
    args = parse_args()
    review_root = Path(args.review_root).expanduser().resolve()
    if not review_root.exists():
        raise SystemExit(f"review-root not found: {review_root}")
    summary = load_summary(review_root)
    html_content = build_html(summary, review_root)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = review_root / output_path
    output_path.write_text(html_content, encoding="utf-8")
    print(f"3D review page generated: {output_path}")


if __name__ == "__main__":
    main()
