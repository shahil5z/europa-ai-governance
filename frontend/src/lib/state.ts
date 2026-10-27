import {
  AGENT_ORDER,
  type AgentName,
  type AgentStatus,
  type AuditEvent,
  type GovernanceReport,
  type Level,
} from "./types";

export interface AgentView {
  agent: AgentName;
  status: AgentStatus;
  level: Level | null;
  confidence: number | null;
  attempts: number;
  /** Number of times this agent started work (initial run plus reassessments). */
  runs: number;
  startedAt: number | null;
  /** Real elapsed time of the latest run, from backend event timestamps. */
  lastDurationMs: number | null;
  errorCode: string | null;
}

export interface LiveDisagreement {
  id: string;
  kind: string;
  agents: AgentName[];
  resolved: boolean;
  round: number;
}

export interface RunState {
  phase: "idle" | "running" | "done" | "failed";
  agents: Record<AgentName, AgentView>;
  events: AuditEvent[];
  disagreements: LiveDisagreement[];
  reassessmentRound: number;
  report: GovernanceReport | null;
}

function blankAgent(agent: AgentName): AgentView {
  return {
    agent,
    status: "WAITING",
    level: null,
    confidence: null,
    attempts: 0,
    runs: 0,
    startedAt: null,
    lastDurationMs: null,
    errorCode: null,
  };
}

export function initialRunState(): RunState {
  return {
    phase: "idle",
    agents: Object.fromEntries(AGENT_ORDER.map((a) => [a, blankAgent(a)])) as Record<AgentName, AgentView>,
    events: [],
    disagreements: [],
    reassessmentRound: 0,
    report: null,
  };
}

export type RunAction =
  | { type: "start" }
  | { type: "event"; event: AuditEvent }
  | { type: "report"; report: GovernanceReport }
  | { type: "fail" }
  | { type: "reset" };

const asNumber = (v: unknown): number | null => (typeof v === "number" ? v : null);
const asStrings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

function patch(state: RunState, agent: AgentName, p: Partial<AgentView>): RunState {
  return { ...state, agents: { ...state.agents, [agent]: { ...state.agents[agent], ...p } } };
}

/** Pure reducer: agent states come only from audit events emitted by the backend. */
export function applyEvent(state: RunState, ev: AuditEvent): RunState {
  const next: RunState = { ...state, events: [...state.events, ev] };
  const agent = ev.agent;
  const ts = Date.parse(ev.ts);
  switch (ev.type) {
    case "AGENT_STARTED": {
      if (!agent) return next;
      const cur = next.agents[agent];
      return patch(next, agent, {
        status: ev.status ?? "RUNNING",
        startedAt: ts,
        runs: cur.runs + 1,
        attempts: 1,
        errorCode: null,
      });
    }
    case "AGENT_RETRY": {
      if (!agent) return next;
      return patch(next, agent, { attempts: next.agents[agent].attempts + 1 });
    }
    case "AGENT_COMPLETED": {
      if (!agent) return next;
      const cur = next.agents[agent];
      const level = typeof ev.data.level === "string" ? (ev.data.level as Level) : cur.level;
      return patch(next, agent, {
        status: "COMPLETE",
        level,
        confidence: asNumber(ev.data.confidence) ?? cur.confidence,
        lastDurationMs: cur.startedAt !== null ? Math.max(0, ts - cur.startedAt) : null,
      });
    }
    case "AGENT_FAILED": {
      if (!agent) return next;
      const cur = next.agents[agent];
      return patch(next, agent, {
        status: "FAILED",
        errorCode: typeof ev.data.error_code === "string" ? ev.data.error_code : "error",
        lastDurationMs: cur.startedAt !== null ? Math.max(0, ts - cur.startedAt) : null,
      });
    }
    case "ORCHESTRATION_COMPLETED": {
      // The orchestrator has no separate AGENT_COMPLETED event; this one closes its run.
      const cur = next.agents.ORCHESTRATOR;
      const level = typeof ev.data.decision_impact === "string" ? (ev.data.decision_impact as Level) : cur.level;
      return patch(next, "ORCHESTRATOR", {
        status: "COMPLETE",
        level,
        lastDurationMs: cur.startedAt !== null ? Math.max(0, ts - cur.startedAt) : null,
      });
    }
    case "CRITIC_TRIGGERED": {
      // The critic is about to start: show it as running rather than waiting.
      return patch(next, "CRITIC", { status: ev.status ?? "RUNNING", startedAt: ts });
    }
    case "ROUTING_DECIDED": {
      let s = next;
      for (const a of asStrings(ev.data.skipped)) {
        if (a in s.agents) s = patch(s, a as AgentName, { status: "SKIPPED" });
      }
      return s;
    }
    case "DISAGREEMENT_DETECTED": {
      const id = String(ev.data.disagreement_id ?? `d${ev.seq}`);
      if (next.disagreements.some((d) => d.id === id)) return next;
      return {
        ...next,
        disagreements: [
          ...next.disagreements,
          {
            id,
            kind: String(ev.data.kind ?? ""),
            agents: asStrings(ev.data.agents) as AgentName[],
            resolved: false,
            round: ev.round,
          },
        ],
      };
    }
    case "DISAGREEMENT_RESOLVED": {
      const id = String(ev.data.disagreement_id ?? "");
      return { ...next, disagreements: next.disagreements.map((d) => (d.id === id ? { ...d, resolved: true } : d)) };
    }
    case "REASSESSMENT_TRIGGERED":
      return { ...next, reassessmentRound: ev.round };
    default:
      return next;
  }
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case "start":
      return { ...initialRunState(), phase: "running" };
    case "event":
      return applyEvent(state, action.event);
    case "report": {
      // Reconcile with the authoritative final statuses (covers skipped agents and failures).
      let s: RunState = { ...state, phase: "done", report: action.report };
      for (const st of action.report.agent_statuses) {
        s = patch(s, st.agent, {
          status: st.status,
          level: st.level ?? s.agents[st.agent].level,
          confidence: st.confidence ?? s.agents[st.agent].confidence,
          attempts: st.attempts || s.agents[st.agent].attempts,
          errorCode: st.error_code,
        });
      }
      return s;
    }
    case "fail": {
      // Connection or server failure: anything still in flight is unknown, not complete.
      const agents = { ...state.agents };
      for (const a of AGENT_ORDER) {
        const v = agents[a];
        if (v.status === "RUNNING" || v.status === "REASSESSING") agents[a] = { ...v, status: "FAILED", errorCode: "interrupted" };
      }
      return { ...state, agents, phase: "failed" };
    }
    case "reset":
      return initialRunState();
  }
}

export const STATUS_LABEL: Record<AgentStatus, string> = {
  WAITING: "Waiting",
  RUNNING: "Running",
  COMPLETE: "Complete",
  FAILED: "Failed",
  REASSESSING: "Reassessing",
  SKIPPED: "Skipped",
};
