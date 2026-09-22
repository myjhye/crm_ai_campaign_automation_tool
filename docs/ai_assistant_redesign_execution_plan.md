# AI 어시스턴트 화면 재설계 실행 계획

> 상태: 단계 0~13 구현 완료 — 2026-09-22  
> 상위 명세: [AI 어시스턴트 화면 재설계 명세](ai_assistant_redesign_spec.md)  
> 대상 화면: `/#/ai`  
> 원칙: 각 단계는 독립적으로 검증하고 리뷰할 수 있는 커밋 단위로 완료한다.

## 1. 실행 규칙

실제 변경 파일과 검증 증거는 [AI 워크스페이스 구현 결과](ai_assistant_workspace.md)에 정리했다. 아래 커밋 제목은 리뷰 단위 제안이며, 이번 작업에서 커밋·푸시를 실행했다는 뜻은 아니다.

최종 검증: 백엔드 141개, JavaScript 16개, Chromium E2E 25개 통과. 로컬 migration `008`, 실제 OpenAI 비교 도구 선택·완료 캠페인 1개 수치 일치, 실제 데이터 인사이트 3개를 확인했다. 실제 모델을 연결한 전체 브라우저 저장 시연은 단계 13 배포 검증에 남긴다.

- 이전 단계의 필수 검증이 실패하면 다음 단계로 넘어가지 않는다.
- 첨부 문서의 예시 코드는 현재 모델·서비스 계약을 확인한 뒤 적용한다.
- AI-A~D, Campaigns, Experiments, Reports의 기존 기능을 유지한다.
- DB 쓰기는 기존 확인 저장 경로와 트랜잭션 경계를 재사용한다.
- 대화 전문, 프롬프트 원문, 고객 개인정보를 새로 저장하지 않는다.
- 각 커밋 후 해당 범위의 빠른 테스트를 실행한다.
- 백엔드 묶음과 프런트엔드 묶음이 끝날 때 전체 회귀 테스트를 실행한다.

## 2. 전체 단계

| 단계 | 결과 | 주요 검증 |
| ---: | --- | --- |
| 0 | 현재 구현·DB 계약 감사 및 기준선 기록 | 전체 테스트, 실제 모델/응답 구조 확인 |
| 1 | AI 실행 로그에 conversation ID 추가 | migration 왕복, 로그 기록 |
| 2 | 결정론적 인사이트 API | 기존 집계와 값 일치 |
| 3 | 크로스 캠페인 비교 서비스·도구 | dataset 격리, 정렬, 응답 최소화 |
| 4 | `/ai/chat` 도구 라우팅 확장 | strict 인자, 실행 로그 |
| 5 | context hint 재검증·왕복 | foreign/archive 참조 거절 |
| 6 | AI 프런트 파일 분리 | 기능 변화 없는 회귀 통과 |
| 7 | 진입 인사이트 카드 | CTA 입력·화면 이동 |
| 8 | 업무별 예시 그룹 | 입력 자동 채움 |
| 9 | 대화 히스토리와 자동 스크롤 | 역할·스크롤·오류 상태 |
| 10 | 문맥 칩과 후속 요청 | 유지·제거·범위 초기화 |
| 11 | 캠페인 비교 결과 UI | 링크·단위·모바일 |
| 12 | 전체 사용자 흐름 E2E | 세그먼트 저장→후속 요청, 비교 조회 |
| 13 | 전체 회귀·문서 마감 | backend, unit, E2E, diff check |

## 3. 단계 0 — 현재 코드 감사와 기준선

### 목표

예시 코드와 실제 구현 사이의 차이를 먼저 확정한다. 이 단계에서는 제품 코드를 수정하지 않는다.

### 확인할 내용

- Alembic 현재 head와 migration metadata
- `Campaign`의 완료 기준 시각 필드 또는 완료 run의 시각
- `campaign_performance()`의 비율·매출 응답 구조와 단위
- Overview 지표 서비스의 실제 함수·스키마
- 세그먼트 preview의 실제 함수·조건 DSL
- `AIExecutionLog`를 생성하는 모든 실행 경로
- AI 화면의 AbortController와 확인 저장 이벤트 수명
- 기존 `/#/ai` E2E 시나리오

