# Decisions — 2026-10-15

- 2026-10-17: Add digital-twin functions above the category-agnostic existing mesh pipeline. Never restrict standalone uploads, selection or GLB download to industrial equipment. Keep original four demo caches and historical assets unchanged. New industrial caches live under twin-* with tracked authored profiles and photo-source hashes. Geometry and distances remain monocular estimates, not surveyed measurements; simulated status must be labeled. No accuracy evaluation.
- New scene selection: Pexels 4481259 (warehouse), 2280571 (laboratory), 3912981 (precision workbench), 209251 (industrial loading hall). Each gets real SHARP/DAV2 output and photo-guided authored visible assets/relations, two operational zones and two recommendations. People are not registered as equipment. Do not claim these edited graphs are untouched automatic recognition results.
- Deliver four actual browser recordings as H.264/yuv420p/30fps MP4 plus a dependency-free offline gallery. Record real PNG/JSON downloads, cache-only operation and authored prop provenance. Videos include step captions/cursor and no audio. Preserve raw WebM locally; commit portable MP4s and output artifacts. All evaluation/review plans below are historical and superseded by the demo pivot.


- Processing animation follows worker events. Run depth before SHARP to match the displayed order, unloading each model between stages. Cached scene loading has separate wording; never simulate model execution during a cache-only stage presentation. Processing screenshots are labeled UI previews in the documentation.

- Graph presentation uses actual photo crops for background nodes and a rendered GLB thumbnail for inserted props. Support hierarchy controls vertical layout; non-support edges are subdued until selection. Hover does not rebuild the graph and uses cached silhouette points. Technical geometry metrics stay out of the demo UI.

- Placement recommendations use photo-chosen cached points and scene-specific prop sizes/tint. Use a compact authored planter GLB for rehearsal so every scene has a visually appropriate prop; do not label it as an AI mesh-generation result. Preserve existing GLB imports. Snap within 85 screen pixels, ease down over 650ms, and retain authored background relationships.

- Live path changes stop at obvious mistakes: no under, directed on, structural direction exclusions, no RGB labels. Remove the RANSAC invocation rather than continuing to tune it. Historical floor/evaluation tools remain archived but are not invoked. Reprocessing must skip curated demo caches.

- New priority supersedes all accuracy plans below: curate four demo caches, polish interaction, record fallback videos. Stop review/precision/RANSAC work. Curated graphs are photo-guided authored content, not measured automatic predictions; preserve this provenance in JSON/docs while keeping the stage UI focused on the scene.
- Four scenes have 6–10 selected objects, 8–12 obvious relations, natural Korean labels and two authored placement points each. Keep authored edges unchanged when displaying or adding a new object. Preserve automatic source graphs separately. No changes to original missing cases or external/prism-scan.

- Follow-up priority order is pruning -> node cleanup -> mesh runtime recovery -> presentation -> five-photo human review.
- Sparse relations are stored, not hidden by the UI. One fact per unordered node pair; inverse facts are displayed from either selected endpoint without duplicating JSON. Direction neighbors require mutual nearest-three eligibility; same-category pairs additionally require a size-relative gap <=0.75m. on prioritizes raycast evidence, then smallest vertical gap. Preserve pre-pruning graphs as graph-unpruned-v1.json in new local caches.
- Node cleanup uses confidence >=0.60, >=max(150 pixels,0.02% image area), same-category 3D IoU >0.45 / containment >0.8 or mask IoU >0.65, and confidence*sqrt(area) ranking with 24-node budget. Overlap merging keeps the higher-confidence geometry and records aliases; it does not inflate noisy box unions. Mask containment >80% behind a glass/mirror region is suppressed and logged. This is a heuristic subject to human review, not confirmed reflection ground truth.
- Instance labels use masked median RGB color + category + stable number. Do not repeat category-level wicker/white attributes for all chairs. Demo10 obj-001 is a low-confidence distant sliver, so suppress it rather than fabricate a geometric merge with obj-000.
- Preserve the strict Linux TRELLIS runtime lock. Do not substitute the Windows scene environment or fake/mock a successful mesh. WSL activation requires a user restart; record resumable prerequisites and continue independent UI/review work.
- The existing result view gains only a scene-placement link; upload/selection/generation logic is unchanged. The scene service reads completed object_mesh.glb files, verifies their full header length, and copies/normalizes into new asset storage. No source output mutation or arbitrary external URL fetching.
- Presentation profiles crop 6-8% at initial preview and restrict orbit per scene; original-camera export is uncropped. Sunroom needs only +/-0.5 degrees because reflective table distortion remains visible at +/-2. These are presentation limits, not reconstructed hidden geometry.
- Default GLB category is automatic filename classification using existing normalize_category; generated assets use existing metadata. Existing chair policy remains 1m, unknown 1m, small_prop 0.2m. Preserve GLB bytes and glTF materials/extensions; apply existing policy bounds/scale in a parent group instead of exporting via trimesh.
- Freeze post-cleanup predictions for five-image human review (dav2-01/10/13/14/15) with graph hashes. No model-generated or assistant-confirmed ground truth. Precision counts false detections, wrong categories and duplicates as FP; missed individual objects are FN. Color is an auxiliary attribute, not the object-existence criterion. A valid relation must connect two correct unique nodes. Draft or incomplete reviews cannot produce evaluation metrics.

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
- 2026-10-15 revision 6 supersedes RGB labels and reduced orbit limits: source-image positional labels; +/-5 degrees, nearby 0.4m orbit pivot, 1.2 preview crop, original export unchanged. No unsupported per-instance color claims.
- Support targets are an explicit category allowlist. A on B requires the bottom near the support surface and the object above it. Ceiling fixtures use attached to; under requires a separate overhead table/shelf. Structural categories have no directional edges. These are persisted graph rules, not presentation filters.
- RANSAC uses local horizontal depth normals, fixed random seed and existing SAM floor consistency when available. Multi-level scenes may have additional observed landing nodes (up to three geometric support nodes in addition to the 24 semantic detections). Visible boxes are not extended to fabricate hidden legs; demo10 all-chair/table on-floor remains unresolved.
- Reflections below glossy horizontal supports require same-category aligned counterparts and compressed below-plane geometry; retain removal provenance. This is a heuristic awaiting user labels, not perfect reflection recognition.
- Collision tests exclude structural enclosing AABBs (room walls can enclose empty space), use observed support rays and bounded inferred floor planes, and record extrapolation when used. Glass masks are excluded from depth occlusion; 3x3 visibility filtering plus +/-2.5cm transition soften boundaries. Reuse available material-package tint/EV; keep the documented radial replacement shadow.
- The regenerated five-photo pack is unreviewed/on hold. New graph hashes invalidate old drafts. Report the unresolved floor contacts and image cropping alongside the successful counterexample fixes; never infer precision from removal counts.

