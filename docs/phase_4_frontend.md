# 단계 4 — HTML·CSS·JavaScript 공통 화면

## 구현 범위

FastAPI 실행 후 `/`에서 GrowthPilot 화면을 연다. 좌측 메뉴, 상단 데이터셋·기간 선택, 중앙 업무 화면, 접을 수 있는 우측 AI 패널을 구현했다. 빌드 없이 ES modules를 읽고 같은 origin의 `/api/v1` API를 호출한다.

기존 루트 JSON은 `/api/v1/info`로 옮겼다. `/static/styles`와 `/static/src`만 정적 공개하며 테스트 파일·Node 의존성은 제공하지 않는다. 소스 체크아웃의 `frontend/`가 실행 시 필요하다. 배포 이미지에 포함하는 작업은 단계 13에서 수행한다.

실제 사용할 수 있는 기능은 데이터셋 선택·목록·생성·이름 변경이다. 저장 시 version을 전달하고, 저장 중 중복 클릭을 막으며 실패하면 입력을 유지한다. 409 충돌은 최신 정보를 다시 불러오는 버튼으로 복구한다. Overview는 실제 데이터셋 총수·선택 데이터·기준 시점을 표시한다.

모든 메뉴에 접근할 수 있지만 고객 KPI·캠페인·성과·정책·CSV 업로드 화면은 아직 연결 전이다. 없는 지표를 0이나 임의 숫자로 표시하지 않는다. AI 패널에는 준비 상태와 요청 예시를 보여주며 입력은 비활성화했다. 실제 LLM은 단계 6 직후 AI-A에서 연결한다.

## 파일별 역할

| 파일 | 역할 |
| --- | --- |
| `frontend/index.html` | 한국어 문서, 메뉴·필터·본문·AI 영역, 본문 바로가기 |
| `styles/tokens.css` | 색상·글꼴·공통 디자인 값 |
| `styles/layout.css` | Grid/Flex·데스크톱·모바일 배치 |
| `styles/components.css` | 카드·폼·버튼·로딩·오류·메뉴 |
| `src/app/router.js` | hash 파싱·검증·이동, 한국 날짜의 UTC 기간 변환 |
| `src/app/store.js` | 현재 URL 상태·선택 데이터·로딩·오류 |
| `src/app/main.js` | 화면 선택·요청 취소·필터·패널 이벤트 |
| `src/api/client.js` | fetch·응답 검증·공통 오류·취소·데이터셋 API |
| `src/components/dom.js` | textContent 기반 DOM과 공통 상태 표시 |
| `src/components/chart.js` | SVG 막대와 동일 수치의 접근 가능한 표 |
| `src/features/data/index.js` | 데이터셋 목록·생성·수정·검색·페이지 이동 |
| `src/features/overview/index.js` | 현재 연결 상태와 업무 흐름 안내 |

## 화면 상태와 요청 수명

후속 개선: 첫 진입에만 본문 로딩 화면을 표시한다. 메뉴 이동·저장 후 재조회 중에는 기존 본문을 유지하고 새 데이터가 준비되면 갱신한다. 대기 중인 이전 본문은 `inert`와 `aria-busy`로 표시해 오래된 버튼 조작을 막고, 상단 메뉴는 다른 화면으로 이동할 수 있게 유지한다. 같은 메뉴 안의 갱신에서는 본문으로 포커스를 강제 이동하지 않는다. 지연된 API 응답 동안 본문이 로딩 화면으로 교체되지 않는지 브라우저 테스트로 확인한다.

주소 예시는 `/#/data?dataset=<UUID>&from=2026-09-01&to=2026-09-19&page=2&q=demo`다. 화면·데이터셋·기간·페이지·검색어를 URL로 복원한다. 새로고침과 뒤로/앞으로 가기가 같은 상태를 재현한다. 상세 리소스 ID도 `/#/customers/<UUID>`처럼 보존하지만 실제 상세 조회는 단계 5에서 연결한다.

첫 방문에 데이터셋이 있으면 첫 항목을 선택하고 UUID를 URL에 기록한다. 없으면 생성 안내를 보여준다. 상단 목록은 첫 100개까지 제공하고, 나머지는 Data 메뉴의 페이지에서 선택한다. 직접 지정한 UUID가 없으면 다른 데이터셋으로 자동 대체하지 않고 복구 버튼을 제공한다.

데이터셋 목록은 서버 페이지네이션을 사용한다. 현재 백엔드에는 이름 검색 API가 없으므로 검색 범위는 **현재 페이지**라고 표시한다. 원천 분포 SVG와 표도 표시 중인 데이터셋의 DEMO/UPLOADED/SIMULATED 건수만 사용한다.

화면 전환마다 이전 AbortController를 취소한다. 해당 화면의 fetch와 이벤트 리스너도 같은 signal로 정리한다. 늦게 도착한 이전 응답은 새 화면을 덮어쓰지 않는다. 저장 성공 후 API를 다시 조회한다. 오류에는 제공된 request_id를 표시한다.

기간은 Asia/Seoul의 시작일·종료일 포함 선택이다. API용 변환은 `[시작일 자정, 종료일 다음 날 자정)`의 UTC ISO 문자열을 만든다. 단계 4에서는 필터를 보존하고 실제 기간별 고객 집계에는 단계 5에서 적용한다. 데이터셋의 reference_at은 이 필터로 바뀌지 않는다.

## 실행과 검증

프로젝트 루트에서 실행한다.

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`http://127.0.0.1:8000/`에 접속한다. DB가 없어도 정적 화면은 로드되지만 데이터 조회는 연결 오류로 표시한다. 기본 화면을 여는 데 worker는 필요하지 않다.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend ci
npm --prefix frontend test
cd frontend
npx playwright install chromium
npm run test:e2e
```

백엔드는 루트 HTML·info API·정적 MIME·없는 파일·디렉터리 접근 차단과 기존 PostgreSQL 동작을 검증한다. Node는 날짜 경계·URL 복원·응답 검증·오류·취소를 확인한다. E2E는 실제 FastAPI 정적 파일을 Chromium으로 열고 API 응답을 대체하여 메뉴·기간·새로고침·저장·409 복구·문자열 안전 표시·1280px 배치·모바일 폭을 확인한다. UI 테스트는 실제 DB 통합 테스트와 구분한다.

검증 결과: 백엔드 48개, JavaScript 단위 7개, Chromium E2E 4개 통과. 1280px 데스크톱 스크린샷에서 본문과 AI 패널이 겹치지 않는지 확인했고 390px 모바일의 가로 넘침도 검사했다.
