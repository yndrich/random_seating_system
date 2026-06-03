"""공용 API 의존성."""

from __future__ import annotations

from fastapi import Header, HTTPException

from ..core.session_store import SessionState, store


def require_session(x_session_id: str | None = Header(default=None)) -> SessionState:
    """X-Session-Id 헤더로 기존 세션을 찾는다. 없으면 404.

    프론트는 앱 시작 시 POST /api/session 으로 세션을 만들고 이후 모든 요청에
    이 헤더를 동봉한다.
    """
    if not x_session_id:
        raise HTTPException(
            status_code=400, detail="X-Session-Id 헤더가 필요합니다."
        )
    state = store.get(x_session_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail="세션을 찾을 수 없습니다. 새 세션을 생성하세요.",
        )
    return state
