---
name: review-diff
description: >-
  랜덤 조 배정 시스템의 현재 변경(diff)을 이 프로젝트의 교차 관심사·불변식 체크리스트로
  리뷰한다. 일반 버그뿐 아니라 이 코드베이스 특유의 함정 — 3계층 단방향 의존(assignment가
  Pydantic/FastAPI를 import하면 안 됨), 타입 미러 drift(schemas.py ↔ types.ts), 비용의
  테이블 단위 분해 불변식, 하드/소프트 제약 가중치 우선순위, 세션·라운드 수명주기(preview는
  met_count 불변·commit만 갱신·rollback은 재구성), 인메모리 세션 가정 — 을 집중 점검하고
  검증 명령으로 발견을 확인한다. 사용자가 "코드 리뷰", "리뷰해줘", "이 변경/diff 봐줘",
  "PR 리뷰", "커밋 전에 점검", "내 변경 문제 없나", "merge 전에 봐줘" 같은 요청을 하면 —
  명시적으로 이 skill을 부르지 않더라도 — 이 skill을 사용할 것. 단순히 서버를 띄우거나
  (dev-up), 솔버 성능만 재거나(solver-eval), 타입 미러만 맞추는(sync-types) 경우는 제외.
---

# 변경 코드 리뷰 (review-diff)

이 프로젝트는 **수동으로 맞춰야 하는 미러/불변식**이 여러 군데 있어, 한 곳만 바꾸면
컴파일은 통과해도 조용히 어긋난다. 이 skill은 변경(diff)을 그 불변식들에 비춰 리뷰하는
플레이북이다. 큰 그림은 루트 `CLAUDE.md`, 계층 규칙은 `backend/CLAUDE.md`·
`backend/app/assignment/CLAUDE.md`·`frontend/CLAUDE.md` 참고.

## 0. 무엇을 리뷰하나 — diff부터 잡는다

리뷰 대상은 "변경된 코드"다. 전체 파일이 아니라 **diff를 먼저 확보**한다:

```bash
git status --short                 # 무엇이 바뀌었나 개요
git diff --stat HEAD               # 변경 규모
git diff HEAD                      # 작업트리 전체 변경 (스테이징+미스테이징)
# 브랜치 리뷰라면 main 대비:
git merge-base HEAD origin/main && git diff origin/main...HEAD
```

변경된 파일 목록을 보고 **어느 계층이 영향받았는지** 먼저 분류한다(아래 계층 지도 참고).
변경과 무관한 코드는 리뷰하지 않는다 — 발견은 반드시 `file:line`으로 짚는다.

## 1. 계층 지도 (어디를 건드렸나로 점검 항목이 갈린다)

| 변경 위치 | 따라오는 위험 / 점검 |
|---|---|
| `backend/app/assignment/*` | 비용 분해 불변식, 순수성(Pydantic/FastAPI import 금지), 솔버 정확성 → §2.3, §2.4 |
| `backend/app/models/schemas.py` | 프론트 `types.ts` 미러 drift → §2.1 (**sync-types**) |
| `frontend/src/types.ts` | 백엔드 `schemas.py`와 어긋남 → §2.1 (**sync-types**) |
| `backend/app/api/*` | 세션/라운드 수명주기, `run_in_threadpool`, 변환 계층 → §2.2 |
| `backend/app/core/session_store.py` | 인메모리/락 동시성, met_count 재구성 → §2.2 |
| `frontend/src/api/client.ts` | 세션 헤더/404 재시도 계약 → §2.2 |
| `frontend/src/App.tsx` / `components/*` | 단일 상태 소스 규약(상태는 App에) → §2.5 |

## 2. 프로젝트 불변식 체크리스트 (이 리뷰의 핵심 가치)

일반 리뷰어가 놓치는, 이 코드베이스 특유의 것들. **변경이 건드린 항목만** 깊게 본다.

### 2.1 타입 미러 drift — `schemas.py` ↔ `types.ts`
`frontend/src/types.ts`는 `backend/app/models/schemas.py`를 **수동으로 맞춘** 미러다
(자동생성 아님). 한쪽 스키마(`Weights`/`ScoreBreakdown`/`Participant`/유니온 리터럴/
기본값)를 바꾸고 다른 쪽을 안 바꾸면 프론트 빌드가 깨지거나 필드가 `undefined`로 샌다.
- 스키마 필드/기본값/optional 여부가 바뀐 diff를 보면 **반대쪽도 같이 바뀌었는지** 확인.
- 깊은 대조가 필요하면 `sync-types` skill(또는 `type-syncer` 서브에이전트)로 위임.

### 2.2 세션 & 라운드 수명주기 (API/스토어 계층)
- **`X-Session-Id` 계약**: 데이터 엔드포인트는 `require_session`을 거쳐야 한다(없으면
  400, 모르는 세션 404). 새 라우터를 추가했는데 이 의존성을 빠뜨리지 않았는지.
- **preview ≠ commit**: preview는 `met_count`를 **절대 바꾸지 않는다**. 동석 이력은
  `POST /rounds/commit`의 `add_round`에서만 +1. preview 경로에서 이력을 건드리는 변경은 버그.
- **rollback은 재구성**: `DELETE /rounds/{n}`은 남은 라운드로 `met_count`를
  `rebuild_from_rounds`로 **전체 재구성**한다 — 증분 차감이 아니다. "효율화"한답시고
  증분 차감으로 바꾸면 누적이 틀어진다.
- **CPU 바운드는 스레드풀로**: 솔버 호출은 `run_in_threadpool`로 감싼다(이벤트 루프 블로킹
  방지). 라우터에서 `solve()`를 직접 await 없이 동기 호출하면 회귀.
