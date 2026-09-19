# 단계 2 — 공개 데이터셋 API와 변경 이력

단계 2의 백엔드 기반을 구현했다. 로그인 없이 데이터셋 생성·목록·상세·이름 변경과 감사 이력 조회를 제공한다. 샘플 고객 적재는 단계 3, 첫 화면과 URL 복원은 단계 4, 캠페인 승인·실행 이력 연결은 단계 7~9에서 구현한다.

## 실행

기존 실행 환경에서 새 migration을 적용한다.

```powershell
docker compose up -d --wait db
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

현재 migration head는 `003a`다. 기존 001~003을 수정하지 않고 `003a_demo_metadata.py`를 추가했다. 기존 데이터셋의 version은 1로, updated_at은 기존 created_at으로 초기화한다. 과거 감사 기록의 버전 필드는 null로 유지한다. 004 이후의 세그먼트·캠페인 모델은 이번 작업에 포함하지 않는다.

## 데이터셋 API

| 메서드·경로 | 입력 | 결과 |
| --- | --- | --- |
| POST /api/v1/datasets | name | 201, 새 빈 DEMO 데이터셋 |
| GET /api/v1/datasets | page, page_size | 페이지 목록·전체 건수 |
| GET /api/v1/datasets/{id} | UUID | 이름·source·version·생성/수정 시각 |
| PUT /api/v1/datasets/{id} | name, version | 이름 변경과 새 version |

생성 예시:

```json
{"name": "휴면 VIP 실험"}
```

수정 예시:

```json
{"name": "휴면 VIP 재활성화 실험", "version": 1}
```

name은 앞뒤 공백을 제거하고 1~200자로 제한한다. version은 1 이상의 정수이며 문자열·boolean을 허용하지 않는다. source와 actor_type은 클라이언트가 지정할 수 없다. 공개 생성 API는 DEMO를 사용하고 업로드·시뮬레이션 source 지정은 후속 내부 서비스가 담당한다.

생성은 매번 새 데이터셋을 만든다. 동일 이름은 허용하며 고객·주문을 자동 생성하거나 기존 데이터셋을 복제하지 않는다. 고객 샘플 재적재 기능으로 오해하지 않도록 빈 데이터셋 생성이라고 구분한다.

목록은 created_at 내림차순, 동점이면 UUID 내림차순이다. 기본 20건·최대 100건이며 결과가 없는 페이지도 total을 유지한다. 잘못된 UUID·입력은 422, 없는 데이터셋은 404다.

## 변경 충돌과 트랜잭션

`services/datasets.py`가 트랜잭션을 소유하고 repository는 조회만 수행한다.

1. 수정 대상 데이터셋을 `SELECT ... FOR UPDATE`로 잠근다.
2. 클라이언트의 version과 DB version을 비교한다.
3. 다르면 409 / VERSION_CONFLICT를 반환한다. 최신 상세를 다시 조회한 후 새 version으로 수정해야 한다.
4. 같고 이름이 변경되면 version을 1 증가시키고 updated_at을 DB 시각으로 갱신한다.
5. 같은 트랜잭션에서 감사 기록을 작성한다.
6. 모두 성공하면 commit한다. 감사 저장 실패도 데이터셋 변경과 함께 rollback한다.

같은 이름·최신 version을 다시 보내면 변경 없는 성공이다. version·updated_at을 변경하거나 감사 기록을 추가하지 않는다. 같은 이름이어도 오래된 version이면 충돌이다.

여기서 Dataset.version은 **이름 등 데이터셋 메타데이터의 수정 버전**이다. 단계 1의 dataset_versions는 후속 데이터 적재 버전 기록이며 이번 이름 변경에서 증가시키지 않는다.

## 감사 API와 저장 정보

`GET /api/v1/audit-logs`는 누구나 조회할 수 있다. 필터는 dataset_id, resource_id, actor_type, action이며 page·page_size를 지원한다. 지정한 필터는 AND로 결합한다. 없는 데이터셋 ID로 필터링하면 빈 목록이다.

```text
/api/v1/audit-logs?dataset_id=<UUID>&action=DATASET_UPDATED&page=1&page_size=20
```

응답 필드는 id, dataset_id, resource_id, actor_type, action, request_id, previous_version, new_version, created_at이다. 정렬은 created_at·id 내림차순이다.

| 작업 | action | 이전 버전 | 새 버전 |
| --- | --- | --- | --- |
| 생성 | DATASET_CREATED | null | 1 |
| 이름 변경 | DATASET_UPDATED | 현재 값 | 현재 값 + 1 |
| 충돌·검증 실패·변경 없음 | 기록 추가 없음 | — | — |

HTTP 변경의 actor_type은 서버가 VISITOR로 기록하고, request_id는 오류·성공 응답의 X-Request-ID와 동일하다. SYSTEM worker의 기존 이력도 조회할 수 있으며 AI 액션 연결은 후속 단계다. actor_type은 개인 신원이나 계정을 뜻하지 않는다.

`services/audit.py`는 임의 요청 본문을 받지 않는다. 이름에 연락처가 들어갈 수 있어 변경 전후 이름 원문도 감사 기록에 복사하지 않는다. 어떤 작업이 어느 리소스의 몇 번째 버전을 만들었는지를 보존한다. 과거 JSONB details에 민감값이 있더라도 공개 응답에 details 자체를 포함하지 않는다. 공개 감사 생성·수정·삭제 API는 제공하지 않는다.

## 코드 구성

| 파일 | 역할 |
| --- | --- |
| app/models/datasets.py | 데이터셋 수정 버전·시각, 감사 이전/이후 버전 |
| alembic/versions/003a_demo_metadata.py | 기존 데이터 보존 migration |
| app/schemas/datasets.py | 이름·버전 검증과 응답 |
| app/schemas/audit.py | 감사 필터와 공개 응답 필드 |
| app/repositories/datasets.py | 잠금 조회·목록 |
| app/repositories/audit.py | 필터 집계·목록 |
| app/services/datasets.py | 생성·수정·충돌과 트랜잭션 |
| app/services/audit.py | 공통 감사 메타데이터 저장 |
| app/api/routes/datasets.py, audit.py | 공개 HTTP API |
| tests/integration/conftest.py | 테스트별 격리 PostgreSQL schema |
| tests/integration/test_demo.py | API·충돌·rollback·이력·migration 검증 |

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
.\.venv\Scripts\python.exe -m alembic check
```

테스트는 로그인 없는 CRUD 중 생성·조회·수정 흐름, 페이지 경계, 잘못된 입력, 같은 버전의 동시 수정, 감사 실패 시 생성·수정 rollback, 변경 없는 재요청, 이력 필터, 원문 비노출, 기존 데이터의 migration 보존을 확인한다. 데이터셋 삭제와 고객·캠페인 업무 기능은 이번 검증 범위가 아니다.

2026-09-19 검증 결과: 실제 PostgreSQL을 포함한 전체 테스트 **32 passed**. 기존 Starlette 테스트 도구의 deprecation 경고 2개는 남아 있다. 로컬 DB는 `003a (head)`이며 Alembic check에서 추가 변경이 감지되지 않았다.
