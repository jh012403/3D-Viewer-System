# Digital twin presentation

Run `powershell -ExecutionPolicy Bypass -File scripts/start-scene.ps1`, then open [the control room](http://127.0.0.1:5173/scene.html?scene=twin-logistics). Run `powershell -ExecutionPolicy Bypass -File scripts/start-mesh-wsl.ps1` for the separate, generic [photo-to-mesh service](http://127.0.0.1:5173/prismscan-v2.html). Existing object selection, GLB generation and standalone download remain available for arbitrary object categories.

## Scenes

Four additional Pexels photos were processed through local SHARP and metric Depth Anything V2. The graph labels, relations, zones and recommendations are manually curated presentation data. They are not accuracy measurements. Sources, download URLs and hashes are in [photo provenance](twin-photo-sources.json).

| Scene | Photo | Assets / relations | Zones / recommendations |
|---|---|---|---|
| Warehouse | [Pexels 4481259](https://www.pexels.com/photo/4481259/) | 7 / 8 | 2 / 2 |
| Laboratory | [Pexels 2280571](https://www.pexels.com/photo/2280571/) | 8 / 9 | 2 / 2 |
| Precision workbench | [Pexels 3912981](https://www.pexels.com/photo/3912981/) | 7 / 8 | 2 / 2 |
| Industrial loading hall | [Pexels 209251](https://www.pexels.com/photo/209251/) | 8 / 9 | 2 / 2 |

Original sunroom, ceramics, groceries and hall remain below these scenes in the library. Original static assets and `external/prism-scan` were not edited. Local cache files are large and ignored by Git; authored JSON is versioned under `assets/twin-demo`.

## Rehearsal

1. Load a scene and orbit within approximately ±5°. Open the asset register, select a row, then inspect the zone-grouped relation graph.
2. Generate a GLB in the generic service or choose any local GLB. The scene's completed-results list imports generated meshes with their FastVLM metadata. The separate equipment-case button loads an authored prop, not a generated result.
3. Place on a recommendation or visible support surface. Red means box interference; orange means insufficient clearance. Draft objects do not enter the register until confirmation. Use the visible height control and transform gizmos to adjust size and position.
4. The default clearance is 0.50m. Laboratory/workbench demonstrations explicitly select 0.10m for tabletop tools. This setting remains visible and is included in the review; it is not changed silently. The safety footprint follows the selected asset.
5. Confirm a clear placement to issue a scene-local EQ ID and update the register, graph and KPIs. Export the original-camera PNG, register JSON, relation JSON, asset-only glTF and one-page placement report. The report opens a print view: choose Save as PDF.

Coordinates, sizes, distances and zone occupancy are estimates from one photograph, not surveyed dimensions or industrial safety certification. Asset status is registration status; no live sensor values are invented. Register JSON borrows AAS-style fields without claiming standard conformance. Transparent surfaces are excluded from depth occlusion; contact shadows are approximations. Orbit cropping reduces edge artifacts, while PNG export retains original-camera framing.

## Processing and preservation

Live scene jobs show reconstruction, metric alignment, recognition, registration and relation stages driven by real worker events. Cached loading has distinct wording. Generic mesh jobs show separation, understanding, generation and specification registration. All viewer modules and decoders are local npm assets; no runtime CDN is required.

No new precision/recall evaluation, five-photo review or RANSAC work was performed. Historical evaluation documents remain archival. Reboot and GPU power controls remain user-managed.

## Delivery

[Four offline MP4 films and actual reports](twin-videos/index.html) are ready: warehouse 81s, laboratory 91s, workbench 93s, industrial hall 79s. One actual generation recording is reused with explicit editing disclosure. All four films passed local file playback without external requests; every report is one page. [Generation evidence and limitations](mesh-runtime-recovery.md) distinguish the successful service workflow from the generated mesh's incomplete hidden geometry.
