# GrowthPilot 단계별 상세 구현 계획

작성일: 2026-09-14  
기준 문서: [제품 요구사항 및 전체 구현 계획](implementation_plan.md)  
목적: 요구사항을 실제 개발 티켓으로 나누고, 각 작업의 구현 방법·산출물·검증 기준을 정한다.

이 문서는 구현 예정 설계다. 아래 체크박스는 실제 개발과 검증이 끝났을 때 완료 처리한다. 원문에서 정하지 않은 값은 **MVP 기본안**이며, 제품 요구사항이 바뀌면 관련 테스트와 함께 변경한다.

**포트폴리오 운영 기준:** 방문자는 첫 화면에서 바로 모든 기능을 체험한다. 계정 생성이나 로그인 없이 조회·편집·업로드·정책 설정·승인·모의 발송을 동일하게 제공한다. 프런트엔드는 HTML·CSS·JavaScript로 구현한다. 원문과 이 기준이 충돌하면 이 문서의 기준을 우선한다. 캠페인 승인은 누구나 직접 누를 수 있는 업무 검토 단계로 유지한다.

## 1. 출발점과 구현 범위

### 1.1 현재 구현된 것

- `app/main.py`: FastAPI 앱 팩토리, CORS, 루트 API.
- `app/core/config.py`: 환경변수 설정.
- `app/api/router.py`: `/api/v1` 공통 경로.
- `app/api/routes/health.py`: 프로세스 상태 확인.
- `tests/integration/test_api.py`: HTTP 응답, 문서, CORS 테스트.
- `pyproject.toml`, `.env.example`, `README.md`: 설치 및 실행 기반.

단계 10까지 DB·worker, 공개 데이터셋·감사 이력, CSV 적재·샘플 생성, 공통 화면·고객·대시보드, 세그먼트, 캠페인 편집, 정책 검수·승인, 모의 발송과 성과·실험·보고서를 구현했다. AI-A~D로 지표·세그먼트, 캠페인 초안, 정책 검수와 성과 분석·확인 기반 후속 초안을 연결했으며 최신 마이그레이션은 `007`이다. 다음 단계는 13 통합 검증·배포·시연이다. 패키지 설치로 생성되는 `*.egg-info/`나 `.venv/` 내부는 수정 대상이 아니다.

### 1.2 완성할 사용자 흐름

첫 화면 접속 → 준비된 샘플 데이터 확인·추가 적재 → 대시보드 확인 → 세그먼트 미리보기와 저장 → 캠페인·A/B 카피 작성 → 정책 검수 → 방문자 직접 승인 → 모의 발송 → 성과 비교 → AI 요약과 후속 초안 생성.

각 업무의 서비스와 수동 경로를 먼저 검증한 뒤 바로 AI 도구로 연결한다. 전체 수동 운영 흐름이 끝날 때까지 AI 구현을 미루지 않는다. 첫 AI 시연은 자연어 지표 조회 → 세그먼트 미리보기 → 방문자 확인 후 저장이며, 이후 캠페인·검수·성과 도구를 확장한다. 이메일을 첫 번째 수직 구현 대상으로 삼고, 최종 MVP에는 푸시와 SMS의 카피·채널별 검수·모의 발송도 포함한다.

### 1.3 원문과의 차이 및 보완 결정

| 항목 | 실제 구현 기본안 | 이유 |
| --- | --- | --- |
| API 경로 | 모든 업무 API를 `/api/v1`에 배치 | 기존 프로젝트와 일치 |
| JSON 이름 | 요청·응답 모두 `snake_case` | Python 모델과 JavaScript 객체 필드명 일치 |
| 공개 체험 | 모든 방문자에게 모든 업무 기능 제공 | 첫 화면에서 전체 흐름 체험 |
| 프런트엔드 | HTML·CSS·JavaScript와 브라우저 ES modules | 정적 파일로 실행·배포 |
| 구매 정보 | `orders`, `order_items`, `products` 추가 | 재구매·카테고리·매출 계산의 원천 필요 |
| 수신 동의 | 채널별 동의와 연락처 상태 추가 | 단일 boolean으로 이메일·푸시·SMS 동의를 대신하지 않음 |
| 감사 기록 | AI 로그와 별도로 `audit_logs` 추가 | 수동 변경과 승인도 기록 |
| 승인 근거 | 검수 결과와 대상자 스냅샷을 버전별 저장 | 승인 당시 내용 재현 |
| 작업 처리 | PostgreSQL 작업 테이블과 별도 worker | 프로세스 재시작 시 작업 복구 |
| 예약·중지 | `SCHEDULED`, `PAUSED` 전환은 2차 확장 | 원문 MVP 제외 범위와 정합성 유지 |
| 실험 통계 | A/B 비교는 MVP, 무발송 통제군은 확장 | 통제군 없이 증분 효과를 주장하지 않음 |
| RAG·MCP | MVP 후 별도 단계 | 기본 업무 흐름의 선행 조건이 아님 |

## 2. 전체 작업 순서와 의존성

| 단계 | 목표 | 선행 단계 | 사용자에게 확인 가능한 결과 |
| --- | --- | --- | --- |
| 0 | 공통 계약 고정 | 현재 기반 | API·지표·상태 규칙 문서 |
| 1 | DB·마이그레이션·작업 기반 | 0 | DB 연결과 재시작 가능한 작업 |
| 2 | 공개 데모·변경 이력 | 1 | 모든 기능 즉시 체험과 변경 기록 조회 |
| 3 | 데이터 적재·샘플 생성 | 1, 2 | CSV 적재와 재현 가능한 데이터 |
| 4 | HTML·CSS·JavaScript 공통 구조 | 0, 2 | 대시보드 즉시 진입과 메뉴 이동 |
| 5 | 고객 조회·지표 | 3, 4 | 실제 데이터 기반 대시보드 |
| 6 | 세그먼트 엔진·화면 | 5 | 조건별 고객 수 확인과 저장 |
| AI-A (11·12 일부) | 최소 대화형 에이전트 | 4, 5, 6 | 자연어 지표 조회·세그먼트 미리보기·확인 후 저장 |
| 7 | 캠페인·카피 수동 편집 | 6 | A/B 캠페인 초안 |
| AI-B (11·12 일부) | 캠페인 생성 도구 확장 | AI-A, 7 | 대화로 초안·카피 제안 후 저장 |
| 8 | 정책 검수·승인 | 7 | 제외 내역과 승인 기록 |
| AI-C (12 일부) | 검수 도구 연결 | AI-B, 8 | 대화에서 검수 결과 확인·승인 화면 이동 |
| 9 | 모의 발송·이벤트 | 8 | 중복 없는 실행 결과 |
| 10 | 성과·실험·보고서 | 9 | 계산 근거가 있는 성과 화면 |
| AI-D (11·12 잔여) | 성과 분석·후속 제안 연결 | AI-C, 10 | 실제 지표에 근거한 분석과 다음 초안 |
| 13 | 배포·E2E·시연 | 0~12 | 끊기지 않는 전체 시나리오 |

**실제 착수 순서: 4 → 5 → 6 → AI-A → 7 → AI-B → 8 → AI-C → 9 → 10 → AI-D → 13.** 단계 0~3의 구현은 유지한다. 기존 단계 11·12 번호는 기능 명세의 참조 번호로 유지하며, AI-A~D가 그 작업을 선행 서비스에 맞춰 나눠 실행한다. AI-A~D는 별도 중복 구현이 아니다.

### 2.1 첫 에이전트 시연 — AI-A

구현 안내: [AI-A 지표 조회와 확인 기반 저장](phase_ai_a.md). `004a` 마이그레이션, 실제/모의 provider, 단일 도구 실행, 독립 채팅 페이지와 확인 저장을 구현했다. 실제 API 도구 선택·지표 일치·조건 미리보기를 검증했다. 실제 LLM을 연결한 브라우저 전체 시연은 남아 있어 최종 완료 기준은 완료 처리하지 않는다. 첫 버전은 선택한 화면 기간으로 요청당 도구 하나를 실행하고 여러 업무는 나누어 요청한다.

예시: “지난달 활성 고객 수를 알려줘. 최근 60일 동안 구매하지 않았고 구매 합계가 30만 원 이상인 이메일 수신 동의 고객을 세그먼트로 만들어줘.”

- [ ] 11-1의 provider·출력 계약, 11-2의 자연어 DSL, 11-5의 실행 로그·평가를 먼저 구현한다. CI는 mock, 실제 LLM 연결은 서버 키를 사용하는 별도 live 검증으로 확인한다. mock만 연결한 상태를 LLM 연동 완료로 표시하지 않는다.
- [x] `app/ai/tools.py`에 `get_metric`, `preview_segment`, `create_segment_draft`를 등록한다. `get_metric`은 단계 5의 허용 지표·기간·dataset만 받아 동일 집계 서비스를 호출한다. 조건 조회는 단계 6 DSL을 사용하며 자유 SQL·임의 테이블 조회는 제공하지 않는다.
- [x] `app/ai/orchestrator.py`에서 사용자 요청 → 모델의 도구 선택 → 인자 검증 → 서비스 호출 → 결과 응답을 수행한다. 도구 횟수·timeout·출력량 제한을 이 첫 버전부터 적용한다.
- [x] `app/api/routes/ai.py`의 `POST /api/v1/ai/chat`과 `frontend/src/features/ai/`를 연결한다. 질문 입력·처리 중·지표 카드·조건 카드·오류·재시도·mock/live 표시를 제공한다.
- [ ] 12-2의 제안 저장·hash·만료·version·중복 확인 방지를 세그먼트 저장에 먼저 적용한다. `create_segment_draft`는 미저장 제안을 만들고 방문자가 적용하면 일반 세그먼트 서비스를 호출한다. 모호한 VIP 등의 조건은 추가 질문으로 확정한다.
- [ ] 모델에는 허용 필드와 집계 결과만 전달한다. 고객 원문·연락처는 보내지 않는다. dataset·기간·reference_at·data_version은 응답 카드에 표시하고 숫자는 도구 결과에서 렌더링한다.
- [ ] AI 대화에서 선택 기간에 해당하는 집계와 고객 수가 일반 화면 결과와 일치하는지 검증한다. timeout·잘못된 도구 인자·만료된 제안·중복 확인이 잘못된 저장을 만들지 않는지 테스트한다.

