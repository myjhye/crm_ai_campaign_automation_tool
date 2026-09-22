# AI 워크스페이스 — 구현 결과

아키텍처·파일 지도·API 예시·트랜잭션·문맥 수명은 [AI 어시스턴트 상세 구현 해설](ai_assistant_architecture.md)에 별도로 정리했다.

`/#/ai`는 지표·고객 조건 조회, 확인 기반 세그먼트 저장, 저장된 세그먼트의 캠페인 준비, 여러 완료 캠페인 성과 비교를 제공한다. 개별 캠페인 검수·성과 분석 선택기는 제거했으며 Campaigns·Experiments의 기존 기능과 백엔드 API는 유지한다.

## 사용하는 방법

1. 좌측 **AI 어시스턴트**를 연다. 상단 데이터셋과 기간으로 집계한 인사이트를 표시한다.
2. 인사이트 또는 업무 예시를 클릭하면 입력창만 채운다. 전송하면 초기 안내가 사라지고 메시지가 쌓인다.
3. 세그먼트 제안의 **확인 후 세그먼트 저장**을 누르면 저장된 리소스의 문맥 칩이 생긴다.
4. **이 세그먼트로 캠페인 초안 만들어**로 이어간다. 채널·혜택이 없으면 질문하고, `이메일로 15% 할인 쿠폰, 다정한 말투로 만들어줘`처럼 답하면 A/B 초안을 보여준다.
5. 초안의 **확인 후 캠페인 저장**을 눌러 DRAFT를 저장하고 Campaigns에서 편집·검수한다. 생성만으로 캠페인을 저장하거나 발송하지 않는다.
6. 캠페인 비교 예시를 전송하면 집계 표와 캠페인 결과 탭 링크가 나온다. 문맥 칩이 있으면 후속 비교는 그 범위를 사용한다. 전체 비교로 돌아가려면 **문맥 제거**를 누른다.

모의 모드는 화면 예시와 위 후속 문장만 지원한다. 자유 문장의 해석은 실제 AI 모드를 사용한다. 캠페인의 제안 기본값은 전환율 목표 5%, A/B 50:50, 혜택 강조/관계 강조다. 채널과 혜택을 추측해서 채우지 않는다.

## 파일별 책임

| 파일 | 책임 |
| --- | --- |
| `frontend/src/features/ai/index.js` | 화면 수명, 메모리 대화 상태, 요청·취소, 확인 저장 |
| `insights.js` | 인사이트 로딩·오류·CTA |
| `examples.js` | 데이터·세그먼트·비교 예시 |
| `conversation.js` | 사용자/AI 메시지, 기존 preview, 지표·초안·저장 결과 |
| `comparison.js` | 캠페인 비교 표와 범위 보존 링크 |
| `input.js` | 입력창·문맥 칩·Enter/Shift+Enter·한글 조합 |
| `performance.js` | 기존 Campaigns·Experiments의 AI-D UI, 변경 없음 |
| `app/services/insights.py` | 기존 지표·preview·성과 서비스로 인사이트 생성 |
| `app/services/ai_context.py` | 서버에서 데이터셋·archive·최신 revision 재확인 |
| `app/services/performance.py` | 완료 캠페인 비교, 실제 성과·금액 정렬 |
| `app/ai/workspace_schemas.py` | bounded context, 비교 필터, 인사이트 응답 계약 |
| `app/ai/tools.py`, `provider.py` | strict 비교/후속 초안 도구, 실제·모의 provider |
| `app/ai/orchestrator.py` | 도구 허용 인자, 문맥 재확인, 기존 서비스 연결 |
| `alembic/versions/008_ai_conversation.py` | nullable conversation ID와 인덱스 |

## API와 데이터 기준

`GET /api/v1/ai/insights?dataset_id=...&from=...&to=...`는 LLM 없이 계산한다. 활성 고객·휴면 VIP 후보·최근 완료 캠페인을 표시하며, 집계할 항목이 없으면 생략한다. 대상 후보는 수신 동의 검수 전의 `60일 이상 미구매 AND 누적 구매액 30만원 이상`이다. 후보 카드와 채팅 미리보기는 선택 기간의 끝을 같은 기준 시점으로 사용한다.

