# AI-A — 지표 조회와 확인 기반 세그먼트 저장

## 구현 상태

OpenAI Responses API 도구 선택 경로, 모의 provider, 지표 조회·조건 미리보기·저장 제안, 확인 API와 우측 패널을 구현했다. 키 설정 후 로컬 `.env`를 `AI_MODE=live`로 변경했다. 실제 OpenAI 도구 선택, DB와 일치하는 활성 고객 지표, 실제 세그먼트 미리보기(10명)를 검증했다. 실제 LLM과 브라우저를 함께 사용한 확인 저장 전체 시연은 별도 확인 대상이다.

## 실행

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

기존 VS Code 실행 작업도 같은 앱을 실행한다. 데이터셋 선택 후 좌측 메뉴 Settings 바로 아래의 **AI 어시스턴트**로 전용 페이지(`#/ai`)에 들어간다. 메시지는 세로로 누적되고 하단 입력창에서 요청한다. 지표·조건 결과와 저장 확인은 AI 말풍선에 표시한다. 상단 버튼과 우측 패널은 제거했다. 모의 모드는 다음 두 문장을 지원하며 임의 문장을 해석했다고 주장하지 않는다.

- `활성 고객 수를 알려줘`
- `60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘`

실제 모델을 사용하려면 서버 `.env`에 `AI_MODE=live`, `OPENAI_API_KEY`, `AI_MODEL`을 설정하고 서버를 재시작한다. 키는 브라우저에 입력하거나 커밋하지 않는다. 기본 모델 문자열은 `gpt-4.1-mini`이며 계정에서 사용할 모델로 변경할 수 있다.

```powershell
.\.venv\Scripts\python.exe -m scripts.check_ai_live
```

이 명령은 실제 도구 선택만 확인하고 업무 데이터를 저장하지 않는다. 성공 후 화면에서 지표 조회 → 조건 초안 → 확인 후 저장을 별도로 검증한다. 키가 없으면 실행하지 못했다는 메시지와 실패 코드로 종료한다.

## 처리 구조

AI 전용 페이지는 세로 채팅 UI다. 사용자·AI 메시지를 화면 내 배열에 누적하고 지표·미리보기·저장 확인은 해당 AI 말풍선 안에 유지한다. 메시지 영역만 스크롤하고 입력창은 아래에 고정한다. Enter는 전송, Shift+Enter는 줄바꿈이며 한글 조합 중 Enter는 전송하지 않는다. 데이터셋·기간 변경 시 진행 중 요청을 취소하고 대화를 초기화한다. 화면의 메시지 기록은 LLM 대화 기억을 의미하지 않으며 기존 `/ai/chat` 요청 계약은 유지한다.

| 파일 | 책임 |
| --- | --- |
| `app/ai/provider.py` | 실제 Responses 요청, 모의 예시, 입력 연락처·키 차단, timeout·출력 크기·429/5xx 재시도 |
| `app/ai/tools.py` | 허용 지표, 미리보기, 초안, 추가 질문 도구의 strict 계약 |
| `app/ai/orchestrator.py` | 도구 인자 검증, 기존 서비스 실행, 제안·실행 이력, 원자적 확인 저장 |
| `app/models/ai.py`, `alembic/versions/004a_ai.py` | 제안 원본·hash·만료·결과 ID와 실행 로그 |
| `app/api/routes/ai.py` | 상태, 대화, 제안 확인 HTTP 진입점 |
| `frontend/src/features/ai/index.js` | 입력·모드 표시·결과 카드·저장 확인·재시도·화면 이동 |

`POST /api/v1/ai/chat`은 `prompt`, `dataset_id`, `from`, `to`, `reference_at`을 받는다. 기간은 화면 선택값, 세그먼트 기준 시점은 데이터셋 기준 시점(없으면 기간 종료)이다. 첫 버전은 **요청 한 번에 도구 한 개**를 선택한다. 다른 기간을 원하면 기간 필터를 바꾼다. 여러 업무는 나누어 요청하고, 질문에 답할 때는 완성된 조건을 다시 입력한다. 대화 전문이나 장기 기억을 저장하지 않는다.

