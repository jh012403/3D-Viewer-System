# Actual-path diagnosis

One fresh, unrecorded UI run on 2026-10-27. Times include the requested presentation pauses.

| Step | Seconds | Result |
|---|---:|---|
| Step 1. PRISM SCENE | 3.0 | SUCCESS |
| Step 2. 배경 사진 업로드 | 3.1 | SUCCESS |
| Step 3. 최초 관계 그래프 생성 | 81.5 | SUCCESS / TOO SLOW (>60 s) |
| Step 4. 물체 선택과 분리 마스크 | 58.5 | SUCCESS |
| Step 5. 3D 메시 생성 | 262.1 | TIMEOUT / TOO SLOW |
| Step 6. 씬 배치 | 27.5 | SUCCESS |
| Step 7. 갱신된 관계 그래프 | 10.9 | SUCCESS |
| Step 8. 자산 목록 | 30.8 | SUCCESS |
| Step 9. PRISM SCENE · 시연 종료 | 3.0 | SUCCESS |

Mesh completion wait exceeded 260 seconds. Placement continued with explicitly identified previous result job_000007, so it is not evidence that the new mesh finished during the scenario.

No production pipeline or model tuning was attempted. Prepared mode addresses long inference waits using existing genuine outputs and explicit replay timing. Simple automation fixes: wait for hydrated model, use the actual new asset ID when selecting its graph node, assert registration and graph growth, and retain stage duration logs.

Supplemental API inspection: GET segmentation-candidates on a completed SAM3 text job attempted unavailable SAM2. The working text-prompt scenario is unaffected; prepared mode returns the saved SAM3 response for both selection routes without changing production behavior.

Prepared-mode integration fix: the first rehearsal reached the mesh result but could not access `#refreshGenerated`, because the existing UI hides the complete generated-assets row when the initial library is empty. The prepared API now exposes its genuine precomputed box from startup. No frontend visibility override or application modification was used. After this change, validation restarts from the first of two required consecutive clean rehearsals.
