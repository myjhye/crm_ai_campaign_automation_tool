# 단계 5 — 고객 조회와 CRM 대시보드

## 구현 범위

고객 목록·상세·이벤트 타임라인과 대시보드 지표를 실제 PostgreSQL 데이터에 연결했다. 데이터셋·기간을 선택하면 원천 주문과 이벤트에서 계산한다. 새 마이그레이션 없이 단계 3의 테이블을 사용한다.

고객의 발송 이력·피로도·저장 세그먼트 소속은 아직 원천 테이블이 없다. 해당 API는 `not_ready`, `total=null`로 응답하고 화면은 준비 상태로 표시한다. 실제 세그먼트 소속은 단계 6, 발송·피로도는 단계 9 이후, CRM 기여 매출은 단계 10에서 연결한다. 미구현을 실적 0으로 표시하지 않는다.

## 코드와 처리 흐름

| 파일 | 역할 |
| --- | --- |
| `app/schemas/analytics.py` | 기간·dataset·검색·정렬 계약, 마스킹 고객 응답, 고객 필드가 없는 집계 응답 |
| `app/repositories/analytics.py` | 원천 주문 집계 CTE, 고객 필터·정렬·페이지, 퍼널·분포 SQL |
| `app/services/analytics.py` | snapshot 일관성, 이메일 마스킹, 금액·비율·이전 기간 비교 |
| `app/domain/analytics/rfm.py` | 버전이 있는 고정 RFM 점수 규칙 |
| `app/api/routes/analytics.py` | 고객·대시보드 HTTP 엔드포인트 |
| `frontend/src/api/analytics.js` | 요청 파라미터·응답 검사·버전 연결 |
| `frontend/src/features/customers/index.js` | 목록·검색·필터·정렬·상세·타임라인 |
| `frontend/src/features/dashboard/index.js` | KPI·상태 분포·퍼널·동일 고객 조건으로 이동 |
| `scripts/benchmark_analytics.py` | 격리된 테스트 schema에서 demo 생성·응답 시간·SQL 수 측정 |

요청은 route → service → repository → DB를 따른다. 서비스는 읽기 트랜잭션을 REPEATABLE READ로 시작하고 dataset 존재와 데이터 버전을 확인한다. 여러 SQL이 같은 DB snapshot을 사용한다. 고객별 쿼리를 반복하지 않고 목록 한 페이지의 채널을 한 번에 조회한다.

대시보드는 overview에서 받은 `data_version`을 funnel·segments 요청에 전달한다. 중간에 데이터가 바뀌면 `409 DATA_VERSION_CONFLICT`로 전체 화면 재조회를 요구한다. 고객 상세와 이벤트·준비 상태 이력도 같은 방식으로 연결한다. 업로드 당시 캐시와 사용자 선택 기간의 집계가 섞이지 않도록 **원천 주문에서 매번 계산**한다.

## API 계약

모든 경로는 `/api/v1` 아래다. 필수 query는 `dataset_id`, timezone 포함 `from`, `to`이며 `from < to`다. `data_version`은 선택적 일관성 검사 값이다.

| 경로 | 결과 |
| --- | --- |
| `GET /customers` | 마스킹 목록·total·page·page_size·reference_at·data_version |
| `GET /customers/{id}` | 고객 구매 지표·현재 채널 동의·선호 카테고리·RFM |
| `GET /customers/{id}/events` | 선택 기간 이벤트, 발생·적재 시각, 페이지네이션 |
| `GET /customers/{id}/deliveries` | 발송 이력 `not_ready` 계약 |
| `GET /customers/{id}/segments` | 소속 세그먼트 `not_ready` 계약 |
| `GET /dashboard/overview` | 현재·이전 기간 KPI, 차이, 분모, 원천 구분 |
| `GET /dashboard/funnel` | VIEW → CART → PURCHASE 순서별 고유 고객 수 |
| `GET /dashboard/segments` | 고객 상태 분포와 미구현 세그먼트 분포 구분 |

고객 목록 추가 query:

