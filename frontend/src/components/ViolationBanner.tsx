import type { Participant, RoundOut } from "../types";

interface Props {
  round: RoundOut;
  nameOf: (id: string) => string;
}

export function ViolationBanner({ round, nameOf }: Props) {
  const { violations, warnings, hard_violation_count } = round;

  if (hard_violation_count === 0 && warnings.length === 0) {
    return (
      <div className="banner banner-ok">
        ✓ 모든 하드 제약(회사 분리·이전 동석)을 만족하며 균형도 양호합니다.
      </div>
    );
  }

  return (
    <div className="banner-group">
      {violations.map((v, i) => {
        const names = v.member_ids.map(nameOf).join(", ");
        const tableNo = v.table_index + 1;
        if (v.type === "same_company") {
          return (
            <div key={i} className="banner banner-hard">
              ⚠ {tableNo}조: 같은 회사(<b>{String(v.detail.company)}</b>) {names}
            </div>
          );
        }
        return (
          <div key={i} className="banner banner-hard">
            ⚠ {tableNo}조: <b>{names}</b> 는 이미 {String(v.detail.times)}회 동석했습니다
          </div>
        );
      })}
      {warnings.map((w, i) => (
        <div key={`w${i}`} className="banner banner-soft">
          ⓘ {w}
        </div>
      ))}
    </div>
  );
}

export type { Participant };
