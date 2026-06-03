"""배정 스코어링 — 비용 함수, 점수 분해(breakdown), 위반/경고 추출.

알고리즘은 Pydantic이나 IO에 의존하지 않는다. API 계층이 Pydantic 모델을 여기의
``Person`` / ``Weights`` 데이터클래스로 변환해서 넘긴다.

비용은 테이블 단위로 완전히 분해 가능하다:
    total_cost = Σ_table table_cost(table)
따라서 두 테이블 간 스왑은 그 두 테이블의 비용만 다시 계산하면 된다(증분 평가).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from . import balance

# 배치(assignment)의 내부 표현: 테이블별 person 인덱스 리스트
Assignment = list[list[int]]


@dataclass(frozen=True)
class Person:
    """배정 대상 한 명. mbti는 대문자 4글자로 정규화되어 있다고 가정."""

    id: str
    gender: str
    company: str
    age_group: str
    mbti: str
    name: str = ""


@dataclass(frozen=True)
class Weights:
    """비용 항목별 가중치. 하드(company, prev) ≫ 소프트(gender, age, mbti)."""

    company: float = 1000.0
    prev: float = 800.0
    gender: float = 3.0
    age: float = 2.0
    mbti: float = 1.0


@dataclass
class ScoringContext:
    """비용 평가에 필요한 모든 컨텍스트(불변 입력)."""

    persons: list[Person]
    weights: Weights
    met_count: dict[frozenset[str], int] = field(default_factory=dict)
    # 아래 두 값은 __post_init__ 에서 persons로부터 파생
    gender_counts: dict[str, int] = field(default_factory=dict)
    total_people: int = 0

    def __post_init__(self) -> None:
        if not self.gender_counts:
            self.gender_counts = dict(Counter(p.gender for p in self.persons))
        if not self.total_people:
            self.total_people = len(self.persons)


@dataclass(frozen=True)
class Breakdown:
    """비용을 항목별로 분해한 결과(모두 가중치 적용 후 값)."""

    company: float = 0.0
    prev_table: float = 0.0
    gender: float = 0.0
    age: float = 0.0
    mbti: float = 0.0

    @property
    def total(self) -> float:
        return self.company + self.prev_table + self.gender + self.age + self.mbti

    def __add__(self, other: "Breakdown") -> "Breakdown":
        return Breakdown(
            self.company + other.company,
            self.prev_table + other.prev_table,
            self.gender + other.gender,
            self.age + other.age,
            self.mbti + other.mbti,
        )


def table_breakdown(table: list[int], ctx: ScoringContext) -> Breakdown:
    """한 테이블의 가중치 적용 비용 분해."""
    persons = ctx.persons
    w = ctx.weights
    ids = [persons[i].id for i in table]
    companies = [persons[i].company for i in table]
    genders = [persons[i].gender for i in table]
    ages = [persons[i].age_group for i in table]
    mbtis = [persons[i].mbti for i in table]

    return Breakdown(
        company=w.company * balance.company_pair_count(companies),
        prev_table=w.prev * balance.prev_pair_penalty(ids, ctx.met_count),
        gender=w.gender
        * balance.gender_penalty(genders, ctx.gender_counts, ctx.total_people),
        age=w.age * balance.age_penalty(ages),
        mbti=w.mbti * balance.mbti_penalty(mbtis),
    )


def table_cost(table: list[int], ctx: ScoringContext) -> float:
    """한 테이블의 총 가중치 비용(스칼라). 솔버의 증분 평가에서 핫패스."""
    return table_breakdown(table, ctx).total


def score(assignment: Assignment, ctx: ScoringContext) -> tuple[float, Breakdown]:
    """전체 배치의 (총비용, 항목별 분해)."""
    bd = Breakdown()
    for table in assignment:
        bd = bd + table_breakdown(table, ctx)
    return bd.total, bd


@dataclass
class Violation:
    type: str  # "same_company" | "prev_same_table"
    table_index: int
    member_ids: list[str]
    detail: dict


def collect_violations(
    assignment: Assignment, ctx: ScoringContext
) -> list[Violation]:
    """하드 제약 위반 인스턴스를 구체적으로 추출(리포팅용)."""
    persons = ctx.persons
    violations: list[Violation] = []
    for t_idx, table in enumerate(assignment):
        # 같은 회사: 회사별로 2명 이상 모인 클러스터를 하나의 위반으로 보고
        by_company: dict[str, list[str]] = {}
        for i in table:
            by_company.setdefault(persons[i].company, []).append(persons[i].id)
        for company, members in by_company.items():
            if len(members) >= 2:
                violations.append(
                    Violation(
                        type="same_company",
                        table_index=t_idx,
                        member_ids=members,
                        detail={"company": company, "count": len(members)},
                    )
                )
        # 이전 동석: met_count > 0 인 쌍을 각각 위반으로 보고
        if ctx.met_count:
            for a, b in combinations(table, 2):
                ida, idb = persons[a].id, persons[b].id
                times = ctx.met_count.get(frozenset((ida, idb)), 0)
                if times > 0:
                    violations.append(
                        Violation(
                            type="prev_same_table",
                            table_index=t_idx,
                            member_ids=[ida, idb],
                            detail={"times": times},
                        )
                    )
    return violations


def table_balance_summary(table: list[int], ctx: ScoringContext) -> dict:
    """프론트 표시용 테이블별 분포 요약(위반이 아닌 정보)."""
    persons = ctx.persons
    genders = Counter(persons[i].gender for i in table)
    ages = Counter(persons[i].age_group for i in table)
    axis_counts = {}
    mbtis = [persons[i].mbti for i in table]
    size = len(table)
    for pos, (first, second) in enumerate(balance.MBTI_AXES):
        c_first = sum(1 for m in mbtis if len(m) > pos and m[pos] == first)
        axis_counts[f"{first}{second}"] = {first: c_first, second: size - c_first}
    return {
        "size": size,
        "gender": dict(genders),
        "age_group": dict(ages),
        "mbti_axes": axis_counts,
    }


def collect_warnings(assignment: Assignment, ctx: ScoringContext) -> list[str]:
    """소프트 불균형이 임계치를 넘을 때만 사람이 읽을 경고 문구 생성."""
    warnings: list[str] = []
    persons = ctx.persons
    has_multiple_genders = len(ctx.gender_counts) >= 2
    for t_idx, table in enumerate(assignment):
        if not table:
            continue
        genders = Counter(persons[i].gender for i in table)
        # 전체적으로 성별이 섞여 있는데 한 조가 전원 동성이면 경고
        if has_multiple_genders and len(genders) == 1:
            only = next(iter(genders))
            warnings.append(f"{t_idx + 1}조: 전원 동일 성별({only}) 쏠림")
        # 한 연령대가 조의 과반 이상을 차지하면 경고
        ages = Counter(persons[i].age_group for i in table)
        top_age, top_n = ages.most_common(1)[0]
        if len(table) >= 3 and top_n > len(table) / 2:
            warnings.append(
                f"{t_idx + 1}조: 연령대 '{top_age}'가 과반({top_n}/{len(table)})"
            )
    return warnings