**완료 기준:** 실제 LLM을 사용해 지표 조회 → 조건 미리보기 → 방문자 확인 → 세그먼트 저장 → 화면 반영을 시연한다. AI 실패 시 수동 조회·세그먼트 편집은 계속 사용할 수 있다. 미구현 캠페인·성과 도구는 등록하지 않고 지원 범위를 안내한다.

### 2.2 이후 에이전트 확장

| 묶음 | 수행할 기존 명세 | 완료 증거 |
| --- | --- | --- |
| AI-B | 11-3, 12-1의 초안·카피 도구, 12-2의 캠페인 제안, 12-3의 카피 카드 | 조건·혜택을 전달해 카피를 만들고 확인 후 단계 7 서비스로 저장 |
| AI-C | 12-1의 validate_campaign, 12-3의 검수 카드 | 단계 8과 동일한 제외·차단 결과 표시, 방문자가 승인 화면에서 결정 |
| AI-D | 11-4, 성과 평가, 12-1의 analyze_campaign, 12-3의 성과 카드·후속 제안 | 단계 10 실제 지표를 조회해 사실·가설·한계를 구분하고 확인 후 새 초안 생성 |

각 묶음에서 11-5 실행 로그·평가와 12-2 제안 검증을 함께 확장한다. 승인 결정과 모의 발송은 끝까지 방문자가 전용 화면에서 직접 수행한다. RAG·MCP·멀티에이전트는 초기 대화 흐름의 선행 조건이 아니다.

## 3. 목표 코드 구조와 책임

```text
app/
  main.py
  core/                 # 설정, 보안, 오류, 시간, 로깅
  db/                   # engine, session, base
  models/               # SQLAlchemy 영속 모델
  schemas/              # API 요청·응답 모델
  repositories/         # 쿼리와 데이터 저장
  services/             # 트랜잭션과 업무 규칙
  api/
    deps.py             # DB 세션, 데이터셋 선택, 공통 요청 정보
    router.py
    routes/             # customers, imports, dashboard, audit 등
  domain/
    segments/           # DSL, 컴파일, 필드 레지스트리
    campaigns/          # 상태 전환, A/B 배분
    policies/           # 검수 규칙과 사유 코드
    analytics/          # 지표 정의와 계산
  ai/                   # provider, schemas, prompts, tools, orchestrator
  workers/              # 작업 claim, 실행, 재시도
alembic/versions/
scripts/                # 샘플 생성과 데이터 재계산
tests/
  unit/
  integration/
  fixtures/
frontend/
  index.html            # 첫 화면과 공통 HTML 구조
  styles/               # tokens.css, layout.css, components.css
  src/
    app/                # main.js, router.js, store.js
    api/                # fetch client.js, JSDoc과 응답 검증
    components/         # 공통 DOM 생성과 이벤트 처리
    features/           # customers, segments, campaigns, reports, ai의 JS 모듈
  tests/                # 순수 JS 로직 단위 테스트
  e2e/
docs/
compose.yaml
Dockerfile
.github/workflows/ci.yml
```

요청 흐름은 `route → service → repository → DB`로 고정한다. 라우터는 입력 검증과 응답에 집중한다. 여러 테이블을 함께 변경하는 트랜잭션은 서비스가 소유하고 repository에서 임의로 commit하지 않는다. AI 도구와 일반 화면은 같은 서비스를 재사용한다.

DB 접근은 SQLAlchemy 동기 세션을 기본안으로 한다. 동기 DB 작업을 수행하는 HTTP 핸들러는 동기 함수로 구성하고, AI 비동기 호출을 연결할 때 DB 작업을 이벤트 루프에서 직접 실행하지 않는다. 외부 AI 응답을 기다리는 동안 DB 트랜잭션을 유지하지 않는다.

## 4. 단계 0 — 공통 계약과 업무 정의

구현 완료: `docs/api_contract.md`, `docs/metric_definitions.md`, 공통 오류·기간·페이지네이션·금액 모델, Clock과 고객 상태·비율 계산. 단위·HTTP 테스트 17개 통과. 아래 저장·집계 규칙은 확정된 계약이며 실제 DB 적용과 업무별 집계 API는 후속 단계에서 구현한다.

구현 과정과 검증 범위: [단계 0 구현 Walkthrough](phase_0_walkthrough.md). 아래 체크는 공통 코드 구현 또는 계약 확정을 의미한다. DB 저장·SQL 집계·프런트 연동 완료를 의미하지 않는다.

### 0-1. API 계약

- [x] `docs/api_contract.md`에 `/api/v1`, UUID, `snake_case`, 오류 형식을 정의한다.
- [x] timezone 포함 시각의 UTC 정규화와 `Asia/Seoul` 날짜 변환을 구현한다. DB의 UTC 저장은 계약으로 확정하고 단계 1에서 적용한다.
- [x] 기간 집계는 `[from, to)`로 한다. 화면의 종료일 포함 선택은 다음 날 자정의 배타적 상한으로 변환한다.
- [x] 목록은 `items`, `total`, `page`, `page_size`로 반환한다. 기본 20건, 최대 100건으로 제한한다.
- [x] 잘못된 입력 422, 없음 404, 상태·버전 충돌 409를 사용한다.
- [x] `error.code`, `error.message`, `error.details`, `request_id` 오류 응답을 구현한다. 검증 오류도 같은 형식으로 변환한다.
- [x] Python `Decimal`과 JSON 금액 문자열을 구현한다. KRW 단일 통화·DB `Numeric` 사용은 계약으로 확정하고 DB 컬럼은 단계 1에서 구현한다.

**완료 기준:** 프런트와 백엔드가 동일한 요청 예시·오류 예시를 사용하며, 빈 결과와 0 나누기의 표현이 정해져 있다.

### 0-2. 기준 시점과 고객 상태

- [x] `docs/metric_definitions.md`에 계산 기준을 작성한다.
- [x] 계산 함수에 `reference_at`을 전달하고 Clock·FixedClock·공통 의존성을 구현한다. 업무 서비스 연결은 해당 서비스 구현 시 진행한다.
- [x] MVP 상태 기본안: 탈퇴가 최우선, 가입 후 미구매 30일 미만은 ACTIVE, 30~59일은 CHURN_RISK, 60일 이상은 DORMANT. 구매 고객은 마지막 구매 기준으로 같은 30/60일 경계를 적용한다.
- [x] 상태와 별개로 활성 고객 KPI는 선택 기간에 VIEW·CART·PURCHASE 중 하나 이상 발생한 고객으로 정의한다. 상태 분포와 혼용하지 않는다.
- [x] `days_since_last_purchase`는 구매가 없으면 `null`로 처리한다. 휴면 VIP의 `GTE 60`에는 미구매 고객이 자동 포함되지 않는다.
- [x] 미래 이벤트 제외와 발생·적재 시각 구분을 계약으로 확정한다. 미래 구매 입력의 오류 처리를 구현하며 원천 조회·집계 쿼리는 후속 단계에서 구현한다.

**완료 기준:** 29/30/59/60일, 자정, 미구매, 탈퇴 고객의 결과를 작은 고정 데이터로 설명할 수 있다.

## 5. 단계 1 — DB와 실행 기반

구현 범위: PostgreSQL Docker Compose, 동기 DB 세션, 001~003 모델·마이그레이션, readiness·작업 조회 API, lease·heartbeat·재시도 worker. 실행 방법과 복구 보장은 [단계 1 실행 안내](phase_1_database_worker.md)에 정리했다. CSV 적재·모의 발송 handler와 004 이후 모델은 해당 후속 단계에서 추가한다.

### 1-1. PostgreSQL 연결

- [x] `pyproject.toml`에 SQLAlchemy, Alembic, PostgreSQL 드라이버를 추가하고 설치 버전을 고정한다.
- [x] `compose.yaml`에 PostgreSQL, 볼륨, healthcheck를 정의한다.
- [x] `.env.example`에 `DATABASE_URL`을 추가한다. 실제 비밀번호를 커밋하지 않는다.
- [x] `app/db/session.py`에 engine과 session factory를 작성한다.
- [x] `app/api/deps.py`에서 요청 종료 시 세션을 닫고 실패 시 rollback한다.
- [x] `/health`는 프로세스 확인으로 유지하고 `/api/v1/ready`에서 DB 연결을 확인한다. DB 장애면 503을 반환한다.

### 1-2. 모델을 의존 순서대로 추가

| 마이그레이션 묶음 | 테이블 | 핵심 제약·추가 필드 |
| --- | --- | --- |
| 001 데모 이력 | `datasets`, `audit_logs` | dataset_id, actor_type, resource_id, action, request_id |
| 002 고객 원천 | `customers`, `customer_channels`, `products`, `orders`, `order_items`, `customer_events` | external_id unique, 고객+채널 unique, 외부 주문·이벤트 ID unique |
| 003 적재·작업 | `import_batches`, `jobs`, `dataset_versions` | job 상태, 재시도, 오류 요약, 데이터 버전 |
| 004 세그먼트 | `segments`, `segment_revisions` | condition_json, version, reference_at, created_source, archived_at |
| 005 캠페인 | `campaigns`, `campaign_variants`, `campaign_exclusions` | version, segment_revision_id, 채널, 쿠폰 만료, KPI, A/B 비율 |
| 006 검수·승인 | `validation_runs`, `validation_recipients`, `approvals` | campaign_version, policy_version, data_version, 대상 집합, decision_source, decided_at |
| 007 실행·성과 | `campaign_runs`, `campaign_deliveries`, `campaign_events` | idempotency key, 승인 ID, variant_id, event external_id, order_id |
| 004a AI 기반 (AI-A에서 선행) | `ai_execution_logs`, `ai_action_proposals` | 작업 종류, provider, 모델, 상태, 제안 payload/hash, 확인·만료 시각 |

