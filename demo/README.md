# PRISM SCENE · OBS 자동 시연

기존 프론트·백엔드는 수정하지 않습니다. Python Playwright가 실제 UI를 조작합니다. 완료 대기와 추론 시간도 자르지 않는 연속 영상입니다.

## 현재 우선 실행: 한 번 끝까지 녹화

완료 영상: `storage/obs-demo/record-/20261027-232637/capture-h264_nvenc.mp4` (**8분 13.70초**). OBS 연결 거부로 ffmpeg/NVENC 화면 녹화를 사용했고 원본 MKV도 보존했습니다. 메시 생성은 260초 완료 대기에서 시간 초과하여 회전을 건너뛰었습니다. 이전 생성 자산 `job_000006`임을 표시하고 배치·그래프·대장·종료 화면까지 계속했습니다. 단계 기록: [last-recording.json](last-recording.json). 프레임 분석·화질 조정·재녹화는 하지 않았습니다.

```powershell
$env:PYTHONUTF8='1'
.runtime/scene312-env/Scripts/python.exe demo/finish_once.py
```

`finish_once.py`는 기존 `run.py`의 설정·커서·브라우저 조작·OBS 제어를 재사용합니다. 각 단계는 최대 5분 안에 종료하고, 실패는 `run.json`에 기록한 뒤 다음 단계로 넘어갑니다. OBS 설정 변경, GPU 품질 검사, 프레임 분석, 품질을 이유로 한 재녹화는 하지 않습니다. 녹화 방식은 현재 OBS WebSocket → ffmpeg gdigrab 1920×1080/30fps NVENC CQ20 → libx264 veryfast CRF20 → Playwright 순입니다. 종료 시 `finally`에서 녹화를 끝내고 MKV를 보존하며 MP4로 재인코딩 없이 변환합니다.

실제 메시 생성이 시간 안에 완료되지 않으면 작업은 서버에서 계속됩니다. 배치 단계는 이미 완료된 생성 자산을 사용할 수 있으며, 그 경우 화면 자막과 `placement_fallback`에 명시합니다. 새 자동 그래프와 구역·추천 위치가 있는 기존 운영 캐시는 구분합니다. 녹화 결과와 단계별 성공/실패 사유는 `storage/obs-demo/record-/날짜시간/run.json`에 있습니다.

아래 내용은 최초 상세 검증 모드(`run.py`)와 수동 설치 참고입니다. **현재 한 번 녹화 작업에는 추가 리허설·워밍업·OBS 설정 변경이 필요하지 않습니다.**

## 실행

저장소 루트 PowerShell에서:

```powershell
$env:PYTHONUTF8='1'
.runtime/scene312-env/Scripts/python.exe -m pip install -r demo/requirements.txt
powershell -ExecutionPolicy Bypass -File demo/start-services.ps1
# OBS 설정을 끝낸 뒤, GPU 작업은 한 번에 하나씩 실행
.runtime/scene312-env/Scripts/python.exe demo/warmup.py
.runtime/scene312-env/Scripts/python.exe demo/run.py --rehearsal --speed 0.3
.runtime/scene312-env/Scripts/python.exe demo/run.py --speed 1.0
```

설치된 Chrome을 Playwright의 `channel='chrome'`로 구동합니다. Chromium 기반 headed 브라우저이며, 기존 사용자 Chrome 프로필에는 접근하지 않습니다. `chrome://gpu`의 Shadow DOM을 읽어 WebGL 하드웨어 가속을 확인한 후 시나리오를 시작합니다. 주 모니터 물리 해상도·DPI로 viewport/deviceScaleFactor를 정하고, CDP에서 실제 창 상태를 fullscreen으로 지정합니다. `--kiosk`만으로 새 창에 전체화면이 적용되지 않는 문제를 피합니다.

`demo/config.json`에 입력 사진, 물체 텍스트, 서비스 주소, 대기 한도, 배치 높이, OBS host/port/password 환경변수 이름이 있습니다. `--speed 0.3`은 보여주기·움직임 시간만 0.3배로 줄입니다. 추론 타임아웃·OBS 수동 모드 5초 카운트다운은 줄이지 않습니다. `--no-captions`로 하단 자막을 끕니다. `run.py` 상단의 SPEED와 설정 파일 기본값은 1.0입니다.

OBS를 시작하고 캡처 준비를 끝낸 뒤 녹화 명령을 실행하세요. 녹화 중에는 다른 창을 활성화하거나 마우스·키보드를 조작하지 마세요. 디스플레이 캡처에는 실제 주 모니터 화면이 그대로 들어갑니다. 실패 시 해당 단계·예외·스크린샷·HTML을 저장하고, 스크립트가 시작한 녹화만 종료합니다. 이미 사용자가 녹화 중인 세션은 건드리지 않습니다.

## 실제 UI에 맞춘 시나리오

