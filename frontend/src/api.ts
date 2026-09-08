import type {
  AnalysisRequest,
  AnalysisResponse,
  EpisodesResponse,
  Health,
  ProceduresResponse,
  ReviewDecisionRequest,
  ReviewDecisionResponse,
  ReviewQueueResponse,
  Signal,
  SponsorProfile,
  SponsorsResponse,
} from "./types";

// Same-origin in production (FastAPI serves the built bundle), and in
// dev the Vite proxy forwards /api to uvicorn — so a relative base
// works in both cases and there is no environment variable to set.
const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // fetch only rejects on network-level failure — the server being
    // down, DNS, CORS. An HTTP error status resolves normally.
    throw new ApiError("Could not reach the MOSAIC API. Is uvicorn running?", 0);
  }

  if (!response.ok) {
    // FastAPI puts the message in `detail`, which is a string for our
    // own HTTPExceptions and a list of objects for 422 validation errors.
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((d: { loc?: string[]; msg?: string }) =>
            `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`,
          )
          .join("; ");
      }
    } catch {
      // Non-JSON error body — keep the status line we already have.
    }
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

export const api = {
  health: () => request<Health>("/health"),

  // A full run fans out six agents, each doing up to ten tool-calling
  // turns against OpenAI — minutes, not seconds. No timeout is set on
  // purpose; the caller shows progress instead of giving up.
  analyze: (body: AnalysisRequest, signal?: AbortSignal) =>
    request<AnalysisResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    }),

  listSignals: (filters: {
    agent?: string;
    signal_type?: string;
    status?: string;
    limit?: number;
  }) => request<Signal[]>(`/signals${query(filters)}`),

  getSignal: (signalId: string) =>
    request<Signal>(`/signals/${encodeURIComponent(signalId)}`),

  reviewQueue: () => request<ReviewQueueResponse>("/review/queue"),

  submitReview: (queueId: string, body: ReviewDecisionRequest) =>
    request<ReviewDecisionResponse>(`/review/${encodeURIComponent(queueId)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  episodes: (filters: { query?: string; agent_name?: string; limit?: number }) =>
    request<EpisodesResponse>(`/memory/episodes${query(filters)}`),

  procedures: (agentName: string) =>
    request<ProceduresResponse>(
      `/memory/procedures/${encodeURIComponent(agentName)}`,
    ),

  sponsors: (limit = 50) =>
    request<SponsorsResponse>(`/sponsors${query({ limit })}`),

  sponsor: (name: string) =>
    request<SponsorProfile>(`/sponsors/${encodeURIComponent(name)}`),
};
