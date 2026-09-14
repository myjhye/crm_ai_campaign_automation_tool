# CRM AI Campaign Automation API

Python 3.11 이상을 사용하는 FastAPI 백엔드 기본 프로젝트입니다.

## 설치 및 실행 (Windows PowerShell)

프로젝트 루트에서 실행합니다. 가상환경 활성화 없이 실행할 수 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

이미 `.env`가 있으면 복사 단계를 생략합니다. 서버 종료는 `Ctrl+C`입니다.

- API 정보: http://127.0.0.1:8000/
- 상태 확인: http://127.0.0.1:8000/api/v1/health
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

프런트엔드 연동 예시: `CORS_ORIGINS=["http://localhost:3000"]`

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
현재는 서버 기반만 포함하며 DB, 인증, 캠페인 업무 기능은 아직 구현하지 않았습니다.
상태 확인 API는 외부 서비스나 DB 연결 상태를 검사하지 않습니다.

현재 구성 범위는 [상세 구현 계획](docs/detailed_implementation_plan.md)의 1~3절입니다.
새 패키지는 책임을 명시한 뼈대이며 DB 연결, 인증, AI 호출, worker 실행 기능은 아직 없습니다.
빈 디렉터리는 `.gitkeep`으로 버전 관리합니다. 프런트엔드 도구 설치는 단계 4에서 진행합니다.
`compose.yaml`, `Dockerfile`, CI YAML은 해당 구현 단계에서 실행 가능한 설정과 함께 추가합니다.

업무 요청은 `route → service → repository → DB` 순서로 구성합니다.
서비스가 트랜잭션을 소유하고 repository는 임의로 commit하지 않습니다.
일반 화면과 AI 도구는 같은 서비스를 사용하며, API 요청·응답 모델은 `schemas/`,
HTTP와 독립적인 계산 및 검수 규칙은 `domain/`에 배치합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

FastAPI 실행 방식은 [공식 서버 실행 문서](https://fastapi.tiangolo.com/deployment/manually/)를 참고했습니다.
