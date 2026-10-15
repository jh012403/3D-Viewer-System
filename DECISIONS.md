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
