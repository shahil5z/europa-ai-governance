import type { AuditEvent, GovernanceReport, Scenario, StreamEvent } from "./types";

export type ApiErrorKind =
  | "validation"
  | "rate_limited"
  | "busy"
  | "not_configured"
  | "too_large"
  | "timeout"
  | "stalled"
  | "network"
  | "server"
  | "interrupted"
  | "report_lost"
  | "cancelled";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status?: number;
  retryAfter?: number;
  constructor(kind: ApiErrorKind, message: string, opts: { status?: number; retryAfter?: number } = {}) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = opts.status;
    this.retryAfter = opts.retryAfter;
  }
}

/** Whole-run client limit. The server stops at 240 s plus grace, so this is a last resort. */
export const CLIENT_TIMEOUT_MS = 270_000;
/** The server pings every 8 s; silence for this long means the connection is dead. */
export const STALL_TIMEOUT_MS = 45_000;

const KIND_BY_CODE: Record<string, ApiErrorKind> = {
  validation_error: "validation",
  invalid_json: "validation",
  unsupported_media_type: "validation",
  rate_limited: "rate_limited",
  busy: "busy",
  not_configured: "not_configured",
  payload_too_large: "too_large",
  timeout: "timeout",
};

export function errorFromBody(status: number, body: unknown, retryAfterHeader?: string | null): ApiError {
  const err = (body as { error?: { code?: string; message?: string; retry_after_seconds?: number } } | null)?.error;
  const kind: ApiErrorKind = (err?.code && KIND_BY_CODE[err.code]) || "server";
  const retry = err?.retry_after_seconds ?? (retryAfterHeader ? Number(retryAfterHeader) : undefined);
  return new ApiError(kind, err?.message ?? "The service returned an unexpected error.", {
    status,
    retryAfter: Number.isFinite(retry) ? retry : undefined,
  });
}

/** Incremental NDJSON parser. Feed decoded text chunks; returns complete parsed lines. */
export class NdjsonParser {
  private buffer = "";
  push(chunk: string): StreamEvent[] {
    this.buffer += chunk;
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() ?? "";
    return lines.flatMap((l) => this.parse(l));
  }
  flush(): StreamEvent[] {
    const rest = this.buffer;
    this.buffer = "";
    return this.parse(rest);
  }
  private parse(line: string): StreamEvent[] {
    const t = line.trim();
    if (!t) return [];
    try {
      const v = JSON.parse(t) as StreamEvent;
      return v && typeof v === "object" && "type" in v ? [v] : [];
    } catch {
      return [];
    }
  }
}

export interface StreamHandlers {
  onAudit: (event: AuditEvent) => void;
}

export interface StreamOptions {
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  clientTimeoutMs?: number;
  stallTimeoutMs?: number;
}

export async function runAssessment(
  description: string,
  scenarioId: string | null,
  handlers: StreamHandlers,
  opts: StreamOptions = {},
): Promise<GovernanceReport> {
  const doFetch = opts.fetchImpl ?? fetch;
  const controller = new AbortController();
  let abortReason: ApiErrorKind | null = null;
  const abort = (reason: ApiErrorKind) => {
    abortReason = abortReason ?? reason;
    controller.abort();
  };
  opts.signal?.addEventListener("abort", () => abort("cancelled"), { once: true });
  if (opts.signal?.aborted) abort("cancelled");
  const total = setTimeout(() => abort("timeout"), opts.clientTimeoutMs ?? CLIENT_TIMEOUT_MS);
  const stallMs = opts.stallTimeoutMs ?? STALL_TIMEOUT_MS;
  let stall = setTimeout(() => abort("stalled"), stallMs);
  const bump = () => {
    clearTimeout(stall);
    stall = setTimeout(() => abort("stalled"), stallMs);
  };

  try {
    let response: Response;
    try {
      response = await doFetch("/api/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
        body: JSON.stringify({ description, ...(scenarioId ? { scenario_id: scenarioId } : {}) }),
        signal: controller.signal,
      });
    } catch {
      throw abortError(abortReason) ?? new ApiError("network", "Could not reach the service. Check your connection and try again.");
    }
    if (!response.ok) {
      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        /* non-JSON error body (for example a platform timeout page) */
      }
      throw errorFromBody(response.status, body, response.headers.get("retry-after"));
    }
    if (!response.body) throw new ApiError("server", "The service returned an empty response.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const parser = new NdjsonParser();
    const out: { report: GovernanceReport | null } = { report: null };
    let reportAnnounced = false;

    // The report line is terminal: the caller gets it as soon as it is parsed. We do not wait
    // for the proxy to close the stream (a buffered or dropped tail hung a previous project).
    const handle = (events: StreamEvent[]): boolean => {
      for (const ev of events) {
        if (ev.type === "audit") {
          if (ev.event.type === "REPORT_GENERATED") reportAnnounced = true;
          handlers.onAudit(ev.event);
        } else if (ev.type === "report") {
          out.report = ev.report;
          return true;
        } else if (ev.type === "error") {
          throw errorFromBody(500, { error: ev.error });
        }
      }
      return false;
    };

    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        bump();
        if (handle(parser.push(decoder.decode(value, { stream: true })))) break;
      }
      if (!out.report) {
        // Stream closed: a final line may still sit in the parser buffer without a newline.
        handle(parser.push(decoder.decode()));
        handle(parser.flush());
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
      if (!out.report) {
        throw (
          abortError(abortReason) ??
          lostOrInterrupted(reportAnnounced)
        );
      }
    } finally {
      reader.cancel().catch(() => undefined);
    }
    if (!out.report) {
      if (abortReason) throw abortError(abortReason) ?? lostOrInterrupted(reportAnnounced);
      throw lostOrInterrupted(reportAnnounced);
    }
    return out.report;
  } finally {
    clearTimeout(total);
    clearTimeout(stall);
  }
}

function lostOrInterrupted(reportAnnounced: boolean): ApiError {
  return reportAnnounced
    ? new ApiError(
        "report_lost",
        "The analysis finished on the server, but the final report did not reach your browser. Please run it again.",
      )
    : new ApiError("interrupted", "The connection was interrupted before the report finished.");
}

function abortError(reason: ApiErrorKind | null): ApiError | null {
  if (reason === "timeout") return new ApiError("timeout", "The assessment took too long and was stopped.");
  if (reason === "stalled") return new ApiError("stalled", "The connection stopped responding.");
  if (reason === "cancelled") return new ApiError("cancelled", "The assessment was cancelled.");
  return null;
}

export async function fetchScenarios(fetchImpl: typeof fetch = fetch): Promise<Scenario[]> {
  const r = await fetchImpl("/api/scenarios", { headers: { Accept: "application/json" } });
  if (!r.ok) throw new ApiError("server", "Could not load the demo scenarios.", { status: r.status });
  const body = (await r.json()) as { scenarios: Scenario[] };
  return body.scenarios;
}

export async function fetchHealth(
  fetchImpl: typeof fetch = fetch,
): Promise<{ llm_configured: boolean; model: string } | null> {
  try {
    const r = await fetchImpl("/api/health");
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}
