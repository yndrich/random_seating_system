import { useEffect, useMemo, useState } from "react";
import { api } from "./api/client";
import { ConstraintConfigForm } from "./components/ConstraintConfigForm";
import { ParticipantForm } from "./components/ParticipantForm";
import { ParticipantTable } from "./components/ParticipantTable";
import { TableResultGrid } from "./components/TableResultGrid";
import { ViolationBanner } from "./components/ViolationBanner";
import type {
  ConstraintConfig,
  Participant,
  ParticipantInput,
  RoundOut,
} from "./types";
import { DEFAULT_WEIGHTS, GENDER_LABEL } from "./types";

const PALETTE = [
  "#fca5a5", "#fdba74", "#fcd34d", "#86efac", "#67e8f9",
  "#93c5fd", "#c4b5fd", "#f9a8d4", "#a3e635", "#5eead4",
];

const DEFAULT_CONFIG: ConstraintConfig = {
  num_tables: 4,
  table_size: null,
  weights: DEFAULT_WEIGHTS,
  seed: null,
};

type Tab = "participants" | "assign" | "history";

export default function App() {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [config, setConfig] = useState<ConstraintConfig>(DEFAULT_CONFIG);
  const [rounds, setRounds] = useState<RoundOut[]>([]);
  const [preview, setPreview] = useState<RoundOut | null>(null);
  const [tab, setTab] = useState<Tab>("participants");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 회사명 → 안정적인 색상 매핑
  const companyColor = useMemo(() => {
    const companies = Array.from(new Set(participants.map((p) => p.company)));
    companies.sort();
    const map = new Map<string, string>();
    companies.forEach((c, i) => map.set(c, PALETTE[i % PALETTE.length]));
    return (company: string) => map.get(company) ?? "#e5e7eb";
  }, [participants]);

  const participantMap = useMemo(
    () => new Map(participants.map((p) => [p.id, p])),
    [participants]
  );
  const nameOf = (id: string) => participantMap.get(id)?.name ?? id;

  useEffect(() => {
    (async () => {
      try {
        const state = await api.getSession();
        setParticipants(state.participants);
        setConfig(state.config?.num_tables || state.config?.table_size ? state.config : DEFAULT_CONFIG);
        setRounds(state.rounds);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const addParticipant = (p: ParticipantInput) =>
    run(async () => {
      const created = await api.addParticipant(p);
      setParticipants((cur) => [...cur, created]);
    });

  const deleteParticipant = (id: string) =>
    run(async () => {
      await api.deleteParticipant(id);
      setParticipants((cur) => cur.filter((p) => p.id !== id));
    });

  const doPreview = (reshuffle = false) =>
    run(async () => {
      const cfg = reshuffle ? { ...config, seed: null } : config;
      const result = await api.previewRound(cfg);
      setPreview(result);
      setTab("assign");
    });

  const commit = () =>
    run(async () => {
      if (!preview) return;
      const tables = preview.tables.map((t) => t.member_ids);
      await api.commitRound(tables, preview.seed_used);
      const fresh = await api.listRounds();
      setRounds(fresh);
      setPreview(null);
      setTab("history");
    });

  const deleteRound = (n: number) =>
    run(async () => {
      const state = await api.deleteRound(n);
      setRounds(state.rounds);
    });

  const resetAll = () =>
    run(async () => {
      if (!confirm("모든 참가자와 라운드를 초기화할까요?")) return;
      const state = await api.resetSession();
      setParticipants(state.participants);
      setRounds(state.rounds);
      setPreview(null);
      setConfig(DEFAULT_CONFIG);
    });

  // 참가자 집계
  const summary = useMemo(() => {
    const genders: Record<string, number> = {};
    const companies: Record<string, number> = {};
    for (const p of participants) {
      genders[p.gender] = (genders[p.gender] ?? 0) + 1;
      companies[p.company] = (companies[p.company] ?? 0) + 1;
    }
    return { genders, companies };
  }, [participants]);

  return (
    <div className="app">
      <header>
        <h1>🎲 랜덤 조 배정 시스템</h1>
        <button className="link-btn danger" onClick={resetAll}>
          전체 초기화
        </button>
      </header>

      {error && <div className="banner banner-hard">{error}</div>}

      <nav className="tabs">
        <button className={tab === "participants" ? "active" : ""} onClick={() => setTab("participants")}>
          1. 참가자 ({participants.length})
        </button>
        <button className={tab === "assign" ? "active" : ""} onClick={() => setTab("assign")}>
          2. 배정
        </button>
        <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>
          3. 결과·이력 ({rounds.length})
        </button>
      </nav>

      {tab === "participants" && (
        <section>
          <h2>참가자 입력</h2>
          <ParticipantForm onAdd={addParticipant} />
          <div className="summary">
            <span>총 {participants.length}명</span>
            {Object.entries(summary.genders).map(([g, c]) => (
              <span key={g} className="summary-chip">
                {GENDER_LABEL[g as keyof typeof GENDER_LABEL]} {c}
              </span>
            ))}
            <span className="muted">| 회사 {Object.keys(summary.companies).length}개</span>
          </div>
          <ParticipantTable
            participants={participants}
            onDelete={deleteParticipant}
            companyColor={companyColor}
          />
        </section>
      )}

      {tab === "assign" && (
        <section>
          <h2>배정 설정</h2>
          <ConstraintConfigForm
            config={config}
            participantCount={participants.length}
            onChange={setConfig}
          />
          <div className="actions">
            <button className="primary" disabled={busy || participants.length === 0} onClick={() => doPreview(false)}>
              이번 회차 편성
            </button>
            <button disabled={busy || !preview} onClick={() => doPreview(true)}>
              🔀 다시 섞기
            </button>
            <button className="primary" disabled={busy || !preview} onClick={commit}>
              ✓ 이 결과로 확정
            </button>
          </div>

          {preview && (
            <div className="result">
              <div className="result-head">
                <h3>{preview.round_number}회차 미리보기</h3>
                <ScoreSummary round={preview} />
              </div>
              <ViolationBanner round={preview} nameOf={nameOf} />
              <TableResultGrid
                round={preview}
                participantMap={participantMap}
                companyColor={companyColor}
              />
            </div>
          )}
        </section>
      )}

      {tab === "history" && (
        <section>
          <h2>확정된 라운드</h2>
          {rounds.length === 0 && <p className="muted">아직 확정된 라운드가 없습니다.</p>}
          {rounds.map((r) => (
            <div className="result" key={r.round_number}>
              <div className="result-head">
                <h3>{r.round_number}회차</h3>
                <ScoreSummary round={r} />
                <button className="link-btn danger" onClick={() => deleteRound(r.round_number)}>
                  롤백
                </button>
              </div>
              <ViolationBanner round={r} nameOf={nameOf} />
              <TableResultGrid
                round={r}
                participantMap={participantMap}
                companyColor={companyColor}
              />
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function ScoreSummary({ round }: { round: RoundOut }) {
  const ok = round.hard_violation_count === 0;
  return (
    <div className="score-summary">
      <span className={`pill ${ok ? "pill-ok" : "pill-bad"}`}>
        하드 위반 {round.hard_violation_count}
      </span>
      <span className="muted">시드 {round.seed_used}</span>
    </div>
  );
}
