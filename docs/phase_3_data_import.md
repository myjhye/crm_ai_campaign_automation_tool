# 단계 3 — CSV 적재와 합성 샘플 데이터

## 구현 범위

고객·상품·주문·주문 항목·행동 이벤트의 CSV 미리보기와 확정 적재를 구현했다. 미리보기는 업무 데이터를 바꾸지 않는다. 확정 요청은 기존 PostgreSQL 작업 큐에 작업을 넣고, 별도 Python worker가 검증·저장·집계·감사 기록을 처리한다.

Docker는 PostgreSQL 실행에만 사용한다. FastAPI, worker, 샘플 생성기는 로컬 `.venv`에서 실행한다. 업로드 화면은 단계 4 이후, 캠페인 성과 CSV와 발송 이력에 따른 노출 초과 샘플은 단계 9~10에서 연결한다.

## 구현 파일과 처리 흐름

| 파일 | 역할 |
| --- | --- |
| `alembic/versions/003b_import_content.py` | 배치 원본·옵션·보관 기한, 데이터셋 기준 시점 추가 |
| `app/schemas/imports.py` | CSV 종류별 필수 컬럼·타입·금액·시간·properties 검증 |
| `app/api/routes/imports.py` | 크기를 제한하며 CSV 수신, 미리보기·확정·결과 조회 |
| `app/services/imports.py` | 파싱, 중복·참조 검증, 적재 계획, 확정 적재와 집계 |
| `app/repositories/imports.py` | 데이터셋 범위 조회, 원천 주문 집계, 1,000건 단위 저장 |
| `app/workers/handlers.py` | `data.import` 작업 등록 |
| `scripts/seed_demo.py` | 같은 seed·기준 시점으로 재현하는 합성 데이터 |
| `scripts/recalculate_customers.py` | 고객 캐시와 원천 주문 비교·명시적 복구 |
| `scripts/cleanup_imports.py` | 보관 기한이 지난 CSV 원본 정리 |
| `tests/fixtures/imports/` | 적재 순서대로 실행 가능한 정상 CSV와 오류 예제 |

1. `POST /api/v1/data/import/{kind}/preview`에 `text/csv` 원본을 보낸다. UTF-8 BOM을 제거하고 헤더·행 스키마를 검사한다.
2. 같은 데이터셋 안에서 고객·상품·주문 참조와 기존 값을 조회한다. 생성·변경·중복 건수와 오류를 계산한다.
3. UUID 배치에 원본 bytes, SHA-256, `mode`, `reference_at`, 요청 ID를 저장한다. 원본과 옵션을 바꾸는 API는 없다.
4. `POST /api/v1/data/import/{import_batch_id}/commit`은 배치를 잠그고 작업을 생성한 뒤 `202`와 `job_id`를 반환한다. 같은 배치를 다시 확정해도 같은 작업이다.
5. worker는 데이터셋 → 배치 순서로 잠근다. 원본 hash를 확인하고 최신 DB 상태로 다시 검증한다. 미리보기 이후 달라진 참조·중복 조건을 그대로 믿지 않는다.
6. 모든 행이 유효하면 저장 → 영향받은 고객 집계 → 데이터 버전 증가 → 감사 기록 → 배치 완료 → job 완료를 **같은 트랜잭션**으로 처리한다.
7. 예외나 lease 소유권 상실 시 전체 변경이 rollback된다. 재시도는 보관한 동일 원본으로 실행한다.

계획의 임시 파일 저장은 **PostgreSQL `bytea` 보관**으로 구체화했다. API와 worker 사이의 공유 폴더가 필요 없고, 원본과 배치 메타데이터를 함께 저장할 수 있다. 따라서 임의 파일 이름 대신 UUID 배치로 식별한다. 원본은 7일 보관하며 정리 명령으로 제거한다. 요약·hash·감사 기록은 유지하고 대기·실행 중인 작업의 원본은 지우지 않는다.

## CSV 계약

적재 순서는 `customers → products → orders → order_items → events`다. 필수 헤더는 예제 CSV에 있으며, 모르는 헤더·중복 헤더·열 수 불일치를 거절한다. CSV 레코드 번호는 헤더를 1번, 첫 데이터 레코드를 2번으로 센다. 따옴표 안의 줄바꿈은 같은 레코드다.

| 종류 | 필수 필드 | 선택 필드·제약 |
| --- | --- | --- |
| `customers` | `external_id,signup_at,status,email_consent` | `name,withdrawn_at,email,email_valid,hard_bounce,consent_changed_at` |
| `products` | `external_id,name,category` | 빈 이름·카테고리 금지 |
| `orders` | `external_id,customer_external_id,purchased_at,status,amount` | 상태는 `COMPLETED/CANCELLED/REFUNDED`, 부분 환불 거절 |
| `order_items` | `order_external_id,line_id,product_external_id,quantity,amount` | 수량은 양의 정수, 중복 키는 주문+line_id |
| `events` | `external_id,customer_external_id,event_type,event_at` | `order_external_id,properties`; PURCHASE는 주문 필수 |

