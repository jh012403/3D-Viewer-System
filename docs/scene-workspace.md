# Local scene workspace

The current entry point is the [digital-twin control room](digital-twin.md), with four industrial scenes above the original four scenes. The original presentation workflow below remains available. The separate mesh service now uses a native Windows SAM3/FastVLM environment and a WSL TRELLIS runtime; see [runtime recovery](mesh-runtime-recovery.md) for the current verification checkpoint.

## Presentation

Run `powershell -ExecutionPolicy Bypass -File scripts/start-scene.ps1` from the repository, then open http://127.0.0.1:5173/scene.html . Default demonstration mode reads local caches only. Select a background, orbit slightly, inspect the graph, select the demo planter, click a recommended position, then Save. Existing GLB import and move/rotate/scale controls remain available.

Four graphs were manually curated from automatic detections using the source photos: sunroom 8 nodes/10 edges, ceramics 9/9, groceries 8/10, hall 10/10. Each scene has two recommended placements, Korean labels, thumbnail nodes, contour highlights and a paragraph summary. Placement appends a node and support edge. The demo planter is an authored GLB, not a TRELLIS output.

Horizontal orbit is +/-5 degrees, vertical +/-0.5 degrees, pivot radius 0.12m and preview zoom 1.13. The preview crops edges; PNG export uses the original camera framing. Nearby clicks snap to recommendations and props settle over 650ms. Placement uses collision checks, transparent-surface occlusion exclusion, soft depth boundaries, color adjustment and contact shadows. All eight recommended positions passed browser collision/settling checks.

## Offline fallback

Open [the offline video gallery](demo-videos/index.html) directly in a browser without a server. [Video delivery notes](demo-videos/README.md) link all four MP4s and actual PNG/JSON exports. Videos record real browser interaction with step captions and cursor, without audio. Cache rehearsals made no external or inference requests. All four 1600x1000 videos passed offline playback checks.

## Processing and preservation

Disable demonstration mode to process a new background. Worker events drive depth estimation, 3D reconstruction, object recognition and relation analysis. This change verified callbacks and UI states; no new GPU inference run was performed. Cache loading has separate wording.

Accuracy evaluation, five-photo review, precision calculations and RANSAC work are stopped at the user's request. Historical review documents are retained only as archives and do not measure these curated graphs. Live-path changes are limited to directed on, no under, structural direction exclusions and category/position labels instead of RGB colors. Automatic reprocessing skips curated caches.

Reflection, occlusion, contact geometry, glass and hidden surfaces remain monocular reconstruction limitations. Contact shadows are a radial approximation replacing unavailable original code. JSON records authored provenance. Original cases and external/prism-scan remain untouched.

## Environment and resume

Use Python 3.12 at `.runtime/scene312-env`, with local SHARP, DAV2, SAM3 checkouts and weights. Large caches are git-ignored; [cache hashes](scene-cache-manifest.json) record integrity. Curation sources are `pipelines/scene/curate_demo.py` and `assets/scene-demo/*/graph.json`.

The original 23-24 cases, rm06_U01 and original 15 backgrounds have no backup. TRELLIS.2 now runs in WSL and FastVLM/SAM3 run natively; a fresh generic photo-to-GLB job and standalone download passed. See [mesh recovery checkpoint](mesh-runtime-recovery.md) for actual-run evidence and remaining model limitations. The user controls reboot and GPU power settings; no reboot was performed for this presentation work.


## Box placement correction (2026-10-20)

See [before/after gallery](placement-correction/index.html) and [geometry/mesh notes](placement-correction/README.md). Floor-ROI fitting now supplies gravity where a floor asset is identified. Scene imports of job_000003 use the separate bottom-capped GLB and its placement yaw profile; standalone generation downloads retain their original artifact. The warehouse box is verified at original and plus/minus 5-degree camera views.
