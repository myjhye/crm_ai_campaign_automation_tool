# 프런트엔드 구성 예정

현재는 상세 구현 계획 1~3절의 디렉터리만 구성했다.
React·TypeScript·Vite 설치, package.json, 실행 명령은 단계 4에서 추가한다.

| 경로 | 책임 |
| --- | --- |
| `src/app/` | Router, QueryClient, 공통 레이아웃 |
| `src/api/` | API client와 OpenAPI 기반 타입 |
| `src/components/` | 여러 기능에서 사용하는 표시 요소 |
| `src/features/` | auth, customers, segments, campaigns, reports, ai 기능 |
| `e2e/` | 사용자 업무 흐름 테스트 |

업무 규칙과 승인 권한은 백엔드에서 검증하며, 화면과 AI 패널은 같은 업무 API를 사용한다.