### 기준선 명령

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
```

### 산출물

- 코드 변경·커밋 없음
- 실제 계약과 상위 명세의 차이를 작업 메모에 기록

## 4. 단계 1 — Conversation ID migration

### 목표

같은 페이지 세션의 AI 요청을 묶어 추적하되 대화 전문은 저장하지 않는다.

### 파일

- 신규 `alembic/versions/00Xx_ai_conversation_id.py`
- 수정 `app/models/ai.py`
- 관련 migration·metadata 테스트

### 구현

- `ai_execution_logs.conversation_id UUID NULL`
- `conversation_id` 조회 인덱스
- 기존 로그와 호환되는 nullable 컬럼
- 모든 downgrade 동작 제공

### 완료 조건

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic downgrade -1
.\.venv\Scripts\python.exe -m alembic upgrade head
```

- 빈 DB와 기존 DB에서 migration 성공
- metadata 일치 테스트 통과
- 기존 백엔드 테스트 통과

### 커밋

`feat(ai): add conversation id to execution logs`

## 5. 단계 2 — 결정론적 인사이트 API

### 목표

AI 화면 첫 진입에 사용할 인사이트를 LLM 없이 서버 집계로 만든다.

### 파일

- 신규 `app/services/insights.py`
- 수정 `app/api/routes/ai.py`
- 신규 인사이트 응답 스키마
- 신규 `tests/integration/test_ai_insights.py`

### API

```http
GET /api/v1/ai/insights?dataset_id={UUID}&from={ISO8601}&to={ISO8601}
```

### 카드

1. 활성 고객 비율
2. 60일 이상 미구매·누적 30만원 이상 대상 후보
3. 최근 완료 캠페인 성과

### 구현 원칙

- 기존 Overview·Segments·Performance 서비스를 재사용한다.
- 지표가 없으면 0을 만들지 않고 해당 카드를 생략한다.
- 최근 완료 캠페인은 실제 완료 run 기준으로 정한다.
- CTA에는 프롬프트 자동 채움 또는 안전한 내부 화면 이동만 담는다.
- LLM·외부 API를 호출하지 않는다.

### 완료 조건

- 카드 값이 각 원본 서비스 직접 호출 결과와 일치
- 완료 캠페인이 없으면 최근 캠페인 카드만 생략
- 다른 데이터셋의 리소스 미노출
- ISO 기간과 Asia/Seoul 경계 검증

### 커밋

`feat(ai): add deterministic workspace insights`

## 6. 단계 3 — 크로스 캠페인 비교 서비스와 도구

### 목표

여러 완료 캠페인의 성과를 제한된 필터·정렬 조건으로 비교한다.

### 파일

- 수정 `app/services/performance.py`
- 수정 `app/ai/tools.py`
- 신규 `tests/integration/test_compare_campaigns.py`

### 서비스 계약

- 현재 dataset의 `COMPLETED` 캠페인만 대상
- 채널: EMAIL, PUSH, SMS, ANY
- 선택적 segment revision 필터
- 화면 기간을 기본값으로 사용
- 정렬: 전환율, 클릭률, 기여 매출, 발송 수
- 최대 10개 반환
- 기존 `campaign_performance()`를 재사용

### 응답 필드

- campaign ID, 이름, 채널
- 발송 수, 전환율, 클릭률, 기여 매출
- 완료 기준 시각
- 전체 일치 개수

카피 제목·본문, 변형 원문, 고객 행은 포함하지 않는다.

### 완료 조건

- dataset 범위 밖 캠페인 미노출
- foreign segment revision 거절
- 정렬과 limit 적용
- 결과에 카피·고객 필드 없음
- 실제 성과 서비스와 값·단위 일치

### 커밋

`feat(ai): add cross-campaign comparison service`

## 7. 단계 4 — Chat orchestration 확장

### 목표

`/ai/chat`에서 strict `compare_campaigns` 도구를 선택하고 실행한다.

### 파일

- 수정 `app/ai/orchestrator.py`
- 수정 `app/ai/provider.py`
- 수정 `app/ai/schemas.py`
- 관련 provider·통합 테스트

### 요청 확장

```python
conversation_id: UUID | None = None
context_hint: ContextHint | None = None
```

