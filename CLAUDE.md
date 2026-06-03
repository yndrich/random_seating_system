# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

랜덤 조 배정 시스템 — 참가자를 조별 테이블로 **랜덤 + 제약 최적화** 배정하는 웹 앱.
백엔드(FastAPI + 순수 Python 알고리즘)와 프론트엔드(React + Vite + TS)로 나뉜다.
전체 사용자 흐름·제약 정의·API 표는 `README.md` 참고.

## Commands

루트에 `.venv/`가 있고, 백엔드 명령은 그 인터프리터를 직접 호출한다(activate 불필요).
참고: 셸 작업 디렉터리가 `backend/`인지 루트인지에 따라 `.venv` 경로가 `../.venv` 또는 `.venv`로 달라진다.

### 백엔드 (port 8000)
```bash
.venv/bin/python -m pip install -r backend/requirements.txt   # 의존성 설치 (루트에서)

cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000   # 개발 서버

../.venv/bin/python -m pytest -v                       # 전체 테스트
../.venv/bin/python -m pytest tests/test_solver_hard_constraints.py -v   # 파일 하나
../.venv/bin/python -m pytest tests/test_scoring.py::test_breakdown_sums -v   # 테스트 하나
```
- pytest 설정 파일은 없다. `tests/conftest.py`가 `app` 패키지를 import 가능하게 한다 → **`cd backend` 후 실행**해야 한다.

### 프론트엔드 (port 5173)
```bash
cd frontend
npm install
npm run dev        # Vite dev 서버. /api 요청은 127.0.0.1:8000 으로 프록시됨
npm run build      # tsc --noEmit (타입체크) + vite build
```
- 별도 lint 도구는 없다. 타입 안전성은 `tsc`(strict, noUnusedLocals/Parameters)로 강제 → `npm run build`가 사실상 lint 역할.
- **백엔드(8000)가 떠 있지 않으면** Vite 프록시가 `/api/*` 요청에 500을 반환한다(`net::ERR_ABORTED`). 두 서버를 함께 띄울 것.

## Architecture

### 3계층 분리 (백엔드)
의존 방향은 **항상 위→아래**다. 알고리즘 계층은 Pydantic·FastAPI를 전혀 모른다.

1. **`app/assignment/`** — 순수 배정 알고리즘. UI/IO/Pydantic 의존 없음, 단위테스트 격리 대상.
   - `scoring.py` — `Person`/`Weights` **dataclass**(Pydantic 아님)와 비용함수. 핵심 불변식: **비용은 테이블 단위로 완전 분해 가능** (`total = Σ table_cost`). 이 덕분에 솔버가 증분 평가를 한다.
   - `solver.py` — 시뮬레이티드 어닐링 + 다중 재시작. 이웃 연산은 **두 테이블 간 1:1 스왑**만 사용(테이블 크기 보존 → 항상 유효). `seed` 지정 시 완전 재현 가능. `solve()`는 미리보기용, `evaluate_tables()`는 확정된 배치를 그대로 채점(commit용).
   - `balance.py` — 성비/연령/MBTI 분산 메트릭(소프트 제약).
   - `history.py` — `met_count`(누적 동석 횟수) 순수 헬퍼. `add_round`/`rebuild_from_rounds`.

2. **`app/core/session_store.py`** — 프로세스 **인메모리** 세션 스토어(영구 DB 없음, 재시작 시 휘발). `SessionState`가 participants/config/rounds/`met_count`를 보유하고 세션별 `threading.Lock`으로 동시 변경 보호. 전역 단일 인스턴스 `store`.

3. **`app/api/`** — FastAPI 라우터. Pydantic 모델(`app/models/schemas.py`)을 알고리즘 dataclass로 변환해 호출한다(`_alg_weights`, `state.to_persons()`). CPU 바운드 솔버는 `run_in_threadpool`로 실행해 이벤트 루프를 막지 않는다.

### 제약 모델 (하드 vs 소프트)
가중치 차이로 우선순위를 표현한다: 하드(company=1000, prev=800) ≫ 소프트(gender=3, age=2, mbti=1).
완벽한 배정이 불가능하면 **최소 위반**으로 배치하고 `violations`/`warnings`로 리포팅한다(절대 실패시키지 않음). `_HARD_TYPES = ("same_company", "prev_same_table")`로 하드 위반 수를 집계.

### 세션 & 라운드 수명주기
- 프론트가 앱 시작 시 `POST /api/session`으로 세션을 만들고 `session_id`를 `localStorage`(`seating.session_id`)에 보관. 이후 모든 요청에 **`X-Session-Id` 헤더** 동봉(`require_session` 의존성이 검증, 없으면 400 / 모르는 세션 404).
- **preview는 met_count를 변경하지 않는다.** `POST /rounds/commit`(확정) 시에만 `add_round`로 동석 이력이 갱신되어 다음 회차 회피에 반영된다.
- `DELETE /rounds/{n}`(롤백)은 라운드를 재번호 매기고 남은 라운드들로 `met_count`를 **재구성**(`rebuild_from_rounds`)한다 — 증분 차감이 아님.

### 프론트엔드
- 단일 페이지 SPA. `App.tsx`가 모든 상태(participants/config/rounds/preview)와 3개 탭(participants/assign/history)을 보유하는 단일 소스. 하위 `components/*`는 프레젠테이션 위주.
- 모든 백엔드 통신은 `src/api/client.ts`의 `api` 객체를 경유. 세션 생성/헤더 주입/404 시 1회 재생성·재시도를 캡슐화한다.
- `src/types.ts`는 백엔드 `schemas.py`와 **수동으로 맞춰진** 미러 타입(자동생성 아님) — 한쪽 스키마를 바꾸면 다른 쪽도 직접 갱신할 것.