- **인메모리 가정**: 영구 DB가 없다. 프로세스 재시작 시 휘발을 전제로 한 코드여야 한다
  (디스크/외부 영속화 가정 금지). 세션 변경은 세션별 `threading.Lock` 보호 하에.

### 2.3 비용의 테이블 단위 분해 불변식 (assignment 계층)
`scoring.py`의 비용은 `total_cost = Σ_table table_cost(table)`로 **테이블별 완전 분해**돼야
한다. 솔버가 두 테이블 스왑 시 그 두 테이블만 재계산하는 증분 평가가 여기에 의존한다.
- 새 비용 항목/페널티가 **테이블 로컬 함수**로 들어갔는지(전역 상태·교차 테이블 의존이면
  증분 평가가 깨진다). 새 제약 추가는 `add-constraint` skill의 분해 규칙을 따라야 한다.
- `Breakdown`(항목별 분해) 합이 `total_cost`와 일치하는지 — 단위 검증은
  `tests/test_scoring.py::test_breakdown_sums` 영역.

### 2.4 계층 순수성 & 솔버
- **assignment는 순수**해야 한다. `app/assignment/*`에서 `pydantic`/`fastapi`/`app.api`/
  `app.core`를 import하면 단방향 의존 위반(아래 §3에서 grep으로 확인).
- 이웃 연산은 **두 테이블 1:1 스왑**만(테이블 크기 보존). 크기를 바꾸는 이동을 넣으면
  유효 배치가 깨진다.
- `seed` 지정 시 재현 가능해야 한다 — 비결정성(미시드 `random`)을 새로 들이지 않았는지.

### 2.5 하드 vs 소프트 제약 가중치
우선순위를 가중치 차이로 표현한다: 하드(company=1000, prev=800) ≫ 소프트(gender=3,
age=2, mbti=1). 가중치를 만지는 변경은 이 **자릿수 차이(하드 ≫ 소프트)**를 보존해야 한다 —
소프트를 키워 하드를 역전시키면 하드 제약이 깨질 수 있다. 하드 위반 집계는
`app/api/rounds.py`의 `_HARD_TYPES = ("same_company", "prev_same_table")`.

### 2.6 프론트 단일 상태 소스
`src/App.tsx`가 모든 상태(participants/config/rounds/preview)의 단일 소스다. 하위
`components/*`는 프레젠테이션 위주. 컴포넌트에 새 상태/백엔드 호출을 심으면 이 규약 위반
(백엔드 통신은 `src/api/client.ts` 단일 경유지로).

## 3. 빠른 기계적 점검 (grep)

```bash
# 계층 순수성: assignment가 상위 계층을 import하면 위반
grep -rnE "import (pydantic|fastapi)|from (pydantic|fastapi|app\.(api|core))" backend/app/assignment/

# 비시드 무작위가 새로 들어왔는지(재현성)
grep -rn "random\." backend/app/assignment/solver.py

# 디버그 잔재
grep -rnE "console\.log|print\(|breakpoint\(|debugger" backend/app frontend/src
```

## 4. 발견을 검증한다 (추측 → 확인)

리뷰는 "그럴듯한데 틀린" 지적을 남기기 쉽다. 가능하면 명령으로 확인하고, 확인한 것과
추측을 구분해 보고한다.

```bash
cd backend && ../.venv/bin/python -m pytest -q     # 정확성/불변식 (분해 합, 하드 제약 등)
cd frontend && npm run build                       # 타입 미러/빌드 (= 이 프로젝트의 lint)
```

- 위 둘은 커밋 전 `run-checks.py` 훅이 도는 것과 동일한 게이트다 — 리뷰 단계에서 미리 돌려
  실패를 잡아두면 좋다.
- 알고리즘(비용/가중치/냉각)을 만진 변경이면 정확성 외에 **품질 회귀**도 본다:
  `solver-eval` skill로 baseline 대비 Δcost/Δhard 측정.
- API 계약 전체를 한 바퀴 돌려보려면 `dev-up` skill의 스모크(`scripts/smoke_api.py`).

## 5. 보고 형식

심각도를 붙이고, 각 발견은 `파일:줄`로 짚고, 가능하면 **구체적 수정 제안**과 함께
"명령으로 확인함 / 코드만 보고 추정함"을 표시한다.

- **🔴 Blocker** — 머지 금지. 하드 제약 역전, 미러 drift로 빌드 깨짐, 분해 불변식 위반,
  preview가 met_count 변경, 계층 순수성 위반 등.
- **🟠 Major** — 고쳐야 함. 잘못된 동작·누락된 세션 검증·미처리 에러 경로.
- **🟡 Minor** — 고치면 좋음. 가독성·중복·작은 비효율.
- **⚪ Nit** — 취향/스타일.

```
## 리뷰 결과 (origin/main...HEAD, 4 files)
검증: pytest ✅ (37 passed) · npm run build ✅

🔴 backend/app/api/rounds.py:88 — preview 경로에서 add_round() 호출. preview는 met_count
   불변 불변식 위반(§2.2). commit 경로로만 옮길 것. [pytest로 확인: test_multi_round 실패]
🟡 frontend/src/components/WeightsPanel.tsx:40 — DEFAULT_WEIGHTS 중복 정의. types.ts 것 재사용.
```

## 6. 규율

- **읽기 전용 기본**: 명시적으로 "고쳐줘"라고 하지 않는 한 발견을 보고만 하고 코드를
  고치지 않는다(수정은 `/code-review --fix`나 별도 요청). 변경과 무관한 리팩터링 제안 자제.
- 확신 없는 지적은 그 불확실성을 밝힌다 — 단정하지 않는다.
- 변경 규모에 비례: 작은 diff엔 핵심 몇 개만, 큰/위험한 diff엔 계층별로 폭넓게.