`context_hint`는 가능하면 자유 dict가 아닌 명시적 Pydantic union으로 구현한다.

### 구현

- 도구 허용 인자를 `filter`, `sort`, `order`, `limit`로 제한
- provider에는 필터 정의와 집계 가능한 필드만 제공
- 도구 결과는 `campaign_comparison`으로 반환
- 해당 요청의 실행 로그에 conversation ID 기록
- 모델이 반환한 ID·기간·필터를 서버에서 다시 검증

### 완료 조건

- 도구 인자 불일치·추가 필드 거절
- 최대 반환 개수 강제
- `conversation_id` 로그 기록
- prompt 원문과 대화 전문 미기록
- 기존 metric·segment·validation·performance 도구 회귀 없음

### 커밋

`feat(ai): route campaign comparison through chat`

## 8. 단계 5 — Context hint 왕복

### 목표

이전 응답의 업무 리소스를 안전하게 후속 요청의 문맥으로 사용한다.

### 파일

- 신규 `app/services/ai_context.py`
- 수정 `app/ai/orchestrator.py`
- 수정 AI 응답 스키마
- 신규 `tests/integration/test_ai_context.py`

### 지원 문맥

- `segment`: 저장된 세그먼트와 revision
- `campaign_list`: 비교 결과의 캠페인 ID 목록, 최대 10개

### 처리 규칙

- 요청 hint의 이름·라벨은 신뢰하지 않는다.
- UUID로 현재 dataset에서 다시 조회한다.
- archive, foreign dataset, 잘못된 revision, 허용 수 초과를 거절한다.
- 모델에는 서버가 다시 만든 최소 요약만 전달한다.
- 유효하지 않으면 업무를 실행하지 않고 clarification으로 전환한다.
- 세그먼트는 실제 저장 성공 후의 ID·revision으로 hint를 만든다. 제안 ID를 segment ID처럼 사용하지 않는다.

### 완료 조건

- 정상 hint가 후속 provider context에 반영
- foreign·archive·잘못된 UUID 거절
- 비교 결과 hint의 순서와 범위 검증
- hint를 변조해도 다른 dataset 리소스 미노출

### 커밋

`feat(ai): add validated conversational context hints`

## 9. 단계 6 — 프런트엔드 파일 분리

### 목표

기존 동작을 바꾸지 않고 `frontend/src/features/ai/index.js`의 책임을 분리한다.

### 목표 구조

```text
frontend/src/features/ai/
├── index.js
├── insights.js
├── conversation.js
├── examples.js
├── comparison.js
├── input.js
└── performance.js
```

### 책임

- `index.js`: 화면 수명·상태·모듈 조립
- `insights.js`: 인사이트 요청·렌더링
- `conversation.js`: 메시지 말풍선과 결과 카드
- `examples.js`: 업무별 예시
- `comparison.js`: 캠페인 비교 표
- `input.js`: 입력·키보드·문맥 칩
- `performance.js`: 기존 AI-D UI 유지

### 완료 조건

- 분리 전후 DOM 동작 동일
- 기존 AI E2E 통과
- 확인 저장·오류 재시도·AbortController 수명 유지

### 커밋

`refactor(ai): split workspace into focused modules`

## 10. 단계 7 — 인사이트 카드 UI

### 목표

화면 첫 진입에 결정론적 인사이트 카드를 표시한다.

### 파일

- 구현 `frontend/src/features/ai/insights.js`
- 수정 `frontend/src/features/ai/index.js`
- 수정 `frontend/styles/components.css`

### 동작

- 화면 범위로 인사이트 API 호출
- 프롬프트 CTA는 입력창만 채우고 포커스 이동
- 화면 이동 CTA는 현재 dataset·기간을 보존
- 로딩·빈 결과·오류 상태 구분
- 첫 대화가 시작되면 카드 숨김

### 완료 조건

- 카드 CTA 동작
- 카드 텍스트의 안전한 DOM 렌더링
- 좁은 화면에서 1열·가로 넘침 없음
- API 실패 시 채팅 입력은 계속 사용 가능

### 커밋

`feat(ai): render workspace insight cards`

## 11. 단계 8 — 업무별 예시 그룹

### 목표

데이터 조회·세그먼트·성과 비교의 시작점을 제공한다.

