# 최종 발표 자료

[13개 자료 갤러리](index.html). PNG 12장 모두 1920×1080, GIF는 같은 해상도 12초입니다. 이전 발표 파일은 `_old/`에 보관했습니다. 누락 항목은 없습니다.

- 기준은 물류 창고·입출고 구역(`twin-logistics`)과 실제 생성 완료 작업 `job_000003`입니다. 밝은 윗면/어두운 옆면, 12mm 접촉 모서리 그림자, ±3° 회전 제한과 방향별 가장자리 페이드를 적용한 뷰어에서 캡처했습니다.
- 디버그·기술 안내·개발용 버튼은 캡처 전용 CSS로 숨겼습니다. 구조물 ID는 기본 숨김을 유지하고, 나머지 ID는 18px로 확대했습니다. 기존 앱 기능은 제거하지 않았습니다. 10번과 GIF의 실제 간섭 경고는 의도적으로 표시했습니다.
- 06번은 일반 물체인 닫힌 골판지 상자의 실제 원본 사진·SAM3 마스크·TRELLIS.2 메시입니다. [원본 사진](https://commons.wikimedia.org/wiki/File:Small_Cardboard_Moving_Box_Taped_Closed_(47303025881).jpg): HireAHelper, CC BY 2.0. 사양 카드의 종류·재질 한국어 명칭은 사진을 확인해 붙인 발표용 별칭이며, 정확한 자동 추론으로 주장하지 않습니다.
- 08번의 보정 전은 이전에 보관한 원본 시점 캡처, 보정 후는 최신 메시·바닥 정렬·음영·그림자를 적용한 같은 원본 시점입니다. 마무리 음영만 비교한 세 장은 [배치 보정 갤러리](../placement-correction/index.html)에 있습니다.
- 11번은 실제 동일 등록 상태의 KPI·대장·그래프 캡처를 재배치했습니다. 12번은 실제 내보내기 파일의 렌더와 JSON 첫 부분 발췌입니다. 원본 파일은 [exports/asset-register.json](exports/asset-register.json), [exports/asset-relations.json](exports/asset-relations.json), [exports/render.png](exports/render.png)에 있습니다.
- GIF는 생성 완료 결과 비교 2초 → 실제 뷰어의 배치 → 간섭 → 안전 위치 이동 → 등록 → 대장·그래프 갱신 흐름입니다. 생성 추론을 다시 실행한 실시간 녹화가 아니며, 완료된 생성 결과를 재사용하고 대기 시간을 생략한 12초 편집본입니다.

재현: 서비스 실행 상태에서 `frontend`에서 `node scripts/capture-presentation-final.mjs`, 저장소 루트에서 `.runtime/scene312-env/Scripts/python.exe scripts/encode_presentation_final.py`. `manifest.json`에 규격·재생 길이·SHA256을 기록합니다.