모델에는 요청과 허용 필드·기간만 보낸다. 고객 행이나 DB 연락처를 전송하지 않으며 자유 SQL 도구가 없다. strict 도구 인자의 `condition_json` 문자열을 다시 단계 6의 Pydantic DSL 검증기에 통과시킨다. 모델 문장으로 숫자를 만들지 않고 서비스 결과를 카드로 직접 표시하므로 결과 요약을 위한 추가 LLM 호출도 없다. 근거 메타정보는 카드의 조회 기준 툴팁으로 확인한다.

외부 응답 대기 전에 DB 세션을 닫는다. 응답이 돌아오면 데이터 버전을 다시 검사하며 변경된 데이터로 예전 제안을 만들지 않는다. API timeout 기본 20초, 출력 기본 2,000토큰·응답 100KB, 도구 실행 1회로 제한한다. 429/5xx는 시간 예산 내 한 번 재시도하고 나머지 실패는 명확한 오류로 반환한다. 구조화 출력 오류를 자동 저장하거나 숨겨서 대체하지 않는다.

OpenAI 요청 형식은 [공식 Function calling 문서](https://developers.openai.com/api/docs/guides/function-calling)를 기준으로 `strict`, 필수 속성, `additionalProperties=false`를 적용했다. `store=false`를 지정한다.

## 저장 보장

초안 도구는 업무 세그먼트를 만들지 않고 정규화 payload·SHA-256·30분 만료의 제안을 보관한다. 방문자가 `확인 후 세그먼트 저장`을 누르면 `POST /api/v1/ai/actions/{proposal_id}/confirm`에 dataset ID만 전송한다. 브라우저에서 변경한 조건이나 `confirmed=true`는 받지 않는다.

데이터셋 → 제안 잠금 순서로 범위·만료·hash·데이터 버전을 검증한 뒤 기존 세그먼트 서비스를 호출한다. 세그먼트·revision·VISITOR 승인 행위 감사 기록·제안 완료를 같은 트랜잭션에 저장한다. revision의 생성 출처는 AI다. 동시 확인은 같은 저장 결과를 반환하고 재시도도 새 세그먼트를 만들지 않는다. 감사 저장 실패는 전체 롤백한다.

AI 실행 로그에는 dataset/request ID, 주체, provider/model, prompt version, 성공 여부, 허용 도구명, 시간·토큰만 기록한다. 프롬프트·고객 연락처·provider 오류 원문은 기록하지 않는다. 자유 입력의 연락처·키 패턴을 차단하지만 모든 개인정보를 자동 식별하는 보장을 의미하지 않는다. 공개 체험에는 합성 데이터와 집계 조건만 사용한다.

## 검증과 남은 확인

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
```

PostgreSQL에서 지표 일치, 초안 미저장, 중복·동시 확인, 만료·hash·데이터 버전 충돌, 감사 실패 롤백, 모델 응답 중 데이터 변경을 검사한다. provider 테스트는 HTTP 대역으로 strict 요청·429 재시도·timeout을 확인하며 실제 API 성공 증거와 구분한다. E2E는 API 대역으로 패널 입력 → 미리보기 → 명시적 저장 → 성공 표시를 검증한다.

실제 API 키로 한국어 지표 도구 선택과 영어 지표 조회·조건 미리보기를 통과했다. 광범위한 자유 문장 평가와 브라우저 전체 시연은 아직 미실행이다. 캠페인·카피·검수·발송 도구는 후속 AI-B~D에서 연결한다.

로컬 검증 결과: 백엔드 85개, JavaScript 단위 15개, Chromium E2E 12개 통과. 패널 스크롤 조정 후 AI E2E 1개를 다시 통과했다. 로컬 DB의 Alembic head는 `004a`다.
