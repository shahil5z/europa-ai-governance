import { clockTime } from "@/lib/format";
import type { AuditEvent, AuditEventType } from "@/lib/types";

const TYPE_LABEL: Record<AuditEventType, string> = {
  ASSESSMENT_STARTED: "Start",
  ORCHESTRATION_COMPLETED: "Profile",
  ROUTING_DECIDED: "Routing",
  AGENT_STARTED: "Agent start",
  AGENT_RETRY: "Retry",
  AGENT_COMPLETED: "Agent done",
  AGENT_FAILED: "Agent failed",
  CRITIC_TRIGGERED: "Critic",
  DISAGREEMENT_DETECTED: "Disagreement",
  DISAGREEMENT_RESOLVED: "Resolved",
  REASSESSMENT_TRIGGERED: "Reassess",
  CONSENSUS_COMPUTED: "Consensus",
  SUMMARY_WRITTEN: "Summary",
  REPORT_GENERATED: "Report",
};

const TYPE_TONE: Partial<Record<AuditEventType, string>> = {
  AGENT_FAILED: "text-level-critical",
  AGENT_RETRY: "text-level-medium",
  DISAGREEMENT_DETECTED: "text-level-high",
  REASSESSMENT_TRIGGERED: "text-level-medium",
  DISAGREEMENT_RESOLVED: "text-level-low",
  REPORT_GENERATED: "text-level-low",
};

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <section aria-labelledby="audit-title" className="panel p-4 sm:p-5">
      <div className="flex items-baseline justify-between gap-2">
        <h3 id="audit-title" className="section-title">
          Audit trail
        </h3>
        <p className="font-mono text-xs text-faint">{events.length} events</p>
      </div>
      {events.length === 0 ? (
        <p className="mt-3 text-sm text-muted">Events from the backend appear here in order as an assessment runs.</p>
      ) : (
        <ol
          // Scrollable region must be keyboard reachable.
          tabIndex={0}
          aria-label="Audit events in order"
          className="mt-3 max-h-80 list-none space-y-0 overflow-y-auto border-l border-rule-strong pr-1"
        >
          {events.map((e) => (
            <li key={e.seq} className="relative py-1.5 pl-4">
              <span aria-hidden="true" className="absolute -left-[3px] top-3 h-1.5 w-1.5 rounded-full bg-eu" />
              <div className="flex flex-wrap items-baseline gap-x-2 font-mono text-[0.72rem]">
                <span className="text-faint">{clockTime(e.ts)}</span>
                <span className={`uppercase tracking-[0.1em] ${TYPE_TONE[e.type] ?? "text-eu-soft"}`}>
                  {TYPE_LABEL[e.type]}
                </span>
              </div>
              <p className="text-sm leading-snug text-paper">{e.message}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