1. 전체 레이아웃 3초 → 배경 JPEG 업로드. 현장 업로더에는 처리 전 원본 미리보기가 없으므로 **업로드한 File 객체의 실제 사진**을 캡처 전용 라이트박스로 3초 표시합니다. 원래 UI 기능으로 주장하지 않습니다.
2. 실제 SHARP·DAV2·Qwen·SAM3 처리를 기다린 후 자동 그래프 5초, 노드 4개 hover/선택 각각 2초, 요약·정보 카드 천천히 스크롤.
3. 새 자동 장면에는 운영 구역·추천 위치가 없으므로 **같은 사진의 검토된 운영 캐시로 명시적으로 전환**합니다. 자막으로 전환을 알리고 이 시점의 노드·관계 수를 배치 전 기준으로 기록합니다. 기존 시연 캐시는 재생성하지 않습니다.
4. 별도 메시 화면에서 일반 물체 사진 업로드 → 물체 이름 입력 → 실제 SAM3 분리 → cutout 3초. 현재 UI는 텍스트 선택 방식이며 좌표 클릭으로 마스크를 생성하는 기능은 노출되어 있지 않습니다. 가짜 클릭 기반 추론은 만들지 않습니다.
5. 실제 메시 생성 진행률과 완료 신호를 기다림 → 모델 360° 이상 드래그 회전·확대·축소. 원래 씬 탭을 보존한 채 생성된 새 job의 GLB를 가져옵니다.
6. 실제 추천 지지면 클릭 → 높이 0.35m·기존 0.50m 이격 검사 → 빈 위치 찾기 → 4초 확인 → 반입 확정. 기준을 몰래 낮추지 않습니다.
7. 새 노드·지지 관계·대장·KPI 갱신 확인 → 새 노드 선택 → 자산 행 각각 2초 → 마지막 화면 3초.

파일은 `storage/obs-demo/` 아래에 저장합니다. `rehearsal-/날짜시간/`와 `record-/날짜시간/`에 `run.json`, `timestamps.md`, 단계 PNG, `chrome-gpu.txt`가 생깁니다. 실제 MKV/MP4는 OBS 설정의 녹화 경로에 저장합니다. `run.json`의 `mp4` 경로를 확인하세요. OBS 연결 실패 시 수동 모드로 표시하고 5초 뒤 브라우저 조작만 진행합니다. 이 경우 자동 녹화·통계·remux는 완료했다고 보고하지 않습니다.

## 워밍업과 입력 보존

`warmup.py`는 별도 캐시에 실제 현장 생성과 실제 SAM3 → FastVLM → TRELLIS 작업을 순차 실행합니다. JPEG 뒤에 매 실행 식별자를 붙여 픽셀을 그대로 유지하면서 기존 캐시 키와 분리합니다. 최초 업로드·리허설·녹화는 서로 다른 캐시를 사용해 **캐시 로드를 실시간 생성처럼 표시하지 않습니다**. 새 파일은 storage 안에만 생깁니다.

모델이 작업마다 해제되고 메시 모델이 별도 프로세스로 실행되므로 워밍업은 OS 파일 캐시·커널 준비 효과입니다. 모델을 모두 VRAM에 계속 두거나 다음 작업의 초기화 시간을 없애는 기능은 아닙니다. 영상에는 실제 대기 시간이 들어갑니다.

메시 생성 화면으로 넘어간 동안 보이지 않는 현장 탭은 CDP lifecycle frozen으로 일시 정지하고, 복귀 직전에 active로 되돌립니다. 앱 코드나 그래프 데이터를 바꾸지 않고 숨은 splat 렌더 루프의 GPU 사용을 줄이는 브라우저 조작입니다. `freeze_hidden_scene: false`로 끌 수 있습니다.

## OBS에서 직접 설정하는 순서

1. OBS **도구 → WebSocket 서버 설정**에서 서버 사용, 포트 4455, 인증 사용을 설정합니다. 비밀번호는 `$env:PRISM_OBS_PASSWORD='로컬 비밀번호'`에만 넣습니다. 채팅·Git에 넣지 않습니다. 전용 포터블은 git에서 제외한 `demo/obs.local.json`을 사용합니다.
2. 새 장면에 **디스플레이 캡처**를 추가하고 주 모니터를 실제 목록에서 선택합니다. **커서 캡처 끄기**. 이 PC에서는 Windows Graphics Capture 방식이 정상이며 DXGI 방식은 0×0/검은 캡처여서 사용하지 않습니다. 대안은 Chrome 창 캡처입니다. 녹화 전에 미리보기를 반드시 확인합니다.
3. **설정 → 비디오**: 기본 캔버스와 출력 모두 모니터 네이티브 해상도, 60fps. 이 PC는 1920×1080/100% DPI입니다. 1440p·4K 모니터에서는 다운스케일하지 말고 해당 해상도를 사용합니다.
4. **출력 → 고급 → 녹화**: 표준, MKV, NVIDIA NVENC H.264(또는 HEVC), CQP 16~18, Quality 계열 P5, High Quality, Look-ahead 켜기. 전용 프로필은 H.264/CQP18/P5/Look-ahead를 사용합니다. 추론과 동시에 GPU를 사용하므로 렌더 지연이 생기면 통계로 원인을 확인한 뒤 설정을 조정해야 합니다.
5. 음성이 필요 없다면 데스크톱·마이크 오디오를 음소거합니다. 첫 실행의 **구성 마법사는 닫아야** WebSocket StartRecord가 실제 녹화를 시작합니다.
6. Windows **설정 → 게임 → 게임 모드**, **시스템 → 디스플레이 → 그래픽 → 기본 그래픽 설정 → 하드웨어 가속 GPU 스케줄링**을 확인합니다. 이 스크립트는 시스템 설정을 바꾸거나 재부팅하지 않습니다. OBS 로그의 Game Mode/HAGS 항목도 확인합니다.
7. 녹화 종료 후 스크립트가 `ffmpeg -i input.mkv -map 0 -c copy -movflags +faststart output.mp4`로 재인코딩 없이 remux합니다. MKV는 삭제하지 않습니다. 실패하면 `remux.log`를 보고 MKV를 OBS의 **파일 → 녹화 리먹스**로 변환할 수 있습니다.

