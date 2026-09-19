# 단계 6 — 조건 기반 세그먼트

Segments에서 조건을 구성하고 대상 고객 수·특성을 확인한 뒤 이름을 붙여 저장한다. 수정은 새 revision을 만들며 보관해도 과거 revision은 삭제하지 않는다. AI-A는 다음 구현이며 현재는 수동 조건 빌더와 추천 유형 6개를 제공한다.

추천 유형은 휴면 VIP, 첫 구매 유도(주문 0건), 재구매 유도(주문 1건·구매 후 7~29일), 이탈 위험, 충성 고객(주문 3건 이상·최근 30일 내 구매·누적 30만 원 이상), 이메일 반응 고객(최근 30일 오픈 2회 이상)이다. 모두 이메일 동의를 조건에 포함한다. 휴면 VIP를 제외한 유형은 상태 조건으로 탈퇴를 제외하며 휴면 VIP의 기존 3개 조건은 유지한다. 모든 유형에 별도 발송 적격 검수가 필요하다. 추천값은 편집 가능한 데모 기본안으로 성과를 보장하지 않는다.

추천 유형은 설명이 붙은 세로 버튼 목록이다. 버튼을 누르면 현재 조건과 세그먼트 이름이 함께 채워지고 선택한 버튼이 강조된다. 입력한 이름·조건은 직접 수정할 수 있다. 미리보기 결과는 무효화되어 저장 전 다시 조회해야 한다. 해당 조건에 맞는 고객이 없으면 0명으로 표시하며, 템플릿을 위해 데이터를 임의로 만들지 않는다.

## 구현 파일

| 위치 | 책임 |
| --- | --- |
| `app/domain/segments/fields.py` | 공개 필드·타입·연산자와 SQL 표현식 |
| `dsl.py`, `compiler.py`, `human_readable.py` | 조건 검증, 바인딩 SQL, 검증된 조건의 설명 |
| `app/models/segments.py`, `alembic/versions/004_segments.py` | dataset 범위의 세그먼트와 불변 revision |
| `app/repositories/segments.py` | 원천 고객 집합·프로파일·목록 조회 |
| `app/services/segments.py` | 데이터 버전 검사·트랜잭션·감사·저장·보관 |
| `app/schemas/segments.py`, `app/api/routes/segments.py` | 공개 요청 계약과 HTTP 진입점 |
| `frontend/src/features/segments/` | 중첩 조건 빌더, 템플릿, 미리보기, 저장·수정·보관 |

## 조건과 계산 기준

허용 필드는 `days_since_last_purchase`, `total_purchase_amount`, `order_count`, `status`, `email_consent`, `email_opens_30d`, `preferred_category`다. `marketing_consent`는 이메일 동의로 정규화한다. 연락처·개인정보·임의 SQL 필드는 받지 않는다.

AND/OR 그룹 깊이는 루트 포함 3, 전체 leaf 조건은 20개, IN 목록은 100개까지다. BETWEEN은 오름차순 값 두 개, IS_NULL/IS_NOT_NULL은 value를 생략한다. 정수에 boolean·문자열을 받지 않고 금액은 소수점 두 자리 이내 문자열만 받는다. 정규화한 조건으로 설명과 SHA-256 hash를 생성한다.

고객·주문 집계는 단계 5와 같은 `reference_at` 배타적 상한을 사용한다. 가입·완료 주문은 기준 시점 이전 원천만 집계한다. 구매 경과일은 마지막 완료 주문부터의 만 24시간 수이며 미구매는 null이다. 따라서 `GTE 60`에 미구매 고객이 포함되지 않는다. 일반 비교의 null은 SQL의 미지정 값 규칙을 따르며 포함하려면 IS_NULL을 OR로 명시한다.

이메일 동의는 현재 저장 상태다. 과거 동의를 복원한다고 주장하지 않는다. 최근 오픈은 `[reference_at-30일, reference_at)`의 EMAIL_OPEN 원천 이벤트 수다. 선호 카테고리는 기준 이전 완료 주문 항목 금액 합계가 가장 큰 카테고리이며 동률은 카테고리 이름 순서다. 이벤트·카테고리는 고객별 서브쿼리를 사용해 고객이 중복 집계되지 않는다.

프로파일은 평균 누적 구매액, 선호 카테고리 상위 5개, 최근 이메일 오픈 고객 수·비중이다. 오픈 고객 비중은 전달 성공 대비 오픈율과 다르다. 전달·캠페인 이력이 없는 캠페인 반응률은 `not_ready`, 나이대는 `not_available`로 반환한다. AI 전달용 `ai_profile`은 기본 5명 미만 집단의 프로파일과 5명 미만 카테고리를 생략하며 실제 AI 호출은 아직 없다.