AI 테이블은 기존 008 일괄 추가안 대신 AI-A에서 004 세그먼트 이후 먼저 추가한다. 초기 제안은 dataset과 세그먼트에 필요한 필드만 사용하고, 아직 없는 캠페인 테이블에 FK를 만들지 않는다. 후속 도구에 필요한 제약은 해당 단계 migration으로 확장한다. 이미 적용한 001~003b는 수정하지 않고 새 revision의 `down_revision`을 실제 최신 head에 연결한다.

`customer_channels`에는 EMAIL/PUSH/SMS, 동의 여부·변경 시각, 연락처 또는 토큰, 유효성, hard bounce 상태를 둔다. 기존 `marketing_consent`를 수입할 때 이메일 동의로만 매핑하고 나머지 채널은 기본 미동의로 둔다.

업무 테이블·작업·정책·AI 제안에는 dataset_id를 연결한다. 외부 ID unique는 dataset 안에서 적용하고 다른 dataset의 리소스를 연결하는 요청은 거절한다. dataset은 누구나 선택·조회·편집할 수 있다. 작성·승인 이력은 created_source와 decision_source로 VISITOR/AI/SYSTEM을 기록하며 사용자 FK를 두지 않는다.

`orders`는 구매 지표의 원천이다. PURCHASE 이벤트는 주문 ID를 참조하고 매출에 다시 더하지 않는다. MVP는 완료 주문 금액을 사용하며 취소·전액 환불은 제외한다. 부분 환불은 미지원으로 명시하고 적재 시 오류로 처리한다.

`customers`의 구매 합계·주문 수·최근 구매 시각은 파생 캐시다. 주문 적재 트랜잭션에서 영향받은 고객만 갱신하고, 별도 재계산 작업으로 원천과 비교한다. 원천 주문이 없는데 집계 숫자만 업로드하는 방식은 MVP에서 허용하지 않는다.

### 1-3. 제약과 인덱스

- [x] 001~003의 FK, NOT NULL, 금액·수량·상태·작업 진행률 CHECK를 작성한다. 캠페인 비율 제약은 단계 7에서 추가한다.
- [x] 고객 이벤트 `(customer_id, event_at)`, 주문 `(customer_id, purchased_at)` 인덱스를 추가한다. 발송·캠페인 이벤트 인덱스는 단계 9~10에서 추가한다.
- [ ] variant 이름은 캠페인 안에서 unique, 실행 결과는 `(run_id, customer_id)` unique로 둔다.
- [ ] 변형 비율 합계는 서비스 트랜잭션에서 검사한다. 행 하나의 CHECK만으로 합계 검증을 대체하지 않는다.
- [x] Alembic upgrade를 빈 DB와 직전 버전 DB에서 검증한다. 운영 데이터에 downgrade를 자동 적용하지 않는다.

### 1-4. 작업 worker

- [x] `jobs`에 PENDING/RUNNING/SUCCEEDED/FAILED, payload, attempt, available_at, lease_until, heartbeat를 둔다.
- [x] worker가 잠금으로 하나의 작업을 claim하고 주기적으로 lease를 갱신한다.
- [x] lease가 만료된 작업만 재처리한다. 작업별 unique 제약으로 재처리를 안전하게 만든다.
- [x] 작업 생성은 업무 변경과 같은 트랜잭션에 넣는다. `GET /api/v1/jobs/{id}`로 진행률을 제공한다.
- [x] `python -m app.workers.runner` 실행 진입점을 만든다. CSV 파싱·시뮬레이션을 HTTP 프로세스 메모리에만 보관하지 않는다.

**산출물:** DB 설정, 001~003 우선 마이그레이션, readiness API, worker. 004 이후는 해당 업무 단계에서 추가한다.

**완료 기준:** 빈 DB 설치 성공, FK/중복 위반 차단, DB 장애 시 readiness 실패, worker 강제 종료 후 재시작해 작업을 중복 없이 마친다.

## 6. 단계 2 — 공개 데모와 변경 이력

백엔드 기반 구현: 빈 데이터셋 생성·목록·상세·이름 수정 API, version 충돌 검사, 공통 감사 저장·조회, 기존 데이터를 보존하는 003a migration. [단계 2 실행 안내](phase_2_demo_audit.md)에 API와 검증 방법을 정리했다. 아래 화면·샘플·캠페인 요구사항은 단계 3~9 연결 후 완료 처리한다.

### 2-1. 즉시 체험 가능한 진입 흐름

- [ ] 첫 방문에서 대시보드를 표시하고 모든 메뉴와 업무 버튼을 제공한다.
- [ ] 데모는 공개된 합성 데이터를 함께 사용하는 기본안으로 구성한다. 방문자가 작성부터 승인·반려·모의 발송까지 연속 수행할 수 있게 한다.
- [x] 데이터셋과 감사 기록은 사용자 FK 없이 저장하고 실행 주체를 `actor_type=VISITOR|AI|SYSTEM`으로 구분한다. 개인 신원을 뜻하지 않는다.
- [x] DB 연결 정보는 서버 환경변수로만 사용한다. AI 키와 화면 연동은 단계 11에서 추가한다.

### 2-2. 공동 체험 데이터와 충돌 처리

- [ ] 샘플 데이터가 준비된 상태로 공개하고, 업로드 화면에는 즉시 사용할 수 있는 합성 CSV 예제를 제공한다.
- [ ] 같은 데이터에서 여러 방문자가 작업할 수 있다는 점을 화면에 표시한다.
- [x] 데이터셋 이름의 동시 수정은 version 검사로 409를 반환하고 상세 API에서 최신 상태를 조회한다. 화면과 다른 업무 리소스의 version 검사는 해당 단계에서 연결한다.
- [x] 단계 3의 샘플 생성기에 새 `--dataset-key`를 주면 새로운 dataset을 생성한다. 같은 키 재실행은 기존 dataset을 유지하며 방문자의 편집을 덮어쓰지 않는다. 화면 연결은 후속 단계다.
- [ ] 페이지 새로고침 시 URL의 dataset과 리소스 ID로 작업 화면을 복원한다. dataset은 데이터 선택값이며 접근 제한 수단으로 사용하지 않는다.

### 2-3. 감사 이벤트

- [x] `services/audit.py`에서 actor_type, dataset_id, resource_id, action, 이전/이후 version, request_id, 시각을 저장한다.
- [x] 데이터셋 생성·이름 수정은 감사 기록과 같은 트랜잭션에서 처리한다. 삭제(보관)·승인·반려·발송 요청은 후속 업무 서비스에서 연결한다.
- [x] 새 감사 기록에는 요청 본문·이름 원문·고객 연락처·서버 비밀값을 넣지 않는다. 기존 details JSON도 공개 조회에서 제외한다.
- [x] `GET /api/v1/audit-logs`를 누구나 조회할 수 있다. 캠페인 상세 화면 연결은 후속 단계다.

**완료 기준:** 새 브라우저에서 바로 모든 메뉴를 열고 캠페인 작성·승인·모의 발송을 수행할 수 있다. 동시 변경 충돌은 안내되고 실패한 업무 변경이 성공 이력으로 남지 않는다.

## 7. 단계 3 — 데이터 업로드와 샘플 데이터

구현 완료: 5종 CSV 검증·미리보기·worker 확정 적재, 고객 원천 집계, 데이터 버전·감사 이력, 합성 샘플 생성·대조·보관 정리. 처리 흐름과 실행 예시는 [단계 3 실행 안내](phase_3_data_import.md)를 참고한다. 화면·캠페인 성과 CSV·노출 초과 발송 이력은 관련 후속 단계에 연결한다.

### 3-1. CSV 계약과 적재 순서

적재 순서: 고객 → 상품 → 주문 및 주문 항목 → 행동 이벤트 → 캠페인 성과 이벤트.

| 파일 | 필수 필드 예시 | 중복 기준 |
| --- | --- | --- |
| customers.csv | external_id, signup_at, status, email_consent | external_id |
| products.csv | external_id, name, category | external_id |
| orders.csv | external_id, customer_external_id, purchased_at, status, amount | external_id |
| order_items.csv | order_external_id, line_id, product_external_id, quantity, amount | 주문+line_id |
| events.csv | external_id, customer_external_id, event_type, event_at | external_id |
| campaign_events.csv (단계 9~10) | external_id, delivery_id, event_type, event_at | external_id |

연락처·이벤트별 properties는 별도 스키마로 검증한다. CSV 템플릿과 정상/오류 샘플을 `tests/fixtures/imports/`에 둔다.

### 3-2. 미리보기 → 확정 적재

