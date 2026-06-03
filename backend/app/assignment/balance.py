"""순수 균형/분산 메트릭 함수들.

여기 있는 함수는 모두 한 테이블(멤버 리스트) 단위로 페널티를 계산한다.
페널티가 낮을수록 더 좋은 배치이며, 모든 함수는 부수효과가 없는 순수 함수다.
이렇게 테이블 단위로 분해 가능해야 SA 솔버에서 증분(델타) 평가가 가능하다.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

# MBTI 4축. 각 튜플의 첫 글자를 기준 letter로 사용한다.
MBTI_AXES = (("E", "I"), ("S", "N"), ("T", "F"), ("J", "P"))


def company_pair_count(companies: list[str]) -> int:
    """한 테이블 내에서 같은 회사인 (순서 없는) 쌍의 개수.

    회사 c가 k명이면 C(k, 2) 쌍이 충돌한다. 이 값이 0이면 회사 분리가 완벽하다.
    """
    counts = Counter(companies)
    return sum(k * (k - 1) // 2 for k in counts.values() if k >= 2)


def prev_pair_penalty(ids: list[str], met_count: dict[frozenset[str], int]) -> int:
    """이전 회차들에서 이미 같은 조였던 쌍에 대한 누적 페널티.

    met_count[{a, b}] 는 a와 b가 과거에 같은 조였던 횟수다.
    여러 번 만났을수록 페널티가 커져 자연스러운 로테이션을 유도한다.
    """
    if not met_count:
        return 0
    total = 0
    for a, b in combinations(ids, 2):
        total += met_count.get(frozenset((a, b)), 0)
    return total


def gender_penalty(
    genders: list[str], global_counts: dict[str, int], total_people: int
) -> float:
    """전체 성비를 테이블에도 반영하기 위한 제곱 편차 페널티.

    각 성별 g의 기대 인원 = (전체 g 비율) * (테이블 인원). 실제와의 제곱 편차를 합산.
    0이면 이 테이블이 전체 성비를 정확히 반영한다는 뜻.
    """
    if total_people == 0:
        return 0.0
    size = len(genders)
    counts = Counter(genders)
    penalty = 0.0
    for g, gcount in global_counts.items():
        expected = gcount / total_people * size
        actual = counts.get(g, 0)
        penalty += (actual - expected) ** 2
    return penalty


def age_penalty(age_groups: list[str]) -> int:
    """연령대 쏠림(클러스터링) 페널티 — 테이블 내 연령 다양성 유도.

    같은 연령대 쌍 수의 합 = Σ C(count, 2). 같은 연령대가 몰릴수록 커진다.
    """
    counts = Counter(age_groups)
    return sum(k * (k - 1) // 2 for k in counts.values() if k >= 2)


def mbti_penalty(mbtis: list[str]) -> int:
    """MBTI 4축 각각의 테이블 내 불균형 페널티 — 성향 다양성 유도.

    각 축에서 한쪽 글자 수가 a, 인원이 size면 |2a - size| 가 불균형이다.
    (a == size/2 일 때 0으로 가장 균형). 16종 희소성을 피하려 4축으로 분해해 측정.
    """
    size = len(mbtis)
    if size == 0:
        return 0
    penalty = 0
    for pos, (first, _second) in enumerate(MBTI_AXES):
        count_first = sum(1 for m in mbtis if len(m) > pos and m[pos] == first)
        penalty += abs(2 * count_first - size)
    return penalty
