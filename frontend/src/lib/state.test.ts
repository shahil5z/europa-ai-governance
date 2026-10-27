import { describe, expect, it } from "vitest";
import { audit, sampleReport } from "@/test/helpers";
import { initialRunState, runReducer } from "./state";

const ev = (e: Parameters<typeof audit>[0], seq: number) => ({ type: "event" as const, event: audit(e, seq) });

describe("runReducer", () => {
  it("derives agent states only from backend events", () => {
    let s = runReducer(initialRunState(), { type: "start" });
    expect(s.phase).toBe("running");
    expect(s.agents.RISK.status).toBe("WAITING");
    s = runReducer(s, ev({ type: "AGENT_STARTED", agent: "RISK", status: "RUNNING" }, 1));
    expect(s.agents.RISK.status).toBe("RUNNING");
    s = runReducer(s, ev({ type: "AGENT_COMPLETED", agent: "RISK", data: { level: "HIGH", confidence: 0.8 } }, 2));
    expect(s.agents.RISK).toMatchObject({ status: "COMPLETE", level: "HIGH", confidence: 0.8 });
    expect(s.agents.SECURITY.status).toBe("WAITING");
    expect(s.events).toHaveLength(2);
  });

  it("closes the orchestrator on ORCHESTRATION_COMPLETED and marks skipped agents", () => {
    let s = runReducer(initialRunState(), { type: "start" });
    s = runReducer(s, ev({ type: "AGENT_STARTED", agent: "ORCHESTRATOR" }, 1));
    s = runReducer(s, ev({ type: "ORCHESTRATION_COMPLETED", agent: "ORCHESTRATOR", data: { decision_impact: "HIGH" } }, 2));
    s = runReducer(s, ev({ type: "ROUTING_DECIDED", agent: "ORCHESTRATOR", data: { skipped: ["DATA_GOVERNANCE"] } }, 3));
    expect(s.agents.ORCHESTRATOR).toMatchObject({ status: "COMPLETE", level: "HIGH" });
    expect(s.agents.DATA_GOVERNANCE.status).toBe("SKIPPED");
  });

  it("tracks retries, failures and reassessment runs", () => {
    let s = runReducer(initialRunState(), { type: "start" });
    s = runReducer(s, ev({ type: "AGENT_STARTED", agent: "SECURITY" }, 1));
    s = runReducer(s, ev({ type: "AGENT_RETRY", agent: "SECURITY" }, 2));
    expect(s.agents.SECURITY.attempts).toBe(2);
    s = runReducer(s, ev({ type: "AGENT_FAILED", agent: "SECURITY", data: { error_code: "timeout" } }, 3));
    expect(s.agents.SECURITY).toMatchObject({ status: "FAILED", errorCode: "timeout" });
    s = runReducer(s, ev({ type: "AGENT_STARTED", agent: "SECURITY" }, 4));
    expect(s.agents.SECURITY.runs).toBe(2);
  });

  it("records disagreements once and resolves them", () => {
    let s = runReducer(initialRunState(), { type: "start" });
    const d = { disagreement_id: "level-spread", kind: "LEVEL_SPREAD", agents: ["RISK", "SECURITY"] };
    s = runReducer(s, ev({ type: "DISAGREEMENT_DETECTED", data: d }, 1));
    s = runReducer(s, ev({ type: "DISAGREEMENT_DETECTED", data: d }, 2));
    expect(s.disagreements).toHaveLength(1);
    s = runReducer(s, ev({ type: "REASSESSMENT_TRIGGERED", round: 1 }, 3));
    expect(s.reassessmentRound).toBe(1);
    s = runReducer(s, ev({ type: "DISAGREEMENT_RESOLVED", data: { disagreement_id: "level-spread" } }, 4));
    expect(s.disagreements[0]?.resolved).toBe(true);
  });

  it("completes with the report and resets cleanly", () => {
    let s = runReducer(initialRunState(), { type: "start" });
    s = runReducer(s, { type: "report", report: sampleReport });
    expect(s.phase).toBe("done");
    expect(s.report).toBe(sampleReport);
    s = runReducer(s, { type: "reset" });
    expect(s.phase).toBe("idle");
    expect(s.report).toBeNull();
  });

  it("marks in-flight agents as interrupted (not complete) on fail", () => {
    let s = runReducer(initialRunState(), { type: "start" });
    s = runReducer(s, ev({ type: "AGENT_STARTED", agent: "RISK", status: "RUNNING" }, 1));
    s = runReducer(s, { type: "fail" });
    expect(s.agents.RISK).toMatchObject({ status: "FAILED", errorCode: "interrupted" });
    expect(s.phase).toBe("failed");
    expect(s.report).toBeNull();
  });
});
