# AI 어시스턴트 화면 재설계 명세

> 상태: 구현 완료 — 2026-09-22  
> 대상 화면: `/#/ai`  
> 주요 경로: `frontend/src/features/ai/`, `app/ai/`  
> 작성 목적: AI 어시스턴트를 중복 기능 모음에서 대화형 업무 연결·크로스 캠페인 조회 화면으로 재구성한다.

실제 구현 순서와 커밋 경계는 [AI 어시스턴트 화면 재설계 실행 계획](ai_assistant_redesign_execution_plan.md)을 따른다.

## 1. 문서 사용 원칙

이 문서는 구현 기준과 설계 의도를 설명한다. 실제 파일·검증 결과·운영 제한은 [구현 결과](ai_assistant_workspace.md)에 정리했다.

- 기존 트랜잭션 경계, strict 도구 계약, 확인 후 저장 패턴을 유지한다.
- 여기에 없는 공통 규칙은 `app/ai/orchestrator.py`와 단계별 AI 문서를 따른다.
- 예시 코드는 설계 의도를 보여주는 참고다. 실제 모델·서비스·응답 타입은 현재 코드에 맞춰 구현한다.
- 새 기능 때문에 Campaigns, Experiments, Reports에서 이미 제공하는 AI 기능을 제거하지 않는다.
- 공개 데모이므로 대화 전문과 고객 개인정보를 서버에 저장하지 않는다.

관련 문서:

- [AI-A 지표·세그먼트](phase_ai_a.md)
- [AI-B 캠페인 생성](phase_ai_b.md)
- [AI-C 정책 검수](phase_ai_c.md)
- [AI-D 성과 분석](phase_ai_d.md)
- [전체 구현 순서](detailed_implementation_plan.md)

## 2. 문제와 목표

### 현재 문제

현재 `/#/ai`에는 다음 기능이 함께 노출된다.

- 캠페인 검수 드롭다운
- 완료 캠페인 성과 분석 드롭다운
- 지표·세그먼트용 자유 입력과 예시 프롬프트

검수와 개별 캠페인 성과 분석은 Campaigns 화면에서도 수행할 수 있다. AI 화면에서 같은 기능을 다시 선택하게 하면 화면의 정체성이 흐려지고 방문자가 무엇부터 해야 하는지 판단하기 어렵다.

### 목표 정체성

AI 어시스턴트는 다음 두 업무에 집중한다.

1. 세그먼트 조회·저장 → 캠페인 준비처럼 여러 단계를 대화 문맥으로 연결한다.
2. 여러 완료 캠페인의 성과를 한 번에 비교한다.

### AI 화면에서 제거할 UI

- `캠페인 검수` 선택 UI와 해당 프런트 상태
- `완료 캠페인 성과 분석` 선택 UI와 해당 프런트 상태
- 화면 안에서 중복 표시되는 AI 어시스턴트 제목과 데이터셋 이름

백엔드의 `validation_campaign_id`, `analysis_campaign_id`, `/ai/performance-analysis` 계약은 유지한다. 다른 화면과 기존 호출의 호환성을 깨지 않는다.

## 3. 최종 사용자 흐름

### 첫 진입

1. 선택한 데이터셋과 기간으로 인사이트 API를 호출한다.
2. 결정론적 인사이트 카드와 업무별 예시를 보여준다.
3. 카드 CTA는 프롬프트를 채우거나 관련 화면으로 이동한다.

### 대화 시작

1. 첫 메시지를 보내면 인사이트와 예시 영역을 숨긴다.
2. 사용자·AI 메시지를 시간순으로 쌓는다.
3. 결과 카드는 해당 AI 말풍선 안에 표시한다.
4. 새 메시지가 도착하면 메시지 영역의 하단으로 이동한다.

### 문맥 연결

1. 최초 전송 시 브라우저가 `conversation_id`를 만든다.
2. 저장된 세그먼트처럼 후속 업무에 필요한 서버 참조를 `context_hint`로 받는다.
3. 화면은 참조를 입력창 위 칩으로 보여준다.
4. 다음 요청에 같은 `conversation_id`와 `context_hint`를 보낸다.
5. 서버는 전달된 참조를 신뢰하지 않고 데이터셋 범위·현재 상태를 다시 확인한다.

