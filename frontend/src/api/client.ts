// 백엔드 API 클라이언트. 세션 id 를 localStorage 에 보관하고 모든 요청에 동봉한다.

import type {
  ConstraintConfig,
  Participant,
  ParticipantInput,
  RoundOut,
  SessionState,
} from "../types";

const SESSION_KEY = "seating.session_id";

let sessionId: string | null = localStorage.getItem(SESSION_KEY);

async function createSession(): Promise<string> {
  const resp = await fetch("/api/session", { method: "POST" });
  if (!resp.ok) throw new Error("세션 생성 실패");
  const data = (await resp.json()) as { session_id: string };
  sessionId = data.session_id;
  localStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}

async function ensureSession(): Promise<string> {
  if (sessionId) return sessionId;
  return createSession();
}

interface ApiError {
  detail?: string;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let sid = await ensureSession();
  const doFetch = (id: string) =>
    fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Session-Id": id,
        ...(options.headers || {}),
      },
    });

  let resp = await doFetch(sid);
  // 세션이 서버에서 사라졌으면(404) 새로 만들어 1회 재시도.
  // createSession 은 request() 를 거치지 않으므로 /api/session(getSession)도
  // 안전하게 복구 대상에 포함한다 — 재시도는 1회뿐이라 재귀 위험 없음.
  if (resp.status === 404) {
    const body = (await resp.clone().json().catch(() => ({}))) as ApiError;
    if (body.detail?.includes("세션")) {
      sid = await createSession();
      resp = await doFetch(sid);
    }
  }

  if (resp.status === 204) return undefined as T;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = data as ApiError;
    throw new Error(err.detail || `요청 실패 (${resp.status})`);
  }
  return data as T;
}

export const api = {
  getSessionId: () => sessionId,

  getSession: () => request<SessionState>("/api/session"),

  resetSession: () =>
    request<SessionState>("/api/session/reset", { method: "POST" }),

  listParticipants: () => request<Participant[]>("/api/participants"),

  addParticipant: (p: ParticipantInput) =>
    request<Participant>("/api/participants", {
      method: "POST",
      body: JSON.stringify(p),
    }),

  updateParticipant: (id: string, p: ParticipantInput) =>
    request<Participant>(`/api/participants/${id}`, {
      method: "PUT",
      body: JSON.stringify(p),
    }),

  deleteParticipant: (id: string) =>
    request<void>(`/api/participants/${id}`, { method: "DELETE" }),

  updateConfig: (config: ConstraintConfig) =>
    request<ConstraintConfig>("/api/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),

  previewRound: (config: ConstraintConfig) =>
    request<RoundOut>("/api/rounds/preview", {
      method: "POST",
      body: JSON.stringify({ config }),
    }),

  commitRound: (tables: string[][], seedUsed: number) =>
    request<RoundOut>("/api/rounds/commit", {
      method: "POST",
      body: JSON.stringify({ tables, seed_used: seedUsed }),
    }),

  listRounds: () => request<RoundOut[]>("/api/rounds"),

  deleteRound: (roundNumber: number) =>
    request<SessionState>(`/api/rounds/${roundNumber}`, { method: "DELETE" }),
};
