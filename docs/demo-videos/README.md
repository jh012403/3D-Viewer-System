# 무대용 시연 영상

이 폴더의 [index.html](index.html)을 브라우저에서 열면 서버·GPU·인터넷 없이 재생할 수 있습니다. 영상을 고른 뒤 **전체 화면**을 누르세요. MP4 파일은 일반 동영상 플레이어에서도 열립니다.

| 장면 | 영상 |
|---|---|
| 햇살 드는 유리 테이블 방 | [sunroom.mp4](sunroom.mp4) |
| 도자기와 꽃 정물 | [ceramics.mp4](ceramics.mp4) |
| 장바구니를 실은 자동차 | [d4f646fcc79650d6.mp4](d4f646fcc79650d6.mp4) |
| 조각상이 있는 전시 홀 | [hall.mp4](hall.mp4) |

각 영상은 실제 웹 화면에서 **배경 선택 → 좌우 탐색 → 그래프와 윤곽 확인 → 추천 위치에 화분 배치 → 새 노드·관계 추가 → PNG·JSON 저장**을 수행한 화면 녹화입니다. 녹화용 단계 자막과 커서 표시를 덧붙였으며, 장면 이미지를 합성한 대체 화면이 아닙니다. 음성은 없습니다.

네 배경은 사전 캐시를 사용합니다. 그래프는 사진을 보고 직접 편집한 시연 콘텐츠이며 자동 인식 정확도를 입증하는 영상이 아닙니다. 추가한 화분은 별도로 제작한 시연용 GLB입니다. TRELLIS 생성 결과로 표시하지 않습니다.

실제 다운로드한 PNG·JSON은 [results](results)에 있습니다. 길이·프레임 수·파일 해시는 [manifest.json](manifest.json), 브라우저 실행 기록은 [demo-recording-run.json](../demo-recording-run.json)에 있습니다.

다시 녹화하려면 scene 서버 실행 후 `frontend`에서 `node scripts/record-demo.mjs`, 저장소 루트에서 `.runtime/scene312-env/Scripts/python.exe scripts/encode_demo_videos.py`를 실행합니다. 기록은 원래 사례·정적 자산과 분리됩니다.
