# Decisions — 2026-10-15

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