- [x] `POST /api/v1/data/import/{kind}/preview`에서 `text/csv` 원본을 검증하고 `import_batch_id`, 오류 행, 예상 생성·변경·중복 건수를 반환한다.
- [x] CSV는 UTF-8/UTF-8 BOM을 지원하며 파일 20 MiB·데이터 레코드 20만 개를 초과하면 업로드 시 차단한다.
- [x] 필수 컬럼, 타입, 같은 dataset 안의 FK, 음수 금액, 날짜 timezone을 확인한다. 헤더는 1번, 첫 데이터 레코드는 2번으로 센다.
- [x] 오류가 하나라도 있으면 확정 불가로 한다. 오류 상세는 최대 100개와 전체 오류 수를 반환한다.
- [x] `POST /api/v1/data/import/{batch_id}/commit`은 202와 job_id를 반환한다. 보관 원본의 SHA-256을 job에 묶고 worker에서 다시 확인한다.
- [x] worker에서 최신 상태를 재검증한 후 하나의 병합 트랜잭션으로 반영한다. 실제 변경이 있을 때만 `dataset_versions`를 증가시키고 감사 이력을 기록한다.
- [x] 같은 외부 ID·같은 내용은 no-op, 변경 내용은 명시적 upsert에서만 갱신한다. 이벤트 수정과 주문의 고객·구매 시각 변경은 차단한다.
- [x] UUID 배치에 원본 bytes를 PostgreSQL `bytea`로 보관한다. 공유 임시 폴더 대신 DB를 사용하며 7일 경과 후 정리 명령으로 제거한다. 대기·실행 중인 작업의 원본은 보존한다.
- [x] 첫 적재의 dataset `reference_at`을 고정하고 모든 적재에 같은 시점을 요구한다. 원천 주문에서 영향받은 고객 캐시를 갱신하며, 별도 대조·복구 명령을 제공한다.

### 3-3. 샘플 생성기

- [x] `scripts/seed_demo.py`에 `--seed`, `--reference-at`, `--size small|medium|demo`, 새 복사본용 `--dataset-key`를 제공한다.
- [x] small은 고객 300·주문 900·이벤트 6,000건, medium은 고객 5천·주문 1만 5천·이벤트 10만 건, demo는 고객 1만·주문 3만·이벤트 20만 건을 생성한다. 이벤트 수는 주문 연결 PURCHASE를 포함한다.
- [x] VIP 휴면·장바구니 이탈·미동의·탈퇴·hard bounce·연락처 없음·미구매 등 고정 그룹을 생성한다.
- [ ] 노출 초과 그룹의 실제 발송 원천 이력은 campaign_deliveries가 추가되는 단계 9에서 생성한다.
- [x] `device_type`, `LANDING_VIEW`, 주문 연결 PURCHASE를 생성한다. 모바일 이탈 그룹에는 구매를 만들지 않는다. 분석·화면 표시는 후속 단계다.
- [x] 원천 주문에서 고객 집계값을 계산한다. 샘플 집계값을 임의 입력하지 않는다.
- [x] 생성기 버전·seed·기준 시점·크기·dataset key로 중복을 방지한다. 재실행은 기존 데이터를 덮어쓰거나 DB를 삭제하지 않는다.

**완료 기준:** 같은 seed와 기준 시점이면 같은 지표가 나온다. 동일 파일 재업로드가 숫자를 늘리지 않는다. 오류 CSV는 업무 데이터에 반영되지 않는다.

## 8. 단계 4 — HTML·CSS·JavaScript 공통 기반

구현 완료: 공통 화면·정적 제공·hash 라우터·URL 복원·fetch 클라이언트·실제 데이터셋 관리. 백엔드 48개, JavaScript 7개, Chromium E2E 4개 테스트를 통과했다. [단계 4 실행 안내](phase_4_frontend.md)에 실행법과 연결 범위를 정리했다. 아래 완료는 공통 기반이며 고객 지표·캠페인·AI 대화 구현 완료를 뜻하지 않는다.

이 단계에서는 AI 패널의 레이아웃과 미연결 상태를 준비한다. 실제 대화 API·도구 호출은 단계 6 직후 AI-A에서 연결하며 가짜 답변을 실제 AI 응답처럼 표시하지 않는다.

- [x] `frontend/index.html`에 시맨틱 HTML 레이아웃을 만들고 `type="module"`로 `src/app/main.js`를 로드한다. 번들링 없이 브라우저 ES modules를 사용한다.
- [x] `styles/tokens.css`에 색상·간격·타이포그래피 변수, `layout.css`에 Grid/Flex 레이아웃, `components.css`에 공통 UI 스타일을 작성한다.
- [x] `src/api/client.js`에 fetch 기반 요청, 응답 상태·JSON 검사, request_id, 오류 변환, AbortController 취소 처리를 모은다.
- [x] OpenAPI 요청·응답 예시를 기준으로 JSDoc과 필요한 응답 검증 함수를 작성한다. 입력은 HTML 제약 검증과 JavaScript로 검사하고 서버가 최종 검증한다.
- [x] `src/app/router.js`에서 hash 기반 화면 전환을 처리하고 `store.js`에서 현재 dataset·기간·선택 항목·로딩 상태를 관리한다.
- [x] 좌측 메뉴, 중앙 콘텐츠, 상단 기간 필터, 우측 AI 패널을 구성하고 누구나 모든 메뉴에 접근하게 한다.
- [x] 공통 DOM 생성 함수를 `src/components/`에 두고 로딩·빈 데이터·오류·재시도·저장 중·실패 상태를 구현한다.
- [x] 동적 문자열은 textContent로 표시한다. 화면 전환 시 이벤트 리스너와 이전 요청을 정리한다.
- [x] 차트는 SVG 또는 Canvas와 JavaScript로 작성하고 동일 수치의 표와 접근 가능한 설명을 제공한다.
- [x] 기간·페이지·검색어·dataset을 URL과 동기화하고 저장 성공 후 관련 API를 다시 조회해 화면을 갱신한다.
- [x] FastAPI가 `/`에서 index.html, `/static`에서 프런트 정적 파일을 제공하고 `/api/v1`은 업무 API로 유지한다. 기존 `/`의 API 정보는 `/api/v1/info`로 옮기고 기존 테스트를 갱신한다.
- [x] 로컬·배포 모두 HTTP로 제공해 같은 origin에서 `/api/v1`을 호출한다. 개발 실행에 프런트 빌드 서버를 요구하지 않는다.

**산출물:** `frontend/index.html`, `styles/*.css`, `src/app/*.js`, `src/api/client.js`, 공통 DOM 모듈.

**완료 기준:** 기본 API 실행 명령으로 첫 화면과 정적 파일이 로드된다. 메뉴 이동·뒤로 가기·새로고침이 동작하고, 1280px 데스크톱에서 AI 패널을 열어도 본문 주요 버튼이 가려지지 않는다.

## 9. 단계 5 — 고객과 대시보드

구현 완료: 원천 기반 고객 조회·상세·이벤트, KPI·이전 기간 비교·순서형 퍼널·상태 분포와 화면 연결. [단계 5 실행 안내](phase_5_customer_analytics.md)에 API·RFM·기간 기준과 성능 측정을 정리했다. 소속 세그먼트·발송 이력·피로도는 원천 테이블이 없는 후속 기능으로 `not_ready` 계약만 제공한다.

### 5-1. 고객 조회 API와 화면

- [x] `GET /customers`에 검색·상태·가입 기간·페이지·허용 정렬과 기간 활동 필터를 구현한다.
- [x] 목록과 상세 API에서 이메일을 마스킹한다. 향후 LLM 도구용 집계 응답과 고객 조회 모델을 분리한다.
- [x] `GET /customers/{id}`, `/events`를 구현한다. `/deliveries`, `/segments`는 `not_ready`와 total=null 계약을 제공하고 실제 이력은 단계 6·9 이후 연결한다.
- [x] 상세 화면에 구매 합계, 주문 수, 평균 주문 금액, 최근 구매, 현재 채널 동의, 선호 카테고리, 타임라인을 연결한다.
- [x] 기준 시점 이전 완료 주문으로 RFM을 계산하고 `rfm-fixed-v1` 고정 점수 구간과 동점 처리 규칙을 코드·응답·문서에 보존한다.
- [ ] 피로도 점수는 단계 9에서 발송 원천이 생기면 최근 1일/7일 발송 수와 제한 대비 비율로 연결한다. 현재는 `not_ready`다.

### 5-2. 지표 쿼리

| 지표 | MVP 계산 규칙 |
| --- | --- |
| 전체 고객 | `signup_at < to`인 고객, 탈퇴 포함 여부를 화면에 명시 |
| 신규 고객 | `[from,to)`에 가입한 고객 |
| 활성 고객 | 기간 내 VIEW/CART/PURCHASE 고객의 distinct 수 |
| 휴면 고객 | `to` 시점 기준 상태 규칙상 DORMANT인 고객 |
| 구매 전환율 | 기간 내 구매한 활성 고객 / 기간 내 활성 고객 |
| 재구매율 | 기간 내 완료 주문이 2건 이상인 고객 / 기간 내 완료 주문 고객 |
| CRM 기여 매출 | 10단계 기여 규칙으로 귀속된 주문액 합계 |

- [x] `GET /dashboard/overview`, `/funnel`, `/segments`에 동일 기간과 data_version을 사용한다. REPEATABLE READ와 버전 불일치 409로 패널 간 일관성을 검사한다.
- [x] 이전 기간은 바로 앞의 동일 길이 구간으로 정한다. 비율 차이는 `%p`, 상대 변화는 `%`로 구분한다.
- [x] 분모가 0이면 값은 `null`, 사유는 `NO_DENOMINATOR`로 반환한다.
- [x] 퍼널은 기간 내 VIEW→CART→PURCHASE를 시간 순서대로 만족한 distinct 고객으로 계산한다. 단계별 전체 이벤트 수를 퍼널 인원으로 쓰지 않는다.
- [x] 기여 매출은 10단계 전까지 `not_ready`로 표시한다. 미구현을 매출 0으로 표현하지 않는다.

### 5-3. 프런트 연결

- [x] `features/customers/`, `features/dashboard/`에 테이블·상세·KPI 카드·상태 분포·퍼널을 작성한다.
- [x] 집계 기준과 이전 기간 비교를 카드 설명·툴팁으로 표시하고 차트·동일 수치 표 클릭 시 해당 고객 필터로 이동한다.
- [x] 고객 상태 분포와 소속 세그먼트를 구분한다. 세그먼트는 중복 소속 가능성을 안내하고 실제 분포는 단계 6에서 연결한다.

