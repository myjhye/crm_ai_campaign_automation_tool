# 단계 10 — 성과 집계·A/B 실험·보고서

## 구현 범위

모의 발송 원장을 공통 성과 집계로 연결했다. Campaigns의 **발송·결과**, Experiments, Reports가 같은 계산 함수를 사용하며, CSV도 화면과 같은 발송 cohort와 7일 마지막 클릭 귀속 기준으로 생성한다. 모든 화면은 모의 데이터 포함 여부와 관찰 종료 여부를 표시한다.

## 계산 계약

- 발송 cohort는 선택 기간 `[from, to)`에 성공한 발송의 distinct 고객이다.
- OPEN·CLICK·UNSUBSCRIBE는 이벤트가 여러 번 있어도 고객당 한 명으로 센다.
- 전환은 주문 전 7일 이내의 마지막 CLICK 하나에만 귀속한다. 경계의 클릭을 포함하며 같은 시각이면 이벤트 UUID가 큰 클릭을 선택한다.
- 완료 주문만 매출에 포함한다. 취소·전액 환불 주문과 클릭 없는 주문은 제외한다.
- EMAIL이 아닌 채널의 오픈율은 `not_applicable`, 분모 0은 `no_denominator`, 무발송 통제군이 필요한 증분 지표는 `not_available`이다.
- CTOR의 클릭 고객이 오픈 고객보다 많으면 수치를 보정하지 않고 `data_quality_error`로 반환한다.

## API와 화면

| 위치 | 역할 |
| --- | --- |
| `GET /api/v1/campaigns/{id}/performance` | 캠페인 전체·A/B별 분모, 이벤트, 전환, 귀속 매출 |
| `GET /api/v1/reports/campaigns` | 완료 캠페인별 공통 성과 페이지 |
| `GET /api/v1/reports/summary` | 현재·직전 동기간 요약과 채널·세그먼트별 집계 |
| `GET /api/v1/reports/export` | UTF-8 BOM CSV, 수식 실행 문자열 방어 |
| `frontend/src/features/experiments/` | 주지표별 A/B 차이, 신뢰구간, 판단 보류 사유 |
| `frontend/src/features/reports/` | 완료 캠페인 KPI, 표, CSV 다운로드 |

Campaigns의 결과 탭에는 클릭률·전환율·기여 매출과 A/B 차이를 표시한다. Reports의 캠페인명을 누르면 같은 결과 탭으로 이동한다.

## A/B 판단

비율형 주지표는 양측 95% Wilson 신뢰구간과 pooled two-proportion z-test를 사용한다. 이론상 필요 표본은 기준 전환율 대비 50% 상대 개선, 양측 유의수준 5%, 검정력 80% 가정으로 산출해 화면에 표시한다. 작은 합성 데이터에서 판단 경로를 시연하기 위한 실행 최소 표본은 안별 30명이며, 승자 선언에는 기존 `p < 0.05`가 별도로 필요하다. 실험 관찰 기간은 시연용으로 발송 완료 즉시(`0일`)이고 주문의 7일 클릭 귀속 창과 별도로 관리한다. 시연 최소 표본 미달, B안 수신거부율이 A안보다 1%p 넘게 높음, 유의한 차이 없음 중 하나라도 해당하면 승자를 선언하지 않는다. 실제 운영에서는 이 시연 하한과 즉시 종료를 사용하지 않고 상품 구매 주기에 맞춘 MDE와 관찰 기간으로 사전 표본을 결정해야 한다.

`click_rate`는 클릭 고객, `conversion_rate`는 귀속 구매 고객으로 비교한다. 연속형 매출의 유의성 검정은 현재 제공하지 않아 주지표가 `revenue`이면 판단 보류한다. A/B 차이는 두 발송안 비교이며 무발송 대비 증분 효과가 아니다.

## 검증

PostgreSQL 통합 테스트는 중복 OPEN의 distinct 집계, 모의 주문의 7일 클릭 귀속, 보고서·CSV의 동일 수치와 BOM을 확인한다. 단위 테스트는 0 분모, Wilson 구간, 관찰 미종료, 표본 부족, 기준군 0과 가드레일 판단을 검사한다. 브라우저 테스트는 Reports, Experiments, Campaigns 결과 탭과 CSV 진입을 확인한다.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
```

다음 구현은 AI-D다. 이 단계의 구조화 성과만 AI에 전달해 사실·가설·한계를 구분한 요약과 확인 기반 후속 초안을 만든다.

## 실험 시연 데이터

`seed_demo.py --size medium --seed 42`는 `체험용 중형 샘플 (고객 5,000명)`을 만든다. 상품 300개, 주문 15,000건, 주문 항목 15,000건, 이벤트 100,000건이며 같은 옵션의 재실행은 기존 데이터셋을 반환한다. 기본 휴면 VIP 조건(마지막 구매 후 60일 이상·누적 구매액 30만원 이상·이메일 동의)은 500명이고 50:50 배정 시 안별 250명이다.
