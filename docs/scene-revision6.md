# 관계·배치 수정 검증 (34a435c 이후)

검수는 보류 상태입니다. 아래 수치는 예측 그래프 변화이며 정확도나 사용자 정답이 아닙니다. 새 검수 묶음은 [여기](scene-review/README.md)에 있습니다.

| 사진 | 노드 전→후 | 관계 전→후 |
|---|---:|---:|
| dav2-01 | 24 → 24 | 22 → 15 |
| dav2-10 | 17 → 17 | 18 → 16 |
| dav2-13 | 24 → 24 | 29 → 28 |
| dav2-14 | 24 → 24 | 32 → 30 |
| dav2-15 | 24 → 27 | 22 → 23 |

| 반례 / 확인 항목 | 전 | 후 |
|---|---:|---:|
| dav2-10 · ceiling on light | 1 | 0 |
| dav2-13 · glass shelf on label | 1 | 0 |
| dav2-14 · glass shelf on bottle | 1 | 0 |
| dav2-14 · bottle on bottle | 5 | 0 |
| dav2-10 · light attached to ceiling | 0 | 1 |
| dav2-15 · object on floor | 0 | 1 |
| dav2-14 · obj-017 retained | 1 | 0 |
| dav2-14 · obj-020 retained | 1 | 0 |
| dav2-14 · obj-022 retained | 1 | 0 |

## 아직 해결되지 않은 바닥 접촉

demo10의 테이블·의자 전체 `on 바닥` 조건은 **미충족**입니다. 바닥은 SAM3 시드와 수평 법선을 사용한 RANSAC으로 확장했지만, 물체 박스에는 가려진 다리가 없습니다. 보이지 않는 바닥 접촉을 정답처럼 추가하거나 박스를 강제로 늘리지 않았습니다.

| 개체 | 관측 바닥과 평면 높이 차(m) | on 바닥 |
|---|---:|---|
| obj-000 table | 0.525 | False |
| obj-002 chair | 0.121 | False |
| obj-003 chair | 0.518 | False |
| obj-004 chair | 0.286 | False |
| obj-005 chair | 0.427 | False |

## 배치 검증

기본 높이 1m 유지. 시연 GLB는 원래 높이 0.686m인 낮은 라운지 의자이므로 사용자 스케일 0.7로 조절했습니다. 최종 0.7m 의자는 오른쪽 관측 바닥에 배치했고 기존 비구조 물체 박스와 겹치지 않습니다. 1m 의자의 충돌 해소도 별도 시험했으며, 관측 범위 안의 추정 바닥을 사용할 때 provenance를 기록합니다.

[원본 시점](screenshots/revision6-chair-original.png) · [−5°](screenshots/revision6-chair--5.png) · [+5°](screenshots/revision6-chair-5.png) · [그래프](screenshots/revision6-graph.png)

±5° orbit은 유지하며 pivot 거리 0.4m와 preview zoom 1.2로 이동량과 가장자리 노출을 줄입니다. 원본 내보내기는 zoom 1입니다. 오른쪽 공간이 좁아 의자 일부가 화면 밖으로 잘리고, 유리 반사와 단안 깊이의 형태 오류가 남습니다. 완벽한 합성이나 모든 가장자리 해결을 주장하지 않습니다.

유리/투명 마스크가 덮는 가림 삼각형을 제외했습니다(77,532 → 37,803). 남은 가림 경계에는 MSAA, 3×3 depth visibility 필터와 ±2.5cm 전이를 적용했습니다. 물체/접지 그림자 모두 같은 깊이 처리를 사용합니다. 생성 GLB의 material.json에 있는 viewerBaseTint/viewerExposureEV를 적용하고 원본 GLB 재질은 보존합니다. 기존 미복구 그림자 대신 현재 radial 접지 그림자를 유지했습니다.

## 검증과 재현

Python 단위 검사 11개, 관계 방향·지지 대상·천장 부착·구조물 제외 JS 검사, Vite 빌드 통과. 오프라인 5장 검수 UI는 외부 요청 없이 미확정 상태를 유지합니다. `python -m pipelines.scene.reprocess --cleanup`, `python -m pipelines.scene.review_pack`, `python -m pipelines.scene.revision_report`로 재생성합니다.

각 graph_sha256은 [기계 판독 비교표](scene-revision6-comparison.json)와 review-pack.json에 있습니다. 과거 검수 결과는 새 해시와 혼용하지 않습니다.
