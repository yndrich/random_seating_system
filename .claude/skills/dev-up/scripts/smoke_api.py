#!/usr/bin/env python3
"""백엔드(8000) API 스모크 테스트 — 의존성 없는 순수 stdlib(urllib).

세션 생성 → 참가자 bulk 추가 → preview → commit → rounds 조회 → met_count 증가까지
전체 라운드 수명주기를 실제 HTTP로 한 바퀴 돌려 백엔드가 살아있고 계약대로 동작하는지
확인한다. 실패 시 비-0 종료코드와 함께 어디서 깨졌는지 출력한다.

사용:
    .venv/bin/python .claude/skills/dev-up/scripts/smoke_api.py
    .venv/bin/python .claude/skills/dev-up/scripts/smoke_api.py --base http://127.0.0.1:8000 -n 12 --tables 3
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# 결정적 입력: 회사가 겹치고 성비/연령/MBTI가 섞이도록 구성
_COMPANIES = ["Acme", "Globex", "Initech", "Umbrella"]
_GENDERS = ["male", "female", "other"]
_AGES = ["20s", "30s", "40s", "50s"]
_MBTIS = ["INTJ", "ENFP", "ISTJ", "ESFP", "INFP", "ESTJ", "ENTP", "ISFJ"]


def _make_people(n: int) -> list[dict]:
    return [
        {
            "name": f"P{i:02d}",
            "gender": _GENDERS[i % len(_GENDERS)],
            "company": _COMPANIES[i % len(_COMPANIES)],
            "age_group": _AGES[i % len(_AGES)],
            "mbti": _MBTIS[i % len(_MBTIS)],
        }
        for i in range(n)
    ]


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.session_id: str | None = None

    def _req(self, method: str, path: str, body=None) -> object:
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.session_id:
            req.add_header("X-Session-Id", self.session_id)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} → HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"{method} {path} 연결 실패: {e.reason}. 백엔드(8000)가 떠 있나요? "
                f"`cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000`"
            ) from e


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  ✗ 실패: {msg}", file=sys.stderr)
        raise SystemExit(1)
    print(f"  ✓ {msg}")


def main() -> int:
    ap = argparse.ArgumentParser(description="백엔드 API 스모크 테스트")
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="백엔드 베이스 URL")
    ap.add_argument("-n", type=int, default=12, help="참가자 수")
    ap.add_argument("--tables", type=int, default=3, help="조 개수")
    args = ap.parse_args()

    c = Client(args.base)

    print("1) health 확인")
    health = c._req("GET", "/api/health")
    _check(isinstance(health, dict) and health.get("status") == "ok", "GET /api/health == ok")

    print("2) 세션 생성")
    created = c._req("POST", "/api/session")
    c.session_id = created["session_id"]
    _check(bool(c.session_id), f"세션 생성됨 ({c.session_id[:8]}…)")

    print(f"3) 참가자 {args.n}명 bulk 추가")
    people = _make_people(args.n)
    added = c._req("POST", "/api/participants/bulk", people)
    _check(len(added) == args.n, f"{len(added)}명 추가됨")

    print("4) 1회차 미리보기(preview)")
    cfg = {"num_tables": args.tables, "table_size": None,
           "weights": {"company": 1000, "prev": 800, "gender": 3, "age": 2, "mbti": 1},
           "seed": 42}
    preview = c._req("POST", "/api/rounds/preview", {"config": cfg})
    _check(len(preview["tables"]) == args.tables, f"{len(preview['tables'])}개 조 생성")
    _check(preview["committed"] is False, "preview는 미확정(committed=false)")
    seated = sum(len(t["member_ids"]) for t in preview["tables"])
    _check(seated == args.n, f"모든 참가자 배정됨 ({seated}/{args.n})")

    print("5) preview는 met_count를 바꾸지 않아야 함")
    state = c._req("GET", "/api/session")
    _check(len(state["met_pairs"]) == 0, "commit 전 met_pairs 비어있음")

    print("6) 확정(commit)")
    tables = [t["member_ids"] for t in preview["tables"]]
    committed = c._req("POST", "/api/rounds/commit",
                       {"tables": tables, "seed_used": preview["seed_used"]})
    _check(committed["committed"] is True, "commit됨(committed=true)")
    _check(committed["round_number"] == 1, "round_number == 1")

    print("7) commit 후 met_count 증가 확인")
    state2 = c._req("GET", "/api/session")
    _check(len(state2["met_pairs"]) > 0, f"met_pairs 생성됨({len(state2['met_pairs'])}쌍)")
    _check(len(state2["rounds"]) == 1, "rounds에 1개 기록")

    print("8) 2회차 미리보기 — 이전 동석 페널티 반영")
    preview2 = c._req("POST", "/api/rounds/preview", {"config": {**cfg, "seed": 7}})
    _check(len(preview2["tables"]) == args.tables, "2회차도 정상 편성")

    print("\n✅ 스모크 통과 — 백엔드가 살아있고 라운드 수명주기가 계약대로 동작합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
