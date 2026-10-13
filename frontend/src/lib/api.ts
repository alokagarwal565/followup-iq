import type {
  Draft,
  DraftSave,
  DraftSend,
  LeadCreate,
  LeadDetail,
  LeadFilters,
  LeadList,
  LeadUpdate,
  MessagesCreate,
  Meta,
  Ready,
  Summary,
} from "./types";

// The only place the API origin is read. It is public by design and inlined at build time.
export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH";
  body?: unknown;
  query?: Record<string, string | undefined>;
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, value);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url.toString(), {
      method: options.method ?? "GET",
      headers: options.body === undefined ? undefined : { "content-type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError(0, "timeout", "The server took too long to respond.");
    }
    throw new ApiError(
      0,
      "network",
      "Could not reach the server. Check your connection.",
      undefined,
      {
        cause: String(error),
      },
    );
  } finally {
    clearTimeout(timer);
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const envelope = (payload as { error?: Record<string, unknown> } | null)?.error;
    throw new ApiError(
      response.status,
      typeof envelope?.code === "string" ? envelope.code : "http_error",
      typeof envelope?.message === "string"
        ? envelope.message
        : `Request failed (${response.status})`,
      typeof envelope?.request_id === "string" ? envelope.request_id : undefined,
      (envelope?.details as Record<string, unknown> | undefined) ?? undefined,
    );
  }
  return payload as T;
}

const lead = (id: string) => `/api/v1/leads/${encodeURIComponent(id)}`;

export const api = {
  meta: (options?: { timeoutMs?: number }) => request<Meta>("/api/v1/meta", options),
  ready: () => request<Ready>("/api/v1/health/ready"),
  leads: (filters: LeadFilters = {}) =>
    request<LeadList>("/api/v1/leads", { query: { ...filters, limit: "500" } }),
  summary: (rep?: string) => request<Summary>("/api/v1/summary", { query: { rep } }),
  lead: (id: string) => request<LeadDetail>(lead(id)),
  createLead: (body: LeadCreate) => request<LeadDetail>("/api/v1/leads", { method: "POST", body }),
  updateLead: (id: string, body: LeadUpdate) =>
    request<LeadDetail>(lead(id), { method: "PATCH", body }),
  logMessages: (id: string, body: MessagesCreate) =>
    request<LeadDetail>(`${lead(id)}/messages`, { method: "POST", body }),
  saveDraft: (id: string, body: DraftSave) =>
    request<Draft>(`${lead(id)}/draft`, { method: "PUT", body }),
  acceptSuggestion: (id: string, version: number) =>
    request<Draft>(`${lead(id)}/draft/accept-suggestion`, { method: "POST", body: { version } }),
  sendDraft: (id: string, body: DraftSend) =>
    request<LeadDetail>(`${lead(id)}/draft/send`, { method: "POST", body }),
  undoSend: (id: string) => request<LeadDetail>(`${lead(id)}/draft/undo-send`, { method: "POST" }),
  analyze: (id: string) =>
    request<{ analysis_status: "pending" }>(`${lead(id)}/analyze`, { method: "POST" }),
};
