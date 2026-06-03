"""FastAPI 엔드포인트 통합 테스트 (TestClient)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _new_session() -> dict[str, str]:
    resp = client.post("/api/session")
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    return {"X-Session-Id": sid}


def _add(headers, name, gender, company, age_group, mbti):
    resp = client.post(
        "/api/participants",
        headers=headers,
        json={
            "name": name,
            "gender": gender,
            "company": company,
            "age_group": age_group,
            "mbti": mbti,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_16(headers):
    """회사 4개×4명, 성비 8:8 의 표준 시드 데이터."""
    companies = ["Acme", "Beta", "Cyan", "Delta"]
    mbtis = ["INTJ", "ENFP", "ISTJ", "ESFP"]
    ages = ["20s", "30s", "40s", "50s"]
    created = []
    for ci, c in enumerate(companies):
        for j in range(4):
            gender = "male" if (ci * 4 + j) % 2 == 0 else "female"
            created.append(
                _add(headers, f"{c}{j}", gender, c, ages[j], mbtis[j])
            )
    return created


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_requires_session_header():
    assert client.get("/api/participants").status_code == 400
    assert client.get(
        "/api/participants", headers={"X-Session-Id": "nope"}
    ).status_code == 404


def test_participant_crud():
    h = _new_session()
    p = _add(h, "홍길동", "male", "Acme", "30s", "intj")  # 소문자 입력 → 정규화
    assert p["mbti"] == "INTJ"
    assert client.get("/api/participants", headers=h).json()[0]["id"] == p["id"]

    # 수정
    r = client.put(
        f"/api/participants/{p['id']}",
        headers=h,
        json={
            "name": "홍길동2",
            "gender": "male",
            "company": "Beta",
            "age_group": "40s",
            "mbti": "ENFP",
        },
    )
    assert r.status_code == 200 and r.json()["company"] == "Beta"

    # 삭제
    assert client.delete(f"/api/participants/{p['id']}", headers=h).status_code == 204
    assert client.get("/api/participants", headers=h).json() == []


def test_invalid_mbti_rejected():
    h = _new_session()
    r = client.post(
        "/api/participants",
        headers=h,
        json={
            "name": "x",
            "gender": "male",
            "company": "A",
            "age_group": "20s",
            "mbti": "XXXX",
        },
    )
    assert r.status_code == 422


def test_preview_and_commit_multi_round():
    h = _new_session()
    _seed_16(h)

    # 라운드1 미리보기 (시드 고정 → 재현)
    r1 = client.post(
        "/api/rounds/preview",
        headers=h,
        json={"config": {"num_tables": 4, "seed": 42}},
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["committed"] is False
    assert body1["round_number"] == 1
    assert sum(len(t["member_ids"]) for t in body1["tables"]) == 16
    # 회사 분리 완전 가능 → 하드 위반 0
    assert body1["hard_violation_count"] == 0

    # 확정
    tables = [t["member_ids"] for t in body1["tables"]]
    c1 = client.post(
        "/api/rounds/commit",
        headers=h,
        json={"tables": tables, "seed_used": body1["seed_used"]},
    )
    assert c1.status_code == 200
    assert c1.json()["committed"] is True

    # 세션 상태에 met_pairs 누적
    state = client.get("/api/session", headers=h).json()
    assert len(state["rounds"]) == 1
    assert len(state["met_pairs"]) > 0

    # 라운드2 미리보기 → 이전 동석 회피
    r2 = client.post(
        "/api/rounds/preview", headers=h, json={"config": {"num_tables": 4, "seed": 7}}
    )
    assert r2.json()["round_number"] == 2
    assert r2.json()["score_breakdown"]["prev_table"] == 0.0


def test_too_many_tables_returns_400():
    h = _new_session()
    _add(h, "a", "male", "A", "20s", "INTJ")
    _add(h, "b", "male", "B", "30s", "ENFP")
    r = client.post(
        "/api/rounds/preview", headers=h, json={"config": {"num_tables": 5}}
    )
    assert r.status_code == 400


def test_rollback_round():
    h = _new_session()
    _seed_16(h)
    pv = client.post(
        "/api/rounds/preview", headers=h, json={"config": {"num_tables": 4, "seed": 1}}
    ).json()
    tables = [t["member_ids"] for t in pv["tables"]]
    client.post(
        "/api/rounds/commit",
        headers=h,
        json={"tables": tables, "seed_used": pv["seed_used"]},
    )
    assert len(client.get("/api/rounds", headers=h).json()) == 1

    state = client.delete("/api/rounds/1", headers=h).json()
    assert state["rounds"] == []
    assert state["met_pairs"] == []


def test_reset_session():
    h = _new_session()
    _seed_16(h)
    state = client.post("/api/session/reset", headers=h).json()
    assert state["participants"] == []
    assert state["rounds"] == []
