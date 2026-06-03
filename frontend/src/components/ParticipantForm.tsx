import { useRef, useState } from "react";
import type { Gender, ParticipantInput } from "../types";
import { AGE_GROUPS } from "../types";

const MBTI_TYPES = [
  "INTJ", "INTP", "ENTJ", "ENTP",
  "INFJ", "INFP", "ENFJ", "ENFP",
  "ISTJ", "ISFJ", "ESTJ", "ESFJ",
  "ISTP", "ISFP", "ESTP", "ESFP",
];

interface Props {
  onAdd: (p: ParticipantInput) => Promise<void>;
}

const EMPTY: ParticipantInput = {
  name: "",
  gender: "male",
  company: "",
  age_group: "30s",
  mbti: "INTJ",
};

export function ParticipantForm({ onAdd }: Props) {
  const [form, setForm] = useState<ParticipantInput>(EMPTY);
  const [busy, setBusy] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.company.trim()) return;
    setBusy(true);
    try {
      await onAdd(form);
      // 회사/속성은 유지하고 이름만 비워 연속 입력 편의 제공
      setForm((f) => ({ ...f, name: "" }));
      nameRef.current?.focus();
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="participant-form" onSubmit={submit}>
      <input
        ref={nameRef}
        placeholder="이름"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        autoFocus
      />
      <input
        placeholder="회사/소속"
        value={form.company}
        onChange={(e) => setForm({ ...form, company: e.target.value })}
      />
      <select
        value={form.gender}
        onChange={(e) => setForm({ ...form, gender: e.target.value as Gender })}
      >
        <option value="male">남</option>
        <option value="female">여</option>
        <option value="other">기타</option>
      </select>
      <select
        value={form.age_group}
        onChange={(e) => setForm({ ...form, age_group: e.target.value })}
      >
        {AGE_GROUPS.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
      </select>
      <select
        value={form.mbti}
        onChange={(e) => setForm({ ...form, mbti: e.target.value })}
      >
        {MBTI_TYPES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <button type="submit" disabled={busy}>
        + 추가
      </button>
    </form>
  );
}
