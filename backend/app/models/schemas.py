"""API 입출력 Pydantic 스키마.

알고리즘 계층(app.assignment)의 데이터클래스와 1:1로 대응하지만, 검증/직렬화는
여기서만 담당한다. 알고리즘은 Pydantic을 알지 못한다.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# MBTI 각 자리에 허용되는 글자
_MBTI_POS = ("EI", "SN", "TF", "JP")


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class ParticipantBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    gender: Gender
    company: str = Field(min_length=1, max_length=100)
    age_group: str = Field(min_length=1, max_length=20)  # 예: "20s", "30s"
    mbti: str

    @field_validator("mbti")
    @classmethod
    def validate_mbti(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 4 or any(v[i] not in _MBTI_POS[i] for i in range(4)):
            raise ValueError(
                "MBTI는 E/I, S/N, T/F, J/P 조합의 4글자여야 합니다 (예: INTJ)"
            )
        return v

    @field_validator("name", "company", "age_group")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()


class ParticipantCreate(ParticipantBase):
    pass


class Participant(ParticipantBase):
    id: str


class Weights(BaseModel):
    company: float = 1000.0
    prev: float = 800.0
    gender: float = 3.0
    age: float = 2.0
    mbti: float = 1.0


class ConstraintConfig(BaseModel):
    num_tables: Optional[int] = Field(default=None, ge=1)
    table_size: Optional[int] = Field(default=None, ge=1)
    weights: Weights = Field(default_factory=Weights)
    seed: Optional[int] = None


class TableOut(BaseModel):
    index: int
    member_ids: list[str]


class ViolationOut(BaseModel):
    type: str
    table_index: int
    member_ids: list[str]
    detail: dict[str, Any]


class ScoreBreakdownOut(BaseModel):
    company: float
    prev_table: float
    gender: float
    age: float
    mbti: float
    total: float


class RoundOut(BaseModel):
    round_number: int
    tables: list[TableOut]
    score: float
    score_breakdown: ScoreBreakdownOut
    violations: list[ViolationOut]
    warnings: list[str]
    per_table_balance: list[dict[str, Any]]
    seed_used: int
    hard_violation_count: int
    committed: bool = False


class MetPairOut(BaseModel):
    members: list[str]
    count: int


class SessionStateOut(BaseModel):
    session_id: str
    participants: list[Participant]
    config: ConstraintConfig
    rounds: list[RoundOut]
    met_pairs: list[MetPairOut]


# ---- 요청 바디 ----


class PreviewRequest(BaseModel):
    """미리보기 요청. config 미지정 시 세션에 저장된 설정 사용."""

    config: Optional[ConstraintConfig] = None


class CommitRequest(BaseModel):
    """미리보기에서 본 정확한 배치를 확정. tables 는 멤버 id 리스트."""

    tables: list[list[str]]
    seed_used: int


class SessionCreated(BaseModel):
    session_id: str