### 범위 변경

- 데이터셋 또는 기간이 바뀌면 진행 중 요청을 취소한다.
- 대화·문맥·conversation ID를 초기화하고 인사이트를 다시 조회한다.
- 다른 화면으로 이동하면 요청을 취소한다.
- 같은 페이지 세션에서 뒤로 왔을 때는 메모리 상태를 복원할 수 있다.
- 새로고침과 localStorage 복원은 지원하지 않는다.

## 4. 화면 구조

```text
┌─────────────────────────────────────────────┐
│ 공통 데이터셋·기간 필터                       │
├─────────────────────────────────────────────┤
│ 첫 진입: 인사이트 카드 + 업무별 예시           │
│ 대화 후: 사용자/AI 메시지 기록                 │
│                                             │
│                메시지 영역만 스크롤             │
├─────────────────────────────────────────────┤
│ [문맥 칩: 휴면 VIP 세그먼트 기준으로] [×]       │
│ [AI에게 요청하기                     ] [전송]   │
└─────────────────────────────────────────────┘
```

입력 동작:

- Enter: 전송
- Shift+Enter: 줄바꿈
- 한글 조합 중 Enter: 전송하지 않음
- 요청 중: 입력과 전송을 잠그고 진행 상태 표시

## 5. 프런트엔드 구조

`frontend/src/features/ai/`를 다음 책임으로 분리한다.

| 파일 | 책임 |
| --- | --- |
| `index.js` | 라우터 진입, 범위 감지, 모듈 조립 |
| `insights.js` | 초기 인사이트 카드와 CTA |
| `conversation.js` | 메시지 상태와 말풍선 렌더링 |
| `examples.js` | 업무별 예시 그룹 |
| `comparison.js` | 캠페인 비교 결과 테이블 |
| `input.js` | 입력 바, 자동 높이, 문맥 칩 |
| `performance.js` | 기존 개별 캠페인 AI-D 결과 UI 유지 |

권장 화면 상태:

```javascript
{
  conversationId: null,
  messages: [],
  contextHint: null,
  insights: null,
  busy: false,
  controller: null,
}
```

메시지 기본 형태:

```javascript
{
  role: 'user' | 'assistant' | 'system',
  content: '표시할 문장',
  resultType: 'metric' | 'segment_preview' | 'segment_saved' |
              'campaign_comparison' | 'clarification' | null,
  data: null,
  timestamp: 'ISO8601',
}
```

AI 말풍선은 `resultType`에 따라 기존 지표·세그먼트 카드 또는 신규 비교 카드를 삽입한다. 캠페인 비교 결과의 이름은 Campaigns 상세로 이동하는 링크여야 한다.

### 첫 화면 예시 그룹

- 데이터 살펴보기
  - 활성 고객 수는?
  - 지난달 신규 가입자 알려줘
- 세그먼트 만들기
  - 60일 미구매, 누적 30만원 이상, 이메일 동의 고객
  - 이번 달 신규 가입한 VIP 후보
- 성과 비교
  - 이번 달 완료 캠페인 중 전환율이 가장 높은 캠페인은?
  - 휴면 VIP 대상 캠페인의 성과를 비교해줘

예시를 누르면 즉시 요청하지 않고 입력창을 채운 뒤 포커스를 이동한다.

## 6. 인사이트 API

### 계약

```http
GET /api/v1/ai/insights?dataset_id={UUID}&from={ISO8601}&to={ISO8601}
```

```json
{
  "dataset_id": "UUID",
  "reference_at": "ISO8601",
  "cards": [
    {
      "id": "active_customers",
      "kind": "metric",
      "title": "활성 고객 비율",
      "primary_value": "3,842명",
      "secondary_value": "전체의 76.8%",
      "cta": {
        "label": "이 고객들 분석하기",
        "prefill_prompt": "활성 고객의 구매 패턴을 요약해줘"
      }
    }
  ]
}
```

### 카드 종류

1. 활성 고객 비율
   - 기존 Overview 집계 재사용
   - 값이 없으면 카드를 만들지 않는다.
