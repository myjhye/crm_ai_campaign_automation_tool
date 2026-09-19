# GrowthPilot 프런트엔드

HTML·CSS·JavaScript의 브라우저 ES modules를 사용한다. 별도 빌드 서버 없이 FastAPI가 `/`에서 화면을 제공한다. 프로젝트 루트의 실행 명령과 DB 설정은 루트 README를 따른다.

| 경로 | 책임 |
| --- | --- |
| `src/app/` | hash 라우터·URL 상태·요청 취소·공통 화면 |
| `src/api/` | fetch·응답 검증·JSDoc·공통 오류 |
| `src/components/` | 여러 기능에서 사용하는 표시 요소 |
| `src/features/` | Overview·데이터셋 관리 |
| `e2e/` | 사용자 업무 흐름 테스트 |

현재 데이터셋 선택·목록·생성·이름 수정이 실제 API에 연결되어 있다. 고객 KPI·업로드 화면·캠페인·AI 대화는 준비 상태로 표시한다. 로그인은 없다.

Node는 테스트에만 필요하다. frontend 디렉터리에서 `npm ci`, `npm test`, `npx playwright install chromium`, `npm run test:e2e`를 실행한다. E2E는 루트 `.venv`로 FastAPI를 자동 실행하고 업무 API 응답을 대체하므로 실제 DB를 변경하지 않는다.

상세 설명: [단계 4 실행 안내](../docs/phase_4_frontend.md).