**완료 기준:** 손으로 계산한 고정 fixture와 KPI가 일치한다. 쿼리 수를 기록해 고객 수에 비례하는 N+1을 제거한다. demo 규모의 목록·집계 응답 시간을 측정해 기록한다.

## 10. 단계 6 — 세그먼트 DSL과 조건 빌더

### 6-1. 필드 레지스트리

구현 및 실행 안내: [단계 6 세그먼트](phase_6_segments.md). 아래 완료는 수동 조건·템플릿 경로를 뜻하며 실제 LLM은 다음 AI-A에서 연결한다.

- [x] `domain/segments/fields.py`에 필드명, 타입, 허용 연산자, SQLAlchemy 표현식 생성 함수를 등록한다.
- [x] 최초 필드는 구매 경과일, 구매 합계, 주문 수, 상태, 이메일 동의, 최근 30일 이메일 오픈 수, 선호 카테고리로 제한한다.
- [x] 원문의 `marketing_consent`는 이메일 동의의 호환 별칭으로 정의하고, 화면에서는 채널을 명시한다.
- [x] 나이대 프로파일은 선택적 비민감 집계 속성으로만 사용하고, 자료가 없으면 미집계로 표시한다. 민감정보·연락처 필드는 DSL 목록에 넣지 않는다.

### 6-2. 검증기와 SQL 컴파일러

- [x] `dsl.py`에 AND/OR 그룹과 조건 노드의 Pydantic 모델을 작성한다.
- [x] 최대 깊이 3, 조건 20개, IN 항목 100개를 MVP 제한으로 둔다.
- [x] 연산자별 값 형태를 검사한다. BETWEEN은 정확히 두 값과 오름차순, IS_NULL은 값 없음으로 정한다.
- [x] 숫자 필드에 boolean, 날짜 필드에 임의 문자열, 알 수 없는 필드는 거절한다.
- [x] `compiler.py`는 등록된 표현식과 바인딩 값으로만 SQLAlchemy 조건을 만든다. 사용자 문자열을 SQL 식별자나 raw SQL로 사용하지 않는다.
- [x] 이벤트 조건은 EXISTS/집계 서브쿼리로 작성해 한 고객이 여러 번 집계되지 않게 한다.
- [x] `human_readable.py`가 검증된 DSL에서 설명을 생성한다. LLM이 설명과 조건을 각각 임의 생성하게 하지 않는다.

### 6-3. 미리보기와 저장

```json
{
  "condition": {
    "operator": "AND",
    "conditions": [
      {"field": "days_since_last_purchase", "comparison": "GTE", "value": 60},
      {"field": "total_purchase_amount", "comparison": "GTE", "value": "300000"},
      {"field": "email_consent", "comparison": "EQ", "value": true}
    ]
  },
  "reference_at": "2026-09-14T00:00:00+09:00"
}
```

- [x] `POST /segments/preview`는 count, 고객 비중, 프로파일, 설명, 경고, reference_at, data_version, condition_hash를 반환한다.
- [x] 평균 누적 구매액·선호 카테고리·최근 30일 오픈 고객 수와 비중을 SQL로 계산한다. 캠페인 반응률은 발송 이력이 없어 `not_ready`로 구분한다. AI용 프로파일 변환 함수는 최소 집단 5명 미만을 생략하며 실제 AI 전달은 AI-A에서 연결한다.
- [x] 0명은 저장 가능 경고, 전체의 80% 초과도 경고로 처리한다. 발송 적격 검수와 세그먼트 조건 집계를 구분한다.
- [x] `POST /segments`, `PUT /segments/{id}`에서 같은 검증기를 다시 실행하고 revision을 남긴다.
- [x] 수정 요청은 version을 받는다. 다른 사용자가 먼저 변경했으면 409로 처리한다.
- [x] `DELETE /segments/{id}`는 보관 처리한다. 기존 캠페인이 참조하는 revision은 유지한다.
- [x] 프런트 조건 빌더와 템플릿이 동일 DSL로 미리보기·저장한다. 자연어 입력은 이 단계 직후 AI-A에서 같은 API 계약에 연결한다.

**완료 기준:** DSL·표시 설명·실제 고객 집합이 일치한다. 금액 경계, null, AND/OR, 중복 이벤트, 잘못된 필드, 과도한 중첩 테스트를 통과한다.

## 11. 단계 7 — 캠페인 초안과 카피 에디터

### 7-1. 캠페인 생성

구현 안내: [단계 7 캠페인 초안과 A/B 편집](phase_7_campaigns.md). `005` 마이그레이션, 생성·조회·수정 API와 캠페인 화면을 구현했다. 목표→대상→채널→카피→실험을 한 폼에서 편집하고 서버 저장 성공 후 확인 영역을 연다. 실제 대상자 검수·승인은 단계 8, AI 초안·카피는 AI-B에서 연결한다.

- [x] 005 마이그레이션과 `schemas/campaign.py`, `services/campaigns.py`, `routes/campaigns.py`를 추가한다.
- [x] `POST/GET /campaigns`, `GET/PUT /campaigns/{id}`를 구현한다.
- [x] 이름, 목표, 세그먼트 revision, 제외 세그먼트 revision, 채널, 혜택, 브랜드 톤, KPI와 목표값을 저장한다.
- [x] 날짜는 MVP에서 예정 정보로만 저장하며 예약 실행을 제공하지 않는다.
- [x] 한 캠페인은 한 채널을 가진다. 다채널 운영은 캠페인을 복제해 각각 검수한다.

### 7-2. A/B 편집

- [x] A/B 제목·본문·가설·배분 비율을 저장한다. EMAIL/PUSH는 제목과 본문, SMS는 본문을 사용한다.
- [x] 비율은 정수 basis point로 저장해 합계 10,000을 검증한다. UI에는 50:50 등 백분율로 표시한다.
- [x] 채널별 길이 제한·금지 표현·필수 문구를 버전별 데모 정책 상수와 조회 API로 제공하고 적용 버전을 저장한다. 방문자 Settings 편집·영속 정책은 단계 8에서 추가한다. 실제 발송사·법규 준수를 검증한 정책으로 주장하지 않는다.
- [x] 미지원 개인화 변수는 거절한다. 이메일 HTML을 지원할 경우 저장·미리보기에서 허용 태그만 처리한다.
- [x] 사용자가 수정하면 campaign version을 증가시키고 감사 기록을 남긴다.
- [x] `features/campaigns/`에서 목표·대상·채널·카피·실험을 편집하고 서버 저장 성공 후 저장 내용 확인을 제공한다. 실제 대상자 검수 단계는 단계 8에서 연결한다.

**완료 기준:** AI 없이 A/B 캠페인을 저장·재조회·편집할 수 있다. 비율 오류, 빈 필수 카피, 다른 사용자의 변경 충돌을 화면에서 처리한다.

## 12. 단계 8 — 정책 검수와 승인

구현 안내: [단계 8 정책 검수와 승인](phase_8_policy_approval.md). `006` 마이그레이션, 정책 설정, 대상자 스냅샷 검수, 버전 기반 승인·반려·편집 재개와 Campaigns/Settings 화면을 구현했다. `campaign_deliveries`의 실행 결과·run 연결은 [단계 9 모의 발송](phase_9_simulation.md)에서 확장했다.

### 8-1. 규칙 엔진

각 규칙은 `rule_code`, `severity`, `passed`, `affected_count`, `message`를 반환한다. 고객별 제외와 캠페인 전체 차단을 구분한다.

| 적용 순서 | 고객 제외 규칙 | 주요 데이터 |
| --- | --- | --- |
| 1 | 탈퇴 | customers.status |
| 2 | 채널 수신 미동의 | customer_channels.consent |
| 3 | 연락처 없음·무효·hard bounce | 채널 연락처 상태 |
| 4 | 명시적 제외 세그먼트 | 제외 revision의 고객 집합 |
| 5 | 같은 캠페인 기수신 | campaign_deliveries |
| 6 | 일일·주간 노출 초과 | 채널별 최근 발송·예약된 대상 |

MVP 노출 한도 기본안은 채널별 1일 1회·최근 7일 3회다. 1일은 업무 시간대의 당일 구간, 7일은 실행 시각 기준 이동 구간으로 명시한다. 정책값은 누구나 Settings에서 변경할 수 있고 변경 시 version을 증가시킨다.

- [x] `domain/policies/`의 순수 규칙과 대상 조회를 분리한다.
- [x] 고객이 여러 규칙에 걸리면 모든 사유를 보관하되 집계표의 primary_reason은 최초 사유 하나만 사용한다.
- [x] `최초 인원 = primary_reason별 제외 합계 + 최종 인원`을 보장한다.
- [x] 쿠폰 만료, 필수 문구 누락, 금지 표현, 잘못된 실험 비율, 최종 0명은 캠페인 전체 차단으로 처리한다.
- [x] `POST /campaigns/{id}/validate`에서 검수 기록과 후보 고객 스냅샷을 저장한다. 이 엔드포인트는 검수 기록을 쓰지만 캠페인 내용을 변경하지 않는다.

### 8-2. 승인 대상 고정

- [x] `validation_runs`에 campaign/segment/policy/data version, reference_at, content_hash, count, 만료 시각을 둔다.
- [x] MVP 검수 유효시간은 30분으로 한다. 정책 변경·캠페인 변경 시 즉시 무효다.
- [x] `POST /request-approval`은 현재 version의 유효한 검수가 있을 때만 REVIEW로 전환한다.
- [x] `POST /approve`, `POST /reject`는 승인 요청 ID와 version을 확인하고 decision_source=VISITOR와 결정 시각을 기록한다. 작성한 방문자가 그대로 승인·반려할 수 있다.
- [x] 승인 후 카피·혜택·타깃을 변경하려면 먼저 DRAFT로 되돌리고 기존 승인을 무효화한다.
- [x] 세그먼트 원본이 수정되어도 캠페인은 저장된 revision을 유지한다. 새 revision 적용은 명시적 편집이다.

