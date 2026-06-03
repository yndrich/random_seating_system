"""다중 라운드 로테이션: met_count 누적/회피/롤백 검증."""

from __future__ import annotations

from app.assignment import solve
from app.assignment.history import add_round, rebuild_from_rounds

from .conftest import make_person


def _repeat_pairs(tables_ids, met_count):
    """이번 배치에서 met_count>0(과거 동석)인 쌍이 다시 같은 조가 된 횟수."""
    from itertools import combinations

    n = 0
    for table in tables_ids:
        for a, b in combinations(table, 2):
            if met_count.get(frozenset((a, b)), 0) > 0:
                n += 1
    return n


def test_add_round_increments():
    met = {}
    met = add_round(met, [["p1", "p2"], ["p3", "p4"]])
    assert met[frozenset(("p1", "p2"))] == 1
    met = add_round(met, [["p1", "p2"], ["p3", "p4"]])
    assert met[frozenset(("p1", "p2"))] == 2
    assert frozenset(("p1", "p3")) not in met


def test_rebuild_from_rounds_matches_incremental():
    r1 = [["p1", "p2"], ["p3", "p4"]]
    r2 = [["p1", "p3"], ["p2", "p4"]]
    incremental = add_round(add_round({}, r1), r2)
    rebuilt = rebuild_from_rounds([r1, r2])
    assert incremental == rebuilt


def test_round2_avoids_previous_table_mates():
    """라운드1 확정 후 라운드2는 이전 동석 쌍을 가능한 한 회피해야 한다."""
    persons = [make_person(f"p{i}", company=chr(65 + i % 6)) for i in range(24)]
    r1 = solve(persons, num_tables=6, seed=10)
    met = add_round({}, r1.tables_ids)

    r2 = solve(persons, num_tables=6, seed=10, met_count=met)
    repeats = _repeat_pairs(r2.tables_ids, met)
    # 24명/6조(각4명)에서 충분히 분산 가능 → 재동석 0에 수렴해야 함
    assert repeats == 0
    assert r2.breakdown.prev_table == 0.0


def test_rollback_recomputes_met_count():
    r1 = [["p1", "p2"], ["p3", "p4"]]
    r2 = [["p1", "p3"], ["p2", "p4"]]
    met = rebuild_from_rounds([r1, r2])
    # r2 롤백 → r1만 남음
    met_after_rollback = rebuild_from_rounds([r1])
    assert met_after_rollback == add_round({}, r1)
    assert met != met_after_rollback
