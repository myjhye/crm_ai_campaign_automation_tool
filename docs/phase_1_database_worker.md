# 단계 1 — PostgreSQL·마이그레이션·작업 기반

## 구현 범위

PostgreSQL은 Docker Compose로 실행하고 FastAPI와 worker는 기존 `.venv`로 실행한다. API·worker는 같은 Python 코드를 사용하지만 별도 프로세스다. 계정·로그인 기능은 추가하지 않았다.

현재 구현한 것은 DB 저장 구조와 작업 처리 기반이다. 고객 업로드, 주문 집계 캐시 갱신, 데이터 버전 증가, 캠페인 발송, 공개 화면은 후속 서비스에서 구현한다.

## 실행 순서

프로젝트 루트에서 `.env.example`을 `.env`로 복사한다. 기존 `.env`가 있으면 덮어쓰지 않는다. POSTGRES_PASSWORD를 정하고 DATABASE_URL에도 같은 비밀번호를 넣는다. 특수문자는 URL에서 percent encoding한다. 현재 작업 환경에는 생성된 로컬 비밀번호로 `.env`를 준비했으며 Git에서 제외되어 있다.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

worker는 다른 터미널에서 실행한다.

```powershell
.\.venv\Scripts\python.exe -m app.workers.runner
```

DB 컨테이너의 5432 포트는 로컬 127.0.0.1에만 공개한다. 포트 충돌 시 POSTGRES_PORT와 DATABASE_URL을 함께 바꾼다. PostgreSQL 18 이미지의 데이터 경로 `/var/lib/postgresql`을 named volume에 연결한다. `docker compose stop db`로 중지하고 `docker compose up -d db`로 다시 실행할 수 있다. 볼륨을 삭제하면 저장 데이터도 사라진다.

POSTGRES_PASSWORD는 최초 DB 초기화에 사용되므로 기존 볼륨이 있는 상태에서 환경변수만 바꿔도 DB 비밀번호가 바뀌지는 않는다. 비밀번호 변경은 별도 DB 변경 절차가 필요하다.

## 모델과 migration

| 버전 | 테이블 | 주요 제약 |
| --- | --- | --- |
| 001 | datasets, audit_logs | dataset FK, actor_type, 감사 event_key 중복 방지 |
| 002 | customers, customer_channels, products, orders, order_items, customer_events | dataset 내부 외부 ID unique, 채널 동의 기본 false, 금액·수량 범위, 복합 FK |
| 003 | jobs, import_batches, dataset_versions | 작업 멱등 키, 상태·진행률·시도 수 CHECK, 동일 dataset의 job 연결 |

각 리소스는 UUID를 사용한다. `Numeric(18,2)`에 금액, timezone 포함 컬럼에 시각, JSONB에 payload와 properties를 저장한다. DB 연결은 UTC 세션으로 설정된다. 고객 이벤트에는 `(customer_id,event_at)`, 주문에는 `(customer_id,purchased_at)` 인덱스가 있다.

dataset_id와 참조 ID의 복합 FK로 다른 dataset의 고객·상품·주문 연결을 거절한다. PURCHASE 이벤트는 같은 dataset·고객의 주문을 참조해야 한다. DB의 외부 ID 중복 기준은 dataset 안에서 적용한다.

004 이후 캠페인·실험·발송 테이블, A/B 비율 합계 검증과 발송 인덱스는 이번 범위가 아니다. 원본 주문에서 고객 구매 캐시를 갱신하는 서비스는 단계 3에서 추가한다.

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

현재 head는 `003`이다. migration 파일은 생성 시점의 고정 DDL이며 실행 시 최신 ORM 모델로 create_all하지 않는다. 앱 시작 시 자동 migration이나 downgrade도 실행하지 않는다.

## DB 세션과 API

`app/db/session.py`의 Database가 engine과 session factory를 만든다. 요청의 `get_session()`은 세션을 제공하고 실패 시 rollback, 종료 시 close한다. 정상 요청을 자동 commit하지 않는다. 업무 서비스가 트랜잭션을 소유한다. 앱 종료 시 engine을 dispose한다.

| API | 정상 | 실패 |
| --- | --- | --- |
| GET /api/v1/health | 200, 프로세스 응답 | DB를 사용하지 않음 |
| GET /api/v1/ready | SELECT 1 성공 시 200 | 미설정·연결 장애 시 503 / DATABASE_UNAVAILABLE |
| GET /api/v1/jobs/{id} | 상태·시도 수·진행률·결과 | 잘못된 UUID 422, 없는 작업 404 |

