import type { TableBalance } from "../types";

interface Props {
  balance: TableBalance;
}

const GENDER_COLORS: Record<string, string> = {
  male: "#3b82f6",
  female: "#ec4899",
  other: "#a3a3a3",
};

function Segment({ label, count, total, color }: {
  label: string;
  count: number;
  total: number;
  color: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  if (count === 0) return null;
  return (
    <div className="seg" style={{ width: `${pct}%`, background: color }} title={`${label}: ${count}`}>
      {pct > 14 ? `${label} ${count}` : count}
    </div>
  );
}

export function BalanceBar({ balance }: Props) {
  const { size, gender, age_group, mbti_axes } = balance;
  const palette = ["#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6"];

  return (
    <div className="balance">
      <div className="balance-line">
        <span className="balance-label">성비</span>
        <div className="bar">
          {Object.entries(gender).map(([g, c]) => (
            <Segment key={g} label={g === "male" ? "남" : g === "female" ? "여" : "기타"} count={c} total={size} color={GENDER_COLORS[g] || "#999"} />
          ))}
        </div>
      </div>

      <div className="balance-line">
        <span className="balance-label">연령</span>
        <div className="bar">
          {Object.entries(age_group).map(([a, c], i) => (
            <Segment key={a} label={a} count={c} total={size} color={palette[i % palette.length]} />
          ))}
        </div>
      </div>

      <div className="balance-line">
        <span className="balance-label">MBTI</span>
        <div className="mbti-axes">
          {Object.entries(mbti_axes).map(([axis, counts]) => {
            const [l1, l2] = axis.split("");
            const c1 = counts[l1] ?? 0;
            const c2 = counts[l2] ?? 0;
            return (
              <span key={axis} className="axis-chip" title={`${l1}:${c1} / ${l2}:${c2}`}>
                {l1}
                {c1}·{c2}
                {l2}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
