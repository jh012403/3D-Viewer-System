# Decisions — 2026-10-15

- Follow-up priority order is pruning -> node cleanup -> mesh runtime recovery -> presentation -> five-photo human review.
- Sparse relations are stored, not hidden by the UI. One fact per unordered node pair; inverse facts are displayed from either selected endpoint without duplicating JSON. Direction neighbors require mutual nearest-three eligibility; same-category pairs additionally require a size-relative gap <=0.75m. on prioritizes raycast evidence, then smallest vertical gap. Preserve pre-pruning graphs as graph-unpruned-v1.json in new local caches.
- Node cleanup uses confidence >=0.60, >=max(150 pixels,0.02% image area), same-category 3D IoU >0.45 / containment >0.8 or mask IoU >0.65, and confidence*sqrt(area) ranking with 24-node budget. Overlap merging keeps the higher-confidence geometry and records aliases; it does not inflate noisy box unions. Mask containment >80% behind a glass/mirror region is suppressed and logged. This is a heuristic subject to human review, not confirmed reflection ground truth.
- Instance labels use masked median RGB color + category + stable number. Do not repeat category-level wicker/white attributes for all chairs. Demo10 obj-001 is a low-confidence distant sliver, so suppress it rather than fabricate a geometric merge with obj-000.

- Follow stage order 0 → 1 → 3 → 2.
- Preserve original upload/selection/mesh-generation implementation and original assets.
- New scene viewer uses locally installed npm dependencies, no CDN.
- Background SHARP PLY uses OpenCV coordinates; viewer must explicitly convert to Three.js coordinates and preserve original camera intrinsics.
- Metric Depth Anything V2 is the scale reference. Alignment diagnostics must be retained; do not claim exact metric truth from monocular estimates.
- Visible splats and raycast geometry are separate: derive a discontinuity-filtered surface mesh from metric depth.
- Objects: existing generated GLB files; do not regenerate existing case assets.
- VLM supplies names/attributes only. Relations computed from mask/depth boxes with documented geometry conventions.
- Offline demonstration must load precomputed background and graph caches only.
- Missing original reports/assets have no backup per user. New validation set must be labelled separately; no invented baseline reproduction or accuracy numbers.
- Power limit is user-managed. Do not query or change it.
- Restart checkpoint goes in STATUS.md. Do not initiate a restart while work can continue.
- Local-only application; no Sites hosting. Git author email supplied by user: qowlghkss@naver.com.

- Spark pinned to 0.1.10 to retain Three.js 0.178.0. Its embedded raycast WASM is served locally via Vite to avoid Chromium data-URL empty-body initialization failure.
- SHARP source aed6527499ef91cba3b54c18d49a870f25947190; DAV2 a561b849ebae10a6f5ef49e26c83cbbcd36c71bf.
- First replacement photo is DAV2 official example demo10.jpg; not an original project asset. Transparent/reflective regions are not reliable support geometry.
- Existing category_policy and bottom-center normalization are available; previous contact-shadow code is absent from inspected checkout. New shadow must be documented as replacement.

- Stage 3 uses a depth-only pass after splat rendering for mesh occlusion. Support normals must have up component >=0.65; do not place through the nearest wall. Constrain fallback snap to measured local plane bounds.
- Contact relation from placement is recorded as raycast-support-contact; unrecognized supports remain unnamed geometry until semantic masks exist.
- Validation GLB: KhronosGroup/glTF-Sample-Assets Models/SheenChair/glTF-Binary/SheenChair.glb; original missing assets remain untouched.

- Combined inference uses Python 3.12, NumPy 1.26.4 and OpenCV 4.11 to satisfy SAM3 requirements. Retain the previous 3.13 environment as historical evidence; it is not the default launcher.
- Cache mode never requests model generation. New upload generation runs SHARP, metric depth, Qwen and SAM3 sequentially on one GPU worker.
- VLM attributes are category-level observations, not verified attributes of every SAM3 instance. Export labels them category_attributes.
- The 15-photo audit measures selected correspondence and relation recovery only. Do not label 33/36 as node precision or 11/16 as exhaustive relation accuracy. No baseline improvement claim without original labels.
- Local graph quality remains insufficient for an exact scene graph claim. Independent exhaustive labels and contact/reflective-surface handling remain next quality work. An API VLM alternative would provide only names/attributes and requires a separate choice about sending photographs.
- Four new caches are local ignored assets with a tracked SHA256 manifest, not restored historical demos.
