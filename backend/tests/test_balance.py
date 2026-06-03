"""균형/분산 메트릭 함수의 경계값·단조성 검증."""

from __future__ import annotations

from app.assignment import balance


def test_company_pair_count():
    assert balance.company_pair_count(["A", "B", "C"]) == 0
    assert balance.company_pair_count(["A", "A"]) == 1
    assert balance.company_pair_count(["A", "A", "A"]) == 3  # C(3,2)
    assert balance.company_pair_count(["A", "A", "B", "B"]) == 2


def test_prev_pair_penalty():
    met = {frozenset(("p1", "p2")): 2, frozenset(("p2", "p3")): 1}
    assert balance.prev_pair_penalty(["p1", "p2", "p3"], met) == 3
    assert balance.prev_pair_penalty(["p1", "p4"], met) == 0
    assert balance.prev_pair_penalty(["p1", "p2", "p3"], {}) == 0


def test_gender_penalty_balanced_is_zero():
    # 전체 8:8, 테이블도 2:2면 페널티 0
    global_counts = {"male": 8, "female": 8}
    assert balance.gender_penalty(
        ["male", "male", "female", "female"], global_counts, 16
    ) == 0.0


def test_gender_penalty_skewed_is_positive():
    global_counts = {"male": 8, "female": 8}
    balanced = balance.gender_penalty(
        ["male", "male", "female", "female"], global_counts, 16
    )
    skewed = balance.gender_penalty(
        ["male", "male", "male", "male"], global_counts, 16
    )
    assert skewed > balanced


def test_age_penalty_boundaries():
    # 전부 다른 연령대 → 0 (가장 분산)
    assert balance.age_penalty(["10s", "20s", "30s", "40s"]) == 0
    # 전부 같은 연령대 → 최대 C(4,2)=6
    assert balance.age_penalty(["20s", "20s", "20s", "20s"]) == 6
    # 부분 중복은 그 사이
    assert 0 < balance.age_penalty(["20s", "20s", "30s", "40s"]) < 6


def test_mbti_penalty_4axis_balance():
    # 4명이 INTJ/ENFP/ISFJ/ESTP → 각 축 2:2 → 0
    assert balance.mbti_penalty(["INTJ", "ENFP", "ISFJ", "ESTP"]) == 0
    # 전원 INTJ → 각 축 4:0 → 축당 |8-4|=4, 4축 → 16
    assert balance.mbti_penalty(["INTJ", "INTJ", "INTJ", "INTJ"]) == 16
    # 부분 쏠림은 그 사이
    assert 0 < balance.mbti_penalty(["INTJ", "INTP", "ENFP", "ESFP"]) < 16
