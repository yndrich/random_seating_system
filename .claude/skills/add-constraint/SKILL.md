---
name: add-constraint
description: >-
  랜덤 조 배정 시스템에 새 제약(constraint) 또는 균형(balance) 차원을 끝까지 추가하는
  플레이북. 새 가중치 항목·페널티 함수·점수 분해(Breakdown) 필드를 백엔드 알고리즘부터
  Pydantic 스키마, API 변환 계층, 프론트 타입 미러, 가중치 UI, 테스트까지 6~7개 파일에
  걸쳐 일관되게 추가하고 "비용의 테이블 단위 분해" 불변식을 보존한다. 사용자가 "새 제약
  추가", "회사/이전동석/성비/연령/MBTI 외에 다른 기준으로 배정", "가중치 항목 추가",
  "balance 메트릭 추가", "예: 부서/직급/지역 분리", "점수 분해에 항목 추가" 같은 요청을
  하면 — 명시적으로 이 skill 이름을 부르지 않더라도 — 반드시 이 skill을 사용할 것.
  단일 파일만 건드리는 가중치 기본값 변경은 이 skill이 아니라 직접 수정으로 충분하다.
---

# 새 제약/균형 차원 추가 (add-constraint)

새 제약 하나를 추가하려면 **여러 파일을 한 번에 맞춰야** 하고, 한 군데라도 빠지면
점수 분해가 어긋나거나 프론트 빌드가 깨진다. 이 skill은 그 순서와 빠지기 쉬운 지점을
codify한다. 작업 전 `backend/app/assignment/CLAUDE.md`(불변식)와 `backend/CLAUDE.md`
(제약 모델·3계층 의존)를 함께 읽으면 맥락이 잡힌다.

## 가장 중요한 불변식 — 깨지 말 것

비용은 **테이블 단위로 완전히 분해**된다: `total_cost = Σ_table table_cost(table)`.
솔버는 두 테이블 간 1:1 스왑 시 **그 두 테이블 비용만** 다시 계산하는 증분 평가에
의존한다(`solver.py:127-129`, `backend/tests/test_scoring.py`의
`test_incremental_delta_matches_full_recompute`가 이를 검증).

따라서 **새 페널티 함수는 반드시 한 테이블의 멤버만 보는 순수 함수**여야 한다. 다른
테이블이나 전역 상태(예외: 읽기 전용 `met_count`·`gender_counts` 같은 컨텍스트 상수)를
참조하면 증분 평가가 틀어진다.

## 먼저 갈래를 정하라

**갈래 A — 기존 사람 속성으로 계산하는 새 균형/분산 페널티**
(예: "회사는 분리하되 같은 회사여도 직급이 겹치지 않게"가 아니라 단순히 새 다양성 점수).
→ `Person`에 새 필드 불필요. 1단계의 "Person 속성 추가"는 건너뛴다.

**갈래 B — 새 사람 속성이 필요한 제약** (예: 부서/지역/직급 분리).
→ `Person`, `ParticipantBase`(+검증), `ParticipantInput`, 참가자 입력 폼까지 추가로
손대야 한다. 아래 표에서 (B) 표시 단계를 포함한다.

또한 **하드 vs 소프트**를 정한다. 하드는 가중치를 크게(예: company=1000, prev=800),
소프트는 작게(gender=3, age=2, mbti=1). 하드면 위반 인스턴스를 `collect_violations`로
구체적으로 리포팅하고 `_HARD_TYPES`에 등록한다. 소프트면 보통 점수에만 반영한다.

## 이름 주의 (자주 틀리는 지점)

가중치 키와 분해 필드 이름이 **항상 같지 않다**. 예: 가중치 키는 `prev`인데 분해
필드는 `prev_table`이다. 새 항목 `foo`를 넣을 땐 가중치 키와 분해 필드 이름을 의도적으로
정하고 모든 파일에서 **동일하게** 쓰되, 기존 `prev`/`prev_table` 같은 비대칭을 흉내내지
말고 헷갈리지 않게 같은 이름으로 통일하는 걸 권장한다.

## 수정 파일과 순서

예시로 소프트 제약 `region`(지역 분산, 가중치 기본 2.0, 갈래 B)을 추가한다고 하자.
실제 작업 시 이름·기본값·하드여부만 바꾸면 된다.

### 1. `backend/app/assignment/balance.py` — 순수 페널티 함수

기존 함수(`company_pair_count`, `age_penalty` 등)와 같은 모양으로, **한 테이블의 값
리스트만 받는** 순수 함수를 추가한다. "같은 값이 몰릴수록 페널티"는 `Counter` + `C(k,2)`
패턴이 정석이다:

```python
def region_pair_count(regions: list[str]) -> int:
    """한 테이블 내 같은 지역인 (순서 없는) 쌍의 수."""
    counts = Counter(regions)
    return sum(k * (k - 1) // 2 for k in counts.values() if k >= 2)
```