`POST /api/v1/ai/chat`에 optional `conversation_id`, `context_hint`를 추가했다. 이전 요청과 호환된다. 세그먼트 hint는 실제 확인 저장 후의 ID/revision이며 캠페인 목록 hint는 최대 10개 ID다. 클라이언트 이름·라벨을 신뢰하지 않고 다시 조회한다. 변경·보관·다른 데이터셋 참조는 clarification으로 처리하며 문맥을 해제한다.

`compare_campaigns`는 같은 데이터셋의 미보관 COMPLETED 캠페인 중 선택한 발송 기간에 SENT 기록이 있는 캠페인을 조회한다. 완료 시각은 CampaignRun.finished_at, 성과 값은 기존 campaign_performance를 재사용한다. 비율은 이미 퍼센트이므로 다시 100을 곱하지 않는다. 금액은 Decimal로 정렬하고 null은 마지막에 둔다. 출력은 최대 10개, 집계 후보가 100개를 넘으면 범위를 좁히도록 요청한다. 비교 결과에는 카피와 고객 행이 없다.

화면의 지표 질문은 데이터셋 전체 기준이다. 세그먼트 내 별도 지표 계산, 임의 SQL, 임의 캠페인 평균은 지원하지 않는다. 비교 도구는 명시적인 발송 기간과 채널·세그먼트 필터를 지원한다. 결과 표 링크도 실제 비교 기간을 보존한다.

## 상태와 저장 보장

- 대화와 입력값은 브라우저 메모리에만 보관한다. 같은 범위에서 다른 화면을 다녀와도 복원하고, 데이터셋·기간 변경 또는 새로고침 때 초기화한다.
- 화면 이탈·범위 변경은 요청을 abort한다. 중단된 입력을 복구하며 늦은 응답이 새 화면에 반영되지 않는다.
- 문맥 칩 제거와 새 대화를 제공한다. 원문을 다음 모델 요청에 대화 기록으로 보내지 않는다. 이전 혜택 같은 자유 텍스트를 장기 기억하지 않는다.
- 요청 중 입력·중복 확인을 잠근다. 30분 만료, hash, 데이터/정책 version, 원자적 확인 저장은 기존 서비스를 재사용한다.
- conversation ID는 AI-A~D 실행 로그를 묶는 식별자다. 로그에 사용자 프롬프트·대화 원문을 추가하지 않는다.
- strict 중첩 필터도 모든 속성을 required로 두고 additionalProperties=false로 제한한다. [OpenAI 공식 계약](https://developers.openai.com/api/docs/guides/function-calling)을 따른다.

## 실행과 검증

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m scripts.check_ai_workspace
```

기존 VS Code 실행 작업도 migration 후 같은 앱을 실행한다. 로컬 DB에 `008`을 적용했다. 다운그레이드 검증은 운영 데이터 대신 격리 테스트 스키마에서 수행한다.

새 PostgreSQL 통합 검증은 인사이트 원본 일치, 세그먼트→캠페인 확인 저장, 문맥 변조·범위 격리, 비교 최소 응답·정렬·상한·archive, migration 왕복을 포함한다. 브라우저 API 대역으로 입력 자동 채움, 명시적 저장, 문맥 전달·제거, 화면 이동 복원, 기간 변경·요청 중단, IME, 모바일 입력창과 결과 링크를 검사한다.

최종 로컬 검증: PostgreSQL을 포함한 백엔드 141개, JavaScript 단위 16개, Chromium E2E 25개 통과. 모바일 레이아웃 보정 후 새 워크스페이스 E2E 2개를 다시 통과했다. 1280px 대화와 390px 진입 화면을 스크린샷으로 확인했다. 실제 로컬 데이터로 인사이트 응답 3개도 스키마 검증을 통과했다. `git diff --check` 통과.

실제 OpenAI와 로컬 DB의 읽기 전용 검증에서 compare_campaigns 선택·strict 인자·완료 캠페인 1개의 지표 일치를 확인했다. 업무 저장 없이 1,204토큰을 사용했다. 실제 LLM을 연결한 모든 자유 문장과 전체 브라우저 저장 시연을 검증했다는 의미는 아니다. 확인 저장 흐름은 격리 DB·브라우저 대역 테스트로 검증한다.
