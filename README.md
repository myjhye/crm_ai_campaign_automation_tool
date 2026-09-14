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
  main.py               # 앱 생성, 미들웨어, 라우터 등록
  core/config.py        # 환경변수 설정
  api/router.py         # /api/v1 라우터
  api/routes/health.py   # 프로세스 상태 확인 API
tests/test_api.py       # HTTP 계약, 문서, CORS 검증
```

새 API는 `app/api/routes/`에 추가하고 `app/api/router.py`에 등록합니다.
현재는 서버 기반만 포함하며 DB, 인증, 캠페인 업무 기능은 아직 구현하지 않았습니다.
상태 확인 API는 외부 서비스나 DB 연결 상태를 검사하지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

FastAPI 실행 방식은 [공식 서버 실행 문서](https://fastapi.tiangolo.com/deployment/manually/)를 참고했습니다.
