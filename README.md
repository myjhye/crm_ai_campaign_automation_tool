# CRM AI Campaign Automation API

Python 3.11 이상을 사용하는 FastAPI 백엔드 기본 프로젝트입니다.

## 설치 및 실행 (Windows PowerShell)

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
현재는 단계 0 공통 규칙, 단계 1 DB·worker, 단계 2 데이터셋·감사 이력, 단계 3 CSV 적재·샘플 생성 백엔드를 구현했습니다.
`/api/v1/health`는 프로세스, `/api/v1/ready`는 DB 연결을 검사합니다. readiness는 스키마 최신 여부까지 검사하지 않으므로 배포 시 migration을 별도로 실행합니다.

현재 구성 범위는 [상세 구현 계획](docs/detailed_implementation_plan.md)의 단계 5 고객·대시보드까지입니다.
데이터셋 관리, 고객 검색·상세·이벤트, KPI·퍼널·상태 분포를 화면에서 사용할 수 있습니다. 집계 기준·API·RFM·성능 검증은 [단계 5 실행 안내](docs/phase_5_customer_analytics.md)에 정리했습니다. 캠페인·AI 대화는 후속 단계입니다.
화면 실행에는 Node나 빌드가 필요하지 않습니다. 프런트 테스트는 `npm --prefix frontend ci`, `npm --prefix frontend test`로 실행합니다. 브라우저 테스트와 구현 설명은 [단계 4 실행 안내](docs/phase_4_frontend.md)를 참고하세요.
PostgreSQL은 `compose.yaml`로, API와 worker는 로컬 `.venv`로 실행합니다. 서버 Dockerfile과 CI는 배포 단계에서 추가합니다.

업무 요청은 `route → service → repository → DB` 순서로 구성합니다.
서비스가 트랜잭션을 소유하고 repository는 임의로 commit하지 않습니다.
일반 화면과 AI 도구는 같은 서비스를 사용하며, API 요청·응답 모델은 `schemas/`,
HTTP와 독립적인 계산 및 검수 규칙은 `domain/`에 배치합니다.

## 단계 0 공통 규칙

- [API 계약](docs/api_contract.md): JSON·페이지네이션·날짜·금액·공통 오류 응답.
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

API와 별도 터미널에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m app.workers.runner
```

진단 작업 생성 → 한 건 실행 → 상태 조회 예시:

```powershell
.\.venv\Scripts\python.exe -m scripts.enqueue_worker_check
.\.venv\Scripts\python.exe -m app.workers.runner --once
# 출력된 job_id로 GET /api/v1/jobs/{job_id} 조회
```

현재 handler는 `system.check`와 CSV 적재용 `data.import`입니다. 모의 발송 handler는 이후 단계에서 추가합니다.
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

`--size demo`는 고객 1만 명·주문 3만 건·이벤트 20만 건을 생성합니다. 같은 옵션 재실행은 기존 데이터를 유지합니다. `--dataset-key fresh-1`을 추가하면 새 복사본을 만듭니다.

CSV는 `/api/v1/data/import/{kind}/preview`에 `text/csv`로 전송하고, 반환된 배치를 `/commit`으로 확정합니다. 실행 중인 worker가 있어야 적재가 완료됩니다. CSV 예제·PowerShell 요청·중복 처리·원천 대조·보관 정리는 [단계 3 실행 안내](docs/phase_3_data_import.md)에 정리했습니다.

FastAPI 실행 방식은 [공식 서버 실행 문서](https://fastapi.tiangolo.com/deployment/manually/)를 참고했습니다.
