# Progress — 2026-10-15 (Asia/Seoul)

## Current checkpoint
Stage 0 audit complete; environment installation in progress. Next: stage 1 background reconstruction and local viewer, then stage 3 placement, then stage 2 graph.
Node.js 24 and Python 3.13 installed. WSL optional components installation running; no restart initiated.
GPU RTX 3090 24576 MiB, driver 595.71. Power limit deliberately not queried or changed in this run.

## Missing assets
No previous STATUS.md or DECISIONS.md in checkout or searched user folders.
No original 23–24 generated case outputs, rm06_U01 demo, preprocessed 15-background set, GLB/PLY results or model checkpoints found.
User confirmed no backup. Do not reconstruct/overwrite original demo assets. New evaluation assets must be separate.
26 candidate WebP images and some example input images/videos exist; these are not the missing generated cases.
storage contains placeholders only. SAM3, TRELLIS.2-4B, FastVLM and Depth Anything V2 weights not found in inspected locations.

## Existing state
Repository main at c65b40b before this work.
Pre-existing deleted tracked files: Chair_infer.mp4, TV_infer.mp4, vase_infer.mp4. Preserve deletions unstaged.
Existing docs describe Linux TRELLIS.2 runtime with pinned dependencies. Existing pipeline not executable on this fresh host yet.
Original scene graph results (relations 9/10, object correspondence 14/36) are user-reported baselines; annotations unavailable.

## Resume
Read this file and DECISIONS.md. Check installed Node/Python and WSL completion without reading/changing power limits.
Continue stage 1 in separate scene entrypoint. Do not modify existing pipeline or external/prism-scan.
No implementation/visual/accuracy completion claimed. Stage screenshots pending local preview.

WSL components completed; restart required, not initiated. Native Windows scene environment is being prepared. Stage 0 screenshot: docs/screenshots/stage0-audit.png (audit report, not viewer).
