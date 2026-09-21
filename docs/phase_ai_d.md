# AI-D — 근거 기반 성과 분석과 후속 실험 초안

## 사용 방법

- **Campaigns → 완료된 캠페인 → 발송·결과 → AI 성과 분석**을 누른다.
- **Experiments**의 각 카드에서도 같은 버튼을 사용할 수 있다.
- **Reports → 분석 열기 → AI 성과 분석**으로 캠페인별 분석을 연다.
- **AI 어시스턴트 → 완료 캠페인 성과 분석**에서 캠페인을 선택하고 요청을 전송한다. 검수 선택과 성과 분석 선택은 서로 배타적이다.

상단 기간은 발송 고객 집합의 범위다. 해당 기간에 발송된 고객이 없거나 캠페인이 완료 상태가 아니면 분석하지 않는다. 분석 화면은 확인된 사실, 검증 전 가설, 해석의 한계, 다음 행동을 구분한다. 실제 AI와 모의 응답도 표시한다.

Campaigns는 **작성 / 검수·승인 / 발송·결과 / AI 분석** 탭으로 나뉜다. AI 분석 탭은 COMPLETED에서만 활성화한다. 발송·결과의 **✦ AI 성과 분석 요청**을 누르면 해당 위치에서 로딩을 표시하고 성공 후 `tab=ai-analysis`로 이동한다. 실패하면 원래 탭에서 오류를 표시한다. 분석 결과가 있으면 **✦ AI 분석 결과 보기**는 재호출 없이 이동한다. **다시 분석**만 새 분석 요청을 보낸다.

Campaigns와 Experiments의 AI 분석 탭은 가설·다음 행동을 전체 폭의 AI 해석 카드로 먼저 보여준다. 아래에는 간단한 성과 요약과 기본 접힘 상태의 한계를 배치하며, 상단 판정과 같은 한계 문구는 중복 표시하지 않는다. 원본 수치는 발송·결과 탭으로 연결한다. 후속 초안은 표시 이름을 ‘후속 실험’으로 단순화하고 A/B 제목·본문을 2열로 비교한다. 좁은 화면에서는 1열이다. 표시 이름만 바꾸며 제안 payload와 확인 저장 계약은 변경하지 않는다.

결과는 캠페인·버전·데이터셋·기간별로 페이지 세션 메모리에 유지하며, 다른 범위에 재사용하지 않는다. 탭을 오가도 확인 저장 완료 표시를 유지한다. 새로고침하면 URL의 탭은 복원하지만 분석 내용은 다시 요청해야 한다. 서버 제안의 30분 만료·hash·원자적 확인 저장은 그대로 적용한다.

Experiments도 실험 결과 / AI 분석 탭으로 분리한다. 카드에서 분석을 요청하면 완료 후 해당 캠페인의 AI 분석 탭으로 이동한다. 캠페인 선택기로 다른 완료된 실험을 선택하고, 다시 분석하거나 후속 초안을 저장할 수 있다. `/#/experiments/{campaign_id}?dataset=...&tab=ai-analysis`로 선택과 탭을 보존한다. Reports·일반 AI 채팅은 기존 인라인 분석 흐름을 유지한다.

재실험 제안이 있으면 이름·채널·혜택·A/B 문안을 먼저 확인하고 **확인 후 후속 초안 저장**을 누른다. 성공하면 **저장된 초안 열기**로 작성 화면에 이동한다. 새 캠페인은 DRAFT이며 별도의 검수·승인이 필요하다.

## 범위와 해석

LLM은 서버가 제공한 지표 중 핵심 근거를 선택하고, 허용된 가설과 액션을 고른다. 자유로운 원인 서술을 그대로 표시하지 않는다. `COPY_RESPONSE`, `RANDOM_VARIATION`은 검증 전 가설이고, `RETEST`, `REVIEW_COPY`는 권장 행동이다. 표시 문장은 서버의 검토된 문구를 사용한다. 기기별 데이터가 없는데 모바일 이탈을 원인으로 설명하거나, 새로운 성과 숫자를 만드는 응답은 허용하지 않는다.

후속 제안은 **기존 A/B 조건을 보존한 재실험 초안**이다. 새로운 혜택이나 카피를 자동으로 창작하는 기능이 아니다. 대상·제외 revision·혜택·브랜드 톤·KPI·목표값·배분·문안을 유지하고 이름에 후속 실험을 붙인다. 예정 시각은 비우며 쿠폰 만료는 유지한다. 저장 후 표본 범위와 문안을 편집하고, 만료된 혜택을 재확인해야 한다. 기존 캠페인은 변경하지 않는다.

승자 판단은 단계 10 통계 결과를 그대로 사용한다. 합성 성과, 시연용 최소 표본·즉시 판정, 무발송 통제군 부재, 마지막 클릭 귀속과 인과관계의 한계를 표시한다. 통계 계산과 판정 기준은 변경하지 않았다.

## 구현 위치

| 파일 | 역할 |
| --- | --- |
| `app/ai/performance.py` | 요청 스키마, 지표 ID 목록, strict 도구 계약, 응답 대조, 후속 제안·확인 |
| `app/ai/provider.py` | 실제/모의 `analyze_campaign` 호출 |
| `app/ai/orchestrator.py`, `app/ai/schemas.py` | 채팅의 분석 컨텍스트, 후속 제안 확인 분기 |
| `app/api/routes/ai.py` | `POST /api/v1/ai/performance-analysis` |
| `app/services/performance.py` | 기존 성과 집계와 실험 판정 재사용 |
| `frontend/src/features/ai/performance.js` | 공통 분석 카드, 제안 미리보기, 확인 저장·오류·재시도 |
| `scripts/check_ai_performance.py` | 로컬 완료 캠페인 집계로 실제 provider를 한 번 호출하는 읽기 검증 |