### 8-3. 상태 전환표

| 현재 | 작업 | 다음 | 필수 조건 |
| --- | --- | --- | --- |
| DRAFT | 검수 | DRAFT | 검수 결과만 저장 |
| DRAFT | 승인 요청 | REVIEW | 최신 검수 통과·대상 1명 이상 |
| REVIEW | 승인 | APPROVED | 방문자 확인·유효한 검수·version 일치 |
| REVIEW | 반려/요청 철회 | DRAFT | 사유 또는 방문자 확인 |
| APPROVED | 편집 재개 | DRAFT | 기존 승인 무효화 |
| APPROVED | 모의 발송 요청 | RUNNING | 유효 승인·실행 직전 검수·멱등 키 |
| RUNNING | 작업 완료 | COMPLETED | 모든 대상 결과 확정 |
| DRAFT/REVIEW/APPROVED | 취소 | CANCELLED | 실행 시작 전 |

RUNNING 중 오류는 캠페인 상태를 임의로 DRAFT로 되돌리지 않고 run/job을 FAILED로 기록한다. 동일 실행을 재개하거나 작업 복구 절차를 따른다. RUNNING 취소·PAUSED·SCHEDULED는 MVP API에서 거절한다.

**완료 기준:** 누구나 승인할 수 있으며 승인 전 발송과 오래된 검수 승인은 409로 처리한다. 승인 후 수정 시 재승인이 필요하다. 동시 승인 요청 중 하나만 성공한다.

## 13. 단계 9 — 모의 발송과 성과 이벤트

### 9-1. 실행 요청을 원자적으로 처리

- [x] `POST /campaigns/{id}/simulate-send`에 `Idempotency-Key`를 필수로 받는다.
- [x] 캠페인 행 잠금 → 상태/승인 검사 → run 생성 → 대상 예약 → job 생성 → RUNNING 전환을 한 트랜잭션으로 처리한다.
- [x] 같은 키·같은 payload면 기존 run을 반환하고, 같은 키·다른 payload면 409를 반환한다.
- [x] 다른 키로 다시 호출해도 RUNNING/COMPLETED 캠페인은 새 실행을 만들 수 없게 한다. 새 실험은 캠페인 복제로 생성한다.
- [x] 서로 다른 캠페인의 동시 실행도 피로도 한도를 넘지 않도록 dataset과 고객을 일정 순서로 잠그고 기존 예약분까지 한도에 포함한다.

### 9-2. 실행 직전 재검수와 A/B 배정

- [x] 승인 스냅샷을 후보 상한으로 사용한다. 새로 자격을 얻은 고객을 실행 시 임의로 추가하지 않는다.
- [x] 현재 탈퇴·동의·연락처·노출 상태를 다시 검사한다. 변경으로 제외되는 고객과 사유를 실행 결과에 기록한다.
- [x] 내용/정책 변경 또는 승인 만료는 재승인을 요구한다. 안전상 제외 인원이 생겼다는 이유만으로 새 고객을 보충하지 않는다.
- [x] 적격 고객을 campaign seed와 고객 ID의 안정적 hash로 정렬하고 비율만큼 A/B로 나눈다. 정수 몫 뒤의 나머지는 B안에 배정한다.
- [x] A/B 배정을 DB에 저장하고 재시도 시 재추첨하지 않는다.

### 9-3. 시뮬레이션 처리

- [x] 외부 발송 API 대신 `Simulator`가 SENT/FAILED/EXCLUDED를 만든다.
- [x] 전달 성공 이후에만 OPEN/CLICK/CONVERSION 이벤트를 만든다. 이벤트 시간 순서와 채널별 가능 이벤트를 지킨다.
- [x] 난수 seed와 반응 확률을 run에 저장한다. 같은 run의 재시도는 동일 결과를 만들고 unique 키로 중복 삽입을 막는다.
- [x] 모의 주문과 이벤트는 `source=SIMULATED`, dataset_id로 구분한다. 보고서에서 분리할 원천 표지를 저장한다.
- [x] 별도 `GET /campaigns/{id}/runs/{run_id}`와 job 조회로 진행률·성공·실패·제외 수를 보여준다.
- [x] 실패 재시도는 동일 run의 예약 고객을 같은 트랜잭션에서 다시 처리한다. 외부 실제 발송과 동일한 exactly-once 보장을 주장하지 않는다.

**완료 기준:** 더블클릭·HTTP 재전송·worker 중단 후 재개에도 고객당 결과 1건이다. A/B 교집합은 0명이고 실행 시점 미동의 고객은 SENT가 되지 않는다.

## 14. 단계 10 — 성과 집계·실험·보고서

### 10-1. 이벤트 정규화와 매출 귀속

- [x] `campaign_events`는 delivery_id·variant_id와 연결하고 외부 이벤트 ID로 deduplicate한다.
- [x] 동일 고객의 여러 OPEN/CLICK은 이벤트 타임라인에는 남기되 비율에서는 distinct 고객 1명으로 센다.
- [x] 기여 모델 기본안: 주문 전 7일 이내 마지막 유효 캠페인 클릭에 주문을 한 번만 귀속한다. 클릭이 없으면 CRM 기여 매출로 계산하지 않는다.
- [x] 동일 시각 클릭의 tie-break는 이벤트 ID로 고정한다. 주문 취소·전액 환불 시 기여를 재계산한다.
- [x] 시뮬레이션 주문도 같은 귀속 함수를 통과한다. 매출을 AI가 생성하거나 별도 숫자로 덮어쓰지 않는다.
- [x] 관찰 기간, 귀속 모델 버전, 집계 시각을 응답에 포함한다.

### 10-2. 성과 API

- [x] `GET /campaigns/{id}/performance`에서 발송·전달·오픈·클릭·전환·매출과 A/B별 분모를 반환한다.
- [x] 오픈율/클릭률/전환율은 해당 이벤트 고객 수 ÷ 전달 성공 고객 수다. CTOR은 클릭 고객 ÷ 오픈 고객이다.
- [x] 푸시/SMS에서 지원하지 않는 OPEN은 0% 대신 `not_applicable`로 반환한다.
- [x] 기간 필터는 발송 cohort 기간과 전환 관찰 기간을 분리한다. 서로 다른 cohort의 분모와 분자를 섞지 않는다.
- [x] 수신 거부 이벤트도 추가해 가드레일 지표를 계산한다.

### 10-3. A/B 결과 판단

- [x] 배정 시 실험 seed, 비율, primary KPI, 관찰 종료 시각, 최소 표본 기준을 고정한다.
- [x] A/B 표본 수, 전환 수, 절대 차이 `%p`, 상대 개선율을 표시한다. 기준군 전환 0이면 상대 개선율은 null이다.
- [x] 비율 신뢰구간은 Wilson 방식으로 계산한다. 적용 방법과 가정을 `metric_definitions.md`에 기록한다.
- [x] 관찰 미종료·최소 표본 미달·가드레일 악화면 판단 보류한다. 50% 상대 MDE의 이론상 검정력 표본을 표시하고, 합성 데이터 시연에는 안별 30명의 별도 하한을 명시한다. 승자 판정은 기존 양측 `p < 0.05`를 그대로 요구한다.
- [x] 통제군이 없는 MVP에서는 증분 전환율·증분 매출을 `not_available`로 표시한다. A/B 차이를 무발송 대비 증분으로 부르지 않는다.

### 10-4. 보고서와 화면

- [x] `features/reports/`, 캠페인 상세, Experiments 화면을 공통 성과 API로 연결한다.
- [x] `GET /reports/summary`, `/reports/campaigns`, `/reports/export`에서 세그먼트·채널·현재/직전 동기간 비교를 제공한다.
- [x] CSV에는 기간·기준 시점·모의 데이터 여부를 포함하고 셀 수식으로 실행될 수 있는 사용자 문자열을 안전하게 처리한다.
- [x] 화면에서 0/미집계/해당 없음 상태를 구분한다. AI 요약 영역은 AI-D에서 연결한다.

**완료 기준:** 작은 fixture의 모든 지표가 수계산과 일치한다. 이벤트 중복, 0 분모, 취소 주문, 기여 경계 7일, 동일 주문 다중 클릭, 관찰 미종료 테스트를 통과한다.

## 15. 단계 11 — AI 기능을 개별 서비스로 연결

이 절은 기능 명세이며 일괄 후행 단계가 아니다. 11-1·11-2와 초기 11-5는 AI-A, 11-3은 AI-B, 11-4는 AI-D에서 수행한다. provider와 프롬프트·출력 스키마는 `app/ai/`, HTTP 진입점은 `app/api/routes/ai.py`, 실제 데이터 조회·저장은 기존 service/repository가 담당한다.

### 11-1. AI provider와 출력 계약

- [ ] `ai/provider.py`에 조건 생성·카피 생성·성과 분석 인터페이스를 만들고 mock provider부터 작성한다.
- [ ] `OPENAI_API_KEY`, `AI_MODEL`, `AI_MODE=mock|live`, timeout, 최대 출력량을 서버 설정으로 둔다. 모델 이름은 배포 시 사용 가능성과 기능 지원을 확인해 고정한다.
- [ ] `ai/schemas.py`에 SegmentConditionResult, CampaignDraftResult, CopyVariantsResult, PerformanceAnalysisResult를 정의한다.
- [ ] 구조화 출력으로 스키마를 제한하되, 필드 허용 여부·금액·업무 상태는 서버에서 다시 검증한다. 거절·출력 중단·파싱 실패는 정상 결과와 구분한다. 구현 참고: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
- [ ] timeout·429·일시적 서버 오류에 제한된 재시도를 적용한다. 스키마 재생성은 1회로 제한하고 최종 실패 시 수동 입력을 제공한다.
- [ ] AI 호출 전후 DB 트랜잭션을 짧게 분리한다. 응답이 돌아오면 입력 resource version이 여전히 같은지 확인한다.

