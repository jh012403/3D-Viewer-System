# Progress — 2026-10-15 (Asia/Seoul)

## Current checkpoint
Follow-up priority 4 complete: human-readable Korean cache titles, UI warnings moved to documents, per-scene orbit/crop profiles (sunroom +/-0.5 degrees, ceramics +/-3, hall/groceries +/-1.5). Original-view export keeps zoom 1. Browser tests exercise both orbit extremes and place a real GLB beside the right chair: default filename classification uses chair policy, height 1.000m instead of small_prop 0.2m. Found and fixed GLB material/UV loss caused by trimesh re-export: preserve original bytes, apply existing normalization to a Three.js parent group. Screenshot docs/screenshots/revision4-chair-scale.png. Visual overlap/occlusion is retained, not hidden; no claim of perfect monocular reconstruction. Next: five-image review pack, then user-confirmed precision/recall.
Follow-up priority 3 partially complete / reboot-blocked: TRELLIS.2-4B and all referenced model weights downloaded (20.9 GB total with FastVLM); official TRELLIS source cloned at 75fbf018. FastVLM selected-chair CUDA inference returns valid JSON/category chair. WSL Ubuntu installation explicitly returned restart required; no reboot initiated. TRELLIS Linux/CUDA environment and new-photo end-to-end GLB generation remain UNVERIFIED. Resume docs/mesh-runtime-recovery.md after Windows restart. Generated GLB -> scene bridge implemented and unit-tested with isolated fixture, with result-page link and scene generated-results list. Screenshot docs/screenshots/revision3-placement.png is Khronos fixture validation, NOT a TRELLIS output. Continue independent priorities 4 and 5 while reboot remains pending.
Follow-up priority 2 complete: demo10 20 -> 17 nodes, one table (obj-000); obj-001 rejected at confidence 0.523 rather than unioning unrelated geometry. dav2-01 77 -> 24, dav2-14 63 -> 24. Post-cleanup demo10 18 edges / 17 nodes. Per-node masked color + stable ID labels; confidence/area budget, same-category overlap merging and reflective-mask containment suppression run before relations. Original raw predictions retained. Unit/browser checks pass. Screenshot docs/screenshots/revision2-sunroom.png. Next priority 3: restore TRELLIS/FastVLM.
2026-10-15 follow-up priority 1 complete: persisted graph pruning, demo10 492 -> 27 edges / 20 nodes (1.35 edges/node; mean undirected degree 2.7). One immediate on target, mutual nearest three eligible neighbors, close-only same-category predicates, unordered-pair deduplication and same-predicate transitive reduction. Browser caches match persisted JSON; zero errors/external requests/inference. Screenshot docs/screenshots/revision1-sunroom.png. Next: priority 2 node cleanup, then runtime restoration, presentation and review pack.
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
