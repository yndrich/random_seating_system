# frontend/ — CLAUDE.md

React + Vite + TypeScript 단일 페이지 앱.

## Commands (port 5173)

```bash
cd frontend
npm install
npm run dev        # Vite dev 서버. /api 요청은 127.0.0.1:8000 으로 프록시됨
npm run build      # tsc --noEmit (타입체크) + vite build
```

- **별도 lint 도구가 없다.** 타입 안전성은 `tsc`(strict, noUnusedLocals/noUnusedParameters,
  `tsconfig.json` 참고)로 강제 → `npm run build`가 사실상 lint 역할이다.
- **백엔드(8000)가 떠 있지 않으면** Vite 프록시가 `/api/*`에 500을 반환한다
  (`net::ERR_ABORTED`). dev 시 두 서버를 함께 띄울 것(프록시 설정은 `vite.config.ts`).

## 구조

- **`src/App.tsx`** — 단일 페이지 SPA의 **단일 상태 소스**. 모든 상태
  (participants/config/rounds/preview)와 3개 탭(participants/assign/history)을 보유한다.
  하위 `src/components/*`는 프레젠테이션 위주(상태를 들고 있지 않음).
- **`src/api/client.ts`** — 모든 백엔드 통신의 단일 경유지. `api` 객체가 세션 생성,
  `X-Session-Id` 헤더 주입, 404 시 1회 세션 재생성·재시도를 캡슐화한다. 세션 id는
  `localStorage` 키 `seating.session_id`에 보관.
- **`src/types.ts`** — 백엔드 `backend/app/models/schemas.py`를 **수동으로 맞춘** 미러
  타입(자동생성 아님). 한쪽 스키마를 바꾸면 **다른 쪽도 직접 갱신**해야 한다.
