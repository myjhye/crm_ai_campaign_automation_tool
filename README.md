# CRM AI Campaign Automation API

Python 3.11 이상을 사용하는 FastAPI 백엔드 기본 프로젝트입니다.

`/#/ai`의 AI 어시스턴트는 업무별 질문 탐색에서 시작해 고객 조건 조회 → 세그먼트 확인 저장 → 캠페인 초안 제안으로 이어집니다. 완료 캠페인을 전환율·클릭률·매출·발송 수로 비교하고 결과에 맞는 후속 질문을 선택할 수 있습니다. 업무 저장에는 별도 확인이 필요합니다. 대화는 브라우저 메모리에서 유지되며 데이터셋·기간 변경 또는 새로고침 시 초기화됩니다. [사용법·구현 파일·실행 흐름·검증 안내](docs/ai_assistant_architecture.md)

## 설치 및 실행 (Windows PowerShell)

### Windows DB driver startup errors

`no pq wrapper available`와 `애플리케이션 제어 정책에서 이 파일을 차단했습니다`가 함께 나오면 Windows가 psycopg의 네이티브 DLL을 차단한 상태입니다. Docker DB가 Healthy여도 Python에서 드라이버를 불러오지 못하므로 마이그레이션과 서버가 시작되지 않습니다. 이 오류만으로 `DATABASE_URL`이 잘못됐다고 판단하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.check_db_driver
# 정확한 import 오류 확인
.\.venv\Scripts\python.exe -c "import psycopg"
```

2026-09-25 로컬 재현에서는 `Microsoft-Windows-CodeIntegrity/Operational` 이벤트 3077에 `.venv\Lib\site-packages\psycopg_binary.libs\libpq-*.dll` 차단이 기록됐습니다. 정책 관리자에게 해당 이벤트와 파일 경로를 전달해 허용 가능한 드라이버 배포 또는 정책 승인을 요청해야 합니다. 파일 이름 변경·보안 기능 해제로 해결하는 방식은 실행 스크립트에 넣지 않습니다. `-ExecutionPolicy Bypass`는 PowerShell 스크립트 실행 옵션이며 이 DLL 차단을 해결하지 않습니다.

드라이버 import가 성공한 뒤 기존 VS Code 실행 작업을 다시 실행합니다. `start-dev.ps1`은 이제 Docker·마이그레이션 전에 드라이버를 확인해 이 문제를 명확하게 표시합니다.

### 기본 실행

설치와 `.env` 설정을 한 번 마친 뒤에는 VS Code에서 **Ctrl + Shift + P → Tasks: Run Task(작업: 작업 실행) → GrowthPilot: 서버와 화면 실행**을 선택합니다. PostgreSQL 시작 → 마이그레이션 → FastAPI 실행 → 기본 브라우저 열기까지 자동으로 진행합니다. Docker Desktop은 먼저 실행해두세요.

터미널에서는 루트의 `powershell -ExecutionPolicy Bypass -File .\start-dev.ps1`로 동일하게 실행합니다. 종료는 실행 터미널에서 `Ctrl+C`입니다. PostgreSQL은 유지되며 별도로 종료하려면 `docker compose stop db`를 사용합니다. 포트 변경은 `-Port 8001`, 브라우저 생략은 `-NoBrowser`, Docker 시작 생략은 `-SkipDatabase` 옵션입니다. `-SkipDatabase`도 설정된 DB에 마이그레이션은 수행합니다.

프로젝트 루트에서 실행합니다. 가상환경 활성화 없이 실행할 수 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
# .env의 POSTGRES_PASSWORD와 DATABASE_URL을 같은 비밀번호로 설정한 뒤:
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

이미 `.env`가 있으면 복사 단계를 생략합니다. 서버 종료는 `Ctrl+C`입니다.

- GrowthPilot 화면: http://127.0.0.1:8000/
- API 정보: http://127.0.0.1:8000/api/v1/info
- 상태 확인: http://127.0.0.1:8000/api/v1/health
- DB 연결 확인: http://127.0.0.1:8000/api/v1/ready
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI: http://127.0.0.1:8000/openapi.json

## 환경변수

`.env.example`을 참고해 `.env`를 작성합니다. 시스템 환경변수가 `.env`보다 우선합니다.

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `APP_NAME` | `CRM AI Campaign Automation API` | API 문서 제목 |
| `ENVIRONMENT` | `development` | 환경 식별값 (동작을 자동 변경하지 않음) |
| `CORS_ORIGINS` | `[]` | 허용할 프런트엔드 origin의 JSON 배열 |
| `DATABASE_URL` | 미설정 | PostgreSQL psycopg 연결 URL |
| `POSTGRES_PASSWORD` | 직접 설정 | 로컬 Docker DB 비밀번호 |
| `WORKER_LEASE_SECONDS` | `30` | 작업 실행권 만료 시간 |
| `WORKER_HEARTBEAT_SECONDS` | `10` | 실행권 갱신 간격, lease의 절반 미만 |
| `WORKER_POLL_SECONDS` | `1` | 실행 가능한 작업이 없을 때 조회 간격 |

기본 화면은 API와 같은 origin을 사용하므로 CORS 설정이나 별도 프런트 서버가 필요하지 않습니다.

## 구조

```text
app/
  main.py                 # 앱 팩토리, 미들웨어, 라우터 등록
  core/                   # 공통 설정
  api/deps.py             # 공통 의존성 배치 위치
  api/router.py           # /api/v1 라우터
  api/routes/health.py     # 프로세스 상태 확인 API
  db/                     # DB engine과 세션
  models/                 # 영속 모델
  schemas/                # API 요청·응답 모델
  repositories/           # 데이터 조회와 저장
  services/               # 업무 흐름과 트랜잭션
  domain/
    segments/             # DSL과 조건 컴파일
    campaigns/            # 상태 전환과 A/B 배분
    policies/             # 정책 검수
    analytics/            # 지표 계산
  ai/                     # AI 연동과 업무 도구
  workers/                # 백그라운드 작업
