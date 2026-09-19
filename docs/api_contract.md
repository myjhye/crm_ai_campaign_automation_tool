# API 공통 계약 — 단계 0

업무 API 기본 경로는 `/api/v1`, JSON 필드명은 `snake_case`, 리소스 ID는 UUID 문자열이다. 공개 데모의 모든 방문자는 같은 기능을 사용한다. DB·업무 엔드포인트는 이후 단계에서 구현하며 이 문서의 목록·기간 예시는 공통 계약이다.

## 요청과 응답

- 요청·응답 본문은 JSON이다. 성공 응답은 각 기능 모델을 직접 반환한다.
- 목록 요청은 `page=1&page_size=20`을 기본값으로 사용한다. page는 1 이상, page_size는 1~100이다. 정렬은 업무 API마다 허용 목록을 정하고 동점은 UUID로 안정적으로 정렬한다.
- 목록 응답은 `{"items":[],"total":0,"page":1,"page_size":20}`이다. 페이지 범위를 벗어나면 items는 비어 있고 total은 전체 조건 결과 수를 유지한다.
- 금액은 KRW 단일 통화이며 JSON 문자열 `"300000.10"`으로 반환한다. 계산은 Decimal, 향후 DB는 Numeric을 사용한다. 공통 Money는 음수·NaN·무한대를 거절한다. 입력도 문자열을 권장하며 각 업무 모델이 자릿수 제한을 정한다.
- 비율은 0~100 단위 Decimal 문자열이다. 분모 0은 `{"value":null,"reason":"NO_DENOMINATOR"}`, 실제 0%는 `{"value":"0","reason":null}`로 구분한다. 표시 반올림은 화면에서 수행한다.

## 기간과 기준 시점

`from`, `to`, `reference_at`은 timezone을 포함하는 ISO 8601 값이다. 예: `2026-09-14T00:00:00+09:00`. timezone 없는 값은 거절한다. UTC로 정규화하고 향후 DB에도 UTC로 저장한다.

ReportingPeriod는 `[from,to)`이며 `from < to`여야 한다. JSON 직렬화 시 `model_dump(mode="json", by_alias=True)`를 사용한다. 한국 시간 9월 14일 하루 선택은 UTC `2026-09-13T15:00:00Z`부터 `2026-09-14T15:00:00Z` 미만이다. 날짜 선택 변환은 `inclusive_dates_to_utc`가 담당한다.

한 요청의 기준 시점은 주입한 Clock에서 한 번 얻어 모든 계산에 재사용한다. 테스트는 FixedClock을 사용한다. 이전 기간은 바로 앞의 동일 길이 구간이다.

## 공통 오류

| 상태 | code | 의미 |
| --- | --- | --- |
| 404 | NOT_FOUND | 경로 또는 리소스 없음 |
| 405 | METHOD_NOT_ALLOWED | 지원하지 않는 HTTP 메서드 |
| 409 | CONFLICT 또는 업무별 코드 | 상태·버전 충돌 |
| 422 | VALIDATION_ERROR | 입력 형식·범위 오류 |
| 500 | INTERNAL_ERROR | 예기치 않은 내부 오류 |

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력값을 확인해주세요.",
    "details": [{"loc": ["query", "page_size"], "type": "less_than_equal"}]
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

모든 응답에 서버가 생성한 `X-Request-ID`를 포함한다. 오류 본문 request_id는 이 헤더와 동일하다. 입력값·내부 예외 메시지를 응답에 복사하지 않는다. details는 위치와 검증 오류 종류만 제공한다. 업무에서 사용자에게 보여줄 메시지는 AppError로 명시한다.

단계 4부터 `/`는 HTML 화면이며 기존 API 정보 JSON은 `/api/v1/info`로 이동했다. `/docs`, `/redoc`, `/openapi.json`, `/api/v1/health`는 유지한다. 정적 CSS·JS는 `/static/styles`, `/static/src`에서 제공한다.

구현 파일: `app/schemas/common.py`, `app/core/errors.py`, `app/core/time.py`, `app/api/deps.py`.
오류 처리 구현은 [FastAPI 공식 오류 처리 문서](https://fastapi.tiangolo.com/tutorial/handling-errors/)를 따른다. Decimal·timezone 검증은 [Pydantic 표준 타입 문서](https://docs.pydantic.dev/latest/api/standard_library_types/)를 참고했다.

## 단계 5 고객·대시보드 요청

단계 5의 고객·대시보드 API는 `dataset_id`, timezone 포함 `from`, `to`를 필수 query로 받는다. 고객 검색·정렬·기간 활동 필터와 데이터 버전 일관성 계약은 [단계 5 실행 안내](phase_5_customer_analytics.md)를 따른다. 고객 응답의 금액은 문자열, 지표 비율은 숫자 또는 null이며 CRM 기여 매출·발송 이력·소속 세그먼트의 미구현 상태를 별도로 구분한다.

## 단계 3 CSV 요청

CSV 미리보기는 JSON 대신 `Content-Type: text/csv`의 원본 body를 받는다. `dataset_id`, timezone이 있는 `reference_at`, `mode=insert|upsert`는 query다. 이후 응답·확정·조회는 JSON 계약을 유지한다. 배치 식별자는 `import_batch_id`, 작업 식별자는 `job_id`다.

`POST /api/v1/data/import/{kind}/preview` → `POST /api/v1/data/import/{import_batch_id}/commit` → `GET /api/v1/data/import/{import_batch_id}`로 진행한다. 확정 응답은 202이며 최종 성공 여부는 배치 status로 확인한다. 종류별 CSV 필드와 전체 요청 예시는 [단계 3 실행 안내](phase_3_data_import.md)에 정의했다.
# 공개 데이터셋 선택 보완

`GET /api/v1/datasets`는 `purpose=ANALYSIS`만 반환하며 전체 고객 원천이 존재하는 데이터셋을 우선 정렬한 뒤 페이지네이션한다. SYSTEM의 상세·수정은 404다. 데이터셋 응답의 `customer_count`, `order_count`, `event_count`는 기간과 무관한 전체 원천 건수이며 모두 0일 수 있다. 상세 규칙은 [공개 데모 데이터셋 선택](dataset_entry_experience.md)을 따른다.
