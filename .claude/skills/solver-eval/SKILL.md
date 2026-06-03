---
name: solver-eval
description: >-
  랜덤 조 배정 시스템의 시뮬레이티드 어닐링 솔버 품질을 정량 측정한다. 여러 문제 크기 ×
  여러 시드로 solve()를 반복 실행해 비용(평균±표준편차)·하드 위반 수·실행 시간을 집계하고,
  저장한 baseline과 비교해 회귀/개선을 판정한다. 솔버는 확률적이라 단발 실행으로는 변경의
  영향을 알 수 없으므로, 비용 함수·가중치·냉각 스케줄·재시작 수·반복 수 등을 건드린 뒤
  검증할 때 쓴다. 사용자가 "솔버 성능 측정", "수렴 확인", "어닐링 튜닝했는데 좋아졌나",
  "배정 품질 벤치마크", "시드별 편차 보고싶다", "하드 위반이 남는지", "느려졌나 빨라졌나",
  "비용 함수 바꾼 거 회귀 확인" 같은 요청을 하면 — 명시적으로 이 skill을 부르지 않더라도
  — 이 skill을 사용할 것. 알고리즘 정확성(분해 불변식 등) 단위 검증은 pytest 영역이다.
---

# 솔버 수렴/품질 측정 (solver-eval)

SA 솔버(`backend/app/assignment/solver.py`)는 시드 없이는 무작위, 시드를 줘도 입력 분포에
따라 비용이 달라진다. 그래서 "솔버를 바꿨더니 나아졌나?"는 **반복 실행 통계**로만 답할 수
있다. 이 skill은 순수 알고리즘 계층(`app.assignment.solve`)을 HTTP 없이 직접 불러
크기·시드를 쓸어 비용/위반/시간을 집계한다. 설계 배경(증분 평가·다중 재시작)은
`backend/app/assignment/CLAUDE.md` 참고.

## 무엇을 측정하나

- **cost (mean ± stdev)** — 시드 간 평균 비용과 편차. stdev가 크면 수렴이 불안정(같은
  입력 난이도인데 시드 운에 따라 결과가 출렁임).
- **hard (mean / max)** — 하드 위반 수(`_HARD_TYPES`: 같은 회사·이전 동석). 만족 가능한
  입력인데 `hard_max > 0`이면 솔버가 최적해를 못 찾는다는 신호 → 회귀 의심.
- **time (ms)** — 크기별 평균 풀이 시간. 반복 수(`max_iters`)나 재시작 수를 바꾸면 여기로
  드러난다.

## 기본 사용

```bash
# 어디서 실행하든 스크립트가 backend/ 를 자동 탐색해 app.assignment 를 import 한다
.venv/bin/python .claude/skills/solver-eval/scripts/solver_eval.py
```

기본은 크기 `12,24,48`, 각 8시드. 출력은 크기별 한 줄 표다.

## baseline 비교 (회귀 판정의 핵심)

솔버/비용 함수를 바꾸기 **전에** 현재 상태를 baseline으로 저장하고, 바꾼 **뒤** 같은
설정으로 다시 돌려 비교한다:

```bash
# 변경 전: 기준선 저장
.venv/bin/python .claude/skills/solver-eval/scripts/solver_eval.py \
    --sizes 12,24,48 --seeds 8 --save /tmp/solver_baseline.json

# (여기서 solver.py / scoring.py / 가중치 등을 수정)

# 변경 후: 같은 설정으로 비교
.venv/bin/python .claude/skills/solver-eval/scripts/solver_eval.py \
    --sizes 12,24,48 --seeds 8 --baseline /tmp/solver_baseline.json
```

비교 시 각 줄 끝에 `Δcost`(↓좋음/↑나쁨)와 `Δhard`가 붙는다. 입력 생성 시드와 솔버 시드가
고정돼 있어 **비교가 결정적**이다 — 같은 코드 + 같은 설정이면 Δ는 0이어야 한다.

> 주의: 비교는 `--sizes`/`--seeds`/`--tables-divisor`가 baseline과 동일할 때만 의미 있다.
> 다르게 주면 사과-오렌지 비교가 된다.

## 옵션

| 옵션 | 기본 | 의미 |
|---|---|---|
| `--sizes` | `12,24,48` | 콤마 구분 참가자 수 목록 |
| `--seeds` | `8` | 크기별 반복(시드) 횟수 — 클수록 통계가 안정되나 느려짐 |
| `--tables-divisor` | `4` | 조 개수 = ceil(n / divisor) (조당 약 divisor명) |
| `--save PATH` | — | 이번 결과를 baseline JSON으로 저장 |
| `--baseline PATH` | — | 해당 JSON과 비교(Δ 표시) |

## 언제 쓰나

- `solver.py`의 `restarts`·`max_iters`·`t_start`/`t_end`(냉각) 튜닝 후 품질/속도 트레이드오프 확인
- `scoring.py`/`balance.py`의 비용 함수나 가중치 기본값 변경의 영향 측정
- `add-constraint`로 새 제약을 넣은 뒤, 새 항목이 실제로 비용/위반에 반영돼 배치를 바꾸는지 확인
- 큰 입력(예: `--sizes 60,120`)에서 시간이 허용 범위인지 점검

## 한계 (정직하게)

- 이건 **상대 비교 도구**다. 절대 비용 값 자체에는 의미 부여가 어렵다(입력 분포 의존).
- 입력은 합성 데이터(랜덤 분포)다. 특정 실데이터 패턴을 재현하려면 `_make_people`을
  바꾸거나, 실제 시나리오는 `dev-up`의 API 스모크로 별도 확인한다.
- 정확성(분해 합 일치·증분 델타·불변식)은 이 도구가 아니라 `cd backend && pytest`가 본다.
