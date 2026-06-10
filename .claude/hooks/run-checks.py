#!/usr/bin/env python3
"""커밋 전 검증 게이트 — 이 프로젝트의 lint·build·test를 돌리고, 하나라도 실패하면 커밋을 막는다.

이 프로젝트의 검증 실체(전용 린터가 따로 없다):
  - lint + build : frontend  `npm run build`  (= tsc --noEmit[타입체크=lint] && vite build)
  - test         : backend   `.venv/bin/python -m pytest -q`
  (backend엔 별도 파이썬 린터가 없고, frontend엔 테스트가 없다. CLAUDE.md 참고.)

두 가지 방식으로 동작한다(하나의 스크립트):
  1) Claude Code PreToolUse 훅 — settings.json에서 Bash 매처로 등록. Claude가 `git commit`을
     실행하기 직전 stdin으로 훅 JSON을 받는다. commit이 아니면 즉시 통과(exit 0), commit이면
     검사를 돌려 실패 시 exit 2로 커밋을 막는다(stderr가 Claude에게 전달됨).
  2) git pre-commit 훅 — 아래처럼 설치하면 사람이 직접 `git commit` 할 때도 동일 게이트가 돈다:
         chmod +x .claude/hooks/run-checks.py
         ln -sf "$(pwd)/.claude/hooks/run-checks.py" .git/hooks/pre-commit
     git가 호출하면 stdin이 비어 있거나 tty라, JSON이 없으면 항상 검사를 돌린다.

탈출구: `git commit --no-verify` (Claude 경로에서도 명령에 --no-verify가 있으면 건너뛴다).
검증 도구가 없으면(예: .venv/node_modules 부재) 해당 검사는 경고만 내고 통과시킨다 — 커밋을
도구 부재로 막지 않는다. 실패는 exit 2로 통일(git·Claude 양쪽 모두 차단으로 해석).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CHECK_TIMEOUT = 600  # 초. pytest + vite build 합산 상한.
# 한 명령 세그먼트 안의 `git [옵션/-c key=val ...] commit` 을 탐지(commit-graph 등은 제외).
_GIT_COMMIT_RE = re.compile(r"\bgit\b(?:\s+(?:-{1,2}\S+|\S+=\S+))*\s+commit\b(?!-)")
# 입력이 "구조화된 Claude 훅 JSON"임을 알려주는 표지 키. 하나라도 있으면 Claude 이벤트로 확정하고,
# 그 안에서 git commit이 식별될 때만 검사한다(모르는 이벤트/도구로 무거운 게이트를 돌리지 않음).
_CLAUDE_HOOK_KEYS = ("hook_event_name", "tool_name", "tool_input", "session_id")


def project_root() -> Path:
    """루트 디렉터리. Claude가 주는 CLAUDE_PROJECT_DIR 우선, 없으면 스크립트 위치로 역산."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    # <root>/.claude/hooks/run-checks.py  → parents[2] == <root> (심링크도 resolve로 따라감)
    return Path(__file__).resolve().parents[2]


