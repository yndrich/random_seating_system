# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

랜덤 조 배정 시스템 — 참가자를 조별 테이블로 **랜덤 + 제약 최적화** 배정하는 웹 앱.
전체 사용자 흐름·제약 정의·API 표는 `README.md` 참고.

## 큰 그림

두 파트가 `/api` HTTP로만 통신한다.

- **백엔드** (`backend/`, port 8000) — FastAPI + 순수 Python 배정 알고리즘(시뮬레이티드
  어닐링). 상태는 **인메모리 세션**(영구 DB 없음, 프로세스 재시작 시 휘발).
- **프론트엔드** (`frontend/`, port 5173) — React + Vite + TS 단일 페이지 앱. Vite dev
  서버가 `/api`를 8000으로 프록시한다.

### 교차 관심사 (어느 한쪽을 열기 전에 알아야 할 것)

- **dev에서는 두 서버를 함께 띄워야 한다.** 백엔드(8000)가 꺼져 있으면 Vite 프록시가
  `/api/*`에 **500(`net::ERR_ABORTED`)**을 반환한다 — 프론트 버그가 아니다.
- **세션 계약:** 프론트가 시작 시 `POST /api/session`으로 세션을 만들고, 이후 모든 데이터
  요청에 `X-Session-Id` 헤더를 동봉한다.
- **타입 미러:** `frontend/src/types.ts`는 `backend/app/models/schemas.py`를 **수동으로
  맞춘** 미러다(자동생성 아님). 한쪽 스키마를 바꾸면 다른 쪽도 직접 갱신해야 한다.

## 하위 가이드 (작업 위치에 따라 자동 로드)

명령어·아키텍처 상세는 해당 디렉터리에서 작업할 때 읽히는 중첩 CLAUDE.md에 있다.

| 작업 영역 | 파일 | 내용 |
|---|---|---|
| 백엔드 전반 | `backend/CLAUDE.md` | 명령어(pytest·uvicorn), 3계층 의존, 세션/라운드 수명주기, 제약 모델 |
| 배정 알고리즘 | `backend/app/assignment/CLAUDE.md` | 비용 분해 불변식, 솔버(SA·스왑·시드), met_count 기계 |
| 프론트엔드 | `frontend/CLAUDE.md` | 명령어(build=lint), App 단일 상태, client/types 미러 |