### 2. `backend/app/assignment/scoring.py` — dataclass 3곳 + 호출부

- `Weights` dataclass에 `region: float = 2.0` 추가.
- **(B)** `Person` dataclass에 `region: str = ""` 추가.
- `Breakdown` dataclass에 `region: float = 0.0` 추가 — **그리고 이게 핵심 함정**:
  `total` property와 `__add__` 메서드는 필드를 **수기로 나열**한다. 둘 다 `region`을
  더하도록 갱신해야 한다(안 하면 분해 합이 total과 안 맞아 테스트 실패).
- `table_breakdown()`에서 값 리스트를 뽑아 `region=w.region * balance.region_pair_count(regions)`
  를 반환에 추가.
- (하드라서 위반을 보고하려면) `collect_violations`에 새 `type="same_region"` 블록 추가.

### 3. `backend/app/models/schemas.py` — Pydantic 미러

- `Weights` 모델에 `region: float = 2.0` 추가 (**dataclass 기본값과 동일하게**).
- 점수 분해를 프론트에 노출하려면 `ScoreBreakdownOut`에 `region: float` 추가.
- **(B)** `ParticipantBase`에 `region: str = Field(...)` 추가, 필요시 `@field_validator`.

### 4. `backend/app/api/rounds.py` — 변환 계층

- `_alg_weights()`에 `region=w.region` 추가 (Pydantic→dataclass 변환에서 누락 금지).
- `ScoreBreakdownOut`에 필드를 넣었다면 `_result_to_round()` 매핑에 `region=bd.region` 추가.
- 하드 제약이고 위반 타입을 만들었다면 `_HARD_TYPES`에 `"same_region"` 추가.

### 5. `frontend/src/types.ts` — 타입 미러 (자동생성 아님)

- `Weights` 인터페이스에 `region: number;` 추가.
- `DEFAULT_WEIGHTS`에 `region: 2,` 추가 (**백엔드 기본값과 동일하게** — 안 맞으면 새
  세션과 미리보기 기본 가중치가 달라짐).
- `ScoreBreakdown`에 필드를 추가했다면 여기도 추가.
- **(B)** `ParticipantInput`에 `region: string;` 추가.

> 타입 미러 동기화가 불안하면 `sync-types` skill로 전체 정합성을 한 번 점검한다.

### 6. `frontend/src/components/ConstraintConfigForm.tsx` — 가중치 슬라이더

`WEIGHT_LABELS` 배열에 항목 추가:

```ts
{ key: "region", label: "지역 분산", hard: false },
```

슬라이더 범위는 `hard`이면 max 2000·step 50, 소프트면 max 30·step 1로 자동 적용된다
(폼이 `hard` 플래그로 분기). **(B)** 참가자 입력 폼(`ParticipantForm.tsx`)에도 입력
필드를 추가해야 새 속성을 받을 수 있다.

### 7. 테스트

- `backend/tests/test_balance.py` — 새 페널티 함수 단위 테스트(같은 값 몰림 → 양수,
  전부 다름 → 0).
- `backend/tests/test_scoring.py` — 분해 합·증분 델타 테스트가 새 항목 포함해도 통과하는지
  확인(이미 일반적인 형태라 보통 자동 커버되지만, 새 속성을 쓰는 케이스를 한 줄 추가하면 안전).

## 검증

```bash
cd backend && ../.venv/bin/python -m pytest -v        # 분해 불변식 포함 전체 통과 확인
cd ../frontend && npm run build                       # tsc 타입체크(=lint) + 빌드
```

두 명령이 모두 통과해야 끝이다. pytest는 분해 합 일치(`test_breakdown_sums_to_total`)와
증분 델타(`test_incremental_delta_matches_full_recompute`)로 불변식 보존을, `npm run build`는
타입 미러 정합성을 잡아준다. 끝에 `solver-eval` skill로 새 제약이 실제 비용/위반에
반영되는지 수치로 확인하면 더 좋다.

## 체크리스트 (빠진 곳 없는지 마지막 점검)

- [ ] balance.py 순수 함수 추가 (테이블 로컬)
- [ ] scoring.py: `Weights` + `Breakdown`(필드 + **total** + **__add__**) + `table_breakdown` 호출부
- [ ] (B) scoring.py `Person` + schemas `ParticipantBase` + types `ParticipantInput` + 입력 폼
- [ ] schemas.py: `Weights`(기본값 일치) + 필요시 `ScoreBreakdownOut`
- [ ] rounds.py: `_alg_weights` + 필요시 `_result_to_round` + 하드면 `_HARD_TYPES`
- [ ] types.ts: `Weights` + `DEFAULT_WEIGHTS`(기본값 일치) + 필요시 `ScoreBreakdown`
- [ ] ConstraintConfigForm `WEIGHT_LABELS`
- [ ] 테스트 추가 + `pytest` & `npm run build` 통과
