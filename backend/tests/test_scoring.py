"""스코어 분해 합산 일치 및 증분(델타) 평가 정확성 검증."""

from __future__ import annotations

from app.assignment import ScoringContext, Weights, score
from app.assignment.scoring import table_cost

from .conftest import make_person


def _ctx(persons, met_count=None):
    return ScoringContext(persons=persons, weights=Weights(), met_count=met_count or {})


def test_breakdown_sums_to_total():
    persons = [
        make_person("p1", gender="male", company="A", age_group="20s", mbti="INTJ"),
        make_person("p2", gender="female", company="A", age_group="20s", mbti="ENFP"),
        make_person("p3", gender="male", company="B", age_group="30s", mbti="ISTJ"),
        make_person("p4", gender="female", company="B", age_group="40s", mbti="ESFP"),
    ]
    ctx = _ctx(persons)
    assignment = [[0, 1], [2, 3]]
    total, bd = score(assignment, ctx)
    assert abs(total - bd.total) < 1e-9
    assert abs(total - (bd.company + bd.prev_table + bd.gender + bd.age + bd.mbti)) < 1e-9


def test_total_equals_sum_of_table_costs():
    persons = [make_person(f"p{i}", company=chr(65 + i % 3)) for i in range(9)]
    ctx = _ctx(persons)
    assignment = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    total, _ = score(assignment, ctx)
    sum_tables = sum(table_cost(t, ctx) for t in assignment)
    assert abs(total - sum_tables) < 1e-9


def test_incremental_delta_matches_full_recompute():
    """두 테이블 간 스왑 후, (델타 기반 새 총비용)==(전체 재계산)인지 확인."""
    persons = [
        make_person("p0", gender="male", company="A", age_group="20s", mbti="INTJ"),
        make_person("p1", gender="female", company="B", age_group="30s", mbti="ENFP"),
        make_person("p2", gender="male", company="A", age_group="40s", mbti="ISTJ"),
        make_person("p3", gender="female", company="C", age_group="20s", mbti="ESFP"),
        make_person("p4", gender="male", company="B", age_group="30s", mbti="INFP"),
        make_person("p5", gender="female", company="C", age_group="40s", mbti="ESTJ"),
    ]
    met = {frozenset(("p0", "p3")): 1, frozenset(("p1", "p4")): 2}
    ctx = _ctx(persons, met)
    tables = [[0, 1, 2], [3, 4, 5]]

    costs = [table_cost(t, ctx) for t in tables]
    total_before = sum(costs)

    # p2(table0, pos2) <-> p3(table1, pos0) 스왑
    t1, p1, t2, p2 = 0, 2, 1, 0
    tables[t1][p1], tables[t2][p2] = tables[t2][p2], tables[t1][p1]
    new_c1 = table_cost(tables[t1], ctx)
    new_c2 = table_cost(tables[t2], ctx)
    delta = (new_c1 + new_c2) - (costs[t1] + costs[t2])
    total_after_delta = total_before + delta

    total_after_full, _ = score(tables, ctx)
    assert abs(total_after_delta - total_after_full) < 1e-9
