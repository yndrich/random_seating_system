#!/usr/bin/env python3
"""PostToolUse 훅 — 파일 편집 후 프로젝트 교차 관심사 리마인더.

이 프로젝트엔 손으로 맞춰야 하는 미러/불변식이 있어, 한 파일만 바꾸면 조용히 어긋난다.
편집된 파일 경로를 보고 관련 skill 사용을 상기시킨다(작업을 막지 않는 비차단 안내).

매핑:
  - backend/app/models/schemas.py 편집 → sync-types (types.ts 미러 점검)
  - frontend/src/types.ts          편집 → sync-types (schemas.py 미러 점검)
  - assignment 비용 파일(solver/scoring/balance) 편집 → solver-eval (회귀 측정)

매칭되지 않으면 아무 출력 없이 조용히 종료한다.
입력: stdin으로 PostToolUse 훅 JSON({"tool_input": {"file_path": ...}, ...}).
출력: 매칭 시 hookSpecificOutput.additionalContext 로 안내를 주입.
"""
import json
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # 입력 파싱 실패는 무시 — 훅이 사용자의 편집을 절대 방해하지 않게 한다.
        return 0

    tool_input = data.get("tool_input") or {}
    path = (tool_input.get("file_path") or "").replace("\\", "/")
    if not path:
        return 0

    reminders = []

    # --- 타입 미러 drift (sync-types) ---
    if path.endswith("backend/app/models/schemas.py"):
        reminders.append(
            "backend Pydantic 스키마(schemas.py)를 수정했습니다. "
            "frontend/src/types.ts는 자동생성이 아닌 수동 미러라 어긋날 수 있습니다. "
            "변경이 끝나면 sync-types skill(또는 type-syncer 서브에이전트)로 "
            "types.ts 정합성을 점검하세요."
        )
    if path.endswith("frontend/src/types.ts"):
        reminders.append(
            "프론트 타입 미러(types.ts)를 수정했습니다. "
            "backend/app/models/schemas.py와 어긋날 수 있으니 sync-types skill"
            "(또는 type-syncer 서브에이전트)로 양쪽 정합성을 점검하세요."
        )

    # --- 솔버 비용 함수/가중치 변경 (solver-eval) ---
    cost_files = (
        "backend/app/assignment/solver.py",
        "backend/app/assignment/scoring.py",
        "backend/app/assignment/balance.py",
    )
    if any(path.endswith(f) for f in cost_files):
        reminders.append(
            "솔버 비용/가중치 관련 파일을 수정했습니다. SA 솔버는 확률적이라 단발 "
            "실행으로는 영향을 알 수 없습니다. solver-eval skill(또는 solver-evaluator "
            "서브에이전트)로 baseline 대비 회귀/개선을 수치로 확인하고, 정확성은 "
            "`cd backend && pytest`로 검증하세요."
        )

    if not reminders:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(reminders),
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
