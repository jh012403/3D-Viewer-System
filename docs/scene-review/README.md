> ARCHIVED: accuracy evaluation and review are stopped by user instruction. Current demonstration graphs are manually curated. See ../scene-workspace.md.

# 5장 사용자 검수표

검수 보류 상태의 재생성 자료입니다. 노드 precision/recall 및 관계 정확도는 아직 계산하지 않습니다.

[이미지와 번호를 보며 검수하기](index.html)

범위: 독립된 물체와 주요 지지면. 반사상·물체의 부품·중복 검출은 별도 정답 물체로 세지 않습니다. 라벨은 원본 사진의 좌우 위치이며 RGB 색 추정은 제거했습니다. RANSAC 바닥은 분류 신뢰도가 없는 기하 추정입니다.

맞음=TP, 과검출/잘못된 카테고리/중복=FP. 사진에서 빠진 물체는 한 개체당 한 줄로 추가합니다. 관계도 맞음/틀림과 누락 관계를 기록합니다. 관계는 같은 쌍의 역방향을 중복 정답으로 세지 않습니다.

| 사진 | 노드 | 관계 | 전체 표 |
|---|---:|---:|---|
| dav2-01 | 24 | 15 | [노드·관계 목록](dav2-01.md) |
| dav2-10 | 17 | 16 | [노드·관계 목록](dav2-10.md) |
| dav2-13 | 24 | 28 | [노드·관계 목록](dav2-13.md) |
| dav2-14 | 24 | 30 | [노드·관계 목록](dav2-14.md) |
| dav2-15 | 27 | 23 | [노드·관계 목록](dav2-15.md) |

HTML에서 항목을 검수하고 누락 항목을 입력한 뒤 **검수 확정 JSON 저장**을 누르세요. 임시 저장은 정답 확정으로 취급하지 않습니다.

확정 JSON을 받은 뒤 실행: `python -m pipelines.scene.review_evaluate PATH_TO_REVIEW_JSON`

노드 precision = TP/(TP+FP), 과검출 비율 = FP/(TP+FP), recall = TP/(TP+FN). 관계도 같은 정의를 사용합니다. 결과는 이 5장 검수 범위에 한정합니다.