- 파일 최대 20 MiB, 데이터 레코드 최대 200,000개. 초과 시 `413`이며 배치를 만들지 않는다. CSV 필드 하나는 Python CSV 파서의 기본 131,072자 제한을 사용한다.
- UTF-8·UTF-8 BOM만 지원한다. 잘못된 인코딩·문법은 오류 배치다. 오류 내역은 최대 100개까지 반환하고 전체 오류 수는 `error_count`로 제공한다. 원문 값·연락처를 오류 메시지나 감사 JSON에 넣지 않는다.
- 날짜는 timezone 필수이며 UTC로 정규화한다. 금액은 음수·NaN·무한대·소수점 2자리 초과를 거절한다. CSV에는 숫자 문자열, DB에는 `Numeric(18,2)`로 저장한다.
- `marketing_consent`는 `email_consent`의 호환 헤더다. 두 헤더를 동시에 보내면 거절한다. 이메일 동의는 EMAIL에만 적용하며 PUSH/SMS는 처음에 미동의로 만든다.
- `email_valid`는 업로드한 연락처 유효성 표시이며 실제 이메일 전달 가능성을 검사한 결과가 아니다. 기본값은 false다. 이메일이 없는데 true이면 거절한다.
- 고객 `status`는 허용된 값인지 검증하되 ACTIVE/CHURN_RISK/DORMANT는 가입·완료 주문으로 다시 계산한다. WITHDRAWN에는 `withdrawn_at`이 필수다. 원천 없이 구매 합계나 주문 수를 업로드할 수 없다.
- 이벤트 종류는 `VIEW/CART/PURCHASE/EMAIL_OPEN/CLICK/LANDING_VIEW/UNSUBSCRIBE`다. `properties`는 JSON 객체이며 `device_type`(mobile/desktop/tablet), `page`(query 없는 경로), `category`만 허용한다.
- PURCHASE의 주문은 같은 고객이어야 하고 발생 시각은 주문 구매 시각과 같아야 한다. 가입 이전의 주문·이벤트와 다른 데이터셋의 참조는 거절한다.
- 미래 주문·이벤트는 원천으로 보관할 수 있지만 기준 시점 이후 주문은 고객 캐시에서 제외한다. 발생 시각과 DB 적재 시각(`created_at`)은 별도다. 미래 가입·탈퇴 고객은 현재 배치 기준으로 거절한다.

### 중복·수정·기준 시점

기본 `mode=insert`에서 같은 외부 ID·같은 내용은 no-op이다. 변경 내용은 `mode=upsert`를 명시해야 하며, 이는 부분 수정이 아닌 행의 전체 내용 교체다. 생략한 선택값도 기본값으로 반영한다. 같은 파일 안의 동일 행은 중복으로 세고, 같은 키의 다른 내용은 오류다.

이벤트는 upsert에서도 수정하지 않는다. 주문의 고객·구매 시각은 기존 이벤트 연결을 유지하기 위해 수정하지 못하며 금액·상태는 수정할 수 있다. 구매 합계·주문 수·최근 구매는 **기준 시점 이하 COMPLETED 주문만** 사용한다. PURCHASE 이벤트 금액을 다시 더하지 않는다. 취소·전액 환불로 바꾸면 해당 고객 집계도 갱신한다.

첫 실제 적재에서 데이터셋의 `reference_at`을 고정한다. 이후 적재도 같은 기준 시점을 요구해 고객마다 다른 시점의 캐시가 섞이지 않게 한다. 다른 기준 시점을 실험하려면 새 데이터셋을 사용한다. 고객·주문을 바꾸면 영향받은 고객만 집계한다. 실제 변경이 없는 중복 업로드는 데이터 버전과 `DATA_IMPORTED` 이력을 늘리지 않는다. 데이터셋 이름 수정의 `version`과 원천 변경의 `dataset_versions`는 별개다.

## 실행 방법

프로젝트 루트에서 기존 `.env`와 PostgreSQL을 준비한 뒤 마이그레이션한다.

```powershell
docker compose up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

다른 터미널에서 worker를 실행한다.

```powershell
.\.venv\Scripts\python.exe -m app.workers.runner
```

### 미리보기 → 확정 → 결과 확인

```powershell
$base = "http://127.0.0.1:8000/api/v1"
$dataset = Invoke-RestMethod -Method Post -Uri "$base/datasets" `
  -ContentType "application/json" -Body '{"name":"CSV demo"}'
$reference = [uri]::EscapeDataString("2026-09-19T00:00:00Z")
$preview = Invoke-RestMethod -Method Post `
  -Uri "$base/data/import/customers/preview?dataset_id=$($dataset.id)&reference_at=$reference" `
  -ContentType "text/csv" -InFile "tests/fixtures/imports/customers.csv"
$preview.summary
$queued = Invoke-RestMethod -Method Post `
  -Uri "$base/data/import/$($preview.import_batch_id)/commit"
