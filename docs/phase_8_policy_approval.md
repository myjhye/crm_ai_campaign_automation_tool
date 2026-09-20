# 단계 8 — 정책 검수와 버전 기반 승인

## 구현 범위

저장된 캠페인의 대상 고객을 검수 시점 기준으로 다시 계산하고, 채널 동의·연락처 상태·명시적 제외·동일 캠페인 기수신·일일/최근 7일 피로도를 순서대로 검사한다. 결과는 고객별 스냅샷으로 보관하며 검수를 통과한 캠페인만 `DRAFT → REVIEW → APPROVED`로 전환할 수 있다.

Campaigns 오른쪽에는 최초 대상·제외·승인 대상과 사유별 인원을 표시한다. Settings에서는 하루/7일 한도와 채널별 금지·필수 문구를 편집한다. 정책을 저장하면 version이 증가하므로 이전 검수로 승인 요청할 수 없다.

검수 패널은 `validation_runs.rules`의 `primary_count`를 사용해 탈퇴, 채널 미동의, 연락처 없음·오류·하드 바운스, 제외 세그먼트, 기수신, 일일 한도, 최근 7일 피로도를 모두 표시한다. 0명인 규칙도 숨기지 않는다. `affected_count`는 여러 사유에 동시에 해당하는 전체 건수이고 `primary_count`는 최초 사유 기준의 상호 배타적 집계이므로, 화면의 사유별 합계에는 `primary_count`를 사용한다.

캠페인 전체 차단 사유는 결과 상단의 경고로 표시한다. 검수 만료 시각은 한국 시간의 절대 시각으로 안내한다. 승인 요청은 검수 통과, 유효시간 미경과, 차단 사유 없음, 승인 대상 1명 이상, 캠페인 version 일치를 모두 만족할 때만 활성화하며 비활성 상태에는 이유를 함께 표시한다.

## 저장 구조

`006_policies_approvals.py`가 다음 테이블을 추가한다.

| 테이블 | 역할 |
| --- | --- |
| `policy_settings` | 데이터셋별 노출 한도와 채널별 문구 정책, version |
| `validation_runs` | 캠페인·정책·데이터·세그먼트 버전, 내용 hash, 집계, 30분 만료 |
| `validation_recipients` | 검수 당시 후보 고객, 모든 제외 사유, 우선 사유, 적격 여부 |
| `approvals` | 승인 요청과 승인·반려·철회 결과, 방문자 결정 시각 |
| `campaign_deliveries` | 중복·피로도 조회용 발송 이력 원장 |

`campaign_deliveries`는 정책 조회에 필요한 최소 원장을 단계 9보다 먼저 만든 것이다. 단계 9에서 run, A/B 배정, 결과 상세를 연결하고 실제 모의 발송 결과를 기록한다.

## 검수 계산

1. 캠페인에 고정된 `segment_revision_id`의 조건을 검수 기준 시점으로 컴파일한다.
2. 제외 세그먼트 revision의 고객 집합을 계산한다.
3. 대상 고객마다 탈퇴, 동의, 연락처, 명시적 제외, 같은 캠페인 기수신, 노출 한도를 순서대로 검사한다.
4. 고객이 여러 규칙에 걸리면 `reasons`에 모두 저장하고 첫 사유만 `primary_reason`으로 집계한다.
5. `최초 대상 = 우선 사유별 제외 합계 + 승인 대상`을 DB CHECK와 테스트로 보장한다.
6. 쿠폰 만료, 금지 표현, 필수 문구 누락, A/B 비율 오류, 최종 대상 0명은 캠페인 전체 차단 사유다.

하루 한도는 `Asia/Seoul`의 당일 자정부터 검수 시각까지이며 7일 한도는 검수 시각 직전 7일의 이동 구간이다. 검수는 기록을 만들지만 캠페인의 내용이나 상태는 바꾸지 않는다.

## 승인 상태와 충돌 방지

- `POST /campaigns/{id}/validate`: 검수 기록과 대상 스냅샷 생성
- `POST /campaigns/{id}/request-approval`: 유효한 통과 결과를 확인하고 REVIEW 전환
- `POST /campaigns/{id}/approve`: 방문자가 APPROVED로 결정
- `POST /campaigns/{id}/reject`: 방문자가 DRAFT로 반려
- `POST /campaigns/{id}/resume-editing`: REVIEW 요청을 철회하거나 APPROVED를 DRAFT로 되돌림
- `GET /campaigns/{id}/review`: 최신 캠페인·검수·승인 상태 조회
- `GET/PUT /policy-settings`: 정책 조회·버전 기반 수정

승인 요청과 결정은 캠페인 행을 잠그고 version을 검사한다. 검수 후 30분이 지났거나 캠페인 내용 hash, 정책 version, 원천 데이터 version이 달라지면 409를 반환한다. PENDING 승인 요청은 캠페인당 하나만 허용하는 PostgreSQL partial unique index도 둔다. 상태 변경과 감사 기록은 같은 트랜잭션에서 처리한다.

APPROVED 상태에서는 일반 캠페인 수정 API가 거절된다. 방문자가 먼저 **편집 재개**를 눌러 DRAFT와 새 version을 받은 뒤 수정하고 다시 검수해야 한다.

캠페인 목록의 삭제도 DRAFT에서만 허용한다. 삭제는 `archived_at`을 기록하는 보관 처리이며 목록·상세 API에서는 더 이상 노출하지 않는다. 승인 또는 검수 이력을 물리적으로 연쇄 삭제하지 않는다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.run_db_tests --create
npm --prefix frontend test
npm --prefix frontend run test:e2e
```

단위 테스트는 제외 사유 우선순위와 전체 사유 보존을 검사한다. PostgreSQL 통합 테스트는 검수 인원 등식, 승인·중복 결정 충돌, 승인 후 편집 재개, 정책 변경에 따른 검수 만료, 쿠폰 만료 차단을 확인한다. 기존 마이그레이션의 빈 DB/증분 설치와 Alembic metadata 일치도 함께 검사한다.

데모 generator v2의 소형 샘플은 고객 300명으로 확장했다. 이메일·푸시·SMS마다 정상 수신 가능, 미동의, 연락처 없음, 연락처 무효, hard bounce, 탈퇴 고객이 반복 가능하게 배치된다. 따라서 특정 규칙만 100% 걸리는 오래된 샘플 대신 승인 대상과 여러 제외 사유를 한 검수 결과에서 함께 확인할 수 있다.