### 11-2. 자연어 세그먼트

- [ ] `POST /ai/segment-condition`에 prompt와 reference_at을 받는다.
- [ ] 필드 목록·연산자·타입·기준 시점만 모델에 제공한다. 고객 행을 보내지 않는다.
- [ ] 응답 DSL을 6단계 검증기와 컴파일러에 통과시킨다.
- [ ] 금액·기간·채널이 모호하면 `needs_clarification`과 질문을 반환한다. 조건을 임의로 넓혀 저장하지 않는다.
- [ ] 설명·고객 수는 서버 DSL 설명기와 집계에서 생성하고, 사용자가 확인한 후 일반 `/segments` API로 저장한다.

### 11-3. 캠페인 초안과 카피

AI-B 구현 안내: [캠페인 AI 생성·자동 채우기](phase_ai_b.md). `005a` 마이그레이션과 실제/모의 생성, 제안·확인 API를 구현했다. 방문자 UI는 Campaigns 오른쪽 AI 카피 어시스턴트에서 생성해 메인 폼의 A/B 입력란을 자동으로 채우는 방식이다. 검토 후 일반 저장 버튼으로 저장하며 일반 챗봇의 캠페인 설정·카드는 제거했다. 실제 API 초안 생성도 검증했다. 공용 Settings 브랜드 가이드 편집은 아직 남아 있으며 현재는 입력한 브랜드 톤을 사용한다.

- [x] `POST /ai/campaign-draft`, `/ai/copy-variants`에 집계 프로파일, 사용자가 정한 목표·혜택·브랜드 톤과 채널별 카피 정책을 제공한다.
- [x] A/B 제목·본문·가설·생성 근거를 반환한다. 혜택 원문 유지와 입력에 없는 숫자 혜택을 검사한다. 비수치 사실의 최종 검토는 방문자가 수행한다.
- [x] AI 결과는 편집 가능한 제안으로 표시한다. 사용자가 적용하면 일반 캠페인 저장 서비스가 version과 감사를 처리한다.
- [ ] 브랜드 가이드는 누구나 Settings에서 편집할 수 있는 짧은 데모 설정 문서로 공급한다. RAG가 없어도 카피 생성이 가능해야 한다.

### 11-4. 성과 분석

구현 안내: [AI-D 성과 분석과 후속 실험](phase_ai_d.md). 해석은 검토된 가설·액션 코드로 제한하며 자유 원인 서술을 생성하지 않는다.

- [x] `POST /ai/performance-analysis`에 캠페인 ID와 기간을 받고 서버가 10단계 집계를 조회한다.
- [x] 출력은 `facts`, `hypotheses`, `limitations`, `recommended_actions`, `metric_refs`로 나눈다.
- [x] 사실에 포함된 숫자는 제공한 metric ID와 대조한다. 근거 없는 수치나 없는 device 데이터를 이용한 설명은 거절한다.
- [x] 원인 설명은 관찰상 가설로 표시한다. 상관관계를 인과 효과로 확정하지 않는다.
- [x] 다음 액션은 허용된 enum과 대상 ID로 반환하고 자동 실행하지 않는다.

### 11-5. AI 로그와 평가 데이터

- [ ] actor_type·dataset_id·작업·모델·prompt version·입출력 요약·시간·토큰 사용량·성공/실패를 기록한다.
- [ ] 자유 입력에 개인정보가 포함될 수 있으므로 모델 전달 전 제거·차단하고 로그에도 원문을 무조건 저장하지 않는다.
- [ ] 한국어 조건 해석 평가셋을 만든다: 기간 경계, 30만 원, 미구매, OR, 부정 조건, 모호한 VIP, 금지 필드 등.
- [ ] CI는 고정 mock 응답으로 실행한다. live 검증은 별도 명령으로 실제 API 성공·거절·timeout을 확인한다.

**완료 기준:** AI가 실패해도 수동 업무 흐름은 사용 가능하다. 잘못된 조건·숫자·도구 인자는 DB 변경으로 이어지지 않는다. mock 결과는 화면에 모의 응답임을 표시한다.

## 16. 단계 12 — 실행형 AI 패널과 사용자 확인

AI-A에서 최소 orchestrator·도구 레지스트리·대화 API·패널·세그먼트 확인 저장을 먼저 구현한다. 같은 구조를 AI-B~D에서 확장하며 두 번째 챗봇이나 별도의 업무 저장 경로를 만들지 않는다. 초기부터 12-1의 실행 제한과 12-2의 확인 검증을 적용한다.

### 12-1. 도구 레지스트리

- [ ] `ai/tools.py`에 get_metric, preview_segment, create_segment_draft, create_campaign_draft, generate_copy, validate_campaign, analyze_campaign을 등록한다.
- [ ] 도구 호출 인자를 스키마 검증하고 선택한 dataset과 리소스의 존재·버전·업무 상태를 서버에서 확인한다.
- [ ] 모델은 도구 호출을 제안하고 서버가 함수를 실행한다. 호출 이름을 임의의 함수명·SQL·URL로 해석하지 않는다. 구현 참고: [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling).
- [ ] 도구 호출 횟수·전체 실행 시간·출력 크기를 제한하고 무한 반복 시 종료한다.
- [x] validate_campaign은 검수 기록을 남기는 제한적 쓰기로 취급한다. 승인·발송 동작을 이 도구에 포함하지 않는다. 구현·검증 범위는 [AI-C 검수 도구 연결](phase_ai_c.md)에 정리했다.

### 12-2. 확인 가능한 액션 제안

- [ ] 저장·승인 요청은 `ai_action_proposals`에 정규화된 payload, hash, dataset_id, actor_type, resource version, 만료 시각을 저장한다.
- [ ] 패널에 조건·카피·변경 내용을 보여주고 사용자가 적용 버튼을 누르게 한다.
- [ ] `POST /ai/actions/{proposal_id}/confirm`에서 dataset·만료·버전·이미 실행 여부를 검사한 후 일반 업무 서비스를 호출한다.
- [ ] 수정된 payload는 기존 확인을 재사용하지 않고 새 제안을 만든다.
- [ ] 승인 결정과 모의 발송은 각각 승인 화면·캠페인 실행 버튼으로 수행한다. AI 도구 목록에 무인 승인·발송을 노출하지 않는다.
- [ ] 프런트가 `confirmed=true`만 보내면 실행되는 방식은 사용하지 않는다.

### 12-3. 패널 UI

- [ ] `POST /ai/chat` 응답을 message, result_type, data, actions, reference_at, request_id로 통일한다.
- [ ] 세그먼트 미리보기·카피 비교·검수 결과·성과 분석 카드 renderer를 분리한다. 검수 결과 카드는 AI-C에서 구현했고 성과 카드는 AI-D에서 추가한다.
- [ ] 저장 성공 시 관련 데이터를 fetch로 다시 조회하고 store와 DOM을 갱신해 상세 화면으로 이동할 수 있게 한다.
- [ ] 실패 후 재시도와 확인 버튼 중복 클릭을 처리한다. 확인된 제안은 다시 실행하지 않는다.
- [ ] 현재 화면 ID·기간·선택 세그먼트만 문맥으로 전달한다. 화면의 전체 고객 테이블을 프롬프트에 넣지 않는다.
- [ ] 대화 전문의 장기 저장은 확장 기능으로 두되 모든 AI 실행·확인 액션 로그는 MVP에서 보존한다.

**완료 기준:** 자연어 요청 → 조건 카드 → 확인 → 저장 → 화면 반영이 가능하다. 새로고침·더블클릭·오래된 카드 확인이 중복 변경을 만들지 않는다.

## 17. 단계 13 — 통합 검증·배포·포트폴리오

### 13-1. 테스트 계층

| 계층 | 위치 | 필수 검증 |
| --- | --- | --- |
| 단위 | `tests/unit/` | DSL, 상태 전환, 제외 우선순위, 배정, 지표 계산 |
| DB 통합 | `tests/integration/` | 실제 PostgreSQL의 FK·JSONB·잠금·트랜잭션·멱등성 |
| API | `tests/integration/` | 공개 접근·업로드·업무 HTTP 흐름 |
| 프런트 | `frontend/tests/*.test.js` | 순수 JS 조건 변환·입력 검증·응답 처리 |
| E2E | `frontend/e2e/` | DOM 표시·한 방문자의 작성·승인·모의 발송·성과 확인 |
| AI 평가 | `tests/fixtures/ai/` 및 별도 실행기 | 조건 의미 일치, 잘못된 출력 차단, live 연결 |

SQLite로 통과한 테스트를 PostgreSQL 잠금·JSONB 검증의 대체로 삼지 않는다. CI는 전용 DB를 사용하고 실제 운영 DB 주소로 테스트를 실행하지 못하도록 검사한다.

### 13-2. CI와 배포