- Asset IDs are stable within a scene and never recycled during a session. Status is registration workflow, not simulated sensor health. Coordinates and dimensions are estimates. FastVLM metadata augments any imported generated GLB without restricting categories. AAS-inspired exports do not claim AAS standard conformance.

- Twin placement is a draft until explicit confirmation; collisions and insufficient clearance block confirmation. Default clearance is 0.5m, editable by the operator and recorded in reports. Small tabletop rehearsals visibly select 0.1m. Never silently shrink imported meshes or lower the threshold. The equipment-case fixture is authored, not an AI generation result. Search only visible horizontal depth surfaces inside the selected support's photo rectangle.

- Control-room UI keeps a prominent independent generic photo-to-GLB link. KPI occupancy uses overlapping-footprint union, marked estimated. Status is registration state, not sensor health; no fake uptime is introduced. Asset register selection and graph selection share the existing 3D highlight path.

- Export only asset boxes and inserted GLBs to glTF; background Gaussian splats remain excluded. JSON uses AAS-inspired identification/technicalData/operations submodels without conformance claims. Reports show the chosen clearance and current checks; PDF is produced through browser print. Exports hide manipulation/zone/safety overlays and use the original camera.

- Process animation follows actual worker stages. The requested metric alignment title is accompanied by an explicit model-estimate explanation; no measured-scale claim. Cached loading remains distinct. Generic standalone mesh routes and APIs are unchanged; progress names and specification presentation are additive.

- Generic mesh service uses native SAM3/FastVLM with the unchanged official TRELLIS implementation in WSL. Required runtime probes must pass; failed jobs remain failed even if an intermediate mesh exists. Accept the explicit shared output destination when a successful subprocess reports a path in a different OS namespace. Use portable file locking on Windows.
- Vendor the generic model viewer and its decoders through an isolated pinned npm package, preserving the scene viewer's Three.js version. Do not fetch CDN modules at runtime.
- Four final films may reuse one actual photo-to-mesh generation recording, explicitly disclosed in video captions and delivery notes. Edit long waiting intervals, never replace inference results with a fixture. Show height/clearance adjustments on screen before confirmation.
- 2026-10-20 presentation figures use one consistent warehouse scene and actual job_000002 input/mask/GLB. Apply visual cleanup and Korean display aliases only within capture sessions. Keep real interference warnings in the warning figure and GIF; preserve uncertainty/provenance in documentation. Composite comparisons with browser-rendered Korean captions, without generative alteration of scene or mesh evidence. The 12-second GIF uses 120 actual UI captures at 10fps.

- 2026-10-20: The explicit gravity correction request supersedes the earlier camera-vertical assumption. Fit only the identified floor ROI with trimmed orthogonal least squares; do not change the photo camera extrinsics or cached demo assets. Preserve SHARP input intrinsics, including principal point. Scenes without an identified floor retain the legacy uncalibrated support behavior. Keep old box and before screenshots; generate a separate closed-box asset from an attributed photograph.

- 2026-10-20 box correction final: Use HireAHelper CC BY 2.0 closed-box photograph and actual TRELLIS job_000003; preserve original output and prefer the separately capped object_mesh_grounded.glb for scene import. Store its warehouse yaw in placement-profile.json. Bottom caps close lower openings only, not all topology. Ground lower 2 percent at -15mm along fitted floor normal. Shadow uses a projected lower-contour convex hull with narrow contact and wide ambient layers; light direction is visually chosen, not photometrically recovered. Bound RGB/exposure/saturation adjustment to the scene cardboard ROI, blur texture mildly, and align lighting to gravity. Hide structural IDs and omit misleading structural size values in the ledger. Keep attribution, hashes and before/after camera diagnostics in docs/placement-correction.

- 2026-10-20 finishing pass: Calibrate the added upward-face shader from explicit top/side photo polygons and the prior rendered ratio. Add a metric 12mm contact rim, retain existing shadows. Limit orbit to +/-3 degrees and fade the exposed edge up to 6.5 percent without changing SHARP K. The user selected candidate/exclusion AMR areas as the next stage; do not add route planning or robot control.