def venv_python(root: Path) -> Path | None:
    for rel in (".venv/bin/python", ".venv/Scripts/python.exe"):
        p = root / rel
        if p.exists():
            return p
    return None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """명령을 돌려 (반환코드, 합쳐진 출력)을 준다. 실행 자체가 불가하면 (-1, 사유)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=CHECK_TIMEOUT,
        )
        return proc.returncode, proc.stdout or ""
    except FileNotFoundError as e:
        return -1, f"실행 파일을 찾을 수 없음: {e}"
    except subprocess.TimeoutExpired:
        return -1, f"시간 초과({CHECK_TIMEOUT}s)로 중단"


def tail(text: str, n: int = 40) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:]) if len(lines) > n else "\n".join(lines)


def run_gauntlet(root: Path) -> list[dict]:
    """검사들을 돌려 결과 리스트를 준다. status: 'pass' | 'fail' | 'skip'."""
    results: list[dict] = []

    # --- backend test: pytest (정확성/불변식) ---
    backend = root / "backend"
    py = venv_python(root)
    if not backend.is_dir():
        results.append({"name": "backend pytest", "status": "skip", "why": "backend/ 없음"})
    elif py is None:
        results.append({"name": "backend pytest", "status": "skip",
                        "why": ".venv 인터프리터 없음 (.venv/bin/python). `python -m venv .venv` 후 의존성 설치"})
    else:
        # conftest가 app 패키지를 import 가능하게 하므로 반드시 backend/ 에서 실행한다.
        code, out = run([str(py), "-m", "pytest", "-q"], cwd=backend)
        results.append({
            "name": "backend pytest", "cmd": "cd backend && ../.venv/bin/python -m pytest -q",
            "status": "pass" if code == 0 else "fail", "output": out,
        })

    # --- frontend lint + build: npm run build (tsc --noEmit && vite build) ---
    frontend = root / "frontend"
    if not (frontend / "package.json").is_file():
        results.append({"name": "frontend build", "status": "skip", "why": "frontend/package.json 없음"})
    elif not (frontend / "node_modules").is_dir():
        results.append({"name": "frontend build", "status": "skip",
                        "why": "node_modules 없음. `cd frontend && npm install` 후 다시 시도"})
    else:
        code, out = run(["npm", "run", "build"], cwd=frontend)
        results.append({
            "name": "frontend build (tsc+vite)", "cmd": "cd frontend && npm run build",
            "status": "pass" if code == 0 else "fail", "output": out,
        })

    return results


def format_failure(results: list[dict]) -> str:
    icon = {"pass": "✅", "fail": "❌", "skip": "⚠️"}
    lines = ["✋ 커밋 전 검증 실패 — 아래 검사가 통과해야 커밋됩니다:", ""]
    for r in results:
        head = f"{icon[r['status']]} {r['name']}"
        if r.get("cmd"):
            head += f"  ({r['cmd']})"
        lines.append(head)
        if r["status"] == "fail":
            lines.append("─" * 60)
            lines.append(tail(r.get("output", "")))
            lines.append("─" * 60)
        elif r["status"] == "skip":
            lines.append(f"  건너뜀: {r.get('why', '')}")
    lines += ["", "수정 후 다시 커밋하세요. 의도적으로 건너뛰려면: git commit --no-verify"]
    return "\n".join(lines)


def should_check_from_claude_payload(raw: str) -> bool | None:
    """Claude 훅 JSON을 보고 검사 여부 결정.

    True=검사, False=통과(무관), None=Claude 훅 JSON이 아님(→ 호출자가 안전판단).

    표지 키(_CLAUDE_HOOK_KEYS)가 하나라도 있으면 Claude 훅 이벤트로 '확정'하고, 그 안에서
    Bash·git commit이 명확히 식별될 때만 True. tool_input이 없거나 다른 도구/이벤트면 False(통과)다 —
    훅이 다른 이벤트로 재사용되거나 페이로드 스키마가 바뀌어도 무거운 게이트가 헛돌지 않게 한다.
    """
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not any(k in data for k in _CLAUDE_HOOK_KEYS):
        return None  # Claude 훅으로 인식 안 됨(빈 stdin·비JSON 등) → 호출자가 안전판단
    # 여기부터는 Claude 훅 JSON으로 확정 → 모르는 도구/이벤트는 '무관(통과)'으로 본다.
    if data.get("tool_name") != "Bash":
        return False  # Bash가 아닌 도구/이벤트는 우리 관심사 아님 → 통과
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    if not _GIT_COMMIT_RE.search(cmd):
        return False  # git commit이 아닌 Bash 명령 → 통과
    if "--no-verify" in cmd:
        return False  # 명시적 우회 존중
    return True


def main() -> int:
    # 모드 판정: --git-hook 강제 / tty(사람의 git) / 파이프된 Claude JSON
    if "--git-hook" in sys.argv[1:]:
        do_check = True
    elif sys.stdin.isatty():
        # 사람이 터미널에서 git commit → stdin이 tty. 읽지 않고(블로킹 방지) 검사한다.
        do_check = True
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            do_check = True  # 파이프지만 비어있음(=git 훅 등) → 검사
        else:
            decision = should_check_from_claude_payload(raw)
            if decision is None:
                do_check = True   # Claude 훅 JSON 아님(비JSON·비표지 = git 훅 경로) → 안전하게 검사
            else:
                do_check = decision

    if not do_check:
        return 0  # 통과(검사 불필요)

    results = run_gauntlet(project_root())
    if any(r["status"] == "fail" for r in results):
        print(format_failure(results), file=sys.stderr)
        return 2  # git·Claude 양쪽 모두 '차단'으로 해석
    return 0


if __name__ == "__main__":
    sys.exit(main())
