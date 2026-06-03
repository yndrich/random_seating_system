# backend/app/assignment/ — CLAUDE.md

순수 배정 알고리즘 패키지. **UI/IO/Pydantic 의존이 전혀 없다** — API 계층이 Pydantic
모델을 여기의 dataclass(`Person`/`Weights`)로 변환해 넘긴다. 덕분에 단위테스트가
격리돼 있다(`backend/tests/test_scoring.py`, `test_solver_hard_constraints.py`,
`test_balance.py`, `test_multi_round.py`).

## 핵심 불변식 — 비용의 테이블 단위 분해

`scoring.py`의 비용은 테이블별로 **완전히 분해 가능**하다:

```
total_cost = Σ_table  table_cost(table)
```

이게 이 패키지 설계의 중심이다. 두 테이블 간 스왑은 **그 두 테이블의 비용만** 다시
계산하면 되므로 솔버가 증분 평가를 한다. 비용 항목을 추가/수정할 때 이 분해 가능성을
깨면 솔버의 증분 평가가 틀어진다 — 반드시 테이블 로컬 함수로 유지할 것.

## 파일별 역할

- **`scoring.py`** — `Person`/`Weights` **dataclass**(Pydantic 아님)와 비용 함수,
  `Breakdown`(항목별 분해), `collect_violations`/`collect_warnings`. 가중치 기본값은
  하드(company=1000, prev=800) ≫ 소프트(gender=3, age=2, mbti=1).
- **`solver.py`** — 시뮬레이티드 어닐링 + **다중 재시작**(최저 비용 해 채택).
  - 이웃 연산은 **두 테이블 간 멤버 1:1 스왑**만 사용한다. 스왑은 테이블 크기를
    보존하므로 항상 유효한 배치가 유지된다(크기는 `compute_table_sizes`로 고정).
  - `seed` 지정 시 **완전 재현 가능**. 미지정이면 무작위 시드를 뽑아 `seed_used`로 반환.
  - `solve()` = 미리보기용 풀이. `evaluate_tables()` = 이미 확정된 배치를 **그대로
    채점만**(commit 경로). 둘 다 `SolveResult` 반환, 불가능 입력은 `SolveError`.
- **`balance.py`** — 성비/연령/MBTI 분산 메트릭(소프트 제약 점수의 재료).
- **`history.py`** — `met_count`(누적 동석 횟수, `{frozenset({a,b}): count}`) 순수 헬퍼.
  `add_round`(라운드 확정 시 +1), `rebuild_from_rounds`(롤백 시 전체 재구성).

> 언제 `add_round`/`rebuild`가 호출되는지(수명주기)는 API 계층 책임이다 —
> `backend/CLAUDE.md`의 "세션 & 라운드 수명주기" 참고.
