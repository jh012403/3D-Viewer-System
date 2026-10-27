# Prepared demo package

This package is **prepared-results playback**, not a claim of live model inference.
The normal application and its original caches are unchanged.

- Fixed site photograph: warehouse / inbound-outbound area (`twin-logistics`).
- The standalone intake workflow has its own fixed cardboard-box photograph, as in the existing two-screen UI. It is not falsely presented as a crop of the warehouse.
- Background splat and metric surface: real existing SHARP / Depth Anything V2 outputs.
- Initial graph: the existing photo-guided curated warehouse graph, copied here (7 assets, 8 relations, 2 zones).
- Segmentation: actual SAM3 mask and cutout from `job_000006`.
- Mesh/specification: actual completed TRELLIS.2 GLB and FastVLM metadata from that same job.
- Updated graph, asset list and composite: saved from actual browser placement during rehearsal. The browser continues to compute registration, support relations and ledger updates normally.

`public/` and `responses/` contain large local prepared files; they are git-ignored. `manifest.json` records file hashes. Rebuild them with `python demo/prepare_assets.py` while the original local services and source assets are available. Then complete a rehearsal to refresh `graph-updated.json`, `asset-list-updated.json` and `composite-result.png`.

The API replays scene stages over 8 seconds, segmentation over 4 seconds and mesh stages over 8 seconds. These are presentation delays, not inference benchmarks. Different demo clicks/prompts intentionally return the fixed mask. Only the isolated server with `DEMO_MODE=1` implements this behavior.