2. 캠페인 대상 후보
   - `60일 이상 미구매 AND 누적 구매액 30만원 이상` 조건 미리보기
   - 세그먼트 저장 초안 프롬프트를 제공한다.
3. 최근 완료 캠페인
   - 최신 완료 캠페인의 실제 집계를 사용한다.
   - CTA는 Campaigns의 AI 분석 탭으로 이동한다.

인사이트는 LLM이 만들지 않는다. 서버 서비스가 기존 지표·세그먼트·성과 계산기를 호출해 결정론적으로 생성한다.

구현 위치:

- 신규 `app/services/insights.py`
- `app/api/routes/ai.py`의 `GET /insights`
- 응답 Pydantic 스키마

## 7. 크로스 캠페인 비교

### 도구

기존 `/api/v1/ai/chat`에 strict 도구 `compare_campaigns`를 추가한다. 별도 실행 API는 만들지 않는다.

도구 인자:

| 필드 | 계약 |
| --- | --- |
| `filter.status` | `COMPLETED` 고정 |
| `filter.channel` | `EMAIL`, `PUSH`, `SMS`, `ANY` |
| `filter.segment_revision_id` | 빈 문자열 또는 같은 데이터셋 revision UUID |
| `filter.from`, `filter.to` | 빈 문자열이면 화면 기간 사용 |
| `sort` | `conversion_rate`, `click_rate`, `revenue`, `sent_count` |
| `order` | `desc`, `asc` |
| `limit` | 1~10 |

### 서버 처리

`app/services/performance.py`에 비교 전용 서비스를 추가한다.

- 데이터셋 범위에서 완료 캠페인만 조회한다.
- 채널·세그먼트·기간 필터를 서버에서 검증한다.
- 기존 `campaign_performance()`를 재사용한다.
- A/B 합산 성과를 정렬한다.
- 최대 10개만 반환한다.
- 캠페인명·채널·발송 수·클릭률·전환율·기여 매출·완료 기준 시각을 반환한다.
- 카피 본문과 고객 행은 반환하지 않는다.

응답 타입은 `campaign_comparison`이다.

```json
{
  "result_type": "campaign_comparison",
  "data": {
    "campaigns": [
      {
        "campaign_id": "UUID",
        "name": "휴면 VIP 재활성화",
        "channel": "EMAIL",
        "sent_count": 1402,
        "conversion_rate": 3.27,
        "click_rate": 25.46,
        "revenue": "3477000"
      }
    ],
    "total_matched": 4
  }
}
```

비율 단위는 기존 `campaign_performance()` 응답과 동일하게 유지한다. 프런트에서 임의로 100을 다시 곱하지 않는다.

## 8. 대화 문맥 계약

### 요청 확장

`ChatRequest`에 선택 필드를 추가한다.

```python
conversation_id: UUID | None = None
context_hint: dict | None = None
```

`context_hint`는 자유 dict로 끝내지 말고 가능한 종류를 discriminated union 또는 명시적 Pydantic 모델로 검증하는 것을 우선한다.

지원할 문맥:

- `segment`: 세그먼트 ID, revision ID, 이름, 표시 라벨
- `campaign_list`: 비교 결과의 캠페인 ID 목록과 표시 라벨

서버 검증:

- ID가 현재 데이터셋에 속하는지 확인
- archive·상태·revision 유효성 확인
- 실패하면 쓰기나 조회를 진행하지 않고 `clarification`으로 응답
- 모델에는 재조회한 요약만 제공

### 실행 로그

`ai_execution_logs`에 nullable `conversation_id`와 조회 인덱스를 추가한다.

- 요청 그룹 추적에만 사용한다.
- 사용자 프롬프트와 대화 전문은 저장하지 않는다.
- 신규 Alembic revision이 필요하다.

## 9. 기존 동작과 호환성

다음 기능은 그대로 유지한다.

- `safe_prompt()`의 연락처·API 키 패턴 차단
- 도구별 허용 인자와 `additionalProperties=false`
- 모델 호출 전 DB 세션 종료
- Responses API `store=false`
- `parallel_tool_calls=false`, `tool_choice=required`
- 제안 30분 만료, payload hash 검증
- dataset 잠금과 확인 저장 원자성
- 기존 `/ai/chat`, `/ai/campaign-plan`, `/ai/performance-analysis`
- Campaigns·Experiments·Reports의 기존 AI 기능