미리보기 화면은 대상 수·전체 대비 비중을 상단에, 평균 구매액·이메일 반응을 별도 요약 칸에 표시한다. 금액에는 천 단위 쉼표와 원 단위를 붙이고 기본 카테고리는 한국어로 표시하되 알 수 없는 카테고리는 원래 이름을 유지한다. “적용된 조건”은 항상 표시한다. AND는 `·`로 구분하며 바깥 괄호를 생략하되 중첩 AND/OR는 괄호로 의미를 보존한다. 금액·일수·주문 수의 단위와 동의 문구는 서버 설명기에서 생성한다. 오픈 고객 0명은 기록이 없다는 설명을 붙이고 휴면이 원인이라고 추정하지 않는다. 기준 시점은 한국어 날짜와 자정 또는 실제 선택 시간을 표시한다.

## API

모든 경로 앞에 `/api/v1`을 붙인다.

| 요청 | 동작 |
| --- | --- |
| `GET /segments/fields` | 조건 빌더용 필드 계약 |
| `POST /segments/preview` | count·total·percentage·profile·description·warnings·condition_hash·reference_at·data_version |
| `GET /segments?dataset_id=UUID&page=1` | 보관되지 않은 목록, 기본 20·최대 100건 |
| `POST /segments` | 서버 재검증 후 생성, 201 |
| `GET /segments/{id}?dataset_id=UUID` | 현재 조건과 revision ID, 보관 후에도 조회 가능 |
| `PUT /segments/{id}` | version 검사 후 새 revision 저장 |
| `DELETE /segments/{id}` | JSON body의 dataset_id·version 확인 후 보관 |

```json
{
  "dataset_id": "선택한 데이터셋 UUID",
  "reference_at": "2026-09-19T00:00:00Z",
  "condition": {
    "operator": "AND",
    "conditions": [
      {"field": "days_since_last_purchase", "comparison": "GTE", "value": 60},
      {"field": "total_purchase_amount", "comparison": "GTE", "value": "300000"},
      {"field": "email_consent", "comparison": "EQ", "value": true}
    ]
  }
}
```

저장은 위 요청에 name, 수정은 version을 추가한다. 미리보기의 data_version을 보내면 원천 변경 시 409로 다시 확인하도록 한다. 화면은 조건·기준 시점을 바꾸면 미리보기를 무효화하며 저장 전 미리보기를 요구한다. API도 저장마다 검증·조회하며 화면의 count를 신뢰하지 않는다. 0명은 경고와 함께 저장 가능, 전체 80% 초과도 경고다. 세그먼트는 발송 적격 검수를 대신하지 않는다.

데이터셋 행 잠금은 원천 변경·세그먼트 수정과 같은 순서로 획득한다. 저장·revision·감사는 한 트랜잭션이며 감사 실패 시 모두 rollback된다. 동시 수정은 하나만 성공한다. `archived_at`과 메타 version을 변경하는 보관 동작은 조건 revision을 추가하지 않는다. 기존 revision에는 생성 당시 이름·조건·데이터 버전·기준 시점이 남는다.

## 실행과 검증

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

브라우저의 Segments 메뉴에서 **템플릿 → 대상 미리보기 → 이름 입력 → 저장**을 수행한다. worker는 이 조회·저장에 필요하지 않다. 상세 URL을 새로고침하면 저장한 조건과 기준 시점이 복원된다. 충돌은 최신 내용 불러오기로 복구한다.

기준 시점은 달력·시간 선택 입력으로 제공한다. 화면은 한국 시간(Asia/Seoul)이며 브라우저의 OS 시간대와 무관하게 UTC로 변환해 요청한다. **현재 시각**, **선택 기간 종료** 바로가기를 제공하고 후자는 종료일 다음 날 한국 시간 00:00을 뜻한다. 날짜·시간을 변경하면 기존 미리보기를 무효화한다. 저장한 시각도 한국 시간으로 복원한다.

데스크톱은 왼쪽 편집기·오른쪽 저장 목록으로 구성하고 좁은 화면에서는 위아래로 배치한다. 목록 카드는 이름·조건·기준 시점과 불러오기·삭제 버튼을 제공한다. 삭제는 기존 보관 API를 사용하므로 revision은 유지된다. 저장·삭제 성공은 화면 상단 알림으로 표시한다. **초기화**는 저장 리소스 선택과 입력 이름·미리보기를 해제하고 기본 조건(주문 수 0건 이상), 상단 기간 종료 시점으로 되돌린다. 저장된 세그먼트 자체는 초기화로 변경되지 않는다.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
```

PostgreSQL에서 금액·60일 경계, null·AND/OR, 중복·미래 이벤트, 빈 결과, 데이터 버전·동시 수정 충돌, 보관 후 revision 보존, 감사 실패 rollback을 검증한다. 브라우저 테스트는 mock API를 사용하며 조건 수정 후 재미리보기·저장·새로고침·409 복구·보관을 확인한다. 실제 DB의 API 테스트와 브라우저 UI 테스트는 별도다.
