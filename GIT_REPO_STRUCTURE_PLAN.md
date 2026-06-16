# Git Repository Structure Plan

## 목적

이 문서는 현재 `ai-3d-service`를 공개 가능한 서비스 저장소 형태로 정리하기 위한 엄격한 기준 문서다.

목표는 단순히 파일을 줄이는 것이 아니라, 국내외 유명 소프트웨어 서비스 저장소처럼 다음 조건을 만족하는 구조를 만드는 것이다.

- 루트만 봐도 역할이 바로 이해된다.
- 실행 산출물과 소스코드가 섞여 있지 않다.
- 문서, 실행 방법, 예제, 배포 단서가 분명하다.
- 복제물, 압축본, 캐시, 런타임 바이너리 같은 비소스 자산이 저장소 신뢰도를 떨어뜨리지 않는다.

프로젝트명:

`배경·모델링 베이스용 3D 에셋 생성 서비스`

핵심 파이프라인:

`Image Input -> SAM3 Object Segmentation -> Object-only Image -> FastVLM Metadata Extraction -> TRELLIS.2 3D Asset Generation -> Web Viewer -> Export`

## 엄격 재검토 결과

기존 문서는 방향은 맞았지만, 공개 저장소 품질 기준으로 보면 아직 다음 한계가 있었다.

- “포함/제외” 관점은 있었지만, 유명 서비스 저장소가 공통적으로 갖는 신뢰 구조가 빠져 있었다.
- `docs/`와 `assets/`를 줄이는 기준은 있었지만, `tests/`, `deploy/`, `docker/`, `examples/`, `CONTRIBUTING` 같은 공개 저장소 표준 요소가 언급되지 않았다.
- “무조건 적게 올리는 것”에 기울어 있었고, 실제 서비스 저장소들이 보여주는 “설명 가능성”과 “재현 가능성” 기준이 부족했다.
- 제출용 복제물 제거 기준은 좋았지만, 연구용 문서 중 무엇은 남겨도 되는지의 기준이 더 명확해야 했다.

즉, 기존 문서는 “정리” 문서로는 괜찮았지만, “유명 서비스 repo 수준의 공개 기준”으로는 더 엄격해져야 한다.

## 실제 공개 저장소 사례에서 보이는 공통 패턴

국내외 공개 저장소를 비교해보면, 서비스 성격이 있는 repo는 대체로 아래 패턴을 반복한다.

- 루트에는 소스 진입점, 환경설정, 핵심 문서만 둔다.
- 앱이 크면 `apps/`, `packages/`, `services/` 같은 분리가 있다.
- 문서는 많더라도 `docs/`에 모아두고, 루트는 짧게 유지한다.
- `examples/`, `demo/`, `templates/`는 남기되, 대용량 실행 결과물은 두지 않는다.
- `node_modules/`, `dist/`, `runtime/`, `logs/`, `outputs/`, `uploads/`는 저장소 밖으로 뺀다.
- `CONTRIBUTING.md`, `LICENSE`, `SECURITY.md`, `CODE_OF_CONDUCT.md` 같은 신뢰 문서가 자주 있다.
- 배포/실행 단서로 `docker/`, `deploy/`, `infra/`, `compose.yaml`, `Makefile` 중 일부가 보인다.

## 참고한 실제 저장소 유형

아래 사례를 구조 관점에서 참고하는 것이 적절하다.

### 해외 대표 사례

- `supabase/supabase`
  루트에 `apps/`, `packages/`, `examples/`, `docker/`, `scripts/`, `supabase/`, `tests/`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`가 보이는 대형 서비스형 monorepo다.
- `calcom/cal.com`
  루트에 `apps/`, `packages/`, `tests/`, `scripts/`, `docs/`, 설정 파일들이 모여 있고, 서비스와 패키지를 명확히 분리한다.
- `appwrite/appwrite`
  루트에 `app/`, `docs/`, `tests/`, `docker-compose.yml`, `appwrite.json`, 다양한 정책 문서가 있다. 배포/운영 힌트가 강한 서비스 repo다.
- `n8n-io/n8n`
  루트에 `packages/`, `docker/`, `cypress/`, `patches/`, `README`, `LICENSE`, `SECURITY.md`가 있고, 실행 코드와 배포/문서를 잘 분리한다.

### 국내 공개 사례

국내에서 “서비스 본체 전체를 공개한 repo”는 해외보다 훨씬 적다. 공개된 경우에도 SDK, 샘플, 실험 코드만 제공하는 사례가 많다. 그 안에서 구조적으로 참고할 수 있는 패턴은 다음과 같다.

- `gisman/public-data`
  비교적 가벼운 서비스 repo 형태로 `docs/`, `screenshots/`, 서비스 진입 코드, README 중심 구조를 가진다.
- `marshallku/have-u-tried-this`
  대형 서비스 repo는 아니지만, 웹 서비스 성격 repo에서 README와 앱 코드 중심으로 루트를 짧게 유지하는 패턴을 보여준다.

결론적으로, 국내 사례만 따라가면 표본이 너무 적다. 공개 저장소 구조 기준은 해외 서비스형 repo 패턴을 기본으로 삼고, 국내 repo에서는 “루트 단순화”와 “설명 중심 README” 정도를 참고하는 것이 현실적이다.

참고 링크:

- `https://github.com/supabase/supabase`
- `https://github.com/calcom/cal.com`
- `https://github.com/appwrite/appwrite`
- `https://github.com/n8n-io/n8n`
- `https://github.com/gisman/public-data`
- `https://github.com/marshallku/have-u-tried-this`

