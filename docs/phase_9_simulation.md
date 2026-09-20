# 단계 9 — 승인 기반 모의 발송과 이벤트

## 구현 범위

Campaigns는 **작성 / 검수·승인 / 발송·결과** 탭으로 구성한다. 작성 탭은 캠페인 폼과 AI 초안 도구, 검수 탭은 대상과 사유별 제외 및 승인 동작, 결과 탭은 실행 상태와 발송 집계를 전체 폭으로 표시한다. 선택 캠페인과 탭은 `/#/campaigns/{campaign_id}?dataset=...&tab=results`처럼 URL에 보존한다.

목록의 `APPROVED` 카드에는 **모의 발송**을 바로 표시하고, 실행하면 발송·결과 탭으로 이동해 기존 진행률 폴링을 이어간다. `RUNNING` 카드는 진행 상황 보기, `COMPLETED` 카드는 발송 완료 배지와 결과 보기를 표시하며 작성 중 캠페인에는 발송 동작을 노출하지 않는다.

요청은 승인 당시 검수 스냅샷을 후보 상한으로 사용하며 실행 직전에 탈퇴, 채널 동의, 연락처, 같은 캠페인 기수신, 일일·최근 7일 노출 한도를 다시 검사한다. 새로 자격을 얻은 고객은 추가하지 않고 자격을 잃은 고객만 `EXCLUDED`와 사유로 기록한다.

API는 외부 메시지를 보내지 않는다. PostgreSQL 작업 큐에 `campaign.simulate`를 넣고 별도 worker가 안정적인 A/B 배정, `SENT`·`FAILED`, 채널별 반응 이벤트와 모의 주문을 생성한다. VS Code의 **GrowthPilot: 서버와 화면 실행** 작업은 API와 worker를 함께 시작한다.

## 저장 구조

`007_campaign_runs.py`가 다음 구조를 추가한다.

| 구조 | 역할 |
| --- | --- |
| `campaign_runs` | 승인·검수·job·멱등 키·seed·반응 확률·실행 집계 |
| `campaign_deliveries` 확장 | run, A/B variant, 예약·발송·실패·제외 상태와 제외 사유 |
| `campaign_events` | delivery·variant·고객·주문에 연결된 반응 이벤트 |
| `orders.source` | 업로드 주문과 `SIMULATED` 주문 구분 |

한 캠페인은 한 번만 실행한다. `(campaign_id, idempotency_key)`와 `(run_id, customer_id)`, 외부 이벤트 ID unique 제약으로 HTTP 재전송과 worker 재시도의 중복을 막는다.

## 실행 요청

`POST /api/v1/campaigns/{id}/simulate-send`는 JSON의 `dataset_id`, `campaign_version`과 `Idempotency-Key` 헤더를 받는다. 같은 키와 같은 요청은 기존 run을 반환하고, 같은 키의 다른 version은 409다. 다른 키라도 캠페인이 이미 RUNNING 또는 COMPLETED면 새 run을 만들지 않는다.

캠페인·dataset 잠금 아래에서 승인 상태, 내용 hash, 정책 version, 데이터 version을 확인한다. 검수 결과의 30분 유효 시간은 승인 요청 전까지 적용하며, 동일한 스냅샷에 대한 방문자 승인이 완료된 뒤에는 이 임시 시각만으로 실행을 차단하지 않는다. 승인 후보 고객을 UUID 순서로 잠근 뒤 현재 동의·탈퇴·연락처·노출 상태를 다시 적용한다. run, delivery 예약, job, 캠페인 RUNNING 전환과 감사 기록은 한 트랜잭션이다.

## worker와 결정론

worker는 run seed와 고객 ID의 SHA-256 순서로 고객을 정렬한다. A안은 `대상 수 × allocation_bp // 10,000`명이며 나머지는 B안이다. 배정과 결과는 DB에 저장되며 작업 트랜잭션이 실패하면 job 완료까지 함께 rollback된다.

전달 성공 고객에게만 `DELIVERED`를 만들고 EMAIL에만 OPEN을 생성한다. CLICK 이후에만 CONVERSION을 생성하며 전환에는 `source=SIMULATED` 완료 주문을 연결한다. 시연 결과가 비어 보이지 않도록 첫 전달 성공 고객 한 명은 최소 퍼널 표본으로 만들고 이 설정도 run에 기록한다. 나머지는 저장된 반응 확률과 seed로 결정한다. 실제 발송 provider의 exactly-once 보장은 이 단계의 범위가 아니다.

일반 고객·대시보드·세그먼트 집계는 `source=UPLOADED` 주문만 사용한다. 모의 주문은 고객 구매 캐시나 원천 데이터 version을 바꾸지 않으며 단계 10의 캠페인 성과 집계에서만 별도로 사용한다.

조회 API는 `GET /campaigns/{id}/runs/{run_id}`와 기존 `GET /jobs/{job_id}`다. run 응답은 예약·실행 전 제외·성공·실패 외에 `failure_summary`, `variant_summary`, `event_summary`를 반환한다. 결과 탭은 실행 전 제외와 시스템 실패 사유, A/B별 발송·실패, 전달·오픈·클릭·전환·수신거부 고유 고객 수를 표시한다.

## 검증

PostgreSQL 통합 테스트는 같은 키 재요청, 같은 키의 다른 payload, 다른 키 재실행 차단, 고객당 결과 1건, A/B 배정, 전달 성공 이후 이벤트, SIMULATED 주문과 일반 고객 캐시 분리, 실행 직전 동의 철회 제외를 확인한다. 브라우저 테스트는 탭 URL 보존, 목록 직접 실행, 멱등 키 헤더와 상세 완료 집계를 확인한다. 로컬 검증에서 백엔드 전체 111개, JavaScript 단위 16개, Chromium E2E 16개가 통과했다.