alembic/versions/         # 향후 DB 마이그레이션
scripts/                 # 개발용 데이터·계정 생성 명령
tests/
  unit/                   # 업무 규칙 단위 테스트
  integration/test_api.py # 기존 HTTP·문서·CORS 테스트
  fixtures/               # 고정 테스트 데이터
frontend/
  src/app/                # 라우팅과 레이아웃
  src/api/                # API client와 타입
  src/components/         # 공통 UI
  src/features/           # 기능별 화면
  e2e/                    # 사용자 흐름 테스트
docs/                     # 요구사항과 상세 계획
.github/workflows/        # 향후 CI workflow
```

새 API는 `app/api/routes/`에 추가하고 `app/api/router.py`에 등록합니다.
현재는 단계 0~10의 데이터 적재, 고객·지표, 세그먼트, AI 초안, 정책 검수·승인, 모의 발송과 성과 보고서를 구현했습니다.
`/api/v1/health`는 프로세스, `/api/v1/ready`는 DB 연결을 검사합니다. readiness는 스키마 최신 여부까지 검사하지 않으므로 배포 시 migration을 별도로 실행합니다.

현재 구성 범위는 [상세 구현 계획](docs/detailed_implementation_plan.md)의 단계 10 성과·실험·보고서까지입니다.
데이터셋 관리, 고객·지표, 세그먼트, AI 캠페인 초안, 정책 검수·방문자 승인, 모의 발송과 A/B 성과·CSV 보고서를 화면에서 사용할 수 있습니다. 성과 계약은 [단계 10 실행 안내](docs/phase_10_performance_reports.md)에 정리했습니다.
화면 실행에는 Node나 빌드가 필요하지 않습니다. 프런트 테스트는 `npm --prefix frontend ci`, `npm --prefix frontend test`로 실행합니다. 브라우저 테스트와 구현 설명은 [단계 4 실행 안내](docs/phase_4_frontend.md)를 참고하세요.
PostgreSQL은 `compose.yaml`로, API와 worker는 로컬 `.venv`로 실행합니다. 서버 Dockerfile과 CI는 배포 단계에서 추가합니다.

업무 요청은 `route → service → repository → DB` 순서로 구성합니다.
서비스가 트랜잭션을 소유하고 repository는 임의로 commit하지 않습니다.
일반 화면과 AI 도구는 같은 서비스를 사용하며, API 요청·응답 모델은 `schemas/`,
HTTP와 독립적인 계산 및 검수 규칙은 `domain/`에 배치합니다.

## 단계 0 공통 규칙

- API 계약 (이전 문서 정리됨): JSON·페이지네이션·날짜·금액·공통 오류 응답.
- [CRM 지표 정의](docs/metric_definitions.md): 고객 상태, 기간 비교, 지표 분모와 매출 귀속 기준.
- `app/core/errors.py`: 공통 오류와 `X-Request-ID`.
- `app/core/time.py`: UTC 변환, Clock, 한국 날짜 범위 변환.
- `app/schemas/common.py`: Pagination, Page, ReportingPeriod, Money.
- `app/domain/analytics/`: 고객 상태·구매 경과일·비율 계산.

고객·캠페인 DB 집계 API는 이후 단계에서 추가합니다. 기존 실행 명령은 동일합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

기본 실행에서는 `TEST_DATABASE_URL`이 없으면 PostgreSQL 통합 테스트를 건너뜁니다.
DB가 실행된 상태에서 전체 테스트는 다음과 같이 실행합니다. 설정 DB 이름에 `_test`를 붙인 별도 DB를 생성하고 테스트별 임시 schema만 정리합니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
```