## 현재 ai-3d-service 상태 진단

현재 디렉토리는 “공개 저장소”라기보다 “개발 작업 폴더 + 산출물 보관 폴더 + 제출용 복제물 폴더”가 섞인 상태다.

현재 혼재 요소:

- 핵심 서비스 코드:
  `backend/`, `frontend/`, `pipelines/`, `workers/`, `scripts/`, `docs/`
- 런타임/가중치/외부 모델:
  `.runtime/`
- 실행 산출물:
  `storage/`
- 프론트엔드 빌드/의존성:
  `frontend/dist/`, `frontend/node_modules/`
- 제출용 복제물 및 압축본:
  `copyright_submission/`, `copyright_submission.zip`, `copyright_submission_clean.zip`, `배경모델링_베이스용_3D_에셋_생성서비스/`, `배경모델링_베이스용_3D_에셋_생성서비스.zip`
- 데모/테스트용 에셋:
  `assets/`

이 상태로는 “서비스 코드”보다 “정리 안 된 연구 폴더”처럼 보일 가능성이 높다.

## 공개 저장소 기준의 엄격한 원칙

이 프로젝트를 GitHub에 올릴 때는 아래 원칙을 강하게 적용하는 것이 좋다.

1. 루트에는 복제물, zip, 로그, 산출물이 있으면 안 된다.
2. 소스코드와 실행 결과는 같은 트리에 두지 않는다.
3. 외부 모델 런타임과 가중치는 저장소에 포함하지 않는다.
4. README 하나만 읽어도 서비스 목적, 구조, 실행 방법이 이해되어야 한다.
5. `docs/`는 핵심 설계 문서만 남기고, 연구 메모 성격 문서는 분리한다.
6. `assets/`는 설명용 최소 샘플만 남기고 테스트셋/리뷰셋은 제거하거나 외부 보관한다.
7. `frontend/node_modules/`, `frontend/dist/`, `storage/`, `.runtime/`는 반드시 제외한다.
8. `LICENSE`, `.gitignore`, `.env.example`, 실행 가이드가 없으면 공개 저장소 완성도가 떨어진다.
9. “서비스 repo”라면 테스트가 없더라도 왜 없는지, 어떤 방식으로 검증했는지가 문서에 드러나야 한다.

## 권장 공개 루트 구조

현재 프로젝트는 monorepo처럼 과하게 쪼갤 필요는 없다. 지금 상태에서는 아래 구조가 가장 자연스럽다.

```text
ai-3d-service/
├─ README.md
├─ LICENSE
├─ .gitignore
├─ .env.example
├─ environment.yml
├─ pyproject.toml
├─ backend/
├─ frontend/
├─ pipelines/
├─ workers/
├─ scripts/
├─ docs/
├─ assets/
└─ deploy/
```

`deploy/`는 지금 없어도 되지만, 추후 `docker-compose.yml`, 배포 스크립트, 서비스 실행 예시를 둘 자리를 만들면 공개 저장소 인상이 더 좋아진다.

## 포함 대상

공개 저장소에 포함할 핵심 대상은 아래다.

- `backend/`
  FastAPI 엔드포인트, job API, 설정, job store, 서비스 main
- `frontend/`
  업로드 UI, cutout 확인 UI, 결과 뷰어, mesh viewer, 스타일, 라우팅
- `pipelines/`
  SAM3, FastVLM, TRELLIS.2 연동과 메타데이터, cleanup, material package, viewer package
- `workers/`
  비동기 작업 처리 로직
- `scripts/dev/`
  로컬 실행 스크립트
- `docs/`
  공개 가치가 높은 설계 문서
- `README.md`
  서비스 소개, 스크린샷, 로컬 실행, 파이프라인 설명
- `.env.example`
- `environment.yml`
- `pyproject.toml`

## 제외 대상

아래는 엄격히 제외하는 편이 좋다.

