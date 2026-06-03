"""조 배정 솔버 — 시뮬레이티드 어닐링(다중 재시작) + 증분 평가.

표 크기는 미리 정해진 목표 크기로 고정되며(인원이 안 나눠떨어지면 ±1),
이웃 연산은 '두 테이블 간 멤버 1:1 스왑'만 사용한다. 스왑은 테이블 크기를
보존하므로 항상 유효한 배치가 유지된다.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .scoring import (
    Assignment,
    Breakdown,
    Person,
    ScoringContext,
    Violation,
    collect_violations,
    collect_warnings,
    score,
    table_balance_summary,
    table_cost,
)


@dataclass
class SolveResult:
    assignment: Assignment  # 테이블별 person 인덱스
    tables_ids: list[list[str]]  # 테이블별 person id
    cost: float
    breakdown: Breakdown
    violations: list[Violation]
    warnings: list[str]
    per_table_balance: list[dict]
    seed_used: int


class SolveError(ValueError):
    """배정 불가능한 입력(인원 부족 등)."""


def compute_table_sizes(total: int, num_tables: int) -> list[int]:
    """total 명을 num_tables 개 테이블에 최대한 균등 분배한 크기 리스트."""
    if num_tables <= 0:
        raise SolveError("테이블 수는 1 이상이어야 합니다.")
    if num_tables > total:
        raise SolveError(
            f"테이블 수({num_tables})가 인원({total})보다 많을 수 없습니다."
        )
    base, extra = divmod(total, num_tables)
    # 앞쪽 extra 개 테이블이 1명 더 많음
    return [base + 1 if i < extra else base for i in range(num_tables)]


def resolve_num_tables(
    total: int, num_tables: int | None, table_size: int | None
) -> int:
    """num_tables 또는 table_size 중 지정된 값으로 테이블 수를 결정."""
    if total <= 0:
        raise SolveError("참가자가 없습니다.")
    if num_tables is not None and table_size is not None:
        raise SolveError("조 개수와 조당 인원 중 하나만 지정하세요.")
    if num_tables is not None:
        return num_tables
    if table_size is not None:
        if table_size <= 0:
            raise SolveError("조당 인원은 1 이상이어야 합니다.")
        return math.ceil(total / table_size)
    raise SolveError("조 개수 또는 조당 인원을 지정하세요.")


def _initial_assignment(
    ctx: ScoringContext, sizes: list[int], rng: random.Random
) -> Assignment:
    """회사별로 라운드로빈 분산한 초기 배치(용량 준수)."""
    n = len(ctx.persons)
    # 회사 그룹이 흩어지도록 (회사, 무작위키)로 정렬 후 라운드로빈 배치
    order = sorted(range(n), key=lambda i: (ctx.persons[i].company, rng.random()))
    tables: Assignment = [[] for _ in sizes]
    t = 0
    for i in order:
        # 용량이 남은 다음 테이블로 이동
        while len(tables[t]) >= sizes[t]:
            t = (t + 1) % len(sizes)
        tables[t].append(i)
        t = (t + 1) % len(sizes)
    return tables


def _anneal(
    ctx: ScoringContext,
    sizes: list[int],
    rng: random.Random,
    max_iters: int,
    t_start: float,
    t_end: float,
) -> tuple[Assignment, float]:
    """한 번의 SA 실행. (최적 배치, 비용) 반환."""
    tables = _initial_assignment(ctx, sizes, rng)
    costs = [table_cost(t, ctx) for t in tables]
    current_total = sum(costs)

    best = [list(t) for t in tables]
    best_total = current_total

    k = len(tables)
    if k < 2:
        return best, best_total  # 테이블이 1개면 스왑 불가, 그대로

    # 기하 냉각비
    cooling = (t_end / t_start) ** (1.0 / max(1, max_iters)) if t_start > 0 else 1.0
    temp = t_start

    for _ in range(max_iters):
        # 서로 다른 두 테이블에서 한 명씩 골라 스왑
        t1 = rng.randrange(k)
        t2 = rng.randrange(k)
        if t1 == t2 or not tables[t1] or not tables[t2]:
            temp *= cooling
            continue
        p1 = rng.randrange(len(tables[t1]))
        p2 = rng.randrange(len(tables[t2]))

        tables[t1][p1], tables[t2][p2] = tables[t2][p2], tables[t1][p1]
        new_c1 = table_cost(tables[t1], ctx)
        new_c2 = table_cost(tables[t2], ctx)
        delta = (new_c1 + new_c2) - (costs[t1] + costs[t2])

        accept = delta <= 0
        if not accept and temp > 1e-9:
            accept = rng.random() < math.exp(-delta / temp)

        if accept:
            costs[t1], costs[t2] = new_c1, new_c2
            current_total += delta
            if current_total < best_total - 1e-9:
                best_total = current_total
                best = [list(t) for t in tables]
        else:
            # 되돌리기
            tables[t1][p1], tables[t2][p2] = tables[t2][p2], tables[t1][p1]

        temp *= cooling

    return best, best_total


def solve(
    persons: list[Person],
    *,
    num_tables: int | None = None,
    table_size: int | None = None,
    weights=None,
    met_count: dict[frozenset[str], int] | None = None,
    seed: int | None = None,
    restarts: int = 8,
    max_iters: int | None = None,
    t_start: float = 5.0,
    t_end: float = 0.01,
) -> SolveResult:
    """조 배정을 풀어 최적(최저 비용) 결과를 반환.

    seed가 주어지면 완전히 재현 가능하다. 여러 재시작 중 최저 비용 해를 채택해
    하드 위반을 최소화한다.
    """
    from .scoring import Weights

    if weights is None:
        weights = Weights()
    total = len(persons)
    k = resolve_num_tables(total, num_tables, table_size)
    sizes = compute_table_sizes(total, k)

    ctx = ScoringContext(
        persons=persons, weights=weights, met_count=met_count or {}
    )

    base_seed = seed if seed is not None else random.randrange(1, 2**31 - 1)
    if max_iters is None:
        # 문제 크기에 비례한 반복 수(작은 입력도 충분히 수렴하도록 하한 둠)
        max_iters = max(2000, total * 200)

    best_assignment: Assignment | None = None
    best_total = math.inf
    for r in range(max(1, restarts)):
        rng = random.Random(base_seed + r)
        assignment, total_cost = _anneal(
            ctx, sizes, rng, max_iters, t_start, t_end
        )
        if total_cost < best_total:
            best_total = total_cost
            best_assignment = assignment

    assert best_assignment is not None
    return _build_result(best_assignment, ctx, base_seed)


def _build_result(
    assignment: Assignment, ctx: ScoringContext, seed_used: int
) -> SolveResult:
    """배치 하나에 대한 비용/위반/균형 등 전체 결과를 산출(solve·evaluate 공용)."""
    final_cost, breakdown = score(assignment, ctx)
    return SolveResult(
        assignment=assignment,
        tables_ids=[[ctx.persons[i].id for i in table] for table in assignment],
        cost=final_cost,
        breakdown=breakdown,
        violations=collect_violations(assignment, ctx),
        warnings=collect_warnings(assignment, ctx),
        per_table_balance=[table_balance_summary(t, ctx) for t in assignment],
        seed_used=seed_used,
    )


def evaluate_tables(
    persons: list[Person],
    tables_ids: list[list[str]],
    *,
    weights=None,
    met_count: dict[frozenset[str], int] | None = None,
    seed_used: int = 0,
) -> SolveResult:
    """이미 정해진 배치(멤버 id 리스트)를 재계산만 한다(확정 시 사용).

    미리보기에서 본 그대로를 확정하기 위해 다시 풀지 않고 평가만 수행한다.
    """
    from .scoring import Weights

    if weights is None:
        weights = Weights()
    id_to_idx = {p.id: i for i, p in enumerate(persons)}
    seen: set[str] = set()
    assignment: Assignment = []
    for table in tables_ids:
        row = []
        for mid in table:
            if mid not in id_to_idx:
                raise SolveError(f"알 수 없는 참가자 id: {mid}")
            if mid in seen:
                raise SolveError(f"참가자가 중복 배정됨: {mid}")
            seen.add(mid)
            row.append(id_to_idx[mid])
        assignment.append(row)
    if seen != set(id_to_idx):
        raise SolveError("확정하려는 배치가 전체 참가자를 정확히 포함하지 않습니다.")

    ctx = ScoringContext(persons=persons, weights=weights, met_count=met_count or {})
    return _build_result(assignment, ctx, seed_used)
