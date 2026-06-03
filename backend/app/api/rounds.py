"""라운드 미리보기/확정/조회/롤백 및 제약 설정 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..assignment import SolveError, SolveResult, evaluate_tables, solve
from ..assignment import Weights as AlgWeights
from ..assignment.history import add_round, rebuild_from_rounds
from ..core.session_store import SessionState
from ..models import schemas
from .deps import require_session

router = APIRouter(prefix="/api", tags=["rounds"])

_HARD_TYPES = ("same_company", "prev_same_table")


def _alg_weights(w: schemas.Weights) -> AlgWeights:
    return AlgWeights(
        company=w.company, prev=w.prev, gender=w.gender, age=w.age, mbti=w.mbti
    )


def _result_to_round(
    result: SolveResult, round_number: int, committed: bool
) -> schemas.RoundOut:
    bd = result.breakdown
    return schemas.RoundOut(
        round_number=round_number,
        tables=[
            schemas.TableOut(index=i, member_ids=ids)
            for i, ids in enumerate(result.tables_ids)
        ],
        score=result.cost,
        score_breakdown=schemas.ScoreBreakdownOut(
            company=bd.company,
            prev_table=bd.prev_table,
            gender=bd.gender,
            age=bd.age,
            mbti=bd.mbti,
            total=bd.total,
        ),
        violations=[
            schemas.ViolationOut(
                type=v.type,
                table_index=v.table_index,
                member_ids=v.member_ids,
                detail=v.detail,
            )
            for v in result.violations
        ],
        warnings=result.warnings,
        per_table_balance=result.per_table_balance,
        seed_used=result.seed_used,
        hard_violation_count=sum(
            1 for v in result.violations if v.type in _HARD_TYPES
        ),
        committed=committed,
    )


@router.put("/config", response_model=schemas.ConstraintConfig)
def update_config(
    config: schemas.ConstraintConfig,
    state: SessionState = Depends(require_session),
) -> schemas.ConstraintConfig:
    with state.lock:
        state.config = config
        return state.config


@router.post("/rounds/preview", response_model=schemas.RoundOut)
async def preview_round(
    body: schemas.PreviewRequest,
    state: SessionState = Depends(require_session),
) -> schemas.RoundOut:
    with state.lock:
        if body.config is not None:
            state.config = body.config
        config = state.config
        persons = state.to_persons()
        met_count = dict(state.met_count)
        next_round_number = len(state.rounds) + 1

    if not persons:
        raise HTTPException(status_code=400, detail="참가자가 없습니다.")

    try:
        result = await run_in_threadpool(
            solve,
            persons,
            num_tables=config.num_tables,
            table_size=config.table_size,
            weights=_alg_weights(config.weights),
            met_count=met_count,
            seed=config.seed,
        )
    except SolveError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return _result_to_round(result, next_round_number, committed=False)


@router.post("/rounds/commit", response_model=schemas.RoundOut)
async def commit_round(
    body: schemas.CommitRequest,
    state: SessionState = Depends(require_session),
) -> schemas.RoundOut:
    with state.lock:
        persons = state.to_persons()
        met_count = dict(state.met_count)
        weights = _alg_weights(state.config.weights)

    try:
        result = await run_in_threadpool(
            evaluate_tables,
            persons,
            body.tables,
            weights=weights,
            met_count=met_count,
            seed_used=body.seed_used,
        )
    except SolveError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    with state.lock:
        round_number = len(state.rounds) + 1
        round_out = _result_to_round(result, round_number, committed=True)
        state.rounds.append(round_out)
        state.met_count = add_round(state.met_count, body.tables)
        return round_out


@router.get("/rounds", response_model=list[schemas.RoundOut])
def list_rounds(
    state: SessionState = Depends(require_session),
) -> list[schemas.RoundOut]:
    return state.rounds


@router.delete("/rounds/{round_number}", response_model=schemas.SessionStateOut)
def delete_round(
    round_number: int,
    state: SessionState = Depends(require_session),
) -> schemas.SessionStateOut:
    """라운드 롤백. 남은 라운드를 재번호 매기고 met_count 를 재구성."""
    from .session import _serialize_state

    with state.lock:
        target = next(
            (r for r in state.rounds if r.round_number == round_number), None
        )
        if target is None:
            raise HTTPException(status_code=404, detail="라운드를 찾을 수 없습니다.")
        state.rounds.remove(target)
        # 재번호 매기기
        for i, r in enumerate(state.rounds):
            r.round_number = i + 1
        # met_count 재구성
        state.met_count = rebuild_from_rounds(
            [[t.member_ids for t in r.tables] for r in state.rounds]
        )
        return _serialize_state(state)