직접 API는 `dataset_id`, `campaign_id`, `from`, `to`, 선택적 `prompt`를 받는다. 채팅은 기존 요청에 `analysis_campaign_id`를 추가한다. 응답 `data`는 `facts`, `hypotheses`, `limitations`, `recommended_actions`, `metric_refs`, `experiment`, `cohort`, `reference_at`, `proposal`을 포함한다.

모델에 고객 행·연락처·캠페인 이름·카피를 전달하지 않는다. 지표 ID·값·단위, 기존 실험 결과와 합성 데이터 여부만 제공하며 사용자 prompt는 기존 개인정보 패턴 검사에 통과해야 한다. 도구는 요청마다 `analyze_campaign` 하나만 허용한다. [공식 Function calling 계약](https://developers.openai.com/api/docs/guides/function-calling)에 따라 strict·필수 속성·추가 속성 차단을 적용했다.

모델의 `facts[].metric_id`는 제공한 ID여야 한다. 모델은 숫자를 반환하지 않으며, 화면 응답의 `value`는 서버의 해당 지표에서 직접 가져온다. 없는 metric, 불필요한 value 필드, 허용하지 않은 가설·액션·도구는 502로 거절한다. 모델은 승자나 임의 SQL·실행 대상 ID를 만들지 못한다. 검증 실패 시 업무 데이터와 제안을 저장하지 않고 수동 성과 화면을 유지한다.

## 저장과 충돌 보장

외부 호출 전 DB 세션을 닫고, 응답 후 데이터·원본 캠페인·정책 버전을 다시 확인한다. 분석 기준 시각을 고정한 집계 hash도 대조한다. 후속 제안은 기존 `ai_action_proposals`에 `CAMPAIGN_FOLLOWUP` 종류로 보관한다. 새 migration은 없으며 Alembic head는 `007`이다.

확인 API는 기존 `POST /ai/actions/{proposal_id}/confirm`이며 dataset ID만 받는다. 30분 만료·payload hash·dataset 범위·원본 version·데이터/정책 version·동일 분석 기준의 성과 hash를 다시 검사한다. 같은 제안의 동시 확인은 같은 캠페인 ID를 반환한다. 새 캠페인·감사 기록·확인 완료 표시는 같은 트랜잭션이며 감사 실패 시 전체 롤백한다. 서로 다른 분석 요청은 별도 제안이므로 별개 초안을 만들 수 있다.

AI 실행 이력에는 `analyze_campaign`, `ai-d-3`, provider/model, 성공 여부, 시간·토큰을 기록한다. 사용자 prompt나 모델 원문은 로그에 저장하지 않는다. 검증 실패 서버 로그에는 요청 ID·실패 단계·예외 종류만 기록한다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m scripts.check_ai_performance
```

AI-D PostgreSQL 통합 테스트는 실제 지표 대조, 분석 시 업무 미저장, 동시·중복 확인, 만료·hash·원본·정책·성과 변경 거절, 감사 실패 롤백, 모델 응답 중 원본 변경과 dataset 범위를 확인한다. provider HTTP 대역은 strict 도구와 동적 metric ID 계약을 검사한다. 브라우저 대역은 사실·가설 표시, 확인 전 미저장, 저장 성공 알림과 실패 후 수동 통계 유지·재시도를 확인한다.

실제 API 검증은 로컬 완료 캠페인 집계에 대한 지표 참조 4개를 통과했다(1,299토큰). 업무 캠페인을 저장하지 않는 provider 검증이며, 실제 모델과 브라우저를 함께 사용하는 전체 저장 시연과는 구분한다.

로컬 검증 결과: 전체 백엔드 134개, JavaScript 단위 16개, 전체 Chromium E2E 22개 통과. 채팅 분석 테스트 추가 후 Reports·Experiments·AI 분석 E2E 7개를 통과했다. 마지막 지표 참조·표시 보완 후 확인 저장/채팅 통합과 provider 테스트 6개도 다시 통과했다. 기존 테스트 도구의 deprecation 경고 2개는 남아 있다.

실제 호출에서 지표 14개를 반환해 서버의 최대 12개 제한에 걸리는 502를 재현했다. strict 도구에도 facts 1~12개, 가설 최대 2개, 액션 1~2개 제한을 동일 상수로 적용했다. provider 규격 회귀 테스트 5개와 확인 저장 통합 테스트 1개를 통과했고, 실제 모델을 사용하는 `/ai/performance-analysis` 전체 경로에서 지표 12개와 HTTP 200을 확인했다. 이 검증은 제안만 생성하며 업무 캠페인은 저장하지 않았다.

후속 오류 요청 `e4567d2f-2e5c-41a3-9ead-91dd59f38eb3`은 v2에서도 실패한 것을 확인했다. 같은 데이터로 실제 모델이 숫자 `15`를 `15},{`로 반환하는 현상을 재현하여, v3에서는 모델의 숫자 복사를 제거하고 지표 ID만 받는다. 실제 분석 API 연속 3회가 HTTP 200이었으며 모든 반환 값이 서버 근거와 일치했다. AI-D 통합·provider 테스트 17개가 통과했다.
