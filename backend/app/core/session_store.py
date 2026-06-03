"""세션 내 상태를 프로세스 메모리에 보관하는 인메모리 스토어.

영구 DB 없이 "현재 세션 내에서만" 이력을 유지한다(요구사항). 프로세스가 재시작되면
모두 휘발된다. 멀티탭/멀티유저 대비 세션 id 로 상태를 분리하고, 세션별 락으로
동시 변경을 보호한다.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from ..assignment import Person
from ..models import schemas


@dataclass
class SessionState:
    session_id: str
    participants: list[schemas.Participant] = field(default_factory=list)
    config: schemas.ConstraintConfig = field(
        default_factory=schemas.ConstraintConfig
    )
    rounds: list[schemas.RoundOut] = field(default_factory=list)
    # 누적 동석 횟수: {frozenset({id_a, id_b}): count}
    met_count: dict[frozenset[str], int] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    # ---- 편의 메서드 ----

    def find_participant(self, pid: str) -> schemas.Participant | None:
        return next((p for p in self.participants if p.id == pid), None)

    def to_persons(self) -> list[Person]:
        """알고리즘 계층용 Person 리스트로 변환."""
        return [
            Person(
                id=p.id,
                gender=p.gender.value,
                company=p.company,
                age_group=p.age_group,
                mbti=p.mbti,
                name=p.name,
            )
            for p in self.participants
        ]

    def met_pairs_out(self) -> list[schemas.MetPairOut]:
        return [
            schemas.MetPairOut(members=sorted(pair), count=count)
            for pair, count in self.met_count.items()
            if count > 0
        ]


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._global_lock = threading.Lock()

    def create(self) -> SessionState:
        sid = uuid.uuid4().hex
        state = SessionState(session_id=sid)
        with self._global_lock:
            self._sessions[sid] = state
        return state

    def get(self, sid: str) -> SessionState | None:
        with self._global_lock:
            return self._sessions.get(sid)

    def get_or_create(self, sid: str | None) -> SessionState:
        if sid:
            existing = self.get(sid)
            if existing is not None:
                return existing
        return self.create()

    def reset(self, sid: str) -> SessionState:
        """참가자/라운드/이력을 비우고 새 빈 상태로 교체(세션 id 유지)."""
        with self._global_lock:
            state = SessionState(session_id=sid)
            self._sessions[sid] = state
            return state


# 앱 전역 단일 스토어
store = SessionStore()