## 10. 구현 전 확인할 코드 차이

첨부 초안의 예시를 그대로 복사하지 말고 아래를 현재 코드에서 확인한다.

1. Campaign에 실제 `completed_at` 컬럼이 있는지 확인한다. 없다면 완료 run의 완료 시각이나 기존 성과 서비스의 cohort 기준을 사용한다.
2. `campaign_performance()`의 비율과 매출 응답이 scalar인지 `{value, unit}` 구조인지 확인한다.
3. Overview와 세그먼트 preview의 현재 함수명·요청 스키마를 재사용한다.
4. `AIExecutionLog` 생성 위치가 여러 곳이면 모든 실행 경로에서 conversation ID가 누락되지 않게 공통화한다.
5. 현재 `index.js`의 확인 저장 UI와 AbortController 수명을 분리 과정에서 잃지 않는다.
6. 컨텍스트로 캠페인 생성을 이어가는 범위가 AI-B의 현재 UI 정책과 충돌하는지 확인한다. 이번 단계에서 완전한 대화형 캠페인 생성까지 연결하지 못하면 명확한 `clarification`과 Campaigns 이동 CTA를 제공한다.

## 11. 구현 순서

1. 현재 모델·서비스·응답 구조 감사
2. migration과 `conversation_id` 기록
3. 결정론적 인사이트 서비스와 API
4. 크로스 캠페인 비교 서비스
5. strict 도구와 orchestrator 분기
6. context hint 재검증과 응답 계약
7. 프런트 상태·파일 분리
8. 인사이트와 예시 렌더링
9. 대화·스크롤·문맥 칩 연결
10. 비교 결과 카드 연결
11. 단위·통합·E2E·실제 provider 검증

각 단계는 독립적으로 검증하고, 쓰기 기능은 기존 확인 저장 경로만 사용한다.

## 12. 완료 기준

### 백엔드

- [x] 인사이트 카드 값이 기존 DB 집계와 일치한다.
- [x] 인사이트 생성 과정에서 LLM을 호출하지 않는다.
- [x] 캠페인 비교는 같은 데이터셋의 완료 캠페인만 반환한다.
- [x] 비교 결과에 고객 정보와 카피 본문이 없다.
- [x] 잘못된 segment revision과 context hint를 거절한다.
- [x] conversation ID가 실행 로그에 기록된다.
- [x] 대화 전문과 프롬프트 원문은 저장하지 않는다.
- [x] 기존 AI-A~D API 회귀 테스트가 통과한다.

### 프런트엔드

- [x] 첫 진입에 인사이트와 예시 그룹을 표시한다.
- [x] 카드 CTA가 입력을 채우거나 올바른 화면으로 이동한다.
- [x] 첫 전송 후 초기 콘텐츠 대신 대화를 표시한다.
- [x] 메시지 역할을 시각·접근성 라벨로 구분한다.
- [x] 새 메시지 도착 시 메시지 영역만 자동 스크롤한다.
- [x] 문맥 칩을 표시하고 사용자가 제거할 수 있다.
- [x] 캠페인 비교 결과 이름이 상세 링크다.
- [x] 범위 변경과 화면 이탈 시 이전 요청을 취소한다.
- [x] 모바일에서 가로 넘침이 없다.

### 대표 시나리오

1. 대상 후보 인사이트로 세그먼트 미리보기를 요청한다.
2. 확인 후 세그먼트를 저장한다.
3. 저장된 세그먼트 문맥 칩이 나타난다.
4. 후속 업무를 입력한다.
5. 서버가 문맥 리소스를 재검증한다.
6. 필요한 정보가 부족하면 clarification을 반환한다.
7. 다음 작업 화면으로 이동할 수 있는 CTA를 제공한다.

## 13. 비목표

- 대화 전문 서버 저장
- localStorage 기반 대화 복원
- 계정별 대화 기록
- LLM이 생성하는 인사이트 카드
- 비교 결과에 포함되는 고객 행·연락처·카피 본문
- 실시간 스트리밍 응답
- AI의 자동 승인·자동 발송