### 파일

- 구현 `frontend/src/features/ai/examples.js`
- 수정 `frontend/src/features/ai/index.js`

### 동작

- 세 그룹과 짧은 예시 문장 표시
- 클릭 시 자동 전송하지 않고 입력창만 채움
- 대화 시작 후 숨김

### 완료 조건

- 키보드로 모든 예시 선택 가능
- 입력값을 덮어쓸 때 방문자가 내용을 확인할 수 있음
- E2E에서 그룹·프롬프트 값 확인

### 커밋

`feat(ai): add workflow prompt examples`

## 12. 단계 9 — 대화 히스토리와 자동 스크롤

### 목표

인사이트 화면에서 실제 대화 화면으로 자연스럽게 전환한다.

### 파일

- 구현 `frontend/src/features/ai/conversation.js`
- 수정 `frontend/src/features/ai/index.js`
- 수정 `frontend/styles/components.css`

### 동작

- 전송 즉시 사용자 메시지 추가
- 응답·실패를 별도 AI 메시지로 추가
- 기존 metric·segment preview·confirmation 카드 재사용
- campaign comparison 카드 연결 지점 제공
- 메시지 영역만 스크롤
- 사용자가 과거 메시지를 읽는 중이면 무조건 스크롤을 빼앗지 않는 동작을 검토
- `aria-live=polite`, 역할별 접근성 라벨 유지

### 완료 조건

- 첫 전송 후 인사이트·예시 숨김
- 사용자 우측·AI 좌측 정렬
- Enter·Shift+Enter·한글 조합 동작
- 실패 뒤 입력 복구·재시도
- dataset·기간 변경 시 진행 요청 취소와 초기화

### 커밋

`feat(ai): add workspace conversation history`

## 13. 단계 10 — 문맥 칩과 후속 요청

### 목표

서버가 검증한 업무 문맥을 방문자가 확인하고 제거할 수 있게 한다.

### 파일

- 구현 `frontend/src/features/ai/input.js`
- 수정 `frontend/src/features/ai/index.js`

### 동작

- 응답의 top-level 또는 명시된 응답 위치에서 `context_hint` 수신
- 입력창 위에 읽을 수 있는 라벨 표시
- 제거 버튼과 접근성 이름 제공
- 다음 요청에 conversation ID와 hint 포함
- 범위 변경 시 hint와 conversation ID 초기화

### 완료 조건

- 저장 성공 전에는 segment hint를 만들지 않음
- 제거 후 후속 요청에 hint 미포함
- 다른 dataset으로 전환 시 hint 미재사용
- E2E로 두 요청의 payload 검증

### 커밋

`feat(ai): connect validated context chips`

## 14. 단계 11 — 캠페인 비교 카드

### 목표

`campaign_comparison` 결과를 한눈에 비교 가능한 표로 표시한다.

### 파일

- 구현 `frontend/src/features/ai/comparison.js`
- 수정 `frontend/src/features/ai/conversation.js`
- 수정 `frontend/styles/components.css`

### 표시

- 캠페인명, 채널, 발송, 전환율, 클릭률
- 필요 시 기여 매출
- 전체 일치 수와 현재 표시 수
- 캠페인명은 `/#/campaigns/{id}?tab=results` 링크

### 구현 주의

- 기존 서버 비율 단위를 그대로 표시한다.
- `0`과 `null`을 구분한다.
- 긴 캠페인명과 작은 화면에서 표가 깨지지 않게 한다.
- 표만으로 읽기 어려운 모바일에서는 카드형 보조 레이아웃을 고려한다.

### 완료 조건

- 정렬된 순서 그대로 표시
- 모든 내부 링크가 dataset·기간을 보존
- 비어 있는 결과 상태 제공
- 카피·고객 정보 미표시

### 커밋

`feat(ai): render linked campaign comparisons`

## 15. 단계 12 — 통합 E2E

### 목표

새 화면의 존재 이유인 다단 업무 연결과 크로스 캠페인 조회를 검증한다.

### 파일

- 신규 `frontend/e2e/ai_workspace_flow.spec.js`
- 필요 시 기존 `frontend/e2e/ai.spec.js` 보완

### 시나리오 A: 세그먼트 문맥 연결