- `.runtime/`
- `storage/`
- `frontend/node_modules/`
- `frontend/dist/`
- `__pycache__/`
- `ai_3d_service.egg-info/`
- `copyright_submission/`
- `copyright_submission.zip`
- `copyright_submission_clean.zip`
- `배경모델링_베이스용_3D_에셋_생성서비스/`
- `배경모델링_베이스용_3D_에셋_생성서비스.zip`

## docs 정리 기준

서비스 공개 저장소에서는 `docs/`가 너무 연구 일지처럼 보이면 안 된다.

우선 공개 추천:

- `docs/architecture.md`
- `docs/pipelines.md`
- `docs/object_selection.md`
- `docs/result_contract.md`
- `docs/quality_gate.md`

내부 보관 또는 2차 공개 추천:

- `docs/runtime_issues.md`
- `docs/failure_cases.md`
- `docs/image_recon_benchmark.md`
- `docs/repeatability.md`
- `docs/image_alternative_models.md`
- `docs/image_backends.md`
- `docs/wonder3d_official_recovery.md`
- `docs/image_upgrade_plan.md`
- `docs/test_dataset.md`
- `docs/trellis2_runtime_lock.md`

기준은 단순하다.

- 사용자/기여자가 구조를 이해하는 데 필요한 문서는 공개
- 실험 실패 기록, 복구 메모, 비교 메모는 내부 보관

## assets 정리 기준

`assets/`는 공개 저장소에서 가장 쉽게 지저분해 보이는 영역이다.

권장 정리:

- 유지:
  `assets/mock/`
  README나 서비스 설명에 쓸 대표 샘플만 유지
- 일부만 유지:
  `assets/trellis_demo_ready/`
  데모에 꼭 필요한 샘플만 남김
- 제외 또는 별도 보관:
  `assets/test_datasets/`
  `assets/trellis_demo_512_fallback/`
  임시 JSON, 삭제 기록 파일

공개 저장소에서는 `assets/examples/`나 `assets/demo/`처럼 이름도 더 단순하게 정리하는 편이 낫다.

## 기존 문서 대비 바뀐 판단

이번 재검토에서 바뀐 핵심 판단은 아래다.

- 단순히 “파일을 줄이는 것”만으로는 유명 서비스 repo처럼 보이지 않는다.
- 공개 저장소는 “무엇을 숨길지”보다 “무엇을 명확하게 설명할지”가 더 중요하다.
- 테스트, 정책 문서, 배포 단서는 오히려 저장소 신뢰도를 높인다.
- 반대로 zip, 복제물, storage, runtime, review pack은 강하게 감점 요소다.

## 이 프로젝트에 맞는 1차 공개 저장소 추천안

처음 GitHub에 올릴 때는 아래 구성이 가장 안정적이다.

```text
README.md
LICENSE
.gitignore
.env.example
environment.yml
pyproject.toml
backend/
frontend/
pipelines/
workers/
scripts/dev/
docs/architecture.md
docs/pipelines.md
docs/object_selection.md
docs/result_contract.md
docs/quality_gate.md
assets/mock/
```

추가 가능:

- `assets/examples/`
- `deploy/`
- `CONTRIBUTING.md`
- `SECURITY.md`

## 실제 정리 순서

실제 정리는 아래 순서로 진행하는 것이 좋다.

1. 루트에서 zip과 제출용 복제물 디렉토리를 제거 또는 외부 보관한다.
2. `.gitignore`를 먼저 완성한다.
3. `.runtime/`, `storage/`, `node_modules/`, `dist/`를 Git 제외 대상으로 확정한다.
4. `assets/`를 데모용 최소 샘플 중심으로 줄인다.
5. `docs/`를 공개용 핵심 문서만 남기도록 재편한다.
6. `README.md`를 서비스 소개형으로 다시 쓴다.
7. 필요하면 `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`를 추가한다.
8. 그 다음에 첫 공개 커밋 구조를 만든다.

## 최종 판단

현재 `ai-3d-service`는 핵심 코드 구조 자체는 나쁘지 않다.

좋은 점:

- `backend/`, `frontend/`, `pipelines/`, `workers/`가 이미 나뉘어 있다.
- 서비스 중심 코드의 위치가 비교적 명확하다.
- 문서와 실행 스크립트가 따로 존재한다.

보완이 필요한 점:

- 루트에 복제물, zip, 실행 산출물 계열이 섞여 있다.
- `assets/`와 `docs/`가 공개 저장소 기준으로는 조금 넓다.
- 공개 저장소 신뢰 문서와 정책 파일이 아직 부족하다.

결론:

이 프로젝트는 구조를 처음부터 다시 짜야 하는 상태가 아니다.

필요한 것은 “대공사”가 아니라 아래 두 가지다.

- 공개 저장소에 맞는 제거
- 공개 저장소에 맞는 설명 강화

즉, 다음 단계는 폴더 재설계보다 `README`, `.gitignore`, 루트 정리, `assets/docs` 선별이 핵심이다.
