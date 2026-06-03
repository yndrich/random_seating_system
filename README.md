# 🎲 랜덤 조 배정 시스템

참가자를 조별 테이블로 **랜덤 + 제약 최적화** 배정하는 웹 애플리케이션.
단순 랜덤이 아니라 다음을 동시에 고려한다.

- **하드 제약(가능한 한 준수, 위반 시 경고)**
  - 같은 회사 사람은 같은 조에 배정하지 않음
  - 이전 회차에 같은 조였던 사람은 다시 만나지 않게 함 (다중 라운드 로테이션)
- **소프트 제약(균형 분산)**
  - 조별 남녀 비율 균형
  - 연령대 분산 (한 조에 같은 연령대 쏠림 방지)
  - MBTI 분산 (E/I·S/N·T/F·J/P 4축 균형)

제약상 완벽한 배정이 불가능하면 **최소 위반**으로 배치하고 결과에 경고를 표시한다.

## 구조

```
backend/   FastAPI + 순수 Python 배정 알고리즘 (시뮬레이티드 어닐링)
frontend/  React + Vite + TypeScript 단일 페이지 앱
```

- 알고리즘은 `backend/app/assignment/` 에 UI/IO 의존 없이 격리되어 단위테스트가 쉽다.
- 상태는 **서버 인메모리 세션**으로 관리한다(영구 DB 없음). 프로세스 재시작 시 휘발된다.
- 배정은 비용(cost) 최소화 문제로, 하드 제약은 큰 페널티 + 위반 리포팅, 소프트 제약은
  균형 점수로 평가한다. 세부 설계는 `backend/app/assignment/scoring.py` 참고.

## 실행 방법

### 1) 백엔드

```bash
# 가상환경 생성 + 의존성 설치
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt

# (만약 venv 에 pip 이 없다는 오류가 나면 — ensurepip 미설치 환경)
#   curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
#   .venv/bin/python /tmp/get-pip.py
#   다시 위의 pip install 실행

# 서버 실행
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

- API 문서(Swagger): http://localhost:8000/docs
- 헬스체크: http://localhost:8000/api/health

### 2) 프론트엔드

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (/api 요청은 8000 으로 프록시됨)
```

브라우저에서 http://localhost:5173 접속 → 참가자 입력 → 배정 설정 → 회차 편성 → 확정.

## 테스트

```bash
cd backend
../.venv/bin/python -m pytest -v
```

- `test_balance.py` — 균형/분산 메트릭 경계값·단조성
- `test_scoring.py` — 점수 분해 합산 일치, 증분(델타) 평가 정확성
- `test_solver_hard_constraints.py` — 하드 제약 만족/최소위반, 성비 균형, 재현성, 불변식
- `test_multi_round.py` — met_count 누적/회피/롤백
- `test_api.py` — 엔드포인트 happy path + 경계(인원<조수)

## 사용 흐름 (UI)

1. **참가자**: 이름/회사/성별/연령대/MBTI 입력(엔터로 연속 추가). 총원·성비·회사 수 요약.
2. **배정**: "조 개수" 또는 "조당 인원" 지정, (선택) 시드·가중치 조정.
   - **이번 회차 편성** → 미리보기 생성
   - **🔀 다시 섞기** → 다른 시드로 재편성
   - **✓ 이 결과로 확정** → 확정 시에만 동석 이력에 반영(다음 회차 회피에 사용)
3. **결과·이력**: 조별 카드(멤버·회사색·성별/연령/MBTI), 균형 미니바, 위반 경고(하드=빨강,
   소프트=노랑). 회차별 **롤백** 가능.

## API 요약

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/session` | 세션 생성 (session_id 발급) |
| GET | `/api/session` | 세션 전체 상태 |
| POST | `/api/session/reset` | 초기화 |
| GET/POST | `/api/participants` | 참가자 조회/추가 |
| PUT/DELETE | `/api/participants/{id}` | 수정/삭제 |
| PUT | `/api/config` | 제약 설정 저장 |
| POST | `/api/rounds/preview` | 미리보기(미확정) |
| POST | `/api/rounds/commit` | 확정 + 동석 이력 갱신 |
| GET | `/api/rounds` | 라운드 목록 |
| DELETE | `/api/rounds/{n}` | 라운드 롤백 |

모든 데이터 요청은 `X-Session-Id` 헤더가 필요하다(프론트가 자동 처리).
