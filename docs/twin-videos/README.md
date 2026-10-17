# Digital twin fallback films

Open [index.html](index.html) directly in a browser. MP4 files are H.264, 1800×1100, 30fps, without audio or external resources. The original four non-industrial films remain at [the original gallery](../demo-videos/index.html).

Each film contains real scene loading, orbit, register/graph inspection, photo segmentation and mesh generation, generated GLB import, a blocked interference state, clearance resolution, asset confirmation, updated graph/KPIs, PNG/JSON export and the actual one-page PDF report.

One actual generation (`job_000002`) is shared across all four edited films. Long waiting intervals are cut/accelerated; this is disclosed in the video caption and gallery. The final download segment was recorded again after fixing a local decoder loader and generic metadata fallback. This is not four separate inference runs. No generated result was substituted with the authored equipment-case fixture.

Rehearsal changes the visible object-height control to fit each support. Laboratory/workbench also explicitly select 0.10m clearance; warehouse/industrial hall retain 0.50m. These are user-selected presentation parameters, not equipment specifications or safety certification. All four use the actual generated mesh, including its imperfect hidden geometry.

See [generation provenance](../twin-real-mesh-provenance.json), [download verification](../twin-real-mesh-run.json), [recorded placement checks](../twin-recording-outro.json), [encoded video hashes](manifest.json) and [offline playback checks](playback-check.json). Actual exports are in `results/`; their graphs include the new asset and inspection threshold.

To rebuild, run `node scripts/record-twin.mjs intro` and `node scripts/record-twin.mjs outro` from `frontend` with both services running. The latter reads the completed generation job from the verification record. Then run `python scripts/encode_twin_videos.py` from the repository using the scene Python environment. These commands record browser actions and encode them; they do not start another inference job. New photo generation is separately exercised by `frontend/scripts/check-real-mesh.mjs`.
