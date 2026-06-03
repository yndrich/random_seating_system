import type { Participant, RoundOut } from "../types";
import { GENDER_LABEL } from "../types";
import { BalanceBar } from "./BalanceBar";

interface Props {
  round: RoundOut;
  participantMap: Map<string, Participant>;
  companyColor: (company: string) => string;
}

export function TableResultGrid({ round, participantMap, companyColor }: Props) {
  // 위반에 연루된 멤버 id (강조 표시용)
  const conflictIds = new Set<string>();
  for (const v of round.violations) {
    for (const id of v.member_ids) conflictIds.add(id);
  }

  return (
    <div className="table-grid">
      {round.tables.map((table) => {
        const balance = round.per_table_balance[table.index];
        return (
          <div className="table-card" key={table.index}>
            <div className="table-card-header">
              <h4>{table.index + 1}조</h4>
              <span className="muted">{table.member_ids.length}명</span>
            </div>
            <ul className="member-list">
              {table.member_ids.map((id) => {
                const p = participantMap.get(id);
                if (!p) return <li key={id}>{id}</li>;
                return (
                  <li
                    key={id}
                    className={`member-chip ${conflictIds.has(id) ? "conflict" : ""}`}
                  >
                    <span
                      className="dot"
                      style={{ background: companyColor(p.company) }}
                      title={p.company}
                    />
                    <span className="member-name">{p.name}</span>
                    <small className="member-meta">
                      {GENDER_LABEL[p.gender]}·{p.age_group}·{p.mbti}
                    </small>
                  </li>
                );
              })}
            </ul>
            {balance && <BalanceBar balance={balance} />}
          </div>
        );
      })}
    </div>
  );
}
