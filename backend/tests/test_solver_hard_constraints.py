"""솔버의 하드 제약 만족 및 소프트 균형, 재현성, 불변식 검증."""

from __future__ import annotations

from collections import Counter

from app.assignment import compute_table_sizes, resolve_num_tables, solve
from app.assignment.solver import SolveError
import pytest

from .conftest import assert_valid_partition, make_person


def _hard_violation_count(result):
    return sum(
        1 for v in result.violations if v.type in ("same_company", "prev_same_table")
    )


def test_compute_table_sizes():
    assert compute_table_sizes(16, 4) == [4, 4, 4, 4]
    assert compute_table_sizes(10, 3) == [4, 3, 3]
    assert compute_table_sizes(7, 7) == [1] * 7


def test_resolve_num_tables():
    assert resolve_num_tables(16, 4, None) == 4
    assert resolve_num_tables(16, None, 4) == 4
    assert resolve_num_tables(17, None, 4) == 5  # ceil(17/4)
    with pytest.raises(SolveError):
        resolve_num_tables(16, 4, 4)  # 둘 다 지정 금지
    with pytest.raises(SolveError):
        resolve_num_tables(0, 4, None)


def test_too_many_tables_raises():
    persons = [make_person(f"p{i}") for i in range(3)]
    with pytest.raises(SolveError):
        solve(persons, num_tables=5, seed=1)


def test_company_separation_feasible_zero_violations():
    """회사 4개 × 4명, 4조 → 회사 분리가 완전히 가능. 위반 0이어야 함."""
    persons = []
    for c in "ABCD":
        for j in range(4):
            persons.append(make_person(f"{c}{j}", company=c))
    result = solve(persons, num_tables=4, seed=42)
    assert_valid_partition(result.assignment, persons)
    same_company = [v for v in result.violations if v.type == "same_company"]
    assert same_company == [], f"회사 분리 실패: {same_company}"
    assert result.breakdown.company == 0.0


def test_company_separation_infeasible_minimal_violation():
    """회사 A 5명 + B 3명, 4조(각 2명). 비둘기집 → 최소 1쌍 충돌이 불가피.

    솔버는 정확히 1개의 same_company 위반(A 2명 한 조)으로 수렴해야 한다.
    """
    persons = [make_person(f"A{j}", company="A") for j in range(5)]
    persons += [make_person(f"B{j}", company="B") for j in range(3)]
    result = solve(persons, num_tables=4, seed=7)
    assert_valid_partition(result.assignment, persons)
    same_company = [v for v in result.violations if v.type == "same_company"]
    assert len(same_company) == 1
    assert same_company[0].detail["company"] == "A"
    assert same_company[0].detail["count"] == 2


def test_gender_balance():
    """성별 8:8, 4조 → 각 조 2:2 근접(편차 ≤ 1)."""
    persons = []
    for j in range(8):
        persons.append(make_person(f"M{j}", gender="male", company=chr(65 + j % 4)))
    for j in range(8):
        persons.append(make_person(f"F{j}", gender="female", company=chr(65 + j % 4)))
    result = solve(persons, num_tables=4, seed=1)
    for table in result.assignment:
        genders = Counter(persons[i].gender for i in table)
        assert abs(genders.get("male", 0) - genders.get("female", 0)) <= 1


def test_reproducibility_same_seed():
    persons = [make_person(f"p{i}", company=chr(65 + i % 5)) for i in range(20)]
    r1 = solve(persons, num_tables=5, seed=123)
    r2 = solve(persons, num_tables=5, seed=123)
    assert r1.assignment == r2.assignment
    assert r1.cost == r2.cost
    assert r1.seed_used == r2.seed_used == 123


def test_table_size_mode():
    persons = [make_person(f"p{i}") for i in range(10)]
    result = solve(persons, table_size=4, seed=1)
    sizes = sorted(len(t) for t in result.assignment)
    # ceil(10/4)=3 조 → 균등 분배하면 [4,3,3]
    assert sizes == [3, 3, 4]
    assert_valid_partition(result.assignment, persons)