- `q`: 이름·이메일·외부 ID의 대소문자 무시 부분 검색, 최대 200자. `%`·`_`는 와일드카드가 아닌 검색 문자로 처리한다.
- `status`: ACTIVE/CHURN_RISK/DORMANT/WITHDRAWN.
- `signup_from`, `signup_to`: 선택적 timezone 포함 가입일 범위, `[from,to)`.
- `cohort`: all/new/active/purchased/repeat/view/cart/purchase. 마지막 세 값은 순서를 지킨 퍼널 단계 고객이다.
- `sort`: name/signup_at/total_purchase_amount/order_count, `direction`: asc/desc. 동점은 고객 UUID로 정렬한다.
- `page`, `page_size`: 공통 기본 1·20, 최대 100건. 이벤트 조회도 페이지네이션을 제공한다.

화면의 가입 종료일은 다음 날 자정으로 변환한다. 검색·상태·활동·가입 기간·정렬·페이지는 URL로 복원한다. 상태 분포 또는 퍼널의 막대·표 버튼을 누르면 같은 조건의 고객 목록으로 이동한다.

```powershell
$base = 'http://127.0.0.1:8000/api/v1'
$dataset = '선택한 데이터셋 UUID'
$period = "dataset_id=$dataset&from=2026-09-01T00:00:00Z&to=2026-09-19T00:00:00Z"
Invoke-RestMethod "$base/customers?$period&status=DORMANT&sort=total_purchase_amount&direction=desc"
Invoke-RestMethod "$base/dashboard/overview?$period"
```

목록과 상세 이메일은 `a***@example.invalid`처럼 마스킹한다. 채널 응답에 원문 연락처·토큰을 넣지 않고 이벤트의 임의 properties도 반환하지 않는다. 미래 AI 조회는 고객 응답 대신 집계 전용 `DashboardSummary`를 사용하도록 계약을 분리했다. 실제 LLM 연결은 아직 없다.

## 계산 기준

업무 기간은 `[from,to)`다. `reference_at=to`이며, 고객은 `signup_at < to`, 구매 합계·횟수·최근 구매는 **COMPLETED이면서 purchased_at < to인 전체 주문**으로 계산한다. 기간 내 지표는 추가로 `purchased_at >= from`을 적용한다. 평균 주문액은 소수점 2자리 Decimal 문자열, 구매가 없으면 null이다.

고객 상태는 `to` 시점에서 탈퇴가 우선이고, 그 외에는 마지막 완료 구매 또는 미구매자의 가입 시각으로 30/60일 경계를 적용한다. 탈퇴 시각이 정확히 `to`이면 상태는 WITHDRAWN이다. 단계 3 캐시는 고정 reference_at 이하의 주문을 사용하지만, 이 조회 API는 기간의 배타적 상한에 맞춰 정확히 `to`인 주문을 제외한다. 캐시를 수정하지 않는다.

| 지표 | 규칙 |
| --- | --- |
| 전체 고객 | 종료 시점 이전 가입, 탈퇴 포함 |
| 신규 고객 | 기간 내 가입 |
| 활성 고객 | 기간 내 VIEW/CART/PURCHASE가 하나 이상인 distinct 고객 |
| 휴면 고객 | 종료 시점 상태 DORMANT, 탈퇴 제외 |
| 구매 전환율 | 기간 내 완료 주문이 있는 활성 고객 / 활성 고객 × 100 |
| 재구매율 | 기간 내 완료 주문 2건 이상 고객 / 기간 내 완료 주문 고객 × 100 |
| CRM 기여 매출 | value=null, reason=not_ready |

분모가 0이면 `value=null`, `reason=NO_DENOMINATOR`다. 이전 기간은 바로 앞의 동일 길이 구간이다. 비율의 `difference`는 %p, 고객 수의 difference는 명, `relative_change`는 %다. 이전 값이 0 또는 미집계이면 상대 변화는 null이다. 화면은 비율을 최대 소수점 2자리로 표시하고 API는 4자리까지 제공한다.

