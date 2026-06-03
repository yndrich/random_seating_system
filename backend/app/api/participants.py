"""참가자 CRUD 엔드포인트."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..core.session_store import SessionState
from ..models import schemas
from .deps import require_session

router = APIRouter(prefix="/api/participants", tags=["participants"])


@router.get("", response_model=list[schemas.Participant])
def list_participants(
    state: SessionState = Depends(require_session),
) -> list[schemas.Participant]:
    return state.participants


@router.post("", response_model=schemas.Participant, status_code=201)
def add_participant(
    body: schemas.ParticipantCreate,
    state: SessionState = Depends(require_session),
) -> schemas.Participant:
    with state.lock:
        participant = schemas.Participant(id=uuid.uuid4().hex, **body.model_dump())
        state.participants.append(participant)
        return participant


@router.post("/bulk", response_model=list[schemas.Participant], status_code=201)
def add_participants_bulk(
    body: list[schemas.ParticipantCreate],
    state: SessionState = Depends(require_session),
) -> list[schemas.Participant]:
    with state.lock:
        created = [
            schemas.Participant(id=uuid.uuid4().hex, **p.model_dump()) for p in body
        ]
        state.participants.extend(created)
        return created


@router.put("/{pid}", response_model=schemas.Participant)
def update_participant(
    pid: str,
    body: schemas.ParticipantCreate,
    state: SessionState = Depends(require_session),
) -> schemas.Participant:
    with state.lock:
        existing = state.find_participant(pid)
        if existing is None:
            raise HTTPException(status_code=404, detail="참가자를 찾을 수 없습니다.")
        updated = schemas.Participant(id=pid, **body.model_dump())
        idx = state.participants.index(existing)
        state.participants[idx] = updated
        return updated


@router.delete("/{pid}", status_code=204, response_model=None)
def delete_participant(
    pid: str,
    state: SessionState = Depends(require_session),
) -> None:
    with state.lock:
        existing = state.find_participant(pid)
        if existing is None:
            raise HTTPException(status_code=404, detail="참가자를 찾을 수 없습니다.")
        state.participants.remove(existing)
        # 삭제된 참가자가 낀 동석 이력 정리
        state.met_count = {
            pair: c for pair, c in state.met_count.items() if pid not in pair
        }
