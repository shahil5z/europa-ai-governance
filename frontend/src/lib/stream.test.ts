import { describe, expect, it, vi } from "vitest";
import { audit, line, ndjsonResponse, sampleReport } from "@/test/helpers";
import { ApiError, errorFromBody, NdjsonParser, runAssessment } from "./stream";

const DESC = "A hiring tool that ranks candidates from their CVs for recruiters.";
const asFetch = (r: Response | (() => Promise<Response>)) =>
  vi.fn(async () => (typeof r === "function" ? r() : r)) as unknown as typeof fetch;

describe("NdjsonParser", () => {
  it("handles a line split across chunks", () => {
    const p = new NdjsonParser();
    const whole = line({ type: "ping" });
    expect(p.push(whole.slice(0, 7))).toEqual([]);
    expect(p.push(whole.slice(7))).toEqual([{ type: "ping" }]);
  });
  it("returns a final line that has no trailing newline on flush", () => {
    const p = new NdjsonParser();
    expect(p.push('{"type":"end"}')).toEqual([]);
    expect(p.flush()).toEqual([{ type: "end" }]);
  });
  it("skips blank lines, padding and garbage", () => {
    const p = new NdjsonParser();
    expect(p.push("\n\nnot json\n[1]\n{\"x\":1}\n" + "\n".repeat(50))).toEqual([]);
  });
});

describe("runAssessment", () => {
  it("streams audit events and returns the report without waiting for end", async () => {
    const seen: string[] = [];
    const res = ndjsonResponse([
      line({ type: "audit", event: audit({ type: "ASSESSMENT_STARTED" }, 1) }),
      line({ type: "ping" }),
      line({ type: "report", report: sampleReport }),
    ]);
    const report = await runAssessment(DESC, null, { onAudit: (e) => seen.push(e.type) }, { fetchImpl: asFetch(res) });
    expect(report.report_id).toBe(sampleReport.report_id);
    expect(seen).toEqual(["ASSESSMENT_STARTED"]);
  });

  it("reads a report line split over chunks and delivered without a newline", async () => {
    const text = JSON.stringify({ type: "report", report: sampleReport });
    const res = ndjsonResponse([text.slice(0, 500), text.slice(500, 9000), text.slice(9000)]);
    const report = await runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(res) });
    expect(report.report_id).toBe(sampleReport.report_id);
  });

  it("returns as soon as the report arrives even if the stream never closes", async () => {
    const enc = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode(line({ type: "report", report: sampleReport })));
      },
    });
    const res = new Response(body, { status: 200 });
    const report = await runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(res) });
    expect(report.status).toBe(sampleReport.status);
  });

  it("raises report_lost when REPORT_GENERATED was seen but the report line never arrived", async () => {
    const res = ndjsonResponse([line({ type: "audit", event: audit({ type: "REPORT_GENERATED" }) })]);
    await expect(
      runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(res) }),
    ).rejects.toMatchObject({ kind: "report_lost" });
  });

  it("raises interrupted when the stream ends early", async () => {
    const res = ndjsonResponse([line({ type: "audit", event: audit({ type: "AGENT_STARTED" }) })]);
    await expect(
      runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(res) }),
    ).rejects.toMatchObject({ kind: "interrupted" });
  });

  it("maps an in-stream error event", async () => {
    const res = ndjsonResponse([line({ type: "error", error: { code: "run_failed", message: "Generic failure." } })]);
    await expect(
      runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(res) }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("maps HTTP errors (429 with Retry-After, non-JSON 504)", async () => {
    const limited = new Response(JSON.stringify({ error: { code: "rate_limited", message: "Slow down." } }), {
      status: 429,
      headers: { "retry-after": "120" },
    });
    await expect(
      runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(limited) }),
    ).rejects.toMatchObject({ kind: "rate_limited", retryAfter: 120 });
    const gateway = new Response("<html>timeout</html>", { status: 504 });
    await expect(
      runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: asFetch(gateway) }),
    ).rejects.toMatchObject({ kind: "server" });
  });

  it("maps a network failure", async () => {
    const f = vi.fn(async () => {
      throw new TypeError("fetch failed");
    }) as unknown as typeof fetch;
    await expect(runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: f })).rejects.toMatchObject({
      kind: "network",
    });
  });

  it("times out a stalled stream instead of waiting forever", async () => {
    const f = vi.fn(async (_url: unknown, init?: RequestInit) => {
      const body = new ReadableStream<Uint8Array>({
        start(c) {
          init?.signal?.addEventListener("abort", () => c.error(new DOMException("aborted", "AbortError")));
        },
      });
      return new Response(body, { status: 200 });
    }) as unknown as typeof fetch;
    await expect(
      runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: f, stallTimeoutMs: 50 }),
    ).rejects.toMatchObject({ kind: "stalled" });
  });

  it("reports cancellation", async () => {
    const controller = new AbortController();
    const f = vi.fn(async (_url: unknown, init?: RequestInit) => {
      return new Promise<Response>((_, reject) =>
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))),
      );
    }) as unknown as typeof fetch;
    const p = runAssessment(DESC, null, { onAudit: () => undefined }, { fetchImpl: f, signal: controller.signal });
    controller.abort();
    await expect(p).rejects.toMatchObject({ kind: "cancelled" });
  });
});

describe("errorFromBody", () => {
  it("maps known codes", () => {
    expect(errorFromBody(422, { error: { code: "validation_error", message: "x" } }).kind).toBe("validation");
    expect(errorFromBody(413, { error: { code: "payload_too_large", message: "x" } }).kind).toBe("too_large");
    expect(errorFromBody(503, { error: { code: "not_configured", message: "x" } }).kind).toBe("not_configured");
    expect(errorFromBody(503, { error: { code: "busy", message: "x" } }).kind).toBe("busy");
  });
});