1. `/#/ai` 진입
2. 대상 후보 인사이트 CTA 선택
3. 프롬프트 전송
4. 세그먼트 preview 확인
5. 확인 후 저장
6. 저장 성공 뒤 segment 문맥 칩 확인
7. 후속 요청 전송
8. 두 번째 요청 payload의 conversation ID·context hint 확인
9. 부족한 캠페인 정보에 clarification 표시

### 시나리오 B: 크로스 캠페인 비교

1. 성과 비교 예시 선택
2. compare 도구 응답 표시
3. 정렬·단위·표시 개수 확인
4. 캠페인 링크로 결과 탭 이동

### 시나리오 C: 범위와 실패 복구

1. 대화 생성
2. dataset 또는 기간 변경
3. 진행 요청 abort
4. 대화·hint·conversation ID 초기화
5. 새 인사이트 표시
6. 인사이트 실패 시에도 수동 입력 가능

### 커밋

`test(ai): cover workspace conversation flows`

## 16. 단계 13 — 전체 검증과 문서 마감

### 검증 명령

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
git diff --check
```

실제 AI 검증은 쓰기 확인을 실행하지 않는 전용 스크립트로 다음만 확인한다.

- 크로스 캠페인 질문이 `compare_campaigns`를 선택한다.
- 반환 도구 인자가 strict 스키마를 통과한다.
- 결과 숫자는 서버 집계와 일치한다.
- 업무 데이터는 생성·변경되지 않는다.

### 문서

- `docs/detailed_implementation_plan.md` 상태 갱신
- [상위 명세](ai_assistant_redesign_spec.md) 완료 체크 갱신
- 이 문서에 실제 테스트 개수와 남은 제한 기록
- README의 AI 어시스턴트 설명 갱신

### 커밋

`docs(ai): finalize assistant workspace redesign`

## 17. 커밋 구성 권장안

첨부 초안은 13개 커밋을 제안하지만, 리뷰 가능성과 파일 중복을 고려해 다음 9개로 묶는 것을 기본안으로 한다.

1. `feat(ai): add conversation id to execution logs`
2. `feat(ai): add deterministic workspace insights`
3. `feat(ai): add cross-campaign comparison service`
4. `feat(ai): connect comparison and validated context to chat`
5. `refactor(ai): split workspace into focused modules`
6. `feat(ai): add workspace insights and prompt examples`
7. `feat(ai): add conversation history and context chips`
8. `feat(ai): render linked campaign comparisons`
9. `test(ai): cover workspace flows and update docs`

실제 구현 중 한 커밋의 테스트가 독립적으로 통과하지 않으면 더 작게 나눈다.

## 18. 롤백 전략

- migration: downgrade가 검증된 경우에만 배포 대상으로 인정한다.
- 백엔드 API: 기존 요청 필드는 선택 사항이므로 이전 프런트와 호환한다.
- 프런트 리팩터링: 기능 변경 전 별도 커밋으로 유지한다.
- 신규 인사이트 API 실패: 채팅 입력을 계속 사용할 수 있게 degrade한다.
- 신규 비교 도구 실패: 기존 metric·segment 도구에 영향을 주지 않게 분기한다.
- 문맥 hint 실패: 자동 추측하지 않고 context를 제거하거나 clarification을 반환한다.

`git reset --hard`나 데이터 삭제로 롤백하지 않는다. 이미 공유된 커밋은 `git revert`를 사용한다.

## 19. 최종 완료 정의

다음을 모두 충족해야 재설계를 완료로 표시한다.

- AI 화면에서 캠페인 검수·개별 성과 분석 드롭다운이 사라짐
- 인사이트와 업무 예시가 실제 데이터와 일치
- 대화가 메시지 형태로 이어지고 범위 변경 시 안전하게 초기화
- 저장된 세그먼트를 후속 문맥으로 사용 가능
- 여러 완료 캠페인을 실제 성과 기준으로 비교 가능
- 비교 결과에서 Campaigns 결과 화면으로 이동 가능
- 대화·개인정보·프롬프트 원문을 새로 저장하지 않음
- 기존 AI-A~D와 캠페인 실행 흐름 회귀 없음
- 전체 backend, JavaScript, E2E 검증 통과