## Worker 실행

VS Code의 `GrowthPilot: 서버와 화면 실행` 작업은 API와 worker를 함께 시작한다. 개별 실행은 별도 터미널에서 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m app.workers.runner
```

진단 작업 생성 → 한 건 실행 → 상태 조회 예시:

```powershell
.\.venv\Scripts\python.exe -m scripts.enqueue_worker_check
.\.venv\Scripts\python.exe -m app.workers.runner --once
# 출력된 job_id로 GET /api/v1/jobs/{job_id} 조회
```

현재 handler는 `system.check`, CSV 적재용 `data.import`, 모의 발송용 `campaign.simulate`입니다.
상세 설정과 복구 방식은 [단계 1 실행 안내](docs/phase_1_database_worker.md)를 참고하세요.

## 공개 데이터셋·감사 이력 API

`alembic upgrade head`로 `003a`를 적용하면 `/api/v1/datasets`에서 빈 데이터셋 생성·조회,
`PUT /api/v1/datasets/{id}`에서 version 기반 이름 변경을 사용할 수 있습니다.
`GET /api/v1/audit-logs`에서 변경 이력을 조회합니다. 로그인은 필요하지 않습니다.
데이터셋 입력 예시와 충돌 처리는 [단계 2 실행 안내](docs/phase_2_demo_audit.md)에 정리했습니다. 화면은 후속 단계입니다.

## CSV 적재·샘플 데이터

최신 `003b` 마이그레이션을 적용한 후 합성 데이터를 생성할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_demo --seed 42 --reference-at "2026-09-19T00:00:00Z" --size small
```

`--size medium`은 고객 5천 명·상품 300개·주문 1만 5천 건·이벤트 10만 건, `--size demo`는 고객 1만 명·주문 3만 건·이벤트 20만 건을 생성합니다. 기준 시점 기본값은 `2026-09-20T00:00:00Z`입니다. 같은 옵션 재실행은 기존 데이터를 유지합니다. `--dataset-key fresh-1`을 추가하면 새 복사본을 만듭니다.

Reports·Experiments·AI 비교 시연용 완료 캠페인은 아래 명령으로 추가합니다. 기존 샘플에 보완 합성 고객 750명과 6종 세그먼트, 3채널 완료 캠페인 12개를 만들며 같은 seed 재실행은 중복 생성하지 않습니다. 과거 발송 기간과 worker 실행 옵션은 [완료 캠페인 시연 데이터 안내](docs/demo_campaign_seeding.md)를 참고하세요.

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo_campaigns --dataset-id <UUID> --seed 42
```

CSV는 `/api/v1/data/import/{kind}/preview`에 `text/csv`로 전송하고, 반환된 배치를 `/commit`으로 확정합니다. 실행 중인 worker가 있어야 적재가 완료됩니다. CSV 예제·PowerShell 요청·중복 처리·원천 대조·보관 정리는 [단계 3 실행 안내](docs/phase_3_data_import.md)에 정리했습니다.

FastAPI 실행 방식은 [공식 서버 실행 문서](https://fastapi.tiangolo.com/deployment/manually/)를 참고했습니다.

## 세그먼트 조건과 저장

Segments에서 조건 빌더 또는 휴면 VIP 템플릿으로 대상을 미리보고 저장·수정·보관할 수 있습니다. 실행 전 Alembic을 `004`까지 적용하세요. [단계 6 구현 안내](docs/phase_6_segments.md)에 API 계약과 검증 범위를 정리했습니다. 자연어 입력과 실제 LLM은 다음 AI-A에서 연결합니다.
