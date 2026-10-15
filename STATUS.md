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

## Stage 1 checkpoint
Actual SHARP 1,179,648-splat PLY generated on RTX 3090. DAV2 metric Hypersim Large alignment scale 0.859914; median relative residual 11.26%, p90 440.15% (glass/outdoor disagreement; not ground-truth accuracy). Native Windows inference succeeds without WSL restart.
Geometry tests: 3 passed. Browser: zero page errors, zero external requests; orbit clamped to 8 degrees. Screenshots docs/screenshots/stage1-original.png and stage1-orbit.png. Separate /scene.html and port 8001 service; existing pipeline unchanged.
Next stage 3: GLB placement and gizmos. Cache count 1; demo set of 3-5 and graph validation still pending.

## Stage 3 checkpoint
GLB upload copies into new scene_assets storage and reuses _normalize_scene_transform/category_policy. Real browser test with Khronos SheenChair GLB: click placement, gizmo drag (x changed -0.3911 to -0.2373), support-plane snap, original-view PNG and graph JSON export passed; browser errors 0. Validation GLB is a public fixture, not recovered project output.
Contact shadow is a replacement radial contact approximation because original implementation is absent. Surface geometry also provides object depth occlusion. Unknown support is labelled support surface, not guessed table/floor.
Screenshots: docs/screenshots/stage3-placement.png and stage3-export.png. Next stage 2: Qwen3-VL + SAM3 graph and separate evaluation set. SAM3 login verified and checkpoint downloaded; Windows SAM3 imports succeed using triton-windows.
