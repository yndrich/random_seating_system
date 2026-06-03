#!/usr/bin/env python3
"""솔버 수렴/품질 측정 — 순수 알고리즘 계층을 직접 import해 통계를 낸다.

시뮬레이티드 어닐링은 확률적이라 단발 실행으로는 회귀를 못 잡는다. 이 스크립트는 여러
문제 크기 × 여러 시드로 solve()를 반복 실행해 비용(평균±표준편차), 하드 위반 수, 실행
시간을 집계한다. baseline과 비교하면 솔버 파라미터/비용 함수를 바꿨을 때 좋아졌는지
나빠졌는지 정량적으로 확인할 수 있다.

API/HTTP를 거치지 않고 `app.assignment.solve`를 바로 부르므로 백엔드 서버가 떠 있을
필요가 없다.

사용:
    # backend/ 에서 실행하거나, 어디서든 실행(스크립트가 backend를 자동 탐색)
    ../.venv/bin/python ../.claude/skills/solver-eval/scripts/solver_eval.py
    .venv/bin/python .claude/skills/solver-eval/scripts/solver_eval.py \
        --sizes 12,24,48 --seeds 8 --tables-divisor 4 --save baseline.json
    .venv/bin/python .claude/skills/solver-eval/scripts/solver_eval.py --baseline baseline.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

_HARD_TYPES = ("same_company", "prev_same_table")
_COMPANIES = ["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark"]
_GENDERS = ["male", "female", "other"]
_AGES = ["20s", "30s", "40s", "50s", "60s+"]
_MBTIS = ["INTJ", "ENFP", "ISTJ", "ESFP", "INFP", "ESTJ", "ENTP", "ISFJ"]


def _find_backend() -> Path:
    """app/assignment 를 가진 backend 디렉터리를 스크립트/CWD 상위에서 탐색."""
    candidates = []
    here = Path(__file__).resolve()
    # 레포 구조: <root>/.claude/skills/solver-eval/scripts/solver_eval.py → parents[4] == root
    if len(here.parents) > 4:
        candidates.append(here.parents[4] / "backend")
    for start in (here, Path.cwd().resolve()):
        for anc in [start, *start.parents]:
            candidates.append(anc / "backend")
            candidates.append(anc)  # 이미 backend 안에서 실행한 경우
    for cand in candidates:
        if (cand / "app" / "assignment" / "__init__.py").exists():
            return cand
    print("✗ backend 디렉터리를 찾지 못했습니다(app/assignment 없음).", file=sys.stderr)
    raise SystemExit(2)


def _make_people(n: int, rng: random.Random, person_cls):
    """현실적인 제약이 생기도록 회사/성별/연령/MBTI를 섞어 n명 생성."""
    return [
        person_cls(
            id=f"p{i:03d}",
            gender=rng.choice(_GENDERS),
            company=rng.choice(_COMPANIES),
            age_group=rng.choice(_AGES),
            mbti=rng.choice(_MBTIS),
            name=f"P{i:03d}",
        )
        for i in range(n)
    ]


def _eval_size(solve, person_cls, n: int, num_tables: int, seeds: int) -> dict:
    costs, hard_counts, times = [], [], []
    for s in range(seeds):
        rng = random.Random(1000 + s)  # 입력 생성 시드(재현 가능)
        people = _make_people(n, rng, person_cls)
        t0 = time.perf_counter()
        result = solve(people, num_tables=num_tables, seed=s)  # 솔버 시드는 s
        elapsed = time.perf_counter() - t0
        costs.append(result.cost)
        hard_counts.append(sum(1 for v in result.violations if v.type in _HARD_TYPES))
        times.append(elapsed)
    return {
        "n": n,
        "num_tables": num_tables,
        "seeds": seeds,
        "cost_mean": statistics.mean(costs),
        "cost_stdev": statistics.stdev(costs) if len(costs) > 1 else 0.0,
        "cost_min": min(costs),
        "cost_max": max(costs),
        "hard_mean": statistics.mean(hard_counts),
        "hard_max": max(hard_counts),
        "time_mean_ms": statistics.mean(times) * 1000,
    }


def _print_table(rows: list[dict], baseline: dict | None) -> None:
    base_by_n = {r["n"]: r for r in baseline["rows"]} if baseline else {}
    hdr = f"{'n':>5} {'조':>4} {'cost(mean±sd)':>22} {'hard(mean/max)':>16} {'time(ms)':>10}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        cost = f"{r['cost_mean']:.1f}±{r['cost_stdev']:.1f}"
        hard = f"{r['hard_mean']:.2f}/{r['hard_max']}"
        line = f"{r['n']:>5} {r['num_tables']:>4} {cost:>22} {hard:>16} {r['time_mean_ms']:>10.1f}"
        b = base_by_n.get(r["n"])
        if b:
            dc = r["cost_mean"] - b["cost_mean"]
            dh = r["hard_mean"] - b["hard_mean"]
            mark = "↑나쁨" if dc > 1e-6 else ("↓좋음" if dc < -1e-6 else "≈")
            line += f"   Δcost={dc:+.1f}({mark}) Δhard={dh:+.2f}"
        print(line)


def main() -> int:
    ap = argparse.ArgumentParser(description="솔버 수렴/품질 측정")
    ap.add_argument("--sizes", default="12,24,48", help="콤마구분 참가자 수 목록")
    ap.add_argument("--seeds", type=int, default=8, help="크기별 반복(시드) 횟수")
    ap.add_argument("--tables-divisor", type=int, default=4,
                    help="조 개수 = ceil(n / divisor)")
    ap.add_argument("--baseline", help="비교할 baseline JSON 경로")
    ap.add_argument("--save", help="이번 결과를 baseline JSON으로 저장할 경로")
    args = ap.parse_args()

    backend = _find_backend()
    sys.path.insert(0, str(backend))
    from app.assignment import Person, solve  # noqa: E402

    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    rows = []
    for n in sizes:
        num_tables = max(1, math.ceil(n / args.tables_divisor))
        print(f"… n={n}, 조={num_tables}, 시드 {args.seeds}회 실행 중", file=sys.stderr)
        rows.append(_eval_size(solve, Person, n, num_tables, args.seeds))

    baseline = None
    if args.baseline:
        bp = Path(args.baseline)
        if bp.exists():
            baseline = json.loads(bp.read_text())
            print(f"\n[baseline: {args.baseline}]")
        else:
            print(f"⚠️ baseline 파일 없음: {args.baseline} (비교 생략)", file=sys.stderr)

    print()
    _print_table(rows, baseline)
    print("\n해석: cost_stdev가 크면 시드 간 편차가 크다(수렴 불안정). hard_max>0이면 어떤"
          "\n시드에서 하드 제약 위반이 남았다는 뜻 — 입력이 만족 가능한데도 그렇다면 회귀 의심.")

    out = {"sizes": sizes, "seeds": args.seeds, "rows": rows}
    if args.save:
        Path(args.save).write_text(json.dumps(out, indent=2))
        print(f"\n💾 baseline 저장: {args.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
