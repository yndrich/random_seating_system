# backend/ — CLAUDE.md

FastAPI 백엔드. 순수 배정 알고리즘은 `app/assignment/`에 격리돼 있고, 그 계층의 상세
규칙은 `app/assignment/CLAUDE.md`에 따로 있다(거기서 작업할 때 읽을 것).

## Commands (port 8000)

루트 `.venv/`의 인터프리터를 직접 호출한다(activate 불필요). 경로는 셸 위치에 따라
`.venv`(루트) 또는 `../.venv`(backend 안)로 달라진다.

```bash
.venv/bin/python -m pip install -r backend/requirements.txt   # 의존성 설치 (루트에서)

cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000   # 개발 서버

../.venv/bin/python -m pytest -v                                          # 전체 테스트
../.venv/bin/python -m pytest tests/test_solver_hard_constraints.py -v    # 파일 하나
../.venv/bin/python -m pytest tests/test_scoring.py::test_breakdown_sums -v   # 테스트 하나
```

- pytest 설정 파일이 없다. `tests/conftest.py`가 `app` 패키지를 import 가능하게 하므로
  **반드시 `cd backend` 후 실행**한다.

## 3계층 단방향 의존

의존 방향은 **항상 위→아래**. 알고리즘 계층은 Pydantic·FastAPI를 전혀 모른다.

1. **`app/assignment/`** — 순수 배정 알고리즘. UI/IO/Pydantic 의존 없음, 단위테스트 격리
   대상. 상세는 `app/assignment/CLAUDE.md`.
2. **`app/core/session_store.py`** — 프로세스 **인메모리** 세션 스토어(영구 DB 없음, 재시작
   시 휘발). `SessionState`가 participants/config/rounds/`met_count`를 보유하고 세션별
   `threading.Lock`으로 동시 변경 보호. 전역 단일 인스턴스 `store`.
3. **`app/api/`** — FastAPI 라우터. Pydantic 모델(`app/models/schemas.py`)을 알고리즘
   dataclass로 변환해 호출한다(`_alg_weights`, `state.to_persons()`). CPU 바운드 솔버는
   `run_in_threadpool`로 실행해 이벤트 루프를 막지 않는다.

> 프론트의 `src/types.ts`는 이 `schemas.py`를 **수동 미러**한 타입이다. 스키마를 바꾸면
> 프론트도 직접 갱신해야 한다(자동생성 아님).

## 제약 모델 (하드 vs 소프트)

우선순위를 가중치 차이로 표현한다: 하드(company=1000, prev=800) ≫ 소프트(gender=3,
age=2, mbti=1). 완벽한 배정이 불가능하면 **최소 위반**으로 배치하고 `violations`/
`warnings`로 리포팅한다(요청을 실패시키지 않음). `app/api/rounds.py`의
`_HARD_TYPES = ("same_company", "prev_same_table")`로 하드 위반 수를 집계한다.
비용 계산 자체의 기계는 `app/assignment/CLAUDE.md` 참고.

## 세션 & 라운드 수명주기 (API 계층)

- 프론트가 앱 시작 시 `POST /api/session`으로 세션 생성. 이후 모든 데이터 요청에
  **`X-Session-Id` 헤더**가 필요하다(`api/deps.py`의 `require_session`이 검증 — 없으면
  400, 모르는 세션이면 404).
- **preview는 met_count를 변경하지 않는다.** `POST /rounds/commit`(확정) 시에만
  `add_round`로 동석 이력이 갱신되어 다음 회차 회피에 반영된다.
- `DELETE /rounds/{n}`(롤백)은 라운드를 재번호 매기고 남은 라운드들로 `met_count`를
  **재구성**(`rebuild_from_rounds`)한다 — 증분 차감이 아님.
