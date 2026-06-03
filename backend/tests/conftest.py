"""테스트 공용 헬퍼."""

from __future__ import annotations

import os
import sys

# `app` 패키지를 import 할 수 있도록 backend/ 를 path 에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.assignment import Person  # noqa: E402


def make_person(
    pid: str,
    gender: str = "male",
    company: str = "A",
    age_group: str = "30s",
    mbti: str = "INTJ",
    name: str = "",
) -> Person:
    return Person(
        id=pid,
        gender=gender,
        company=company,
        age_group=age_group,
        mbti=mbti,
        name=name or pid,
    )


def assert_valid_partition(assignment, persons) -> None:
    """모든 참가자가 정확히 한 조에 배정됐는지(불변식) 확인."""
    flat = [i for table in assignment for i in table]
    assert sorted(flat) == list(range(len(persons))), "모든 참가자가 정확히 1조"
    assert len(flat) == len(persons), "조 크기 합 == 인원수"