퍼널은 기간 안의 첫 VIEW 이후 CART, 그 CART 이후 PURCHASE를 만족해야 한다. 같은 시각은 다음 단계로 인정하지 않는다. 반복 이벤트는 한 고객으로 세고 기간 밖 이벤트는 사용하지 않는다. PURCHASE 이벤트는 구매 행동을 나타내며 환불 후에도 발생 사실은 유지한다. 주문 기준 전환율과 동일한 지표가 아니다. 현재 seed에서 순서를 만족하는 고객이 없으면 실제 퍼널 후속 값은 0이다.

채널 동의·유효성은 **현재 저장 상태**이며 과거 기간으로 되돌리지 않는다. 주문 상태도 현재 저장된 완료·취소·환불 상태로 원천을 재집계한다. 과거 DB 상태를 복원하는 회계 장부는 아니다. 선호 카테고리는 종료 시점 이전 완료 주문 항목의 금액 합계가 가장 큰 카테고리이고, 동점은 DB 카테고리 정렬 순서로 정한다. 원천 항목이 없으면 null이다.

### RFM 고정 규칙

`rfm-fixed-v1` 규칙을 코드와 응답에 보존한다. 동일 값은 항상 같은 점수다. 미구매자는 R/F/M 모두 0이며 reason=NO_PURCHASE다.

| 점수 | R: 최근 구매 경과일 | F: 완료 주문 수 | M: 완료 주문액(KRW) |
| --- | --- | --- | --- |
| 5 | 7일 이하 | 10건 이상 | 50만 이상 |
| 4 | 8~30일 | 5~9건 | 30만 이상~50만 미만 |
| 3 | 31~60일 | 3~4건 | 10만 이상~30만 미만 |
| 2 | 61~90일 | 2건 | 5만 이상~10만 미만 |
| 1 | 91일 이상 | 1건 | 5만 미만 |

## 실행·검증·성능

기존 VS Code의 `Tasks: Run Task → GrowthPilot: 서버와 화면 실행`을 사용한다. 새 migration은 없다. Overview에서 실제 지표를 확인하고 Customers에서 목록·상세를 연다.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m scripts.benchmark_analytics
```

PostgreSQL 테스트는 수계산 지표, 기간 경계, 중복 이벤트, 순서가 뒤집힌 퍼널, 0 분모, 마스킹, dataset 격리, 날짜·정렬 검증, 데이터 버전 충돌, N+1 방지를 확인한다. RFM 경계 단위 테스트와 브라우저의 차트 → 필터 → 상세 → 새로고침 흐름을 추가했다. 실제 로컬 DB에 연결한 대시보드·고객 상세도 브라우저에서 확인했다.

전체 백엔드 테스트 53개, JavaScript 단위 테스트 9개, Chromium E2E 5개를 통과했다. 금액은 프런트에서도 정수부를 BigInt로 포맷해 큰 Decimal 문자열을 Number로 변환하면서 생기는 오차를 피한다.

benchmark는 설정 DB 이름에 `_test`를 붙인 전용 DB의 임시 schema에 고객 10,000·주문 30,000·이벤트 200,000건을 생성하고 정리한다. 테스트 DB는 먼저 `run_db_tests --create`로 준비한다. 원천 테이블 ANALYZE 후 각 API를 3회 호출한 2026-09-19 로컬 중앙값:

| API | 중앙값 | SQL 수 |
| --- | ---: | ---: |
| customers (기본 20건) | 68.60ms | 5 |
| dashboard/overview | 194.28ms | 4 |
| dashboard/funnel | 116.22ms | 3 |
| dashboard/segments | 40.84ms | 3 |

이 값은 TestClient와 로컬 Docker PostgreSQL에서의 측정이며 운영 보장이 아니다. 신규 대량 적재 직후 통계 갱신 전에는 고객 목록 중앙값이 약 2.54초였다. 대량 적재 후 PostgreSQL 통계 갱신 상태가 성능에 영향을 준다. 고객 목록은 page_size 1과 100 모두 SQL 5회임을 통합 테스트로 검증했다.
