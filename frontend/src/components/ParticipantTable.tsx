import type { Participant } from "../types";
import { GENDER_LABEL } from "../types";

interface Props {
  participants: Participant[];
  onDelete: (id: string) => void;
  companyColor: (company: string) => string;
}

export function ParticipantTable({ participants, onDelete, companyColor }: Props) {
  if (participants.length === 0) {
    return <p className="muted">아직 참가자가 없습니다. 위에서 추가하세요.</p>;
  }
  return (
    <table className="participant-table">
      <thead>
        <tr>
          <th>이름</th>
          <th>회사</th>
          <th>성별</th>
          <th>연령대</th>
          <th>MBTI</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {participants.map((p) => (
          <tr key={p.id}>
            <td>{p.name}</td>
            <td>
              <span
                className="tag"
                style={{ background: companyColor(p.company) }}
              >
                {p.company}
              </span>
            </td>
            <td>{GENDER_LABEL[p.gender]}</td>
            <td>{p.age_group}</td>
            <td>{p.mbti}</td>
            <td>
              <button className="link-btn" onClick={() => onDelete(p.id)}>
                삭제
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
