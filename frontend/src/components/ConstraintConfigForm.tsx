import { useState } from "react";
import type { ConstraintConfig, Weights } from "../types";

interface Props {
  config: ConstraintConfig;
  participantCount: number;
  onChange: (c: ConstraintConfig) => void;
}

type Mode = "tables" | "size";

const WEIGHT_LABELS: { key: keyof Weights; label: string; hard: boolean }[] = [
  { key: "company", label: "회사 분리", hard: true },
  { key: "prev", label: "이전 동석 회피", hard: true },
  { key: "gender", label: "성비 균형", hard: false },
  { key: "age", label: "연령 분산", hard: false },
  { key: "mbti", label: "MBTI 분산", hard: false },
];

export function ConstraintConfigForm({ config, participantCount, onChange }: Props) {
  const [mode, setMode] = useState<Mode>(
    config.table_size != null ? "size" : "tables"
  );
  const [showAdvanced, setShowAdvanced] = useState(false);

  const numTables =
    mode === "tables"
      ? config.num_tables ?? 4
      : config.table_size
        ? Math.ceil(participantCount / config.table_size)
        : 0;
  const sizeHint =
    numTables > 0 && participantCount > 0
      ? `${participantCount}명 → ${numTables}조 (조당 약 ${Math.floor(
          participantCount / numTables
        )}~${Math.ceil(participantCount / numTables)}명)`
      : "참가자를 먼저 추가하세요";

  const setMain = (m: Mode, value: number) => {
    setMode(m);
    if (m === "tables") {
      onChange({ ...config, num_tables: value, table_size: null });
    } else {
      onChange({ ...config, table_size: value, num_tables: null });
    }
  };

  return (
    <div className="config-form">
      <div className="config-row">
        <label className={`radio ${mode === "tables" ? "active" : ""}`}>
          <input
            type="radio"
            checked={mode === "tables"}
            onChange={() => setMain("tables", config.num_tables ?? 4)}
          />
          조 개수로 지정
        </label>
        <label className={`radio ${mode === "size" ? "active" : ""}`}>
          <input
            type="radio"
            checked={mode === "size"}
            onChange={() => setMain("size", config.table_size ?? 4)}
          />
          조당 인원으로 지정
        </label>
      </div>

      <div className="config-row">
        {mode === "tables" ? (
          <label>
            조 개수
            <input
              type="number"
              min={1}
              value={config.num_tables ?? 4}
              onChange={(e) => setMain("tables", Number(e.target.value))}
            />
          </label>
        ) : (
          <label>
            조당 인원
            <input
              type="number"
              min={1}
              value={config.table_size ?? 4}
              onChange={(e) => setMain("size", Number(e.target.value))}
            />
          </label>
        )}
        <span className="hint">{sizeHint}</span>
      </div>

      <div className="config-row">
        <label>
          시드 (선택, 비우면 매번 랜덤)
          <input
            type="number"
            placeholder="랜덤"
            value={config.seed ?? ""}
            onChange={(e) =>
              onChange({
                ...config,
                seed: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
        </label>
      </div>

      <button
        type="button"
        className="link-btn"
        onClick={() => setShowAdvanced((s) => !s)}
      >
        {showAdvanced ? "▾ 고급 설정 닫기" : "▸ 고급: 가중치 조정"}
      </button>

      {showAdvanced && (
        <div className="weights">
          {WEIGHT_LABELS.map(({ key, label, hard }) => (
            <label key={key} className="weight-row">
              <span>
                {label}
                <small className={hard ? "badge-hard" : "badge-soft"}>
                  {hard ? "하드" : "소프트"}
                </small>
              </span>
              <input
                type="range"
                min={0}
                max={hard ? 2000 : 30}
                step={hard ? 50 : 1}
                value={config.weights[key]}
                onChange={(e) =>
                  onChange({
                    ...config,
                    weights: { ...config.weights, [key]: Number(e.target.value) },
                  })
                }
              />
              <span className="weight-val">{config.weights[key]}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