- [ ] GitHub Actions에서 백엔드 의존성 설치·lint·pytest, JavaScript 문법·단위 테스트, 브라우저 E2E와 정적 파일 로딩을 검사한다. 프런트 빌드 단계는 두지 않는다.
- [ ] 순수 JavaScript 테스트는 Node 내장 테스트 러너로, DOM·사용자 흐름은 Playwright의 JavaScript 테스트로 검증한다. 테스트 도구용 package.json과 lockfile은 추가하되 사이트 실행에는 Node를 요구하지 않는다.
- [ ] Docker 이미지에 API와 worker 실행 경로를 제공한다. migration은 별도 일회 작업으로 수행한다.
- [ ] 프런트·API는 같은 origin 경로로 노출하고 DB는 외부 공개하지 않는 배포 구성을 작성한다.
- [ ] 배포 업체 선택은 실제 계정·예산·서비스 제한 확인 후 한다. 아직 선택되지 않은 업체에 종속되는 코드를 만들지 않는다.
- [ ] 운영 설정에 DB 연결 비밀값·AI 키를 환경변수로 주입하고 공개 데모에서는 합성 고객만 사용한다.
- [ ] readiness, worker heartbeat, 실패 job 수, AI 실패율·응답 시간 로그를 확인한다.
- [ ] DB 백업 복원과 직전 앱 이미지 재배포 절차를 `docs/deployment_runbook.md`에 작성하고 한 번 실행한다.

### 13-3. 대표 시연

1. 첫 화면을 열어 준비된 샘플 데이터의 재구매율 하락과 집계 기간을 확인한다.
2. 휴면 VIP 조건을 AI에 요청하고 DSL·기준 시점·대상 수를 확인한다.
3. 세그먼트를 저장한 뒤 이메일 캠페인을 생성한다.
4. A/B 카피를 생성하고 혜택 또는 표현을 직접 수정한다.
5. 검수에서 미동의·중복·오류 연락처가 제외되는 것을 확인한다.
6. 같은 화면에서 방문자가 동일 campaign version을 직접 승인한다.
7. 이어서 모의 발송하고 진행률·결과를 확인한다.
8. A/B 결과·모의 데이터 표기·판단 한계를 확인한다.
9. AI 분석에서 근거 지표와 다음 실험 제안을 확인하고 새 초안을 만든다.
10. 푸시·SMS도 채널 동의와 카피 제한이 적용되는 짧은 보조 시연을 수행한다.

**완료 기준:** 빈 환경에서 README대로 설치한 뒤 시연 전 과정이 완료된다. 업무 시간 단축 수치는 실제 사용자 과업 측정치와 목표 가설을 분리해 기록한다.

## 18. 개발 티켓·커밋 묶음

아래 묶음은 한 번에 검토 가능한 변경 단위다. 각 묶음에는 해당 단계의 테스트와 실행 안내를 포함한다. 공수는 1인 개발의 작업 분해용 추정이며 확정 일정이 아니다. UI 완성도·DB 경험·피드백에 따라 달라진다.

| 순서 | 티켓 범위 | 예상 작업일 | 한글 Conventional Commit 예시 |
| --- | --- | --- | --- |
| 01 | API·지표 계약 | 1~2 | `docs: API 계약과 CRM 지표 기준 정의` |
| 02 | DB·초기 migration | 2~3 | `feat(db): PostgreSQL 연결과 초기 스키마 추가` |
| 03 | 작업 worker | 2~3 | `feat(jobs): 작업 실행과 재시도 기반 구현` |
| 04 | 공개 데모·변경 이력 | 1~2 | `feat(demo): 즉시 체험 흐름과 변경 이력 구현` |
| 05 | 데이터 적재 | 3~5 | `feat(data): CSV 검증과 중복 없는 적재 구현` |
| 06 | 샘플 생성 | 1~2 | `feat(data): 재현 가능한 CRM 데모 데이터 생성` |
| 07 | HTML·CSS·JavaScript 기반 | 2~3 | `feat(web): HTML·CSS·JavaScript 대시보드 기반 추가` |
| 08 | 고객·KPI | 3~5 | `feat(analytics): 고객 조회와 CRM 지표 대시보드 구현` |
| 09 | DSL·미리보기 | 3~5 | `feat(segments): 조건 검증과 대상자 미리보기 구현` |
| 10 | 세그먼트 화면 | 2~3 | `feat(segments): 조건 빌더와 세그먼트 저장 화면 추가` |
| 11 | AI-A: provider·로그·대화·조회·세그먼트 확인 저장 | 3~5 | `feat(ai): 자연어 조회와 확인 기반 세그먼트 저장 연결` |
| 12 | 캠페인·A/B 편집 | 3~5 | `feat(campaigns): 캠페인 초안과 채널별 카피 편집 구현` |
| 13 | AI-B: 캠페인·카피 도구 확장 | 2~3 | `feat(ai): 캠페인 초안과 카피 생성 도구 연결` |
| 14 | 정책·승인 | 3~5 | `feat(policies): 정책 검수와 버전 기반 승인 구현` |
| 15 | AI-C: 검수 도구·결과 카드 | 1~2 | `feat(ai): 캠페인 검수 도구와 결과 카드 연결` |
| 16 | 모의 발송 | 3~5 | `feat(campaigns): 중복 방지와 모의 발송 작업 구현` |
| 17 | 성과·보고서 | 3~5 | `feat(reports): 캠페인 성과와 A/B 비교 구현` |
| 18 | AI-D: 성과 분석·후속 제안 | 2~3 | `feat(ai): 성과 분석과 확인 기반 후속 초안 연결` |
| 19 | E2E·배포·시연 | 3~5 | `test: 캠페인 운영 전체 시나리오 검증` |

합계는 약 43~71 작업일의 전체 범위 추정이며 이미 완료한 작업도 포함한다. 남은 기간을 뜻하지 않으며 피드백·재작업 여유는 별도다. 첫 시연은 티켓 11까지의 자연어 조회·세그먼트 확인 저장, 다음 시연은 티켓 17까지의 이메일 운영과 성과 확인이다. 최종 MVP 판정은 모든 필수 기능과 19절 기준으로 한다.

## 19. 요구사항 추적과 최종 체크리스트

| 원문 요구사항 | 상세 단계 | 합격 증거 |
| --- | --- | --- |
| 고객·이벤트 업로드 | 3 | 정상·오류·재업로드 통합 테스트 |
| CRM 대시보드·고객 상세 | 5 | fixture 기대 지표와 화면 비교 |
| 조건 기반·자연어 세그먼트 | 6, 11 | 동일 DSL의 고객 집합 일치 |
| 세그먼트 프로파일 | 6, 11 | 집계 근거와 기준 시점 표시 |
| 캠페인 초안·3채널 A/B 카피 | 7, 11 | 저장·수정·채널별 검수 |
| 동의·중복·피로도 정책 | 8, 9 | 제외 합계와 동시 실행 테스트 |
| 방문자 직접 승인·모의 발송 | 8, 9 | 업무 검토 후 실행과 재시도 멱등성 |
| 성과 대시보드·실험 비교 | 10 | 분모·매출 귀속·판단 보류 테스트 |
| AI 요약·후속 추천 | 11, 12 | 근거 ID와 확인 후 새 초안 |
| AI 실행·방문자 변경 기록 | 2, 11, 12 | actor_type/dataset_id/version/request_id 연결 |
| Reports·CSV | 10 | 화면 수치와 내보내기 일치 |
| Data & Integrations·Settings | 3, 8 | 적재 상태와 버전 있는 정책 설정 |

- [ ] 승인되지 않은 캠페인은 어떤 API 경로에서도 실행되지 않는다.
- [ ] 새 방문자가 첫 화면부터 조회·업로드·편집·정책 설정·승인·모의 발송을 모두 체험한다.
- [ ] HTML·CSS·JavaScript 정적 파일이 별도 빌드 없이 로드되고 모든 화면이 업무 API와 연결된다.
- [ ] 실행 시점에 미동의·탈퇴 고객은 발송 결과에 포함되지 않는다.
- [ ] A/B 고객 교집합은 0명이고 재시도해도 배정이 같다.
- [ ] 승인된 내용과 실행 내용의 version/hash가 일치한다.
- [ ] AI가 만든 조건·설명·실제 SQL 집계가 일치한다.
- [ ] 고객 개별 개인정보가 AI provider 요청과 로그에 노출되지 않는다.
- [ ] 지표 계산·기간 경계·0 분모·중복 이벤트 테스트를 통과한다.
- [ ] AI 장애 시 수동 생성·검수·승인·모의 발송이 가능하다.
- [ ] 재시작 후 작업이 복구되고 데이터가 중복되지 않는다.
- [ ] 모의 데이터와 실측 성과를 모든 보고서에서 구분한다.
- [ ] 문서의 설치 명령으로 새 환경에서 같은 시연을 재현한다.

## 20. MVP 이후 확장 진입 조건

| 확장 | 착수 조건 | 추가 구현 |
| --- | --- | --- |
| 예약·일시 중지 | 모의 발송 복구와 멱등성 검증 완료 | 예약 시각·취소·재개·시간대와 상태 전환 |
| 무발송 통제군 | 무작위 배정·전환 관찰 정의 고정 | 통제군 주문 관찰, ITT 분모, 증분 추정 |
| 브랜드 문서 RAG | 가이드 수가 늘어 단순 설정으로 관리 곤란 | 문서 적재·버전·검색·출처·검색 품질 평가 |
| MCP 분리 | 여러 AI 클라이언트가 같은 업무 도구 사용 | 공개 데모 도구 서버·입출력 계약·호환성 테스트 |
| 실제 발송 | 모의 전체 흐름 검증 및 채널 요구사항 확정 | provider adapter·webhook·수신 거부·실제 정책 검토 |
| 다단계 여정·알림 | 단일 캠페인 운영이 안정적 | 트리거·대기·분기·중단·중복 처리 |

다음 단계는 **13 통합 검증·배포·시연**이다. [AI-D 구현 안내](phase_ai_d.md): 성과 지표 ID·값 대조, 허용 가설·액션, 분석 카드와 확인 기반 동일 조건 재실험 초안을 구현했다. 실제 모델의 지표 참조 검증과 업무 미저장 원칙을 확인했으며, 배포 환경의 전체 live 시연은 단계 13에서 확인한다.
