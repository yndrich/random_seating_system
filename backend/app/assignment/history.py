"""다중 라운드 동석 이력(met_count) 관리 헬퍼 — 순수 함수."""

from __future__ import annotations

from itertools import combinations


def pairs_in_tables(tables_ids: list[list[str]]) -> list[frozenset[str]]:
    """각 테이블 내 같은 조가 된 모든 (순서 없는) 쌍."""
    pairs: list[frozenset[str]] = []
    for table in tables_ids:
        for a, b in combinations(table, 2):
            pairs.append(frozenset((a, b)))
    return pairs


def add_round(
    met_count: dict[frozenset[str], int], tables_ids: list[list[str]]
) -> dict[frozenset[str], int]:
    """라운드 확정 시 새 동석 쌍들의 met_count 를 +1 (새 dict 반환)."""
    updated = dict(met_count)
    for pair in pairs_in_tables(tables_ids):
        updated[pair] = updated.get(pair, 0) + 1
    return updated


def rebuild_from_rounds(
    rounds_tables_ids: list[list[list[str]]],
) -> dict[frozenset[str], int]:
    """확정된 라운드들의 테이블 구성으로부터 met_count 를 재구성(롤백용)."""
    met: dict[frozenset[str], int] = {}
    for tables_ids in rounds_tables_ids:
        met = add_round(met, tables_ids)
    return met
