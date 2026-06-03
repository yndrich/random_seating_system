---
name: sync-types
description: >-
  프론트엔드 타입 미러(frontend/src/types.ts)와 백엔드 Pydantic 스키마
  (backend/app/models/schemas.py) 사이의 drift를 점검하고 동기화한다. 두 파일은 자동생성이
  아니라 수동 미러라, 한쪽 스키마를 바꾸면 다른 쪽이 어긋나 프론트 빌드가 깨지거나 런타임
  필드가 undefined로 샌다. 사용자가 "타입 동기화", "types.ts와 schemas.py 맞춰줘",
  "프론트/백엔드 타입 안 맞는 것 같아", "스키마 바꿨는데 프론트도 갱신", "타입 미러 점검",
  "필드 추가했는데 어디 더 고쳐야 해" 같은 요청을 하거나, schemas.py 또는 types.ts를 수정한
  직후 정합성 확인이 필요할 때 — 명시적으로 이 skill을 부르지 않더라도 — 반드시 사용할 것.
---

# 타입 미러 동기화 (sync-types)

`frontend/src/types.ts`는 `backend/app/models/schemas.py`를 **손으로 맞춘 미러**다
(자동생성 아님 — `backend/CLAUDE.md`·`frontend/CLAUDE.md`에 명시된 위험). 한쪽을 바꾸면
다른 쪽이 조용히 어긋난다. 이 skill은 무엇이 진짜 drift이고 무엇이 정상적인 비대칭인지
구분해, 한 번에 정합성을 맞춘다.

## 작업 절차

1. 두 파일을 모두 읽는다: `backend/app/models/schemas.py`, `frontend/src/types.ts`.
2. 아래 **대응 표**대로 엔티티별 필드·타입·optional 여부·기본값을 비교한다.
3. 불일치를 한 표로 보고한 뒤, 사용자가 "고쳐줘"라고 하면 **어느 쪽을 진실로 볼지**
   먼저 확인한다(보통 방금 바꾼 쪽이 진실). 기본 방향: 백엔드 스키마를 진실로 보고
   프론트를 맞춘다. 다른 쪽을 바꿔야 하면 명시적으로 합의 후 진행.
4. 고친 뒤 `cd frontend && npm run build`로 타입체크(=lint)가 통과하는지 확인한다.

## 엔티티 대응 표 (Pydantic ↔ TypeScript)

| backend `schemas.py` | frontend `types.ts` | 비고 |
|---|---|---|
| `Gender(str, Enum)` male/female/other | `type Gender = "male"｜"female"｜"other"` | 값 3개 일치해야 |
| `ParticipantBase` (name·gender·company·age_group·mbti) | `ParticipantInput` | 필드명·타입 1:1 |
| `Participant`(= Base + `id`) | `Participant extends ParticipantInput { id }` | |
| `Weights` (company·prev·gender·age·mbti, float) | `Weights` (모두 number) | **기본값도** 비교 — 아래 참고 |
| `ConstraintConfig` (num_tables·table_size·weights·seed) | `ConstraintConfig` | `Optional[int]` ↔ `number｜null` |
| `TableOut` (index·member_ids) | `TableOut` | |
| `ViolationOut` (type·table_index·member_ids·detail) | `ViolationOut` | `type`은 TS에선 리터럴 유니온 — 새 위반 타입 추가 시 여기도 |
| `ScoreBreakdownOut` (company·prev_table·gender·age·mbti·total) | `ScoreBreakdown` | 필드명 `prev_table` 주의(가중치 키는 `prev`) |
| `RoundOut` | `RoundOut` | per_table_balance·hard_violation_count·committed 등 전부 |
| `MetPairOut` (members·count) | `MetPair` | 이름만 다름(Out 접미사 없음) |
| `SessionStateOut` | `SessionState` | met_pairs 필드 |

`per_table_balance`는 백엔드에서 `dict[str, Any]`(자유 형식)지만 프론트는 `TableBalance`
(size·gender·age_group·mbti_axes)로 구체화돼 있다. 이 구조는 `scoring.py`의
`table_balance_summary()`가 만든다 — drift 의심 시 그 함수도 함께 본다.

## 정상적인 비대칭 (drift 아님 — 건드리지 말 것)

- **프론트 전용 상수**: `DEFAULT_WEIGHTS`, `AGE_GROUPS`, `GENDER_LABEL` — 백엔드 대응
  없음. (단 `DEFAULT_WEIGHTS`는 아래 "기본값 drift" 대상.)
- **요청 바디 스키마**: `PreviewRequest`, `CommitRequest`, `SessionCreated`,
  `ParticipantCreate`는 `types.ts`에 직접 미러되지 않는다 — 프론트는 이들을
  `src/api/client.ts`의 함수 시그니처/인자로 표현한다. 클라이언트 호출부가 백엔드 바디
  형태와 맞는지는 client.ts에서 확인.

## 자주 새는 drift 유형 (집중 점검)

1. **새 필드 한쪽만 추가** — 가장 흔함. `Weights`/`ScoreBreakdown`/`Participant`에
   필드 추가 후 반대편 누락. (제약 추가 작업이면 `add-constraint` skill의 체크리스트와
   겹친다.)
2. **기본값 drift** — `schemas.py`의 `Weights` 필드 기본값(예: company=1000.0) ↔
   `types.ts`의 `DEFAULT_WEIGHTS` 값(company: 1000). 다르면 "새 세션"과 "미리보기"의
   기본 가중치가 달라지는 미묘한 버그. 숫자까지 대조할 것.
3. **optional/required 뒤집힘** — 백엔드 `Optional[int]`(= `… | None`)인데 프론트가
   `number`(널 불가)로 선언, 또는 그 반대. `num_tables`·`table_size`·`seed`가 단골.
4. **유니온 리터럴 누락** — `ViolationOut.type`에 백엔드가 새 문자열을 넣었는데
   프론트 유니온(`"same_company" | "prev_same_table"`)에 빠짐.
5. **breakdown 필드명 비대칭** — 가중치 키 `prev` vs 분해 필드 `prev_table`. 양쪽 다
   `prev_table`로 일치해야 정상.

## 보고 형식

발견한 불일치를 다음처럼 정리해 보여준다:

```
## 타입 미러 점검 결과
- ✅ ParticipantInput / ParticipantBase — 일치
- ❌ Weights — backend에 `region: 2.0` 있으나 types.ts `Weights`/`DEFAULT_WEIGHTS`에 없음
- ⚠️ ConstraintConfig.seed — backend Optional[int], frontend `number`(널 불가) → `number | null` 권장
```

이후 사용자 합의에 따라 수정하고 `npm run build` 통과로 마무리한다.
