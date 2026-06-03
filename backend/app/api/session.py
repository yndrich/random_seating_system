"""세션 생성/조회/초기화 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.session_store import SessionState, store
from ..models import schemas
from .deps import require_session

router = APIRouter(prefix="/api", tags=["session"])


def _serialize_state(state: SessionState) -> schemas.SessionStateOut:
    return schemas.SessionStateOut(
        session_id=state.session_id,
        participants=state.participants,
        config=state.config,
        rounds=state.rounds,
        met_pairs=state.met_pairs_out(),
    )


@router.post("/session", response_model=schemas.SessionCreated)
def create_session() -> schemas.SessionCreated:
    state = store.create()
    return schemas.SessionCreated(session_id=state.session_id)


@router.get("/session", response_model=schemas.SessionStateOut)
def get_session(
    state: SessionState = Depends(require_session),
) -> schemas.SessionStateOut:
    return _serialize_state(state)


@router.post("/session/reset", response_model=schemas.SessionStateOut)
def reset_session(
    state: SessionState = Depends(require_session),
) -> schemas.SessionStateOut:
    new_state = store.reset(state.session_id)
    return _serialize_state(new_state)
