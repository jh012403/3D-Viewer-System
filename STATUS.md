# Progress — 2026-10-15 (Asia/Seoul)

## Current checkpoint
Stages 0, 1 and 3 committed and pushed. Stage 2 implementation and 15-photo provisional audit committed and pushed as 15ca972; accuracy target NOT achieved.
Node.js 24 and Python 3.13 installed. Python 3.12 compatibility environment installed; pip check clean, geometry tests pass and real SHARP/Qwen/SAM3 upload inference passes. WSL components installed, restart pending; no restart initiated.
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
Resume stage 2 validation in the separate scene entrypoint. Do not modify existing pipeline or external/prism-scan.
Use .runtime/scene312-env and scripts/start-scene.ps1. Current cache/browser tests pass; no full accuracy claim. Read docs/scene-workspace.md and docs/scene-evaluation.md before further quality work.

WSL components completed; restart required, not initiated. Native Windows scene environment is being prepared. Stage 0 screenshot: docs/screenshots/stage0-audit.png (audit report, not viewer).

## Stage 1 checkpoint
Actual SHARP 1,179,648-splat PLY generated on RTX 3090. DAV2 metric Hypersim Large alignment scale 0.859914; median relative residual 11.26%, p90 440.15% (glass/outdoor disagreement; not ground-truth accuracy). Native Windows inference succeeds without WSL restart.
Geometry tests: 3 passed. Browser: zero page errors, zero external requests; orbit clamped to 8 degrees. Screenshots docs/screenshots/stage1-original.png and stage1-orbit.png. Separate /scene.html and port 8001 service; existing pipeline unchanged.
Next stage 3: GLB placement and gizmos. Cache count 1; demo set of 3-5 and graph validation still pending.

## Stage 3 checkpoint
GLB upload copies into new scene_assets storage and reuses _normalize_scene_transform/category_policy. Real browser test with Khronos SheenChair GLB: click placement, gizmo drag (x changed -0.3911 to -0.2373), support-plane snap, original-view PNG and graph JSON export passed; browser errors 0. Validation GLB is a public fixture, not recovered project output.
Contact shadow is a replacement radial contact approximation because original implementation is absent. Surface geometry also provides object depth occlusion. Unknown support is labelled support surface, not guessed table/floor.
Screenshots: docs/screenshots/stage3-placement.png and stage3-export.png. Next stage 2: Qwen3-VL + SAM3 graph and separate evaluation set. SAM3 login verified and checkpoint downloaded; Windows SAM3 imports succeed using triton-windows.

## Stage 2 checkpoint
Qwen3-VL-4B supplies category names/attributes only; SAM3 text masks plus DAV2 metric depth produce visible-surface AABBs. All seven spatial predicates use shared JS geometry, never VLM spatial guesses. Graph panel selection highlights 3D boxes; 3D box picking selects graph nodes. Upload now generates both background and graph. Graph refresh preserves placed GLBs. Contact-derived on/under is omitted when the object is lifted away.

15 replacement photos evaluated: selected correspondence 33/36 (91.7%), selected relation recovery 11/16 (68.8%). These are assistant-created partial reference labels, NOT full accuracy or independent human ground truth. Original 14/36 and 9/10 cannot be compared directly. Reflections/parts and support contacts remain unresolved. See docs/scene-evaluation.md for all rows.

Four local caches: sunroom, ceramics, hall, groceries d4f646fcc79650d6. New Python 3.12 full upload smoke test produced 1,179,648 splats and 24 graph nodes with zero browser errors. Cache tests verify zero external requests and zero inference POSTs. Graph refresh preservation, actual gizmo translation and original-camera PNG/JSON export pass. Build passes (large bundle warning only). Cache hashes: docs/scene-cache-manifest.json.

Screenshots: docs/screenshots/stage2-sunroom.png, stage2-ceramics.png, stage2-hall.png and stage2-upload.png. Native Windows runtime ready; WSL reboot still pending. Existing TRELLIS.2/FastVLM weights and original missing assets remain absent. No power settings queried or modified.