Invoke-RestMethod "$base/jobs/$($queued.job_id)"
Invoke-RestMethod "$base/data/import/$($preview.import_batch_id)"
```

배치 `status=COMPLETED`를 확인한 뒤 같은 데이터셋·기준 시점으로 products, orders, order_items, events를 순서대로 적재한다. 수정 적재는 preview URL에 `&mode=upsert`를 추가한다. 프런트에서는 `fetch`의 body에 File을 그대로 넣고 `Content-Type: text/csv`를 지정하면 된다. multipart 폼은 사용하지 않는다.

미리보기 오류는 HTTP 201의 `status=INVALID`, `summary.errors`로 반환한다. 잘못된 배치 확정·만료·기준 시점 충돌은 `409`, 없는 배치는 `404`, CSV가 아닌 Content-Type은 `415`, 잘못된 query는 `422`다.

확정 후 재검증에서 발견한 업무 충돌은 배치 `FAILED`와 오류 요약으로 남긴다. 이 경우 job은 검증 작업을 정상 마쳤으므로 `SUCCEEDED`지만 `result.status=FAILED`다. 반드시 **배치 상태 또는 job.result.status**로 적재 성공 여부를 확인한다. 예상하지 못한 DB·실행 오류는 기존 worker 재시도 규칙을 따른다. 재시도 소진 시 배치 조회에서도 FAILED로 표시한다. 수정한 CSV는 새로 미리보기한다.

### 합성 샘플 생성

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo --seed 42 `
  --reference-at "2026-09-19T00:00:00Z" --size small
.\.venv\Scripts\python.exe -m scripts.seed_demo --seed 42 `
  --reference-at "2026-09-19T00:00:00Z" --size demo
```

| 크기 | 고객 | 상품 | 주문 | 주문 항목 | 이벤트 |
| --- | ---: | ---: | ---: | ---: | ---: |
| small | 300 | 10 | 900 | 900 | 6,000 |
| demo | 10,000 | 300 | 30,000 | 30,000 | 200,000 |

휴면 VIP, 장바구니 이탈, 미동의, 탈퇴, hard bounce, 연락처 없음, 모바일 landing 이탈, 최근 구매, 미구매, 반복 구매 그룹을 이름으로 구분한다. 이메일은 합성 `example.invalid` 주소다. 이벤트에는 주문에 연결된 PURCHASE가 포함된다. 모바일 이탈 그룹에는 구매를 만들지 않는다. 이 데이터는 시연을 위한 합성 패턴이며 실제 원인 분석 결과가 아니다.

generator version·seed·기준 시점·크기·dataset key로 데이터셋 UUID를 결정한다. 같은 옵션으로 재실행하면 기존 데이터셋을 반환하고 방문자의 편집을 덮어쓰지 않는다. 새 복사본은 `--dataset-key fresh-1`처럼 다른 키로 생성한다. 생성 전체는 한 트랜잭션이고 동시 실행은 advisory lock으로 직렬화한다. 고객 캐시는 임의 숫자가 아니라 생성된 주문을 집계한다.

### 원천 대조와 보관 정리

```powershell
.\.venv\Scripts\python.exe -m scripts.recalculate_customers --dataset-id "출력된 UUID"
# 차이를 실제 반영하려는 경우에만 --apply 추가
.\.venv\Scripts\python.exe -m scripts.recalculate_customers --dataset-id "출력된 UUID" --apply
.\.venv\Scripts\python.exe -m scripts.cleanup_imports
```

기본 대조는 저장하지 않는다. `--apply`로 차이를 복구하면 데이터 버전과 SYSTEM 감사 이력을 남긴다. 정리 명령은 운영 시 주기적으로 실행해야 하며 자동 스케줄러는 아직 없다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
```

실제 PostgreSQL의 격리된 테스트 schema에서 정상 적재, 중복·동시 확정, 잘못된 파일, 다른 데이터셋 참조, refund 집계, 미래 주문 제외, 이벤트 수정 차단, 오래된 preview 재검증, 감사 실패 rollback과 재시도, 업로드 제한, 보관 정리, 샘플 재현성, 고객 캐시 대조·복구를 확인한다. 기존 migration·worker lease 복구 테스트도 함께 실행한다.

2026-09-19 로컬 검증에서 전체 테스트 47개를 통과했다. 별도의 격리 schema에서 demo 크기를 생성해 고객 10,000·상품 300·주문 30,000·주문 항목 30,000·이벤트 200,000건을 확인했고, 원천과 고객 캐시의 불일치는 0건이었다. 생성 시간은 약 66.84초로, 이 개발 환경에서의 1회 측정이며 성능 보장 수치는 아니다.