포터블 준비: 공식 [OBS 32.1.0 Windows x64](https://github.com/obsproject/obs-studio/releases/tag/32.1.0) ZIP을 `.runtime/obs-portable-32/`에 풀어 `bin/64bit/obs64.exe`가 있도록 합니다. OBS를 닫은 상태에서 `python demo/setup_portable_obs.py`를 실행하면 **이 전용 인스턴스만** 설정합니다. 기존 설치형 OBS 설정은 수정하지 않습니다. 공식 33.0.0은 이 PC에서 첫 초기화 명령 지연이 관찰되어 별도 32.1.0을 검증했습니다.

## 코드에서 확인한 셀렉터·API·완료 조건

| 단계 | 실제 셀렉터 / 신호 | API / 근거 파일 |
|---|---|---|
| 현장 업로드 | `#cacheOnly`, `#photo`; disabled 해제, `sceneWorkspace.loading===false`, graph.nodes 존재 | POST `/scene-api/build`, GET `/scene-api/jobs/{id}` ready/failed; `frontend/scene.html`, `frontend/src/scene/main.js`, `pipelines/scene/server.py` |
| 원본 비교·캐시 선택 | `#compare`, `#source`, `[data-scene="..."]` | GET `/scene-api/scenes`, `/scene-cache/{id}/scene.json`; main.js |
| 현장 처리 단계 | `.scene-progress`, `.current`, `.failed` | 서버 stage 0~4, ready/failed; `progress.js`, server.py |
| 그래프 | `#tabGraph`, `#graph svg g[role="button"]`, `.graph-summary`, `#assetSpec` | GET scene graph.json; `graph-presentation.js`, `twin-graph.js`, placement.js |
| 물체 사진 | `#fi`, `.dz-preview-img`, `.seg-text-input`, `[onclick="startProc()"]` | POST `/api/upload`; `frontend/prismscan-v2.html` |
| SAM3 선택 | `#seg-picked-preview img`, `#seg-start-selected`; S.seg.selectedId, text.error/seg.error | POST `/api/jobs/{job}/segmentation-text-prompt`; prismscan-v2.html |
| 메시 생성 | `#ppct`, `#proc-desc`, `#psteps`; S.job.status completed/failed | POST `/api/jobs`, GET `/api/jobs/{job}`, `/result`; prismscan-v2.html |
| 메시 뷰어 | `model-viewer.result-model`, loaded, getCameraOrbit() | result.mesh_url, 로컬 model-viewer; prismscan-v2.html |
| 생성 결과 반입 | `#refreshGenerated`, `#generatedAsset`, `#placeGenerated`; placement.pending | GET `/scene-api/generated-assets`, POST `/scene-api/generated-assets/{job}`; placement.js/server.py |
| 배치 확정 | `[data-spot="spot-0"]`, `#assetHeight`, `#findSafe`, `#confirmAsset`; simulation.draft, result.state=clear, items.length | 프론트 3D 지지면·간섭 검사; placement.js/simulation.js |
| 대장·증분 | `#tabAssets`, `#assetLedger tbody tr`, `#kpiTotal`; 노드·관계 수 증가 | 프론트 asset-register-changed; dashboard.js/asset-model.js |

OBS 통계는 녹화 중 2초 간격으로 수집합니다. rendering lag와 encoding/output skipped frames를 별개로 보고하며, 화면이 정지한 추론 진행 화면을 프레임 드랍으로 오판하지 않습니다. `GetStats`가 지연의 원인까지 증명하지는 않으므로 해당 단계·GPU 부하·OBS 로그를 함께 확인합니다.

참고: [OBS 녹화 설정](https://obsproject.com/kb/advanced-recording-settings-guide), [OBS WebSocket](https://obsproject.com/kb/remote-control-guide), [obsws-python](https://github.com/aatikturk/obsws-python), [Playwright 브라우저 실행](https://playwright.dev/python/docs/api/class-browsertype).
