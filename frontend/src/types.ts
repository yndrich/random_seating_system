// 백엔드 Pydantic 스키마와 1:1 대응하는 타입

export type Gender = "male" | "female" | "other";

export interface ParticipantInput {
  name: string;
  gender: Gender;
  company: string;
  age_group: string;
  mbti: string;
}

export interface Participant extends ParticipantInput {
  id: string;
}

export interface Weights {
  company: number;
  prev: number;
  gender: number;
  age: number;
  mbti: number;
}

export interface ConstraintConfig {
  num_tables: number | null;
  table_size: number | null;
  weights: Weights;
  seed: number | null;
}

export interface TableOut {
  index: number;
  member_ids: string[];
}

export interface ViolationOut {
  type: "same_company" | "prev_same_table";
  table_index: number;
  member_ids: string[];
  detail: Record<string, unknown>;
}

export interface ScoreBreakdown {
  company: number;
  prev_table: number;
  gender: number;
  age: number;
  mbti: number;
  total: number;
}

export interface TableBalance {
  size: number;
  gender: Record<string, number>;
  age_group: Record<string, number>;
  mbti_axes: Record<string, Record<string, number>>;
}

export interface RoundOut {
  round_number: number;
  tables: TableOut[];
  score: number;
  score_breakdown: ScoreBreakdown;
  violations: ViolationOut[];
  warnings: string[];
  per_table_balance: TableBalance[];
  seed_used: number;
  hard_violation_count: number;
  committed: boolean;
}

export interface MetPair {
  members: string[];
  count: number;
}

export interface SessionState {
  session_id: string;
  participants: Participant[];
  config: ConstraintConfig;
  rounds: RoundOut[];
  met_pairs: MetPair[];
}

export const DEFAULT_WEIGHTS: Weights = {
  company: 1000,
  prev: 800,
  gender: 3,
  age: 2,
  mbti: 1,
};

export const AGE_GROUPS = ["10s", "20s", "30s", "40s", "50s", "60s+"];

export const GENDER_LABEL: Record<Gender, string> = {
  male: "남",
  female: "여",
  other: "기타",
};
