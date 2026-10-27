import { pct, seconds } from "@/lib/format";
import type { AgentView, RunState } from "@/lib/state";
import { AGENT_LABEL, AGENT_ROLE, type AgentName } from "@/lib/types";
import { LevelBadge, StatusTag } from "./Badges";

const SPECIALISTS: AgentName[] = ["RISK", "DATA_GOVERNANCE", "SECURITY", "HUMAN_OVERSIGHT", "GOVERNANCE"];

function Node({ view }: { view: AgentView }) {
  const active = view.status === "RUNNING" || view.status === "REASSESSING";
  const border =
    view.status === "FAILED"
      ? "border-level-critical"
      : active
        ? "border-eu"
        : view.status === "COMPLETE"
          ? "border-rule-strong"
          : "border-rule";
  return (
    <li
      data-agent={view.agent}
      data-status={view.status}
      className={`flex min-w-0 flex-col gap-2 border bg-surface p-3 ${border} ${view.status === "SKIPPED" ? "opacity-70" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-display text-[0.8rem] font-medium uppercase leading-snug tracking-[0.1em]">
          {AGENT_LABEL[view.agent]}
        </h4>
      </div>
      <p className="text-xs leading-snug text-muted">{AGENT_ROLE[view.agent]}</p>
      <StatusTag status={view.status} />
      <div className="flex min-h-6 flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[0.7rem] text-muted">
        {view.level && view.status !== "FAILED" ? <LevelBadge level={view.level} /> : null}
        {view.confidence != null && view.status !== "FAILED" ? <span>conf {pct(view.confidence)}</span> : null}
        {view.status === "FAILED" && view.errorCode ? <span>code: {view.errorCode}</span> : null}
        {view.lastDurationMs != null && view.status !== "RUNNING" && view.status !== "REASSESSING" ? (
          <span>{seconds(view.lastDurationMs)}</span>
        ) : null}
        {view.runs > 1 ? <span>runs {view.runs}</span> : null}
        {view.attempts > 1 && view.status !== "WAITING" ? <span>attempts {view.attempts}</span> : null}
      </div>
    </li>
  );
}

export function AgentNetwork({ run }: { run: RunState }) {
  const a = run.agents;
  const rule = "mx-auto h-4 w-px bg-rule-strong";
  return (
    <section aria-labelledby="network-title" className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="network-title" className="section-title">
          Agent network
        </h3>
        <p className="font-mono text-xs text-faint">
          {run.phase === "idle" ? "Idle" : run.phase === "running" ? "Live" : run.phase === "failed" ? "Run did not finish" : "Run finished"}
          {run.reassessmentRound > 0 ? ` / reassessment round ${run.reassessmentRound}` : ""}
        </p>
      </div>
      <p className="mt-1 text-xs text-faint">States are reported by the backend as events arrive. Nothing here is estimated.</p>

      <div className="mt-4 flex flex-col">
        <ul className="mx-auto w-full max-w-xs list-none" aria-label="Coordinator">
          <Node view={a.ORCHESTRATOR} />
        </ul>
        <div aria-hidden="true" className={rule} />
        <ul className="grid list-none grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3" aria-label="Specialist agents">
          {SPECIALISTS.map((s) => (
            <Node key={s} view={a[s]} />
          ))}
        </ul>
        <div aria-hidden="true" className={rule} />
        <ul className="mx-auto w-full max-w-xs list-none" aria-label="Auditor">
          <Node view={a.CRITIC} />
        </ul>
      </div>
    </section>
  );
}
