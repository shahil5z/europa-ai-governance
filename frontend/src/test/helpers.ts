import report from "./report.fixture.json";
import type { AuditEvent, GovernanceReport } from "@/lib/types";

export const sampleReport = report as unknown as GovernanceReport;

export function audit(partial: Partial<AuditEvent> & Pick<AuditEvent, "type">, seq = 1): AuditEvent {
  return {
    seq,
    ts: new Date(1_700_000_000_000 + seq * 1000).toISOString(),
    round: 0,
    agent: null,
    status: null,
    message: partial.type,
    data: {},
    ...partial,
  } as AuditEvent;
}

export function ndjsonResponse(chunks: string[], init: ResponseInit = { status: 200 }): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      for (const ch of chunks) c.enqueue(enc.encode(ch));
      c.close();
    },
  });
  return new Response(body, { ...init, headers: { "content-type": "application/x-ndjson" } });
}

export const line = (o: unknown) => JSON.stringify(o) + "\n";