작업 조회는 payload와 lease_token을 응답에 포함하지 않는다. 오류에는 접속 비밀번호나 내부 예외를 내보내지 않는다. readiness는 DB 연결만 검사하며 migration 최신 상태를 보장하지 않는다.

## 작업 처리 과정

1. 업무 서비스의 트랜잭션 안에서 `enqueue(session, ...)`를 호출한다. 같은 트랜잭션이 실패하면 업무 변경과 작업 생성이 함께 rollback된다.
2. `(dataset_id,kind,idempotency_key)` unique와 payload hash를 사용한다. 동일 요청 재전송은 기존 job을 반환하고 다른 payload·재시도 설정은 409로 거절한다.
3. worker가 실행 가능한 PENDING 또는 lease가 만료된 RUNNING 작업을 `FOR UPDATE SKIP LOCKED`로 가져온다.
4. 시도 수를 증가시키고 실행별 lease_token을 새로 발급한다. 별도 heartbeat 연결이 lease를 연장한다.
5. handler는 DB 트랜잭션 안에서 실행된다. 업무 결과와 SUCCEEDED 전환을 같은 트랜잭션으로 commit한다.
6. 완료 직전에 token·상태·lease 만료를 검사한다. 이미 다른 worker가 회수했다면 이전 실행의 결과도 함께 rollback한다.
7. handler 실패는 제한된 backoff 후 재시도한다. 최대 시도에 도달하면 FAILED다. 마지막 시도 중 프로세스가 종료되어도 lease 만료 시 LEASE_EXHAUSTED로 정리한다.

기본 lease는 30초, heartbeat는 10초, idle polling은 1초다. worker를 종료하면 heartbeat가 중지되고 실행 중 트랜잭션은 rollback된다. 다른 worker가 만료 후 작업을 회수한다.

현재 진행률은 대기·실행 중 0, 완료 시 100이다. CSV 행별 처리 같은 중간 진행률은 해당 handler를 구현할 때 추가한다. `--once`는 실행 가능한 작업 최대 한 건을 시도하고 종료하며 업무 성공 여부는 job 상태로 확인한다.

handler는 직접 commit하거나 외부 메시지를 보내면 안 된다. 현재 보장은 PostgreSQL 안의 결과 저장에 대한 것이며 외부 API의 exactly-once 실행을 보장하지 않는다. 장시간 대량 업무는 이후 단계에서 chunk별 멱등 키와 저장 단위를 설계한다.

## 진단 작업

```powershell
.\.venv\Scripts\python.exe -m scripts.enqueue_worker_check --delay 5
.\.venv\Scripts\python.exe -m app.workers.runner --once
```

첫 명령은 진단 dataset과 `system.check` job을 생성하고 job_id만 출력한다. 두 번째 명령은 감사 기록을 한 건 남기고 작업을 완료한다. 같은 job의 감사 event_key는 unique다. 이 작업은 worker 점검용이며 고객 샘플 생성기가 아니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
```

DATABASE_URL의 DB 이름에 `_test`를 붙인 별도 DB를 사용한다. TEST_DATABASE_URL을 지정하면 해당 주소를 우선한다. 테스트 DB 이름이 `_test`로 끝나지 않으면 실행을 거절한다. `--create`에는 DB 생성 가능한 로컬 사용자가 필요하다. 이미 준비된 테스트 DB는 옵션 없이 사용한다.

각 테스트는 무작위 이름의 schema를 만들고 종료 시 해당 schema만 제거한다. 실제 서비스 schema를 truncate하거나 DB를 삭제하지 않는다. TEST_DATABASE_URL 없는 일반 pytest 실행은 PostgreSQL 테스트를 skip한다.

검증 항목: 빈 DB와 001→002→003 upgrade, ORM과 migration 일치, FK·unique·CHECK, UTC·금액 보존, 트랜잭션 rollback, 동시 enqueue·claim, stale worker 결과 rollback, 재시도 한도, readiness 장애, job 조회, heartbeat, 실제 worker 프로세스 강제 종료 후 복구와 결과 중복 방지.

2026-09-18 검증 결과: PostgreSQL 통합 테스트를 포함해 **27 passed**. 기존 테스트 도구의 deprecation 경고 2개는 남아 있다. 로컬 DB는 `003 (head)`이며 Alembic check에서 모델 차이가 없었다. 문서의 진단 명령으로 생성한 작업도 SUCCEEDED와 감사 기록 1건을 확인했다.

설계 참고: [SQLAlchemy 세션과 트랜잭션](https://docs.sqlalchemy.org/en/20/orm/session_basics.html), [Alembic migration](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [PostgreSQL 행 잠금](https://www.postgresql.org/docs/current/sql-select.html), [PostgreSQL Docker 이미지](https://hub.docker.com/_/postgres).
